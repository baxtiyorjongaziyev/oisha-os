import sqlite3

conn = sqlite3.connect('/home/ubuntu/oisha-os/data/crm_dialer.db')
c = conn.cursor()
c.execute('SELECT count(*) FROM dialer_leads')
print('Total dialer_leads:', c.fetchone()[0])
c.execute('SELECT count(*) FROM dialer_companies')
print('Total companies:', c.fetchone()[0])
c.execute('SELECT count(*) FROM dialer_contacts')
print('Total contacts:', c.fetchone()[0])
