import sqlite3

conn = sqlite3.connect('/home/ubuntu/oisha-os/data/crm_dialer.db')
c = conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('Tables in crm_dialer.db:', [r[0] for r in c.fetchall()])
