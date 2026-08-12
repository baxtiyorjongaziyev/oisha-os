import sys
import subprocess

with open(r'C:\Users\baxti\playground\oisha-os\ssh_wrapper.log', 'a') as f:
    f.write("Wrapper started\n")
    f.write(f"Args: {sys.argv}\n")

try:
    proc = subprocess.Popen(
        [r'C:\WINDOWS\System32\OpenSSH\ssh.exe'] + sys.argv[1:],
        stdin=sys.stdin.fileno(),
        stdout=sys.stdout.fileno(),
        stderr=sys.stderr.fileno()
    )
    proc.wait()
    with open(r'C:\Users\baxti\playground\oisha-os\ssh_wrapper.log', 'a') as f:
        f.write(f"Exit code: {proc.returncode}\n")
except Exception as e:
    with open(r'C:\Users\baxti\playground\oisha-os\ssh_wrapper.log', 'a') as f:
        f.write(f"Error: {e}\n")
