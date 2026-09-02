# سرویس سایهٔ محلی لیام تریدر ۹ — ویندوز (لپ‌تاپ حمید، استارلینک).
# بدون تلگرام، بدون اجرای زنده؛ خروجی فقط signals\shadow\. قانون ۰۲.
#
# نصب یک‌بار:   py -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements-ci.txt
# اجرا:         powershell -ExecutionPolicy Bypass -File service\run.ps1
# آزمایش نصب:   py -m hamid.shadow_service --once   (از داخل claude-liam-signal\python)
Set-Location (Join-Path $PSScriptRoot "..")
if (Test-Path ".\.venv\Scripts\Activate.ps1") { . ".\.venv\Scripts\Activate.ps1" }
if (-not $env:LIAM9_CANDLES) { $env:LIAM9_CANDLES = "perp" }
$env:LIVE_EXECUTION = "false"
Remove-Item Env:TELEGRAM_BOT_TOKEN -ErrorAction SilentlyContinue
Remove-Item Env:TELEGRAM_CHAT_ID -ErrorAction SilentlyContinue
$interval = if ($env:LIAM9_SHADOW_INTERVAL) { $env:LIAM9_SHADOW_INTERVAL } else { "300" }
$symbols  = if ($env:LIAM9_SHADOW_SYMBOLS)  { $env:LIAM9_SHADOW_SYMBOLS }  else { "200" }
Set-Location "claude-liam-signal\python"
while ($true) {
  Write-Host ("[{0:u}] سرویس سایه بالا می‌آید" -f (Get-Date).ToUniversalTime())
  py -m hamid.shadow_service --interval $interval --symbols $symbols
  Write-Host ("[{0:u}] فرایند مرد (کد {1}) — ۱۰ ثانیه بعد دوباره" -f (Get-Date).ToUniversalTime(), $LASTEXITCODE)
  Start-Sleep -Seconds 10
}
