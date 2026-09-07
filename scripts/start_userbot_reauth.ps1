$ErrorActionPreference = 'Stop'

$sshExe = 'C:\Windows\System32\OpenSSH\ssh.exe'
$sshKey = 'C:\Users\baxti\.ssh\oracle_free_tier_ed25519'
$remoteHost = 'ubuntu@163.192.10.104'
$sshArgs = @(
    '-q', '-T', '-i', $sshKey,
    '-o', 'IdentitiesOnly=yes',
    '-o', 'BatchMode=yes',
    '-o', 'ConnectTimeout=15',
    '-o', 'StrictHostKeyChecking=no',
    $remoteHost
)

function Invoke-Oracle([string]$Command) {
    & $sshExe @sshArgs $Command
    if ($LASTEXITCODE -ne 0) {
        throw "Oracle SSH buyrug'i bajarilmadi (exit $LASTEXITCODE)."
    }
}

function Send-SecretFile([string]$RemotePath, [string]$Value) {
    $Value | & $sshExe @sshArgs "umask 077; cat > '$RemotePath'"
    if ($LASTEXITCODE -ne 0) {
        throw "Maxfiy qiymat Oracle'ga yuborilmadi."
    }
}

function Get-AuthStatus {
    $raw = & $sshExe @sshArgs "cd /home/ubuntu/oisha-os && test -f data/userbot_auth_status.json && cat data/userbot_auth_status.json || printf '{\"state\":\"starting\"}'"
    if ($LASTEXITCODE -ne 0) { return @{ state = 'ssh_error' } }
    try { return ($raw | ConvertFrom-Json) } catch { return @{ state = 'starting' } }
}

Write-Host ''
Write-Host 'Telegram USERBOT xavfsiz tiklash — Oracle VM' -ForegroundColor Cyan
Write-Host 'Kod va 2FA faqat shu oynada kiritiladi; ekranga chiqarilmaydi.'
Write-Host ''

try {
    $phone = Read-Host 'Telegram telefon raqamingizni xalqaro formatda kiriting (+998...)'
    if ([string]::IsNullOrWhiteSpace($phone)) { throw "Telefon raqami bo'sh." }

    Invoke-Oracle "sudo systemctl kill -s SIGKILL oisha-os.service; sudo systemctl stop oisha-os.service || true"
    $phone.Trim() | & $sshExe @sshArgs "read -r TELEGRAM_PHONE; export TELEGRAM_PHONE; cd /home/ubuntu/oisha-os; rm -f data/userbot_auth_code.txt data/userbot_auth_password.txt data/userbot_auth_status.json; nohup env USERBOT_AUTH_WAIT_SECONDS=900 ./venv/bin/python3 scripts/prod/auth_userbot_on_oracle.py > data/userbot_auth.log 2>&1 < /dev/null &"
    $phone = $null
    if ($LASTEXITCODE -ne 0) { throw 'Telegram auth jarayoni ishga tushmadi.' }

    $codeSent = $false
    $passwordSent = $false
    $deadline = (Get-Date).AddMinutes(16)

    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 700
        $status = Get-AuthStatus

        switch ($status.state) {
            'waiting_code' {
                if (-not $codeSent) {
                    $code = Read-Host 'Telegram ilovasiga kelgan yangi login kodini kiriting'
                    if ([string]::IsNullOrWhiteSpace($code)) { throw "Login kodi bo'sh." }
                    Send-SecretFile '/home/ubuntu/oisha-os/data/userbot_auth_code.txt' $code.Trim()
                    $code = $null
                    $codeSent = $true
                    Write-Host 'Kod yuborildi, Telegram javobi tekshirilmoqda...'
                }
            }
            'waiting_password' {
                if (-not $passwordSent) {
                    $secure = Read-Host 'Telegram 2FA parolini kiriting' -AsSecureString
                    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
                    try {
                        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
                        Send-SecretFile '/home/ubuntu/oisha-os/data/userbot_auth_password.txt' $plain
                    } finally {
                        if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
                        $plain = $null
                        $secure = $null
                    }
                    $passwordSent = $true
                    Write-Host '2FA yuborildi, sessiya tekshirilmoqda...'
                }
            }
            'authorized' {
                Invoke-Oracle "sudo systemctl start oisha-os"
                Start-Sleep -Seconds 8
                $health = & $sshExe @sshArgs "curl -sS --max-time 15 http://127.0.0.1:8080/readyz/"
                Write-Host ''
                Write-Host 'Telegram login muvaffaqiyatli. Oisha qayta ishga tushdi.' -ForegroundColor Green
                Write-Host $health
                Read-Host 'Oynani yopish uchun Enter bosing'
                exit 0
            }
            'failed' {
                Invoke-Oracle "sudo systemctl start oisha-os"
                throw "Telegram login bajarilmadi: $($status.reason)"
            }
        }
    }

    Invoke-Oracle "sudo systemctl start oisha-os"
    throw 'Login uchun ajratilgan vaqt tugadi.'
} catch {
    try { Invoke-Oracle "sudo systemctl start oisha-os" } catch {}
    Write-Host ''
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Hech qanday kod yoki parol saqlanmadi.'
    Read-Host 'Oynani yopish uchun Enter bosing'
    exit 1
}
