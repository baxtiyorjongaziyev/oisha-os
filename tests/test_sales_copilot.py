import sqlite3

from src.services.core.sales_staff_copilot import bind_and_welcome_staff


def _make_db(path):
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,"
        " role TEXT, position TEXT, created_at TEXT)"
    )
    conn.execute("CREATE TABLE kv_settings (key TEXT PRIMARY KEY, value TEXT, updated_at TEXT)")
    conn.commit()
    conn.close()


def test_bind_and_welcome_staff_binds_once(tmp_path):
    db = tmp_path / "bot.db"
    _make_db(db)
    dialer = tmp_path / "dialer.db"

    is_new, intro = bind_and_welcome_staff(123456, "@RayxonJonbranding", "Rayxona", str(db), str(dialer))
    assert is_new is True
    assert intro

    conn = sqlite3.connect(db)
    kv = dict(conn.execute("SELECT key, value FROM kv_settings").fetchall())
    role = conn.execute("SELECT role FROM users WHERE user_id = 123456").fetchone()[0]
    conn.close()
    assert kv["STAFF_USER_ID_RAYXON"] == "123456"
    assert kv["STAFF_INTRO_SENT_123456"] == "1"
    assert role == "closer"

    # Second call: already introduced, no intro message again
    assert bind_and_welcome_staff(123456, "RayxonJonbranding", "Rayxona", str(db), str(dialer)) == (False, "")


def test_bind_and_welcome_staff_ignores_empty_user():
    assert bind_and_welcome_staff(0, "x", "y") == (False, "")
