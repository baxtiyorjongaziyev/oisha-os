@echo off
echo [%date% %time%] Wrapper started >> C:\Users\baxti\playground\oisha-os\ssh_wrapper.log
echo Arguments: %* >> C:\Users\baxti\playground\oisha-os\ssh_wrapper.log
C:\WINDOWS\System32\OpenSSH\ssh.exe %* 2>> C:\Users\baxti\playground\oisha-os\ssh_wrapper.log
echo [%date% %time%] Exit code: %errorlevel% >> C:\Users\baxti\playground\oisha-os\ssh_wrapper.log
