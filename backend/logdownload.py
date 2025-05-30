from pathlib import Path
import datetime
import aiohttp
import asyncio
from fastapi import UploadFile, HTTPException
from fastapi.responses import HTMLResponse

# 設定基礎目錄
BASE_DIR = Path("./logs")
BASE_DIR.mkdir(exist_ok=True)

B010_API_URL = "https://unibuy.com.tw/Unibuy/api/app/machine/status/B010"


class LogAPI:
    @staticmethod
    async def upload_log(machine_id: str, file: UploadFile):
        machine_dir = BASE_DIR / machine_id
        machine_dir.mkdir(exist_ok=True)
        
          # 刪除超過 1 個月的 log 檔案
        await LogAPI.delete_old_logs(machine_dir)
        
        # 使用上傳檔案原始檔名作為檔名
        file_name = file.filename
        if not file_name:
            raise HTTPException(status_code=400, detail="Invalid file name")
        
        file_path = machine_dir / file_name

        with file_path.open("wb") as buffer:
            buffer.write(await file.read())

        return {"status": "success", "message": "File uploaded", "filename": file_name}
    
    @staticmethod
    async def delete_old_logs(machine_dir: Path):
        one_month_ago = datetime.datetime.now() - datetime.timedelta(days=30)
        for file in machine_dir.iterdir():
            if file.is_file() and datetime.datetime.fromtimestamp(file.stat().st_mtime) < one_month_ago:
                file.unlink()
                print(f"Deleted old log file: {file.name}")
    

    @staticmethod
    async def download_log(machine_id: str, filename: str):
        file_path = BASE_DIR / machine_id / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        try:
            content = file_path.read_text(encoding="utf-8")
            return content.replace("\\n", "\n")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")

    @staticmethod
    async def list_logs(machine_id: str):
        machine_dir = BASE_DIR / machine_id
        if not machine_dir.exists():
            raise HTTPException(status_code=404, detail="Machine ID not found")
        
        files = [f.name for f in machine_dir.iterdir() if f.is_file()]
        return {"machine_id": machine_id, "files": files}

    @staticmethod
    async def list_machines():
        machines = [d.name for d in BASE_DIR.iterdir() if d.is_dir()]
        return {"machines": machines}

    @staticmethod
    async def show_log(machine_id: str, filename: str):
        file_path = BASE_DIR / machine_id / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        try:
            content = file_path.read_text(encoding="utf-8").replace("\\n", "\n")
            return HTMLResponse(content=f"""
            <html>
                <head><meta charset="utf-8"><title>Log File</title></head>
                <body>
                    <pre style="white-space: pre-wrap; word-break: break-word;">{content}</pre>
                </body>
            </html>
            """)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file: {str(e)}")
        
    @staticmethod
    async def parse_log_for_b010(log_content: str):
        # 假設log的格式是 key:value，每行一組資料
        data = {}
        for line in log_content.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip()
        
        # 準備B010所需的資料
        payload = {
            "key": "KahnEwjhfDBHUYS7",
            "machine": data.get("machine", "M0000001"),
            "cabinetT": data.get("cabinetT", ""),
            "door": data.get("door", ""),
            "temperature": data.get("temperature", ""),
            "M_Stus": data.get("M_Stus", ""),
            "M_Stus2": data.get("M_Stus2", ""),
            "M_Ver": data.get("M_Ver", "")
        }
        return payload

    @staticmethod
    async def send_log_to_b010(machine_id: str):
        machine_dir = BASE_DIR / machine_id
        if not machine_dir.exists() or not any(machine_dir.iterdir()):
            return

        latest_log = max(machine_dir.iterdir(), key=lambda f: f.stat().st_mtime)
        log_content = latest_log.read_text(encoding="utf-8")
        payload = await LogAPI.parse_log_for_b010(log_content)

        async with aiohttp.ClientSession() as session:
            async with session.post(B010_API_URL, json=payload) as response:
                if response.status != 200:
                    print(f"Failed to upload log for {machine_id}: {await response.text()}")
    
    @staticmethod
    async def show_machine_logs(machine_id: str):
        machine_dir = BASE_DIR / machine_id
        if not machine_dir.exists():
            raise HTTPException(status_code=404, detail="Machine ID not found")
        
        files = sorted(
            machine_dir.iterdir(), 
            key=lambda f: f.stat().st_mtime, 
            reverse=True
        )
        
        file_list_html = "".join(f'<li><a href="/api/machine/{machine_id}/log/show/{file.name}">{file.name}</a></li>' for file in files if file.is_file())
        return HTMLResponse(content=f"""
        <html>
            <head><meta charset="utf-8"><title>Log List</title></head>
            <body>
                <h1>Logs for Machine {machine_id}</h1>
                <ul>{file_list_html}</ul>
            </body>
        </html>
        """)

async def schedule_log_upload():
    while True:
        machines = await LogAPI.list_machines()
        for machine_id in machines["machines"]:
            await LogAPI.send_log_to_b010(machine_id)
        await asyncio.sleep(600)  # 每10分鐘執行一次