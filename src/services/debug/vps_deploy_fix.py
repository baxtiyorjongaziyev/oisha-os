
import paramiko
import os

def cleanup_vps():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to VPS...")
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # Paths
        db_path = '/home/baxtiyorjongaziyev/telegram_bot/bot_memory.db'
        
        # 1. Delete bad learned facts
        print("Cleaning up learned_facts...")
        sql_del_facts = "DELETE FROM learned_facts WHERE fact_value LIKE '%998777776360%' OR fact_value LIKE '%Aisha bilan suhbat%';"
        ssh.exec_command(f"sqlite3 {db_path} \"{sql_del_facts}\"")
        
        # 2. Delete bad message logs
        print("Cleaning up message_logs...")
        sql_del_msgs = "DELETE FROM message_logs WHERE message_text LIKE '%Aisha bilan suhbat%';"
        ssh.exec_command(f"sqlite3 {db_path} \"{sql_del_msgs}\"")
        
        # 3. Check for specific user issues
        print("Checking owner info...")
        # Baxtiyorjon aka's correct info is in training_data.txt (+998336450097)
        sql_fix_owner = "UPDATE users SET phone='+998336450097' WHERE role='owner' AND phone LIKE '%777776360%';"
        ssh.exec_command(f"sqlite3 {db_path} \"{sql_fix_owner}\"")
        
        # 4. Upload updated files
        print("Uploading updated files...")
        sftp = ssh.open_sftp()
        local_dir = r'C:\Users\baxti\.gemini\antigravity\scratch\telegram_bot'
        sftp.put(os.path.join(local_dir, 'userbot.py'), '/home/baxtiyorjongaziyev/telegram_bot/userbot.py')
        sftp.put(os.path.join(local_dir, 'config.py'), '/home/baxtiyorjongaziyev/telegram_bot/config.py')
        sftp.close()
        
        # 5. Restart bot
        print("Restarting bot...")
        ssh.exec_command('systemctl --user restart userbot')
        
        print("Cleanup and deployment successful!")
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    cleanup_vps()
