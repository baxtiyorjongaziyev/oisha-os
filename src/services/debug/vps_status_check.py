import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('109.199.100.137', username='root', password='#8tV9Hsm0aMqapdb')

print('--- SYSTEMCTL STATUS ---')
stdin, stdout, stderr = ssh.exec_command('systemctl list-units --type=service | grep bot')
print(stdout.read().decode())

print('--- FIND RECENT SESSION FILES ---')
# Check files modified in the last 60 minutes
stdin, stdout, stderr = ssh.exec_command('find /root -name "*.session" -mmin -60')
print(stdout.read().decode())

print('--- CHECKING LOG FILES SIZE ---')
stdin, stdout, stderr = ssh.exec_command('ls -sh /root/telegram_bot/bot.log')
print(stdout.read().decode())

ssh.close()
