import paramiko
import os

def check_vps(host, user, password, remote_path, out_f):
    out_f.write(f"--- Checking VPS: {host} ---\n")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(host, username=user, password=password, timeout=15)
        out_f.write("Connected!\n")
        
        # Check .env
        cmd = f"cat {remote_path}/.env"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        env_content = stdout.read().decode()
        if env_content:
            out_f.write(f"Found .env content on {host}:\n")
            out_f.write(env_content)
            out_f.write("\n")
        else:
            out_f.write(f"No .env content found on {host} at {remote_path}\n")

        ssh.close()
    except Exception as e:
        out_f.write(f"Error connecting to {host}: {e}\n")

with open("vps_audit_results.txt", "w", encoding="utf-8") as f:
    # VPS 1
    check_vps("109.199.100.137", "root", "#8tV9Hsm0aMqapdb", "/root/telegram_bot", f)
    # VPS 2
    check_vps("104.197.19.4", "baxtiyorjongaziyev", "parol1122", "/home/baxtiyorjongaziyev/telegram_bot", f)

print("Audit complete. Results saved to vps_audit_results.txt")
