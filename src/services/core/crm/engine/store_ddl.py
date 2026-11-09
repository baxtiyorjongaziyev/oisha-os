"""Oisha CRM — Maʼlumotlar bazasi DDL sxemalari va dastlabki sozlash."""
from __future__ import annotations

import sqlite3


INIT_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS crm_pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    is_main INTEGER DEFAULT 0,
    is_archive INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    color TEXT DEFAULT '#4c8bf7',
    sort_order INTEGER DEFAULT 0,
    is_won INTEGER DEFAULT 0,
    is_lost INTEGER DEFAULT 0,
    FOREIGN KEY (pipeline_id) REFERENCES crm_pipelines(id)
);

CREATE TABLE IF NOT EXISTS crm_companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    industry TEXT,
    phone TEXT,
    email TEXT,
    website TEXT,
    inn TEXT,
    address TEXT,
    custom_fields_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crm_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    email TEXT,
    position TEXT,
    telegram_username TEXT,
    custom_fields_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES crm_companies(id)
);

CREATE TABLE IF NOT EXISTS crm_deals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pipeline_id INTEGER NOT NULL,
    stage_id INTEGER NOT NULL,
    price REAL DEFAULT 0.0,
    responsible_user_id INTEGER,
    responsible_name TEXT DEFAULT 'Shahnoza Abdijabborova',
    contact_id INTEGER,
    company_id INTEGER,
    phone TEXT,
    email TEXT,
    source TEXT DEFAULT 'Veb-sayt',
    tags_json TEXT DEFAULT '[]',
    custom_fields_json TEXT DEFAULT '{}',
    is_active INTEGER DEFAULT 1,
    next_task_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES crm_pipelines(id),
    FOREIGN KEY (stage_id) REFERENCES crm_stages(id)
);

CREATE TABLE IF NOT EXISTS crm_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    task_type TEXT DEFAULT 'Qoʻngʻiroq qilish',
    responsible_name TEXT DEFAULT 'Shahnoza Abdijabborova',
    due_at TEXT NOT NULL,
    is_completed INTEGER DEFAULT 0,
    result_text TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deal_id) REFERENCES crm_deals(id)
);

CREATE TABLE IF NOT EXISTS crm_timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    deal_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    author TEXT NOT NULL,
    text TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (deal_id) REFERENCES crm_deals(id)
);

CREATE INDEX IF NOT EXISTS idx_deals_pipe_stage ON crm_deals(pipeline_id, stage_id);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON crm_tasks(is_completed, due_at);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON crm_contacts(phone);
"""

DEFAULT_STAGES = [
    ("Saralanmaganlar", "inbox", "#94a3b8", 1, 0, 0),
    ("Birlamchi aloqa", "initial_contact", "#38bdf8", 2, 0, 0),
    ("Ehtiyoj aniqlash (SPIN)", "spin_discovery", "#3b82f6", 3, 0, 0),
    ("Taklif yuborildi", "proposal_sent", "#8b5cf6", 4, 0, 0),
    ("Strategik uchrashuv", "meeting_scheduled", "#eab308", 5, 0, 0),
    ("Shartnoma va toʻlov", "contract_signing", "#f97316", 6, 0, 0),
    ("Muvaffaqiyatli yopildi", "won", "#22c55e", 7, 1, 0),
    ("Rad etildi", "lost", "#ef4444", 8, 0, 1),
]


def init_database_schema(conn: sqlite3.Connection) -> None:
    """CRM jadvallari va indekslarini yaratish."""
    conn.executescript(INIT_TABLES_SQL)
    conn.commit()


def seed_default_pipeline(conn: sqlite3.Connection) -> None:
    """Dastlabki standart savdo voronkasi va bosqichlarini kiritish."""
    cnt = conn.execute("SELECT COUNT(*) FROM crm_pipelines").fetchone()[0]
    if cnt > 0:
        return

    cur = conn.execute(
        "INSERT INTO crm_pipelines (name, slug, is_main) VALUES (?, ?, 1)",
        ("Sotuv Boʻlimi", "sales_main"),
    )
    pipe_id = cur.lastrowid
    for st_name, st_slug, color, order, won, lost in DEFAULT_STAGES:
        conn.execute(
            """
            INSERT INTO crm_stages (pipeline_id, name, slug, color, sort_order, is_won, is_lost)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (pipe_id, st_name, st_slug, color, order, won, lost),
        )
    conn.commit()
