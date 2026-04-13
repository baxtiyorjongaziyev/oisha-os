import paramiko

def fetch_bot_log():
    host = '104.197.19.4'
    user = 'baxtiyorjongaziyev'
    password = 'parol1122'
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, username=user, password=password)
        stdin, stdout, stderr = ssh.exec_command("tail -n 50 /home/baxtiyorjongaziyev/telegram_bot/bot.log")
        print(stdout.read().decode('utf-8'))
    finally:
        ssh.close()

if __name__ == "__main__":
    fetch_bot_log()
