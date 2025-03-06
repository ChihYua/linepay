from pathlib import Path
import datetime
from fastapi import UploadFile, HTTPException
from fastapi.responses import HTMLResponse

# 設定基礎目錄
BASE_DIR = Path("./logs")
BASE_DIR.mkdir(exist_ok=True)

class LogAPI:
    @staticmethod
    async def upload_log(machine_id: str, file: UploadFile):
        machine_dir = BASE_DIR / machine_id
        machine_dir.mkdir(exist_ok=True)
        
        # 使用上傳檔案原始檔名作為檔名
        file_name = file.filename
        if not file_name:
            raise HTTPException(status_code=400, detail="Invalid file name")
        
        file_path = machine_dir / file_name

        with file_path.open("wb") as buffer:
            buffer.write(await file.read())

        return {"status": "success", "message": "File uploaded", "filename": file_name}

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