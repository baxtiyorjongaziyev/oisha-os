import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('109.199.100.137', username='root', password='#8tV9Hsm0aMqapdb')

# Container ni to'xtatish
print('Stopping container...')
stdin, stdout, stderr = ssh.exec_command('docker stop telegram_business_bot 2>/dev/null; docker rm telegram_business_bot 2>/dev/null; echo done')
print(stdout.read().decode())

# Yangi docker-compose.yml yaratish
print('Creating new docker-compose.yml on VPS...')
new_compose = """version: "3.8"

services:
  bot:
    build: .
    container_name: telegram_business_bot
    restart: always
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    env_file:
      - .env
    volumes:
      - .:/app:ro
      - bot_sessions:/app/sessions
      - bot_data:/app/data
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  bot_sessions:
  bot_data:
"""

sftp = ssh.open_sftp()
with sftp.file('/tmp/docker-compose.yml', 'w') as f:
    f.write(new_compose)
ssh.exec_command('mv /tmp/docker-compose.yml /root/telegram_bot/docker-compose.yml')

print('docker-compose.yml updated!')

# Botni qayta ishga tushirish
print('Starting bot...')
ssh.exec_command('cd /root/telegram_bot && docker-compose up -d --build')

ssh.close()
print('Done!')