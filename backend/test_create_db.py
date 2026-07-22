import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import os
from dotenv import load_dotenv

load_dotenv()

conn_str = os.getenv("DATABASE_URL")
if conn_str.startswith("postgresql://"):
    # Connect to default db to create a new one
    conn = psycopg2.connect(conn_str)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    try:
        cur.execute("CREATE DATABASE audit_test_db;")
        print("Database 'audit_test_db' created successfully.")
    except Exception as e:
        print("Failed to create database:", e)
    cur.close()
    conn.close()
