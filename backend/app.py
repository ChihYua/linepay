from fastapi import FastAPI, UploadFile, File
from esunpay import EsunPayAPI, EsunPayRequest
from linepay import LinePayAPI, LinePayRequest, LinePayRefundRequest
from logdownload import LogAPI
from fastapi.responses import HTMLResponse
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

@app.post("/api/machine/{machine_id}/log/update")
async def upload_log(machine_id: str, file: UploadFile = File(...)):
    return await LogAPI.upload_log(machine_id, file)

@app.get("/api/machine/{machine_id}/log/download/{filename}")
async def download_log(machine_id: str, filename: str):
    return await LogAPI.download_log(machine_id, filename)

@app.get("/api/machine/{machine_id}/log/download")
async def list_logs(machine_id: str):
    return await LogAPI.list_logs(machine_id)

@app.get("/api/machine/{machine_id}/log/show/{filename}", response_class=HTMLResponse)
async def show_log(machine_id: str, filename: str):
    return await LogAPI.show_log(machine_id, filename)

