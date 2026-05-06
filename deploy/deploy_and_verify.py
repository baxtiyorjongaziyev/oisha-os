import paramiko
import os

hostname = '109.199.100.137'
username = 'root'
password = '#8tV9Hsm0aMqapdb'
_deploy_base = os.environ.get('VPS_DEPLOY_PATH', '/root/telegram_bot')
remote_path = f'{_deploy_base}/userbot.py'
local_path = 'userbot.py'

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password)
    
    # Upload necessary files
    files_to_upload = ['userbot.py', 'config.py', 'database.py', 'gsheets.py', 'training_data.txt']
    sftp = ssh.open_sftp()
    
    # Root files
    for f in files_to_upload:
        sftp.put(f, f'{_deploy_base}/{f}')
        print(f"[OK] {f} uploaded.")
    
    # Webapp folder
    try:
        ssh.exec_command(f'mkdir -p {_deploy_base}/webapp')
        webapp_files = os.listdir('webapp')
        for f in webapp_files:
            sftp.put(f'webapp/{f}', f'{_deploy_base}/webapp/{f}')
            print(f"[OK] webapp/{f} uploaded.")
    except Exception as e:
        print(f"[ERROR] Webapp upload failed: {e}")
        
    sftp.close()
    
    # Rebuild and Restart
    commands = [
        f'cd {_deploy_base} && docker compose down',
        f'cd {_deploy_base} && docker compose up -d --build --force-recreate'
    ]
    for cmd in commands:
        stdin, stdout, stderr = ssh.exec_command(cmd)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print(f"[OK] Executed: {cmd}")
        else:
            print(f"[ERROR] Command failed ({exit_status}): {cmd}")
            print(stderr.read().decode())
            
    # Check if applied
    stdin, stdout, stderr = ssh.exec_command("docker exec telegram_business_bot grep 'allowed_tags =' /app/userbot.py")
    result = stdout.read().decode()
    if 'allowed_tags =' in result:
        print("[VERIFIED] New code is running inside container.")
    else:
        print("[WARNING] New code NOT found inside container!")
        print(result)
        
    ssh.close()
except Exception as e:
    print(f"[FATAL ERROR] {e}")
