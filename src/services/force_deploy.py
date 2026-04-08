import paramiko
import os
import time

def deploy():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print("Connecting to VPS...")
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        # 1. Stop service
        print("Stopping userbot service...")
        ssh.exec_command('systemctl --user stop userbot')
        
        # 2. Kill any remaining processes
        print("Cleaning up python processes...")
        ssh.exec_command('pkill -9 -f userbot.py')
        time.sleep(2)
        
        # 3. Upload file
        local_file = r'C:\Users\baxti\.gemini\antigravity\scratch\telegram_bot\userbot.py'
        remote_file = '/home/baxtiyorjongaziyev/telegram_bot/userbot.py'
        print(f"Uploading {local_file}...")
        sftp = ssh.open_sftp()
        sftp.put(local_file, remote_file)
        sftp.close()
        
        # 4. Verify
        print("Verifying file content on VPS...")
        stdin, stdout, stderr = ssh.exec_command('tail -n 10 ' + remote_file)
        print("Tail on VPS:\n", stdout.read().decode())
        
        # 5. Start service
        print("Starting userbot service...")
        ssh.exec_command('systemctl --user start userbot')
        
        time.sleep(5)
        
        # 6. Check logs
        print("Checking logs...")
        stdin, stdout, stderr = ssh.exec_command('tail -n 20 /home/baxtiyorjongaziyev/telegram_bot/bot.log')
        print("Logs:\n", stdout.read().decode())
        
        ssh.close()
        print("Deployment finished successfully.")
    except Exception as e:
        print(f"Error during deployment: {e}")

if __name__ == "__main__":
    deploy()
