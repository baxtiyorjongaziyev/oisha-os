@echo off
echo "Starting ssh wrapper..." > C:\Users\baxti\playground\oisha-os\ssh_log.txt
echo "Args: %*" >> C:\Users\baxti\playground\oisha-os\ssh_log.txt
C:\WINDOWS\System32\OpenSSH\ssh.exe %* 2>> C:\Users\baxti\playground\oisha-os\ssh_log.txt
