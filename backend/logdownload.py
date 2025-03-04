from pathlib import Path
import datetime
from fastapi import UploadFile, HTTPException

# 設定基礎目錄
BASE_DIR = Path("./logs")
BASE_DIR.mkdir(exist_ok=True)

class LogAPI:
    @staticmethod
    async def upload_log(machine_id: str, file: UploadFile):
        machine_dir = BASE_DIR / machine_id
        machine_dir.mkdir(exist_ok=True)
        
        # 當前日期命名檔案
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
        
        return file_path.read_text(encoding="utf-8")
