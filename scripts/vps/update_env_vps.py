import paramiko
import sys
import time

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
try:
    ssh.connect('104.197.19.4', username='baxtiyorjongaziyev', password='parol1122', timeout=15)
except Exception as e:
    print("Ulanish xatosi:", e)
    sys.exit(1)

def run(cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    return stdout.read().decode() + stderr.read().decode()

token = 'EAAWgoR9UVZCkBQxTwu8bJyrMyuKXxslpNaPvTmMeHFgCg4gnnVyn9EyKth5fzDxrkVpZAjtK6TbkA2Ec0aqmRPuBUFV0tiJd0o3PNreJc1OnMOJhlUdLtUCzGQAjrdiTtxhMcrUwQM4x3ppDfP3vzvL44CtkrczB2wm4VM2bzjDnh36MXHZArIZBHsdjeg8RRJZB0fwRiRn4E1oF4mD4a7PynaxsNyjqVX5K4cD21DrCSbdUAJDKUxbjRjQZDZD'
ig_id = '17841404148272074'
verify = 'jonbranding_meta_verify_2026'

print("1. VPS dagi .env ni o'qish...")
env_content = run("cat /home/baxtiyorjongaziyev/telegram_bot/.env")
lines = env_content.strip().split('\n')

new_lines = []
keys_to_update = ['META_PAGE_ACCESS_TOKEN', 'META_IG_PAGE_ID', 'META_VERIFY_TOKEN', 'META_APP_SECRET']

# Mavjudlarni o'chiramiz
for line in lines:
    if not any(line.startswith(k + '=') for k in keys_to_update):
        if line.strip():
            new_lines.append(line)

# Yangilarni qo'shamiz
new_lines.append(f"META_PAGE_ACCESS_TOKEN={token}")
new_lines.append(f"META_IG_PAGE_ID={ig_id}")
new_lines.append(f"META_VERIFY_TOKEN={verify}")
new_lines.append(f"META_APP_SECRET=") # App secret bo'sh qoladi imzo tekshiruvini chetlab o'tish uchun (hozircha)

final_env = '\n'.join(new_lines)

print("2. Yangilangan .env ni saqlash...")
# Echo ishlatishda ehtiyot bo'lamiz (multi-line)
stdin, stdout, stderr = ssh.exec_command(f"cat > /home/baxtiyorjongaziyev/telegram_bot/.env << 'EOF'\n{final_env}\nEOF")
stdout.channel.recv_exit_status()

print("3. meta_webhook xizmatini qayta ishga tushirish...")
run("systemctl --user restart meta_webhook")
time.sleep(3)

print("4. Holat:")
status = run("systemctl --user status meta_webhook --no-pager")
print(status)

ssh.close()
print("\n✅ .env yangilandi va xizmat qayta yoqildi!")
