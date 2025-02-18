from fastapi import FastAPI
from esunpay import EsunPayAPI, EsunPayRequest
from linepay import LinePayAPI, LinePayRequest, LinePayRefundRequest

app = FastAPI()

# 合併後的請求格式
@app.post("/api/linepay/pay")
async def linepay_pay(request: LinePayRequest):
    return await LinePayAPI.pay(request)

@app.get("/api/linepay/inquire")
async def linepay_inquire(channel_id: str, channel_secret: str, order_id: str):
    return await LinePayAPI.inquire(channel_id, channel_secret, order_id)

@app.post("/api/linepay/refund")
async def linepay_refund(request: LinePayRefundRequest):
    return await LinePayAPI.refund(request)

@app.post("/api/esunpay/pay")
async def esunpay_pay(request: EsunPayRequest):
    return await EsunPayAPI.pay(request)