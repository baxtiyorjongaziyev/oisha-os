
import paramiko
import datetime

def inject():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        vps_dir = '/home/baxtiyorjongaziyev/telegram_bot'
        
        # VPS time was 15:40. Let's use 14:40.
        vps_time_str = "2026-03-19T14:40:00"
        msg = "REAL TEST: Bizga JonBranding bilan yangi loyiha boshlash niyatimiz bor. PM bilan bog'lab bera olasizmi?"
        sql = f"INSERT INTO message_logs (user_id, message_text, is_ai_reply, created_at) VALUES (888777, '{msg}', 0, '{vps_time_str}');"
        
        cmd = f"cat <<EOF > {vps_dir}/test_msg_v2.sql\n{sql}\nEOF"
        ssh.exec_command(cmd)
        
        # Run SQL
        ssh.exec_command(f'cd {vps_dir} && sqlite3 bot_database.db < test_msg_v2.sql')
        print(f"Test data injected with VPS-compatible time: {vps_time_str}")
        
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
