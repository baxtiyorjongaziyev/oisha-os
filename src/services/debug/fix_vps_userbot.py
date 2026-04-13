import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('109.199.100.137', username='root', password='#8tV9Hsm0aMqapdb')

# Container ni to'xtatish
print('Stopping container...')
ssh.exec_command('docker stop telegram_business_bot && docker rm telegram_business_bot')

# VPS da userbot.py ni to'g'rilash
print('Fixing userbot.py on VPS...')

# Fix script ni VPS ga yuborish
fix_script_content = """with open('/root/telegram_bot/userbot.py', 'r') as f:
    content = f.read()

old_line = 'client = TelegramClient("/tmp/bot_session", api_id=settings.API_ID, api_hash=settings.API_HASH).start(bot_token=BOT_TOKEN)'
new_lines = 'token_str = BOT_TOKEN.get_secret_value() if hasattr(BOT_TOKEN, "get_secret_value") else str(BOT_TOKEN)\\n    client = TelegramClient("/tmp/bot_session", api_id=settings.API_ID, api_hash=settings.API_HASH).start(bot_token=token_str)'

content = content.replace(old_line, new_lines)

with open('/root/telegram_bot/userbot.py', 'w') as f:
    f.write(content)
print('Fixed!')
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/fix_userbot.py', 'w') as f:
    f.write(fix_script_content)

# Fix script ni ishga tushirish
stdin, stdout, stderr = ssh.exec_command('python3 /tmp/fix_userbot.py')
print(stdout.read().decode())
print(stderr.read().decode())

# Yangi container ni ishga tushirish
print('Starting new container...')
ssh.exec_command('docker run -d --name telegram_business_bot --restart always --env-file /root/telegram_bot/.env -v /root/telegram_bot:/app -v /tmp:/tmp telegram_bot-bot python userbot.py')

ssh.close()
print('Done!')