# لیام تریدر ۹ — یک فرمان، برای همیشه.  (ویندوز)
#
# حمید (۴ سپتامبر): «به ساده‌ترین شکل ممکن اجرا شود و بی‌وقفه پشتیبان من باشی.»
#
#   powershell -ExecutionPolicy Bypass -File service\liam9.ps1
#   powershell -ExecutionPolicy Bypass -File service\liam9.ps1 doctor
#   powershell -ExecutionPolicy Bypass -File service\liam9.ps1 boot
#   powershell -ExecutionPolicy Bypass -File service\liam9.ps1 stop
#
# ساده‌ترین راه: روی «لیام۹.cmd» در ریشهٔ پوشه دوبار کلیک کن.
param([string]$Cmd = "run")
$ErrorActionPreference = "Continue"

$Root  = Split-Path -Parent $PSScriptRoot
$PyDir = Join-Path $Root "claude-liam-signal\python"
$Out   = Join-Path $Root "signals\liam9d.out"
Set-Location $Root

function Get-Py {
  foreach ($c in @("py -3.12", "py -3.11", "py -3", "python3", "python")) {
    $exe, $arg = $c.Split(" ", 2)
    if (Get-Command $exe -ErrorAction SilentlyContinue) { return $c }
  }
  return $null
}

function Setup {
  $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPy)) {
    $py = Get-Py
    if (-not $py) { Write-Host "پایتون پیدا نشد. از python.org نصب کن." -Foreground Red; exit 1 }
    Write-Host "→ ساخت محیط پایتون (یک بار، ~۱ دقیقه)"
    $exe, $arg = $py.Split(" ", 2)
    if ($arg) { & $exe $arg -m venv (Join-Path $Root ".venv") }
    else      { & $exe      -m venv (Join-Path $Root ".venv") }
  }
  & $venvPy -c "import requests, matplotlib, arabic_reshaper, bidi, yaml" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "→ نصب کتابخانه‌ها (یک بار)"
    & $venvPy -m pip -q install --upgrade pip
    & $venvPy -m pip -q install -r (Join-Path $Root "requirements-ci.txt")
  }
  return $venvPy
}

switch ($Cmd) {
  "doctor" {
    $vp = Setup; Set-Location $PyDir
    & $vp -m hamid.liam9d --doctor
  }

  "stop" {
    Get-Process python, pythonw -ErrorAction SilentlyContinue |
      Where-Object { $_.Path -like "*\.venv\*" } | Stop-Process -Force
    Write-Host "خاموش شد."
  }

  "boot" {
    # با هر بار روشن‌شدن ویندوز و ورود حمید، خودش بالا بیاید.
    $act = New-ScheduledTaskAction -Execute "powershell.exe" `
      -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $trg = New-ScheduledTaskTrigger -AtLogOn
    $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
      -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName "LiamTrader9" -Action $act -Trigger $trg `
      -Settings $set -Force | Out-Null
    Write-Host "✓ با هر بار روشن‌شدن ویندوز، خودش بالا می‌آید."
  }

  default {
    $vp = Setup
    Write-Host "لیام تریدر ۹ — سرویس محلی"
    Write-Host "پنل: http://127.0.0.1:9009"
    Write-Host "توقف: Ctrl+C  ·  لاگ: $Out`n"
    # حلقهٔ بی‌وقفه — هر مرگی، ۱۰ ثانیه بعد دوباره بالا
    $n = 0
    while ($true) {
      $n++
      Set-Location $PyDir
      & $vp -m hamid.liam9d 2>&1 | Tee-Object -FilePath $Out -Append
      $msg = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] سرویس ایستاد (بار $n) — ۱۰ ثانیه دیگر دوباره"
      Write-Host $msg; Add-Content -Path $Out -Value $msg
      Start-Sleep -Seconds 10
    }
  }
}
