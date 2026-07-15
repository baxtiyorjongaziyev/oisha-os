import paramiko
import sys
host = "163.192.10.104"
username = "ubuntu"
key_filename = r"C:\Users\baxti\.ssh\oracle_free_tier_ed25519"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(hostname=host, username=username, key_filename=key_filename)
stdin, stdout, stderr = client.exec_command("echo hello")
print(stdout.read().decode())
print(stderr.read().decode())
