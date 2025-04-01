import pymysql

host = "152.42.211.122"
user = "root"  # 請填入你的 MySQL 帳號
password = "1234Abcd@"  # 請填入你的 MySQL 密碼
database = "linepay_db"  # 請填入你的資料庫名稱

# 初始化變數，避免 NameError
connection = None  

try:
    connection = pymysql.connect(
        host=host,
        user=user,
        password=password,
        database=database,
        port=3306,
        connect_timeout=10
    )
    print("✅ 成功連接到 MySQL！")

    # 測試查詢
    with connection.cursor() as cursor:
        cursor.execute("SELECT DATABASE();")
        db_name = cursor.fetchone()
        print(f"目前連線到的資料庫: {db_name[0]}")
    
except pymysql.MySQLError as e:
    print(f"❌ 無法連接 MySQL，錯誤訊息：{e}")

finally:
    if connection:  # 確保 connection 變數存在
        connection.close()
        print("🔌 MySQL 連線已關閉")
