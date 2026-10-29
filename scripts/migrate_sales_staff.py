# scripts/migrate_sales_staff.py
"""Migration: create `sales_staff` table and copy existing staff from
`crm_seller_accounts` (if any) to the new table.
Used by the new dynamic Sales Staff Copilot implementation.
"""
import sqlite3
from pathlib import Path

# Path is relative to repository root
DB_PATH = Path(__file__).parents[2] / "data" / "crm_dialer.db"

def run() -> None:
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    # 1️⃣ Create new table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_staff (
            slug TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tg TEXT NOT NULL,
            bound INTEGER DEFAULT 0
        )
        """
    )
    # 2️⃣ Copy existing rows from `crm_seller_accounts`
    cur.execute("SELECT slug, name, tg FROM crm_seller_accounts")
    rows = cur.fetchall()
    cur.executemany(
        "INSERT OR IGNORE INTO sales_staff (slug, name, tg) VALUES (?, ?, ?)",
        rows,
    )
    con.commit()
    con.close()
    print(f"Migration completed – {len(rows)} staff rows copied.")

if __name__ == "__main__":
    run()
