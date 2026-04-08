
$taskName = "Oisha-OS_AutoStart"
$pythonW = "C:\Users\baxti\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\pythonw.exe"
$scriptPath = "c:\Users\baxti\.gemini\antigravity\playground\oisha-os\userbot.py"

# Action to run pythonw.exe (no window)
$action = New-ScheduledTaskAction -Execute $pythonW -Argument $scriptPath -WorkingDirectory "c:\Users\baxti\.gemini\antigravity\playground\oisha-os"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -Hidden

# Check if task already exists
if (Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

Register-ScheduledTask -Action $action -Trigger $trigger -TaskName $taskName -Settings $settings -Description "Oisha-OS Enterprise AI (Hidden Auto-Start)"
Write-Host "✅ Oisha-OS Hidden Auto-Start Task Registered successfully!"
