import os
import sys
from db import get_db_connection

def migrate():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        print("Altering bookings table to support new statuses...")
        # First, add the new values to the enum without removing the old ones so we don't break existing rows before update
        cursor.execute("ALTER TABLE bookings MODIFY COLUMN status ENUM('Pending', 'Confirmed', 'Completed', 'Booked', 'Checked In', 'Checked Out', 'Cancelled') NOT NULL DEFAULT 'Booked'")
        
        print("Mapping old 'Pending' to 'Booked'...")
        cursor.execute("UPDATE bookings SET status = 'Booked' WHERE status = 'Pending'")
        
        print("Mapping old 'Confirmed' to 'Booked'...")
        cursor.execute("UPDATE bookings SET status = 'Booked' WHERE status = 'Confirmed'")

        print("Mapping old 'Completed' to 'Checked Out'...")
        cursor.execute("UPDATE bookings SET status = 'Checked Out' WHERE status = 'Completed'")
            
        print("Finalizing ENUM column...")
        cursor.execute("ALTER TABLE bookings MODIFY COLUMN status ENUM('Booked', 'Checked In', 'Checked Out', 'Cancelled') NOT NULL DEFAULT 'Booked'")

        conn.commit()
        print("Migration complete!")

    except Exception as e:
        print(f"Error during migration: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    migrate()
