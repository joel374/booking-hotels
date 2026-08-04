from app import app
from db import get_db_connection

with app.test_request_context('/admin/hotel/delete/1'):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("UPDATE hotels SET is_deleted = 1 WHERE id = %s", (1,))
        cursor.execute("UPDATE rooms SET is_deleted = 1 WHERE hotel_id = %s", (1,))
        
        conn.commit()
        cursor.close()
        conn.close()
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")
