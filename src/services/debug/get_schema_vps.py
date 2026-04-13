
import paramiko

def get_schema():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        # Run sqlite3 directly and read output
        stdin, stdout, stderr = ssh.exec_command('sqlite3 /home/baxtiyorjongaziyev/telegram_bot/bot_database.db ".schema message_logs"')
        print(stdout.read().decode())
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    get_schema()
