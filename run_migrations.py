import os
import time
from db import get_db_connection
import mysql.connector

def run_migrations():
    # Wait for DB to be ready (important for Docker startup)
    max_retries = 10
    conn = None
    for i in range(max_retries):
        try:
            conn = get_db_connection()
            break
        except Exception as e:
            print(f"Waiting for database to be ready... ({i+1}/{max_retries})")
            time.sleep(2)
            
    if not conn:
        print("Failed to connect to database. Migrations aborted.")
        return

    cursor = conn.cursor()

    # Create migration_history table if it doesn't exist
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS migration_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            migration_name VARCHAR(255) NOT NULL UNIQUE,
            executed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    conn.commit()

    # Read existing migrations
    cursor.execute("SELECT migration_name FROM migration_history")
    executed_migrations = {row[0] for row in cursor.fetchall()}

    migrations_dir = 'migrations'
    if not os.path.exists(migrations_dir):
        os.makedirs(migrations_dir)
        print(f"Created {migrations_dir} directory.")
        return

    # Get all .sql files in migrations directory, sorted by name
    migration_files = sorted([f for f in os.listdir(migrations_dir) if f.endswith('.sql')])

    for file in migration_files:
        if file not in executed_migrations:
            print(f"Executing migration: {file}")
            filepath = os.path.join(migrations_dir, file)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                sql_statements = f.read().split(';')
            
            try:
                for statement in sql_statements:
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
                
                # Record the migration as executed
                cursor.execute(
                    "INSERT INTO migration_history (migration_name) VALUES (%s)", 
                    (file,)
                )
                conn.commit()
                print(f"Successfully applied {file}")
                
            except mysql.connector.Error as err:
                if err.errno in (1060, 1050):
                    print(f"Warning on {file}: {err.msg}. Treating as already applied.")
                    cursor.execute(
                        "INSERT INTO migration_history (migration_name) VALUES (%s)", 
                        (file,)
                    )
                    conn.commit()
                else:
                    print(f"Error applying {file}: {err}")
                    conn.rollback()
                    break # Stop running further migrations on failure

    cursor.close()
    conn.close()
    print("Database migrations check complete.")

if __name__ == "__main__":
    run_migrations()
