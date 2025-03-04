from pathlib import Path
import datetime
import chardet
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
        
        # 以當前日期命名檔案，例如 20250228.txt
        today_date = datetime.datetime.now().strftime("%Y%m%d")
        file_name = f"{today_date}.txt"
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
            with file_path.open("rb") as f:
                raw_data = f.read()

            result = chardet.detect(raw_data)
            encoding = result["encoding"]

            if not encoding:
                raise HTTPException(status_code=500, detail="Unable to detect file encoding")

            return raw_data.decode(encoding, errors='ignore')

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
            with file_path.open("rb") as f:
                raw_data = f.read()

            result = chardet.detect(raw_data)
            encoding = result["encoding"]

            if not encoding:
                raise HTTPException(status_code=500, detail="Unable to detect file encoding")

            content = raw_data.decode(encoding, errors='ignore').replace("\\n", "\n")
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
