
import paramiko

def setup_cron():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=30)
        
        vps_dir = '/home/baxtiyorjongaziyev/telegram_bot'
        python_path = f'{vps_dir}/venv/bin/python3'
        script_path = f'{vps_dir}/proactive_worker.py'
        
        # 1. Get current crontab
        stdin, stdout, stderr = ssh.exec_command('crontab -l')
        current_cron = stdout.read().decode().strip()
        
        # 2. Define jobs
        briefing_job = f'0 9 * * * cd {vps_dir} && {python_path} {script_path} --job briefing >> {vps_dir}/proactive_worker.log 2>&1'
        report_job = f'0 21 * * * cd {vps_dir} && {python_path} {script_path} --job report >> {vps_dir}/proactive_worker.log 2>&1'
        
        new_jobs = [briefing_job, report_job]
        
        # 3. Add if not present
        updated_cron_lines = current_cron.split('\n') if current_cron else []
        for job in new_jobs:
            if not any(job in line for line in updated_cron_lines):
                updated_cron_lines.append(job)
        
        final_cron = '\n'.join(updated_cron_lines) + '\n'
        
        # 4. Apply new crontab
        print("Applying new crontab...")
        # Use a more robust way to write the multi-line string
        stdin, stdout, stderr = ssh.exec_command(f'echo "{final_cron}" > /tmp/new_cron && crontab /tmp/new_cron && rm /tmp/new_cron')
        
        print('Crontab updated!')
        
        # Verify
        stdin, stdout, stderr = ssh.exec_command('crontab -l')
        print('Current Crontab:')
        print(stdout.read().decode())
        
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    setup_cron()
