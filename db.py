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

def init_db_schema():
    """Ensure database and schema tables exist."""
    try:
        base_config = {k: v for k, v in db_config.items() if k != 'database'}
        conn = mysql.connector.connect(**base_config)
        cursor = conn.cursor()
        
        db_name = db_config.get('database', 'hotel_booking')
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`;")
        cursor.execute(f"USE `{db_name}`;")
        
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            for statement in sql_script.split(';'):
                statement = statement.strip()
                if statement:
                    try:
                        cursor.execute(statement)
                    except Exception:
                        pass
        
        # Auto-migrate missing columns for existing databases
        migrations = [
            "ALTER TABLE `users` ADD COLUMN `last_login` DATETIME DEFAULT NULL;",
            "ALTER TABLE `users` ADD COLUMN `google_id` VARCHAR(100) DEFAULT NULL;",
            "ALTER TABLE `users` ADD COLUMN `auth_provider` VARCHAR(50) DEFAULT 'local';",
            "ALTER TABLE `users` ADD COLUMN `full_name` VARCHAR(100) DEFAULT NULL;",
            "ALTER TABLE `users` ADD COLUMN `photo_url` VARCHAR(255) DEFAULT NULL;",
            "ALTER TABLE `users` ADD COLUMN `password_reset_token` VARCHAR(255) DEFAULT NULL;",
            "ALTER TABLE `users` ADD COLUMN `password_reset_expires` DATETIME DEFAULT NULL;",
            "ALTER TABLE `bookings` ADD COLUMN `cancel_reason` TEXT DEFAULT NULL;",
            "ALTER TABLE `hotels` ADD COLUMN `is_deleted` TINYINT(1) DEFAULT 0;",
            "ALTER TABLE `rooms` ADD COLUMN `is_deleted` TINYINT(1) DEFAULT 0;"
        ]
        for m in migrations:
            try:
                cursor.execute(m)
            except Exception:
                pass

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[Warning] Auto-schema check failed: {e}")

def cleanup_expired_bookings(cursor):
    """Marks 'Pending' bookings older than 15 minutes as 'Cancelled'."""
    query = """
        UPDATE bookings 
        SET status = 'Cancelled' 
        WHERE status = 'Pending' AND created_at < NOW() - INTERVAL 15 MINUTE
    """
    cursor.execute(query)
