import paramiko
import os

def check_progress():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')
        
        print('=== PROCESS STATUS ===')
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep bulk_learning.py | grep -v grep')
        print(stdout.read().decode())
        
        print('=== LOGS (TAIL) ===')
        stdin, stdout, stderr = ssh.exec_command('tail -n 20 /home/baxtiyorjongaziyev/telegram_bot/bulk_learning.log')
        print(stdout.read().decode())
        
        print('=== LEARNED FACTS COUNT ===')
        # Use single quotes for the whole command to avoid shell expansion of *
        stdin, stdout, stderr = ssh.exec_command("sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db 'SELECT COUNT(*) FROM learned_facts;'")
        print(f"Total entries: {stdout.read().decode().strip()}")
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_progress()
