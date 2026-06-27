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

def get_db_connection():
    return mysql.connector.connect(**db_config)

def cleanup_expired_bookings(cursor):
    """Marks 'Pending' bookings older than 15 minutes as 'Cancelled'."""
    query = """
        UPDATE bookings 
        SET status = 'Cancelled' 
        WHERE status = 'Pending' AND created_at < NOW() - INTERVAL 15 MINUTE
    """
    cursor.execute(query)
