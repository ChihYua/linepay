import asyncio
from database import Database  # ✅ 確保 `database.py` 在同一個目錄

async def test_mysql_connection():
    try:
        await Database.init_pool()
        conn = await Database.get_connection()
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT DATABASE();")
            result = await cursor.fetchone()
            print(f"✅ 成功連接到 MySQL 資料庫: {result[0]}")
        conn.close()
    except Exception as e:
        print(f"❌ MySQL 連線失敗: {e}")

asyncio.run(test_mysql_connection())