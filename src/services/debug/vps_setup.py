import paramiko
import os

def setup_vps():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')
        
        print('=== 📦 INSTALLING GOOGLE-GENAI ===')
        # Use --break-system-packages for GCP Debian/Ubuntu environments
        cmd_install = 'python3 -m pip install google-genai --break-system-packages'
        stdin, stdout, stderr = ssh.exec_command(cmd_install)
        print(stdout.read().decode())
        print(stderr.read().decode())
        
        print('=== ✅ VERIFYING INSTALLATION ===')
        # Use a simple print without exclamation mark to avoid shell issues
        cmd_verify = 'python3 -c "import google.genai; print(\'SUCCESS_IMPORT\')"'
        stdin, stdout, stderr = ssh.exec_command(cmd_verify)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        if 'SUCCESS_IMPORT' in out:
            print('Installation confirmed: google.genai is available.')
        else:
            print('Verification failed!')
            print(f'STDOUT: {out}')
            print(f'STDERR: {err}')
            
        ssh.close()
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    setup_vps()
