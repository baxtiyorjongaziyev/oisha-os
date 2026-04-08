import paramiko
import sys

def check_gc_status(password):
    host = '104.197.19.4'
    user = 'baxtiyorjongaziyev'
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Connecting to Google Cloud VM at {host}...")
        ssh.connect(host, username=user, password=password, timeout=10)
        print("Connected!")
        
        print("Checking for python processes...")
        stdin, stdout, stderr = ssh.exec_command("ps aux | grep userbot.py | grep -v grep")
        output = stdout.read().decode()
        if output:
            print("Bot is running!")
            print(output)
        else:
            print("Bot is NOT running via python directly.")
            
        print("Checking for docker containers...")
        stdin, stdout, stderr = ssh.exec_command("docker ps -a")
        print(stdout.read().decode())
        
        print("Checking ~/telegram_bot directory...")
        stdin, stdout, stderr = ssh.exec_command("ls -la ~/telegram_bot")
        print(stdout.read().decode())

    except Exception as e:
        print(f"FAILED to connect: {e}")
    finally:
        ssh.close()

if __name__ == "__main__":
    pwd = sys.argv[1] if len(sys.argv) > 1 else "#8tV9Hsm0aMqapdb"
    check_gc_status(pwd)
