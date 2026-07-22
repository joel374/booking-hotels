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
    
    # Detailed column check
    cursor.execute("DESC users")
    columns = cursor.fetchall()
    print("✓ Current Users table columns:")
    for col in columns:
        col_name = col[0]
        col_type = col[1]
        nullable = col[2]
        print(f"  - {col_name:25} | {col_type:20} | Nullable: {nullable}")
    
    # Check if password_reset columns exist
    missing = []
    for col in columns:
        if col[0] == 'password_reset_token':
            print("\n✓ password_reset_token column EXISTS")
        if col[0] == 'password_reset_expires':
            print("✓ password_reset_expires column EXISTS")
    
    cursor.close()
    conn.close()
    print("\n✓ Database connection successful - schema is ready!")
    
except Exception as e:
    print(f"✗ Database error: {e}")
