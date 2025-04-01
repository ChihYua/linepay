import aiomysql
import asyncio

class Database:
    _pool = None

    @classmethod
    async def init_pool(cls):
        if cls._pool is None:
            cls._pool = await aiomysql.create_pool(
                host="152.42.211.122",  # 你的 MySQL 伺服器 IP 或域名
                port=3306,
                user="root",  # 你的 MySQL 使用者名稱
                password="1234Abcd@",  # 你的 MySQL 密碼
                db="linepay_db",  # 你的 MySQL 資料庫名稱
                autocommit=True,
                minsize=1,
                maxsize=10
            )

    @classmethod
    async def get_connection(cls):
        if cls._pool is None:
            await cls.init_pool()
        return await cls._pool.acquire()

    @classmethod
    async def close_pool(cls):
        if cls._pool:
            cls._pool.close()
            await cls._pool.wait_closed()