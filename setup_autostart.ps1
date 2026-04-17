# Oisha-OS Auto-Start Setup Script
# This script creates a Windows Task Scheduler entry to start Oisha-OS on Login.

$TaskName = "OishaOS_AutoStart"
$ScriptDir = "C:\Users\baxti\playground\oisha-os"
$BatPath = "$ScriptDir\start_oisha.bat"

if (-not (Test-Path $BatPath)) {
    Write-Error "start_oisha.bat topilmadi: $BatPath"
    exit
}

$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $BatPath" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 365)

# Try to register the task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force
    Write-Host "✅ Muvaffaqiyatli: Oisha-OS endi kompyuterga kirganingizda avtomatik ishga tushadi."
    Write-Host "Vazifa nomi: $TaskName"
} catch {
    Write-Error "Vazifani yaratishda xatolik: $_"
}
