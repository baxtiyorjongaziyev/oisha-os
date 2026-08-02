import paramiko
import os

hostname = os.environ.get('SSH_HOST', '109.199.100.137')
username = os.environ.get('SSH_USER', 'root')
password = os.environ.get('SSH_PASSWORD', '')
remote_path = '/root/telegram_bot/userbot.py'
local_path = 'userbot.py'

try:
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    ssh.connect(hostname, username=username, password=password)
    
    # Upload necessary files
    files_to_upload = ['userbot.py', 'config.py', 'database.py', 'gsheets.py', 'training_data.txt']
    sftp = ssh.open_sftp()
    
    # Root files
    for f in files_to_upload:
        sftp.put(f, f'/root/telegram_bot/{f}')
        print(f"[OK] {f} uploaded.")
    
    # Webapp folder
    try:
        ssh.exec_command('mkdir -p /root/telegram_bot/webapp')  # nosec B601
        webapp_files = os.listdir('webapp')
        for f in webapp_files:
            sftp.put(f'webapp/{f}', f'/root/telegram_bot/webapp/{f}')
            print(f"[OK] webapp/{f} uploaded.")
    except Exception as e:
        print(f"[ERROR] Webapp upload failed: {e}")
        
    sftp.close()
    
    # Rebuild and Restart
    commands = [
        'cd /root/telegram_bot && docker compose down',
        'cd /root/telegram_bot && docker compose up -d --build --force-recreate'
    ]
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)  # nosec B601
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print(f"[OK] Executed: {cmd}")
        else:
            print(f"[ERROR] Command failed ({exit_status}): {cmd}")
            print(stderr.read().decode())
            
    # Check if applied
    stdin, stdout, stderr = ssh.exec_command("docker exec telegram_business_bot grep 'allowed_tags =' /app/userbot.py")  # nosec B601
    result = stdout.read().decode()
    if 'allowed_tags =' in result:
        print("[VERIFIED] New code is running inside container.")
    else:
        print("[WARNING] New code NOT found inside container!")
        print(result)
        
    ssh.close()
except Exception as e:
    print(f"[FATAL ERROR] {e}")
