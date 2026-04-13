import paramiko
import os
import time

def final_audit():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to VPS...")
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. Check ALL database files and their modification times
        print("--- DATABASE FILES AUDIT ---")
        stdin, stdout, stderr = ssh.exec_command('ls -lt /home/baxtiyorjongaziyev/telegram_bot/*.db')
        print(stdout.read().decode())
        
        # 2. Check users in the primary database
        print("--- USERS DATA ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, first_name, username, role FROM users;"')
        print(stdout.read().decode())
        
        # 3. Check for specific register commands in message_logs
        print("--- REGISTRATION COMMANDS LOG ---")
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db "SELECT user_id, message_text, created_at FROM message_logs WHERE message_text LIKE \'%/register%\' ORDER BY id DESC LIMIT 20;"')
        print(stdout.read().decode())
        
        # 4. Check bot.log for any errors during registration
        print("--- RECENT BOT ERRORS ---")
        stdin, stdout, stderr = ssh.exec_command('grep -i "error" /home/baxtiyorjongaziyev/telegram_bot/bot.log | tail -n 20')
        print(stdout.read().decode())
        
        # 5. Check if bot is actually running right now
        print("--- SERVICE STATUS ---")
        stdin, stdout, stderr = ssh.exec_command('systemctl --user status userbot | grep Active')
        print(stdout.read().decode())

        ssh.close()
        print("Final audit finished.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_audit()
