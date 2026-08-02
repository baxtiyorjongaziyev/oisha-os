import paramiko
import os

def check_all_dbs():
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    try:
        ssh.connect(os.environ.get('VPS_HOST', '104.197.19.4'), username=os.environ.get('VPS_USER', 'baxtiyorjongaziyev'), password=os.environ.get('VPS_PASSWORD', ''), timeout=30)
        
        # 1. Find all .db files
        print("--- ALL DB FILES ON VPS ---")
        stdin, stdout, stderr = ssh.exec_command('find /home/baxtiyorjongaziyev/telegram_bot/ -name "*.db" -ls')  # nosec B601
        print(stdout.read().decode())
        
        # 2. Check bot_database.db users
        print("--- bot_database.db USERS ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, first_name, role FROM users;"')  # nosec B601
        print(stdout.read().decode())
        
        # 3. Check bot_memory.db users if it exists
        print("--- bot_memory.db USERS ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_memory.db "SELECT * FROM users;" 2>/dev/null || echo "bot_memory.db not found or no users table"')  # nosec B601
        print(stdout.read().decode())
        
        # 4. Check for any /register messages in logs
        print("--- /REGISTER IN LOGS ---")
        stdin, stdout, stderr = ssh.exec_command('grep -i "/register" /home/baxtiyorjongaziyev/telegram_bot/bot.log')  # nosec B601
        print(stdout.read().decode())
        
        # 5. Check journal for recent interactions
        print("--- RECENT JOURNAL (LAST 30) ---")
        stdin, stdout, stderr = ssh.exec_command('journalctl --user -u userbot -n 30')  # nosec B601
        print(stdout.read().decode())

        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_all_dbs()
