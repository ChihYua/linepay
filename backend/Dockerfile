# 1️⃣ 使用 Python 3.9 作為基礎映像
FROM python:3.9

# 2️⃣ 設定工作目錄（在容器內）
WORKDIR /app

# 3️⃣ 複製當前目錄內的所有檔案到容器 `/app` 目錄
COPY . .

# 4️⃣ 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 5️⃣ 指定容器啟動時執行的指令
CMD ["python", "app.py"]