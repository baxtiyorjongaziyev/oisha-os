import subprocess

print("Running ssh...")
result = subprocess.run(
    [
        "C:\\WINDOWS\\System32\\OpenSSH\\ssh.exe",
        "-T",
        "-i",
        "C:/Users/baxti/.ssh/oracle_free_tier_ed25519",
        "-o",
        "StrictHostKeyChecking=no",
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=15",
        "ubuntu@163.192.10.104",
        "echo",
        "TEST_REMOTE"
    ],
    capture_output=True,
    text=True
)

print(f"RC: {result.returncode}")
print(f"STDOUT:\n---{result.stdout}---")
print(f"STDERR:\n---{result.stderr}---")
