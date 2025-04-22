import datetime
import httpx
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

        # 🔹 Step 2: 準備玉山支付訂單資料
        order_id = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}{request.machine}"
        transaction_data = {
            "StoreID": store_id,
            "TermID": term_id,
            "Timeout": 20,
            "BuyerID": request.barcode,
            "OrderNo": order_id,
            "OrderCurrency": "TWD",
            "OrderAmount": request.amount,
            "OrderDT": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            "OrderTitle": order_id,
            "BuyerPaymentType": 1,
        }

        # 🔹 Step 3: 呼叫玉山支付 API
        headers = {"Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EsunPayAPI.ESUNPAY_API_URL,
                    json=transaction_data,
                    headers=headers,
                    timeout=20.0
                )
                response.raise_for_status()
            try:
                esunpay_response = response.json()
            except Exception:
                print("❌ 玉山非 JSON 回應：", response.text)
                raise HTTPException(status_code=500, detail=f"EsunPay 回傳非 JSON：{response.text}")
        except httpx.TimeoutException:
            return {"status": "error", "code": 9999, "message": "Payment request timed out."}
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"EsunPay Request failed: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"EsunPay Error: {exc.response.text}")

        return {"status": "success", "data": esunpay_response}
