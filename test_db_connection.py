import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()

try:
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )
    cursor = conn.cursor()
    cursor.execute("SELECT VERSION()")
    version = cursor.fetchone()
    print(f"✓ Database connected: {version[0]}")
    
    cursor.execute("DESC users")
    columns = cursor.fetchall()
    print(f"✓ Users table columns: {len(columns)}")
    
    for col in columns:
        if 'password_reset' in col[0]:
            print(f"  - {col[0]} ({col[1]})")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(f"✗ Database error: {e}")
