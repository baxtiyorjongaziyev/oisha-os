import os
import sqlite3
import time

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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            expires_at REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


def save_oauth_state(state: str, ttl_seconds: int = 600):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    expires_at = time.time() + ttl_seconds
    cursor.execute(
        "INSERT INTO oauth_states (state, expires_at) VALUES (?, ?) "
        "ON CONFLICT(state) DO UPDATE SET expires_at=excluded.expires_at",
        (state, expires_at),
    )
    # Prune expired states
    cursor.execute("DELETE FROM oauth_states WHERE expires_at < ?", (time.time(),))
    conn.commit()
    conn.close()


def verify_and_consume_oauth_state(state: str) -> bool:
    if not state:
        return False
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = time.time()
    cursor.execute("SELECT expires_at FROM oauth_states WHERE state = ?", (state,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    expires_at = row[0]
    cursor.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    conn.commit()
    conn.close()
    return expires_at >= now


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
