import datetime
import httpx
import os
from fastapi import HTTPException
from pydantic import BaseModel

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
    transactionId: str
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
            raise HTTPException(status_code=500, detail="Missing LINE Pay credentials.")

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
        except httpx.RequestError as exc:
            raise HTTPException(status_code=500, detail=f"LINE Pay Request failed: {exc}")
        except httpx.HTTPStatusError as exc:
            raise HTTPException(status_code=exc.response.status_code, detail=f"LINE Pay Error: {exc.response.text}")

        return {"status": "success", "data": line_pay_response}

    @staticmethod
    async def inquire(channel_id: str, channel_secret: str, order_id: str, test: int=0):
        try:
            # ✅ 使用 test 變數來判定環境
            base_url = (
                LinePayAPI.LINE_PAY_SANDBOX_URL if test == 1 else LinePayAPI.LINE_PAY_PRODUCTION_URL
            )
            url = f"{base_url}?orderId={order_id}"

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
            url = f"{base_url}/{request.transactionId}/refund"

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