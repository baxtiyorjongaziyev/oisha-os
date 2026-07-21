import sys
path = '/home/ubuntu/oisha-os/src/api_server.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('url="/client"', 'url="/dashboard"')
with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
