from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import datetime
import os

app = FastAPI()

# 合併後的請求格式
class LinePayRequest(BaseModel):
    key: str
    machine: str
    barcode: str  # 修改為小駝峰形式
    amount: int
    payway: str

# 定義退款請求的資料結構
class LinePayRefundRequest(BaseModel):
    key: str
    machine: str
    transactionId: str  # 修改為小駝峰形式
    refundAmount: int

# 玉山支付交易請求模型
class EsunPayRequest(BaseModel):
    key: str
    machine: str
    barcode: str
    amount: int

# API B 的 URL
API_B_URL = "https://unibuy.com.tw/Unibuy/api/app/machine/setting/B014"

# 玉山支付 API 端點
ESUNPAY_API_URL = "https://mpayment.esuntrade.com/mPay/GatewayV2/API/V2/xTrade.ashx"

# LINE Pay 環境配置
LINE_PAY_SANDBOX_URL = "https://sandbox-api-pay.line.me/v2/payments"
LINE_PAY_PRODUCTION_URL = "https://api-pay.line.me/v2/payments"


@app.post("/api/linepay/pay")
async def linepay_pay(request: LinePayRequest):
    # 檢查 barcode 長度
    if len(request.barcode) != 18:
        return {"status": "barcode error"}

    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {"key": request.key, "machine": request.machine, "time": current_time}
        async with httpx.AsyncClient() as client:
            response = await client.post(API_B_URL, json=payload, timeout=20.0)
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
            LINE_PAY_PRODUCTION_URL if os.getenv("APP_ENV") == "production" else LINE_PAY_SANDBOX_URL
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
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in [1172, 1198]:
            inquire_response = await linepay_inquire(channel_id, channel_secret, order_id)
            return {"status": "check_transaction", "data": inquire_response}
        raise HTTPException(status_code=exc.response.status_code, detail=f"LINE Pay Error: {exc.response.text}")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"LINE Pay Request failed: {exc}")

    return {"status": "success", "data": line_pay_response}


@app.get("/api/linepay/inquire")
async def linepay_inquire(channel_id: str, channel_secret: str, order_id: str):
    try:
        base_url = (
            LINE_PAY_PRODUCTION_URL
            if os.getenv("APP_ENV") == "production"
            else LINE_PAY_SANDBOX_URL
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
        if isinstance(exc, httpx.TimeoutException):
            raise HTTPException(
                status_code=500,
                detail="Network timeout occurred during inquiry.",
            )
        raise HTTPException(status_code=500, detail=f"Request failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=exc.response.status_code, detail=f"Error: {exc.response.text}"
        )


@app.post("/api/linepay/refund")
async def linepay_refund(request: LinePayRefundRequest):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {"key": request.key, "machine": request.machine, "time": current_time}
        async with httpx.AsyncClient() as client:
            response = await client.post(API_B_URL, json=payload)
            response.raise_for_status()
        api_b_response = response.json()

        data_items = api_b_response.get("data", [])
        channel_id = data_items[0].get("LINE_ChannelId")
        channel_secret = data_items[0].get("LINE_ChannelSecret")

        base_url = (
            LINE_PAY_PRODUCTION_URL
            if os.getenv("APP_ENV") == "production"
            else LINE_PAY_SANDBOX_URL
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
        raise HTTPException(
            status_code=exc.response.status_code, detail=f"Error: {exc.response.text}"
        )

@app.post("/api/esunpay/pay")
async def esunpay_pay(request: EsunPayRequest):
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {"key": request.key, "machine": request.machine, "time": current_time}
        async with httpx.AsyncClient() as client:
            response = await client.post(API_B_URL, json=payload, timeout=20.0)
            response.raise_for_status()
        api_b_response = response.json()
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"API B Request failed: {exc}")

    # 取得 StoreID, TermID, Hash
    data_items = api_b_response.get("data", [])
    if not data_items or not isinstance(data_items, list):
        raise HTTPException(status_code=500, detail="Invalid API B response structure.")
    
    store_id = data_items[0].get("ESUN_StoreID")
    term_id = data_items[0].get("ESUN_TermID")
    hash_key = data_items[0].get("ESUN_Hash")
    
    if not store_id or not term_id or not hash_key:
        raise HTTPException(status_code=500, detail="Missing StoreID, TermID, or Hash from API B.")
    
    # 設定訂單資訊
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
    
    headers = {"Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(ESUNPAY_API_URL, json=transaction_data, headers=headers, timeout=20.0)
            response.raise_for_status()
        esunpay_response = response.json()
    except httpx.RequestError as exc:
        if isinstance(exc, httpx.TimeoutException):
            return {
                "status": "error",
                "code": 9999,
                "message": "Payment request timed out."
            }
        raise HTTPException(status_code=500, detail=f"EsunPay Request failed: {exc}")
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=f"EsunPay Error: {exc.response.text}")
    
    return {"status": "success", "data": esunpay_response}
