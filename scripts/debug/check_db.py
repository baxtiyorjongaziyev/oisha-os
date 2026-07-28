"""Server DB ni tekshirish va is_lead_forwarded ni reset qilish skripti."""
import paramiko

hostname = os.environ.get('SSH_HOST', '109.199.100.137')
username = os.environ.get('SSH_USER', 'root')
password = os.environ.get('SSH_PASSWORD', '')

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
    ssh.connect(hostname, username=username, password=password)

    # 1. DB dagi barcha foydalanuvchilarni ko'rish
    print("=== DB: USERS ===")
    cmd1 = """docker exec telegram_business_bot python3 -c "
import sqlite3
conn = sqlite3.connect('/app/bot_database.db')
rows = conn.execute('SELECT user_id, first_name, phone, is_lead_forwarded FROM users').fetchall()
for r in rows:
    print(r)
conn.close()
" """
    stdin, stdout, stderr = ssh.exec_command(cmd1)  # nosec B601
    print(stdout.read().decode())
    print(stderr.read().decode())

    # 2. is_lead_forwarded = 0 ga reset qilish (barcha foydalanuvchilar uchun)
    print("=== RESET: is_lead_forwarded = 0 ===")
    cmd2 = """docker exec telegram_business_bot python3 -c "
import sqlite3
conn = sqlite3.connect('/app/bot_database.db')
conn.execute('UPDATE users SET is_lead_forwarded = 0')
conn.commit()
print('RESET OK: barcha foydalanuvchilar uchun is_lead_forwarded=0 qilindi')
conn.close()
" """
    stdin2, stdout2, stderr2 = ssh.exec_command(cmd2)  # nosec B601
    print(stdout2.read().decode())
    print(stderr2.read().decode())

    # 3. So'nggi loglar
    print("=== RECENT LOGS (last 5 min) ===")
    stdin3, stdout3, stderr3 = ssh.exec_command('docker logs telegram_business_bot --since 300s 2>&1 | tail -50')  # nosec B601
    print(stdout3.read().decode())

    ssh.close()
except Exception as e:
    print(f"[ERROR] {e}")
