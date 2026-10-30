import sys
import subprocess

with open(r'C:\Users\baxti\playground\oisha-os\ssh_wrapper.log', 'a') as f:
    f.write("Wrapper started\n")
    f.write(f"Args: {sys.argv}\n")

try:
    proc = subprocess.Popen(
        [r'C:\WINDOWS\System32\OpenSSH\ssh.exe'] + sys.argv[1:],
        stdin=sys.stdin.fileno(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Capture stdout and stderr
    out, err = proc.communicate()
    
    with open(r'C:\Users\baxti\playground\oisha-os\ssh_wrapper.log', 'a') as f:
        f.write(f"Exit code: {proc.returncode}\n")
        if out:
            f.write(f"STDOUT: {out.decode('utf-8', errors='ignore')}\n")
            sys.stdout.buffer.write(out)
            sys.stdout.flush()
        if err:
            f.write(f"STDERR: {err.decode('utf-8', errors='ignore')}\n")
            sys.stderr.buffer.write(err)
            sys.stderr.flush()
            
except Exception as e:
    with open(r'C:\Users\baxti\playground\oisha-os\ssh_wrapper.log', 'a') as f:
        f.write(f"Error: {e}\n")
