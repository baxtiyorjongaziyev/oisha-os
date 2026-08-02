import paramiko
import sys

def check_gc_status(password):
    host = os.environ.get('VPS_HOST', '104.197.19.4')
    user = os.environ.get('VPS_USER', 'baxtiyorjongaziyev')
    
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.set_missing_host_key_policy(paramiko.RejectPolicy())
    
    try:
        print(f"Connecting to Google Cloud VM at {host}...")
        ssh.connect(host, username=user, password=password, timeout=10)
        print("Connected!")
        
        print("Checking for python processes...")
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep userbot.py | grep -v grep")  # nosec B601
        output = stdout.read().decode()
        if output:
            print("Bot is running!")
            print(output)
        else:
            print("Bot is NOT running via python directly.")
            
        print("Checking for docker containers...")
        stdin, stdout, stderr = ssh.exec_command("docker ps -a")  # nosec B601
        print(stdout.read().decode())
        
        print("Checking ~/telegram_bot directory...")
        stdin, stdout, stderr = ssh.exec_command("ls -la ~/telegram_bot")  # nosec B601
        print(stdout.read().decode())

    except Exception as e:
        print(f"FAILED to connect: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('VPS_PASSWORD', '')
    check_gc_status(pwd)
