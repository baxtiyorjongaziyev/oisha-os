import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

print('Checking cert.pem...')
print(run('find /home/baxtiyorjongaziyev/.cloudflared -name "cert.pem" 2>/dev/null'))
ssh.close()
