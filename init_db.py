import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

def init_db():
    """Initialize database with schema and seed data"""
    
    # Connect without database first to create it
    conn = mysql.connector.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '')
    )
    cursor = conn.cursor()
    
    print("Initializing database...")
    
    # Read and execute schema
    try:
        with open('schema.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        statements = sql_script.split(';')
        
        for statement in statements:
            statement = statement.strip()
            if statement:
                try:
                    cursor.execute(statement)
                except mysql.connector.Error as err:
                    print(f"Warning: {err}")
        
        conn.commit()
        print("[OK] Schema created successfully")
        
    except FileNotFoundError:
        print("Error: schema.sql not found")
        return
    
    # Insert seed data (provinces and cities)
    try:
        with open('seed_data.sql', 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        statements = sql_script.split(';')
        
        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith('--'):
                try:
                    cursor.execute(statement)
                except mysql.connector.Error as err:
                    print(f"Warning: {err}")
        
        conn.commit()
        print("[OK] Seed data inserted successfully")
        
    except FileNotFoundError:
        print("Warning: seed_data.sql not found - run generate_seed_data.py first")
    
    cursor.close()
    conn.close()
    print("\nDatabase initialization completed!")

if __name__ == '__main__':
    init_db()
