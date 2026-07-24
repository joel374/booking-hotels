from db import get_db_connection

def run_migration():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE hotels ADD COLUMN is_deleted TINYINT(1) DEFAULT 0")
        print("Added is_deleted to hotels")
    except Exception as e:
        print("Error on hotels:", e)
        
    try:
        cursor.execute("ALTER TABLE rooms ADD COLUMN is_deleted TINYINT(1) DEFAULT 0")
        print("Added is_deleted to rooms")
    except Exception as e:
        print("Error on rooms:", e)
        
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    run_migration()
