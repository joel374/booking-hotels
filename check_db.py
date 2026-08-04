from db import get_db_connection

try:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW COLUMNS FROM hotels LIKE 'is_deleted'")
    result_hotels = cursor.fetchone()
    
    cursor.execute("SHOW COLUMNS FROM rooms LIKE 'is_deleted'")
    result_rooms = cursor.fetchone()
    
    cursor.execute("SHOW TABLES LIKE 'audit_logs'")
    result_audit = cursor.fetchone()
    
    print(f"Hotels is_deleted: {bool(result_hotels)}")
    print(f"Rooms is_deleted: {bool(result_rooms)}")
    print(f"Audit table: {bool(result_audit)}")
    
    cursor.close()
    conn.close()
except Exception as e:
    print(e)
