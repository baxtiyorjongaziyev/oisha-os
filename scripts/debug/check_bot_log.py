import paramiko

def fetch_bot_log():
    host = os.environ.get('VPS_HOST', '104.197.19.4')
    user = os.environ.get('VPS_USER', 'baxtiyorjongaziyev')
    password = os.environ.get('VPS_PASSWORD', '')
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # nosec B507
    try:
        ssh.connect(host, username=user, password=password)
        stdin, stdout, stderr = ssh.exec_command("tail -n 50 /home/baxtiyorjongaziyev/telegram_bot/bot.log")  # nosec B601
        print(stdout.read().decode('utf-8'))
    finally:
        ssh.close()

if __name__ == "__main__":
    fetch_bot_log()
