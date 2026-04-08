import paramiko
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122')

token = 'EAAWgoR9UVZCkBQxTwu8bJyrMyuKXxslpNaPvTmMeHFgCg4gnnVyn9EyKth5fzDxrkVpZAjtK6TbkA2Ec0aqmRPuBUFV0tiJd0o3PNreJc1OnMOJhlUdLtUCzGQAjrdiTtxhMcrUwQM4x3ppDfP3vzvL44CtkrczB2wm4VM2bzjDnh36MXHZArIZBHsdjeg8RRJZB0fwRiRn4E1oF4mD4a7PynaxsNyjqVX5K4cD21DrCSbdUAJDKUxbjRjQZDZD'
ig_id = '17841404148272074'
verify = 'jonbranding_meta_verify_2026'

print("Cleaning up .env...")
ssh.exec_command('sed -i "/META_/d" /home/baxtiyorjongaziyev/telegram_bot/.env')
time.sleep(1)

print("Writing new keys...")
ssh.exec_command(f'echo "META_PAGE_ACCESS_TOKEN={token}" >> /home/baxtiyorjongaziyev/telegram_bot/.env')
ssh.exec_command(f'echo "META_IG_PAGE_ID={ig_id}" >> /home/baxtiyorjongaziyev/telegram_bot/.env')
ssh.exec_command(f'echo "META_VERIFY_TOKEN={verify}" >> /home/baxtiyorjongaziyev/telegram_bot/.env')
ssh.exec_command(f'echo "META_APP_SECRET=" >> /home/baxtiyorjongaziyev/telegram_bot/.env')
time.sleep(1)

print("Restarting services...")
ssh.exec_command('systemctl --user daemon-reload')
ssh.exec_command('systemctl --user restart meta_webhook')
ssh.exec_command('systemctl --user restart cloudflared')
ssh.exec_command('systemctl --user restart userbot')
time.sleep(5)

stdin, stdout, stderr = ssh.exec_command('systemctl --user status meta_webhook --no-pager | grep Active')
print("Status:", stdout.read().decode())

ssh.close()
print("Done!")
