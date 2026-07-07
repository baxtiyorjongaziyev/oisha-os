import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "marketing.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_token(token: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO config (key, value) VALUES ('meta_access_token', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
    ''', (token,))
    conn.commit()
    conn.close()

def get_token() -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key='meta_access_token'")
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0]
    return ""

def delete_token():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM config WHERE key='meta_access_token'")
    conn.commit()
    conn.close()
