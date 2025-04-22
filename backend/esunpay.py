import datetime
import httpx
import hashlib
import json
import urllib.parse
from fastapi import HTTPException
from pydantic import BaseModel

class EsunPayRequest(BaseModel):
    key: str
    machine: str
    barcode: str
    amount: int

class EsunPayAPI:
    ESUNPAY_API_URL = "https://mpayment.esuntrade.com/mPay/GatewayV2/API/V2/xTrade.ashx"
    API_B_URL = "https://unibuy.com.tw/Unibuy/api/app/machine/setting/B014"

    @staticmethod
    async def pay(request: EsunPayRequest):
        # 🔹 Step 1: 從 B014 取得掃碼設定
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {"key": request.key, "machine": request.machine, "time": current_time}
            async with httpx.AsyncClient() as client:
                response = await client.post(EsunPayAPI.API_B_URL, json=payload, timeout=20.0)
                response.raise_for_status()
            api_b_response = response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"API B Request failed: {exc}")

        data_items = api_b_response.get("data", [])
        if not data_items or not isinstance(data_items, list):
            raise HTTPException(status_code=500, detail="Invalid API B response structure.")

        store_id = data_items[0].get("t050v41")
        term_id = data_items[0].get("t050v42")
        hash_key = data_items[0].get("t050v43")

        print("🔍 B014 回傳：", {
            "StoreID": store_id,
            "TermID": term_id,
            "Key": hash_key
        })

        if not store_id or not term_id or not hash_key:
            raise HTTPException(status_code=500, detail="Missing StoreID, TermID, or Hash from API B.")

         # 2️⃣ 組訂單資料
        order_no = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{request.machine}"
        order_dt = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        transaction_data = {
            "StoreID": store_id,
            "TermID": term_id,
            "Timeout": 20,
            "BuyerID": request.barcode,
            "OrderNo": order_no,
            "OrderCurrency": "TWD",
            "OrderAmount": request.amount,
            "OrderDT": order_dt,
            "OrderTitle": order_no,
            "BuyerPaymentType": 1
        }


        # 將 TransactionData JSON 壓縮為無空格並做 URL encode
        transaction_json = json.dumps(transaction_data, separators=(',', ':'))
        transaction_data_encoded = urllib.parse.quote(transaction_json, safe='')

        # === 3️⃣ 組 HashDigest ===
        hash_source = f"tradeapi" + "payment" + transaction_data_encoded + hash_key
        hash_digest = hashlib.sha256(hash_source.encode("utf-8")).hexdigest().upper()

        # === 4️⃣ 組最終 payload ===
        final_payload = {
            "Type": "tradeapi",
            "Action": "payment",
            "TransactionData": transaction_data_encoded,
            "HashDigest": hash_digest
        }

        # 最終上傳內容需再次 JSON 並 URL encode
        encoded_json = urllib.parse.quote(json.dumps(final_payload, separators=(',', ':')), safe='')

        print("🔍 寄出前內容：")
        print("原始 Transaction JSON:", transaction_json)
        print("URL encoded TransactionData:", transaction_data_encoded)
        print("Hash Source:", hash_source)
        print("HashDigest:", hash_digest)
        print("最終傳送 JSON:", final_payload)

        # 🔹 Step 3: 呼叫玉山支付 API
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EsunPayAPI.ESUNPAY_API_URL,
                    data=f"json={encoded_json}",
                    headers=headers,
                    timeout=20.0
                )
                response.raise_for_status()
            # === 4️⃣ 嘗試雙層解碼 ===
            try:
                first_decode = urllib.parse.unquote(response.text)
                parsed = json.loads(first_decode)

                if "TransactionData" in parsed:
                    parsed["TransactionData"] = json.loads(urllib.parse.unquote(parsed["TransactionData"]))

                return {
                    "status": "success",
                    "data": parsed
                }

            except Exception as e:
                return {
                    "status": "error",
                    "raw": response.text,
                    "message": f"EsunPay 回傳無法解析：{str(e)}"
                }


        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"EsunPay Request failed: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"EsunPay Error: {exc.response.text}")
