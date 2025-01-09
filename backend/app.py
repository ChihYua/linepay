from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import datetime
import os

app = FastAPI()

# API A 請求格式
class RequestData(BaseModel):
    key: str
    machine: str
    time: str

# LINE Pay 請求格式
class LinePayRequest(BaseModel):
    channel_id: str
    channel_secret: str
    one_time_key: str
    store_id: str
    amount: int  # 金額改回整數
    payway: str
    
# 定義退款請求的資料結構
class LinePayRefundRequest(BaseModel):
    channel_id: str
    channel_secret: str
    transaction_id: str
    refund_amount: int  # 金額改回整數

# API B 的 URL
API_B_URL = "https://unibuy.com.tw/Unibuy/api/app/machine/setting/B014"

# LINE Pay 環境配置
LINE_PAY_SANDBOX_URL = "https://sandbox-api-pay.line.me/v2/payments"
LINE_PAY_PRODUCTION_URL = "https://api-pay.line.me/v2/payments"


@app.post("/combined-api")
async def combined_api(data: RequestData, line_pay_request: LinePayRequest):
    # 第一步：發送資料到 API B
    try:
        payload = data.dict()
        async with httpx.AsyncClient() as client:
            response = await client.post(API_B_URL, json=payload)
            response.raise_for_status()
        api_b_response = response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"API B Request failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"API B Error: {exc.response.text}",
        )

    # 第二步：發送資料到 LINE Pay
    try:
        base_url = (
            LINE_PAY_PRODUCTION_URL
            if os.getenv("APP_ENV") == "production"
            else LINE_PAY_SANDBOX_URL
        )
        pay_url = f"{base_url}/oneTimeKeys/pay"
        req_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        order_id = f"{req_time}{line_pay_request.payway}{line_pay_request.store_id}"

        # 設置請求 Body
        body = {
            "amount": line_pay_request.amount,
            "currency": "TWD",
            "orderId": order_id,
            "productName": order_id,
            "oneTimeKey": line_pay_request.one_time_key,
        }

        # 設置 Headers
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-LINE-ChannelSecret": line_pay_request.channel_secret,
            "X-LINE-ChannelId": line_pay_request.channel_id,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(pay_url, json=body, headers=headers)
            response.raise_for_status()
        line_pay_response = response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"LINE Pay Request failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"LINE Pay Error: {exc.response.text}",
        )

    return {"api_b_response": api_b_response, "line_pay_response": line_pay_response}


@app.get("/linepay/inquire")
async def linepay_inquire(channel_id: str, channel_secret: str, order_id: str):
    """
    查詢 LINE Pay 訂單資訊
    """
    try:
        # 確定環境（生產或沙盒）
        base_url = (
            LINE_PAY_PRODUCTION_URL
            if os.getenv("APP_ENV") == "production"
            else LINE_PAY_SANDBOX_URL
        )
        url = f"{base_url}?orderId={order_id}"

        # 設置 Headers
        headers = {
            "Content-Type": "application/json",
            "X-LINE-ChannelId": channel_id,
            "X-LINE-ChannelSecret": channel_secret,
        }

        # 發送請求
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            result = response.json()

        return {"status": "success", "data": result}

    except httpx.RequestError as exc:
        return {"status": "error", "message": f"Request failed: {exc}"}
    except httpx.HTTPStatusError as exc:
        return {"status": "error", "message": exc.response.text}
    


@app.post("/linepay/refund")
async def linepay_refund(request: LinePayRefundRequest):
    try:
        # API URL
        base_url = (
            LINE_PAY_PRODUCTION_URL
            if os.getenv("APP_ENV") == "production"
            else LINE_PAY_SANDBOX_URL
        )
        url = f"{base_url}/{request.transaction_id}/refund"

        # Body 設置
        body = {"refundAmount": request.refund_amount}  # 直接以元為單位
        headers = {
            "Content-Type": "application/json",
            "X-LINE-ChannelId": request.channel_id,
            "X-LINE-ChannelSecret": request.channel_secret,
        }

        # 發送退款請求
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=body, headers=headers)
            response.raise_for_status()
            result = response.json()

        # 檢查 LINE Pay 回應代碼
        if result.get("returnCode") == "1150":
            raise HTTPException(
                status_code=404,
                detail="Transaction record not found. Please verify the transaction ID and environment.",
            )
        
        return {"status": "success", "data": result}

    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Request failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=f"Error: {exc.response.text}"
        )