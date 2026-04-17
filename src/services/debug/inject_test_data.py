
import paramiko
import datetime

def inject():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        vps_dir = '/home/baxtiyorjongaziyev/telegram_bot'
        
        now_str = datetime.datetime.now().isoformat()
        # Escaping quotes for shell echo
        msg = "Test: Salom, bizga brending strategiyasi va logotip kerak. Narxlarni ayta olasizmi?"
        sql = f"INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (12345678, '{msg}', 0, '{now_str}');"
        
        # Use heredoc for safety
        cmd = f"cat <<EOF > {vps_dir}/test_msg.sql\n{sql}\nEOF"
        ssh.exec_command(cmd)
        
        # Run SQL
        ssh.exec_command(f'cd {vps_dir} && sqlite3 bot_database.db < test_msg.sql')
        print('Test data injected into VPS.')
        
        # Run Report
        stdin, stdout, stderr = ssh.exec_command(f'cd {vps_dir} && ./venv/bin/python3 proactive_worker.py --job report')
        print('--- REPORT OUTPUT ---')
        print(stdout.read().decode())
        print('--- ERRORS ---')
        print(stderr.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    inject()
