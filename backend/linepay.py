import datetime
import httpx
import os
from fastapi import HTTPException
from pydantic import BaseModel
from database import Database

# 定義 LINE Pay 交易請求的資料結構
class LinePayRequest(BaseModel):
    key: str
    machine: str
    barcode: str
    amount: int
    payway: str
    test: int  # 1: 測試模式，0: 正式環境

# 定義 LINE Pay 退款請求的資料結構
class LinePayRefundRequest(BaseModel):
    key: str
    machine: str
    orderId: str  # 原來是 transactionId，現在改成 orderId
    refundAmount: int
    test: int  # 1: 測試模式，0: 正式環境

class LinePayAPI:
    API_B_URL = "https://unibuy.com.tw/Unibuy/api/app/machine/setting/B014"
    LINE_PAY_SANDBOX_URL = "https://sandbox-api-pay.line.me/v2/payments"
    LINE_PAY_PRODUCTION_URL = "https://api-pay.line.me/v2/payments"

    @staticmethod
    async def pay(request: LinePayRequest):
        if len(request.barcode) != 18:
            return {"status": "barcode error"}

        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {"key": request.key, "machine": request.machine, "time": current_time}
            async with httpx.AsyncClient() as client:
                response = await client.post(LinePayAPI.API_B_URL, json=payload, timeout=20.0)
                response.raise_for_status()
            api_b_response = response.json()
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"API B Request failed: {exc}")
        
        data_items = api_b_response.get("data", [])
        if not data_items or not isinstance(data_items, list):
            raise HTTPException(status_code=500, detail="Invalid API B response structure.")

        channel_id = data_items[0].get("LINE_ChannelId")
        channel_secret = data_items[0].get("LINE_ChannelSecret")
        if not channel_id or not channel_secret:
            return_code, return_message, status = "200", "金流未開放", "failed"
            await LinePayAPI.save_transaction("N/A", request, status, return_code, return_message)
            return {"status": "failed", "message": "金流未開放"}


        try:
            base_url = (
                LinePayAPI.LINE_PAY_SANDBOX_URL if request.test == 1 else LinePayAPI.LINE_PAY_PRODUCTION_URL
            )
            pay_url = f"{base_url}/oneTimeKeys/pay"
            req_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            order_id = f"{req_time}{request.payway}{request.machine}"

            body = {
                "amount": request.amount,
                "currency": "TWD",
                "orderId": order_id,
                "productName": order_id,
                "oneTimeKey": request.barcode,
            }
            headers = {
                "Content-Type": "application/json;charset=UTF-8",
                "X-LINE-ChannelSecret": channel_secret,
                "X-LINE-ChannelId": channel_id,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(pay_url, json=body, headers=headers, timeout=20.0)
                response.raise_for_status()
            line_pay_response = response.json()
            
            # ✅ 新增 returnCode 判斷邏輯
            return_code = line_pay_response.get("returnCode", "9999")  # 預設錯誤代碼
            return_message = line_pay_response.get("returnMessage", "Unknown error")
            status = "success" if return_code == "0000" else "failed"
            
        except httpx.TimeoutException:  # ✅ **新增逾時處理**
            try:
                inquire_response = await LinePayAPI.inquire(channel_id, channel_secret, order_id, request.test)
                return {
                    "status": "timeout",
                    "data": inquire_response,
                }
            except HTTPException as inquire_exc:
                if inquire_exc.status_code == 500 and "timeout" in inquire_exc.detail.lower():
                    return {
                        "status": "error",
                        "code": 9999,
                        "message": "Payment request and inquiry both timed out.",
                    }
                raise inquire_exc  # 若 `inquire` 本身報錯，則拋出

        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 503:
                return_code, return_message, status = "503", "金流未開放", "failed"
            else:
                return_code, return_message, status = str(exc.response.status_code), exc.response.text, "failed"


        except httpx.RequestError as exc:
            return_code, return_message, status = "9999", str(exc), "failed"
            
           # ✅ 確保交易記錄無論成功或失敗都儲存到 MySQL
        await LinePayAPI.save_transaction(order_id, request, status, return_code, return_message)
            
           # ✅ 修正後的回應邏輯
        if return_code == "0000":
            return {"status": "success", "data": line_pay_response}
        else:
            raise HTTPException(status_code=400, detail=f"LINE Pay Error: {return_message} (Code: {return_code})")

    
    @staticmethod
    async def save_transaction(order_id, request, status, return_code, return_message):
        """將交易記錄存入 MySQL"""
        conn = await Database.get_connection()
        async with conn.cursor() as cursor:
            sql = """
            INSERT INTO linepay_transactions (order_id, machine, barcode, amount, payway, status, return_code, return_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            await cursor.execute(sql, (
                order_id,
                request.machine,
                request.barcode,
                request.amount,
                request.payway,
                status,
                return_code,
                return_message
            ))

    @staticmethod
    async def inquire(channel_id: str, channel_secret: str, order_id: str, test: int=0):
        try:
            # ✅ 使用 test 變數來判定環境
            base_url = (
                LinePayAPI.LINE_PAY_SANDBOX_URL if test == 1 else LinePayAPI.LINE_PAY_PRODUCTION_URL
            )
            url = f"{base_url}/orders/{order_id}/check"

            headers = {
                "Content-Type": "application/json",
                "X-LINE-ChannelId": channel_id,
                "X-LINE-ChannelSecret": channel_secret,
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=20.0)
                response.raise_for_status()
                result = response.json()

            return {"status": "success", "data": result}

        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"Request failed: {exc}")

        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"Error: {exc.response.text}")


    @staticmethod
    async def refund(request: LinePayRefundRequest):
        try:
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            payload = {"key": request.key, "machine": request.machine, "time": current_time}
            async with httpx.AsyncClient() as client:
                response = await client.post(LinePayAPI.API_B_URL, json=payload)
                response.raise_for_status()
            api_b_response = response.json()

            data_items = api_b_response.get("data", [])
            channel_id = data_items[0].get("LINE_ChannelId")
            channel_secret = data_items[0].get("LINE_ChannelSecret")

            base_url = (
                LinePayAPI.LINE_PAY_SANDBOX_URL if request.test == 1 else LinePayAPI.LINE_PAY_PRODUCTION_URL
            )
            url = f"{base_url}/orders/{request.orderId}/refund"

            body = {"refundAmount": request.refundAmount}
            headers = {
                "Content-Type": "application/json",
                "X-LINE-ChannelId": channel_id,
                "X-LINE-ChannelSecret": channel_secret,
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=body, headers=headers)
                response.raise_for_status()
                result = response.json()

            return {"status": "success", "data": result}
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"Request failed: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"Error: {exc.response.text}")