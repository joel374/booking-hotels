import argparse
import os
import re
import sys

import mysql.connector
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'hotel_booking')
MIGRATIONS_DIR = os.path.join(BASE_DIR, 'migrations', 'versions')
MIGRATION_TABLE = 'schema_migrations'


def get_server_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        autocommit=False,
    )


def get_db_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        autocommit=False,
    )


def ensure_database_exists():
    with get_server_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()


def ensure_migration_table(conn):
    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS `{MIGRATION_TABLE}` (
            version VARCHAR(255) NOT NULL PRIMARY KEY,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    )
    conn.commit()


def get_applied_migrations(conn):
    cursor = conn.cursor()
    cursor.execute(f"SELECT version FROM `{MIGRATION_TABLE}` ORDER BY version")
    return {row[0] for row in cursor.fetchall()}


def list_migration_files():
    if not os.path.isdir(MIGRATIONS_DIR):
        raise FileNotFoundError(f"Migrations directory not found: {MIGRATIONS_DIR}")

    files = [f for f in os.listdir(MIGRATIONS_DIR) if f.lower().endswith('.sql')]
    return sorted(files)


def normalize_sql(sql):
    sql = re.sub(r"(?mi)^\s*USE\s+`?[^`;]+`?\s*;?", f"USE `{DB_NAME}`;", sql)
    sql = re.sub(
        r"(?mi)^\s*CREATE\s+DATABASE\s+IF\s+NOT\s+EXISTS\s+`?[^`;]+`?[^;]*;?",
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        sql,
    )
    return sql


def split_sql_statements(sql):
    statements = []
    buffer = []

    for line in sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('--') or stripped.startswith('#'):
            continue

        buffer.append(line)
        if stripped.endswith(';'):
            statement = '\n'.join(buffer).strip()
            statement = statement[:-1].strip() if statement.endswith(';') else statement
            if statement:
                statements.append(statement)
            buffer = []

    if buffer:
        statement = '\n'.join(buffer).strip()
        if statement:
            statements.append(statement)

    return statements


def apply_migration(conn, migration_file):
    path = os.path.join(MIGRATIONS_DIR, migration_file)
    with open(path, 'r', encoding='utf-8') as f:
        sql_text = f.read()

    sql_text = normalize_sql(sql_text)
    statements = split_sql_statements(sql_text)

    cursor = conn.cursor()
    print(f"Applying migration: {migration_file}")
    try:
        for statement in statements:
            cursor.execute(statement)
        cursor.execute(
            f"INSERT INTO `{MIGRATION_TABLE}` (version) VALUES (%s)",
            (migration_file,),
        )
        conn.commit()
        print(f"  -> Applied {migration_file}")
    except mysql.connector.Error as exc:
        conn.rollback()
        print(f"Failed to apply migration {migration_file}: {exc}")
        raise


def run_migrations():
    print(f"Connecting to MySQL server at {DB_HOST}...")
    ensure_database_exists()

    with get_db_connection() as conn:
        ensure_migration_table(conn)
        applied = get_applied_migrations(conn)
        migration_files = list_migration_files()

        pending = [f for f in migration_files if f not in applied]
        if not pending:
            print("Database is up-to-date. No pending migrations.")
            return

        for migration_file in pending:
            apply_migration(conn, migration_file)

        print("All pending migrations have been applied.")


def show_status():
    ensure_database_exists()
    with get_db_connection() as conn:
        ensure_migration_table(conn)
        applied = sorted(get_applied_migrations(conn))
        migration_files = list_migration_files()
        pending = [f for f in migration_files if f not in applied]

        print("Applied migrations:")
        for version in applied:
            print(f"  - {version}")

        print("\nPending migrations:")
        for version in pending:
            print(f"  - {version}")


def main():
    parser = argparse.ArgumentParser(description='Run database migrations for booking-hotels.')
    parser.add_argument('--status', action='store_true', help='Show applied and pending migrations')
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    run_migrations()


if __name__ == '__main__':
    main()
