import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'hotel_booking')
}

def execute_migration():
    print("Menghubungkan ke database MySQL...")
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        migration_file = os.path.join(os.path.dirname(__file__), 'migration.sql')
        if not os.path.exists(migration_file):
            print(f"Error: File {migration_file} tidak ditemukan!")
            return

        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
            
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        print(f"Mengeksekusi {len(statements)} perintah SQL dari migration.sql...")
        for idx, statement in enumerate(statements, 1):
            try:
                cursor.execute(statement)
                first_line = statement.split('\n')[0][:50]
                print(f"[{idx}/{len(statements)}] Sukses: {first_line}...")
            except mysql.connector.Error as err:
                print(f"[{idx}/{len(statements)}] Dilewati/Peringatan: {err}")
                
        conn.commit()
        cursor.close()
        conn.close()
        print("\n[OK] Eksekusi migration.sql berhasil diselesaikan!")
    except Exception as e:
        print(f"Error saat eksekusi migrasi: {e}")

if __name__ == "__main__":
    execute_migration()
