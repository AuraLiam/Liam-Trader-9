# لیام تریدر ۹ — یک دوبار کلیک، برای همیشه.  (ویندوز)
#
# حمید (۴ سپتامبر): «به ساده‌ترین شکل ممکن اجرا شود و بی‌وقفه پشتیبان من
# باشی» و «git pull بزنم یعنی چی؟ لپ‌تاپ من ویندوز هست دقیق بگو چیکار کنم.»
#
# جوابِ عملی: حمید هیچ فرمانی تایپ نمی‌کند. روی «لیام۹.cmd» دوبار کلیک
# می‌کند و این فایل بقیه‌اش را خودش انجام می‌دهد — پیدا کردن پایتون،
# گرفتن آخرین نسخهٔ کد، نصب کتابخانه‌ها، ساختن فایل توکن، معاینه، و
# روشن‌کردن سرویس و پنل.
#
#   لیام۹.cmd            روشن کن (بار اول خودش نصب می‌کند)
#   لیام۹.cmd doctor     فقط بگو این ماشین آماده است یا نه
#   لیام۹.cmd boot       با هر بار روشن‌شدن ویندوز، خودش بالا بیاید
#   لیام۹.cmd stop       خاموش کن
param([string]$Cmd = "run")
$ErrorActionPreference = "Continue"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root  = Split-Path -Parent $PSScriptRoot
$PyDir = Join-Path $Root "claude-liam-signal\python"
$Out   = Join-Path $Root "signals\liam9d.out"
$EnvF  = Join-Path $Root "live.env"
$Port  = if ($env:LIAM9D_PORT) { $env:LIAM9D_PORT } else { "9009" }
Set-Location $Root

function Say($t, $c = "Gray") { Write-Host $t -ForegroundColor $c }

# ── ۱. پایتون ──────────────────────────────────────────────────────────
function Find-Py {
  foreach ($c in @(@("py", "-3"), @("python3", $null), @("python", $null))) {
    $exe = $c[0]
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
      # «python» روی ویندوز گاهی میان‌بُرِ فروشگاه مایکروسافت است که فقط
      # فروشگاه را باز می‌کند. پس واقعاً اجرا می‌شود، نه فقط پیدا.
      $v = if ($c[1]) { & $exe $c[1] -c "print(1)" 2>$null } else { & $exe -c "print(1)" 2>$null }
      if ($v -eq "1") { return $c }
    }
  }
  return $null
}

function Ensure-Py {
  $py = Find-Py
  if (-not $py) {
    Say "`n  پایتون روی این ویندوز نصب نیست." Red
    Say "  ساده‌ترین راه — این خط را در همین پنجره کپی کن و Enter بزن:`n"
    Say "      winget install -e --id Python.Python.3.12" Yellow
    Say "`n  یا از python.org نسخهٔ ویندوز را بگیر و موقع نصب حتماً"
    Say "  تیکِ «Add python.exe to PATH» را بزن."
    Say "  بعد این پنجره را ببند و دوباره روی «لیام۹» دوبار کلیک کن.`n"
    Read-Host "  Enter بزن تا بسته شود"
    exit 1
  }
  $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPy)) {
    Say "  → ساخت محیط پایتون (فقط بار اول، حدود یک دقیقه)"
    if ($py[1]) { & $py[0] $py[1] -m venv (Join-Path $Root ".venv") }
    else        { & $py[0]        -m venv (Join-Path $Root ".venv") }
  }
  if (-not (Test-Path $venvPy)) { $venvPy = $py[0] }   # نشد؟ با پایتون سامانه
  & $venvPy -c "import requests, matplotlib, arabic_reshaper, bidi, yaml" 2>$null
  if ($LASTEXITCODE -ne 0) {
    Say "  → نصب کتابخانه‌ها (فقط بار اول، چند دقیقه)"
    & $venvPy -m pip -q install --upgrade pip 2>&1 | Out-Null
    & $venvPy -m pip -q install -r (Join-Path $Root "requirements-ci.txt")
  }
  return $venvPy
}

# ── ۲. آخرین نسخهٔ کد ──────────────────────────────────────────────────
#
# این همان «git pull» است، ولی حمید تایپش نمی‌کند. اگر گیت نصب نباشد،
# سرویس با همین نسخه کار می‌کند — نبودِ به‌روزرسانی دلیل نمی‌شود پنل
# بالا نیاید. و این تنها جای گیت است: **بیرونِ** مسیر سیگنال.
function Update-Code {
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Say "  (گیت نصب نیست — با همین نسخه کار می‌کنم. برای گرفتن نسخه‌های"
    Say "   بعدی: winget install -e --id Git.Git)"
    return
  }
  if (-not (Test-Path (Join-Path $Root ".git"))) { return }
  Say "  → گرفتن آخرین نسخه از گیت‌هاب"
  git -C $Root fetch origin main -q 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) { Say "    اینترنت نداد — با همین نسخه ادامه." ; return }

  # فقط **کد** به‌روز می‌شود، نه دفترها.
  #
  # `git pull` معمولی این‌جا غلط است و همان کلاسِ عیبی را برمی‌گرداند که
  # حمید از آن شاکی بود: سرویس محلی هر دقیقه در signals/ و brain/
  # می‌نویسد، پس pull هر بار می‌خواهد آن نوشته‌ها را rebase کند و دیر یا
  # زود تصادم می‌دهد — و آن لحظه، حمید پشت یک پیام conflict گیر می‌کند
  # که هیچ ربطی به ترید ندارد.
  #
  # به‌جایش فقط مسیرهای کد از origin برداشته می‌شوند. دفترهای محلی اصلاً
  # لمس نمی‌شوند، پس تصادم **ساختاراً** ممکن نیست، نه اینکه بعید باشد.
  $before = git -C $Root rev-parse origin/main 2>$null
  $head   = git -C $Root rev-parse HEAD 2>$null
  $code = @("claude-liam-signal", "service", ".github", "config", "schemas",
            "prompts", "docs", ".claude", "requirements-ci.txt", "scripts",
            "index.html", "sw.js", "CLAUDE.md", "راهنمای-ویندوز.md",
            "LIAM9.cmd", "LIAM9-DOCTOR.cmd", "LIAM9-AUTOSTART.cmd")
  $have = $code | Where-Object { git -C $Root cat-file -e "origin/main:$_" 2>$null; $LASTEXITCODE -eq 0 }
  if ($have) {
    git -C $Root checkout origin/main -- @have 2>&1 | Out-Null
    git -C $Root reset -q -- @have 2>&1 | Out-Null   # از استیج در بیاور، فایل بماند
  }
  if ($before -ne $head) { Say "    کد به‌روز شد (دفترهای محلی دست‌نخورده)." Green }
  else { Say "    از قبل به‌روز بود." }
}

# ── ۳. توکن تلگرام ─────────────────────────────────────────────────────
function Ensure-Env {
  if (Test-Path $EnvF) { return $true }
  @"
# توکن ربات تلگرام لیام تریدر ۹ — این فایل هرگز به گیت‌هاب نمی‌رود.
# دو خط زیر را پر کن، ذخیره کن (Ctrl+S) و پنجرهٔ Notepad را ببند.
#
# TELEGRAM_BOT_TOKEN را از @BotFather بگیر (همان توکن @LiamTrader9_Bot).
# TELEGRAM_CHAT_ID شناسهٔ عددی چت خودت است.

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
"@ | Set-Content -Path $EnvF -Encoding UTF8
  Say "`n  فایل توکن ساخته شد و الان باز می‌شود." Yellow
  Say "  دو خط آخرش را پر کن، Ctrl+S بزن و پنجره را ببند.`n"
  Start-Process notepad.exe $EnvF -Wait
  $txt = Get-Content $EnvF -Raw
  if ($txt -match "TELEGRAM_BOT_TOKEN=\s*\S") { return $true }
  Say "  توکن خالی ماند — سرویس بالا می‌آید و تحلیل می‌کند،" Yellow
  Say "  ولی تا وقتی توکن نگذاری چیزی به تلگرام نمی‌فرستد." Yellow
  return $false
}

# ── فرمان‌ها ───────────────────────────────────────────────────────────
switch ($Cmd) {
  "doctor" {
    $vp = Ensure-Py; Set-Location $PyDir
    & $vp -m hamid.liam9d --doctor
    Set-Location $Root
    Read-Host "`n  Enter بزن تا بسته شود"
  }

  "stop" {
    Get-Process python, pythonw -ErrorAction SilentlyContinue |
      Where-Object { $_.Path -like "*$Root*" } | Stop-Process -Force
    Say "خاموش شد." Green
  }

  "boot" {
    $act = New-ScheduledTaskAction -Execute "powershell.exe" `
      -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    $trg = New-ScheduledTaskTrigger -AtLogOn
    $set = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
      -DontStopIfGoingOnBatteries -RestartCount 999 `
      -RestartInterval (New-TimeSpan -Minutes 1) `
      -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName "LiamTrader9" -Action $act -Trigger $trg `
      -Settings $set -Force | Out-Null
    Say "✓ از این به بعد با هر بار روشن‌شدن ویندوز، خودش بالا می‌آید." Green
    Read-Host "`n  Enter بزن تا بسته شود"
  }

  default {
    Say "`n  لیام تریدر ۹ — سرویس محلی`n" Cyan
    Update-Code
    $vp = Ensure-Py
    Ensure-Env | Out-Null

    Say "`n  معاینهٔ ماشین:" Cyan
    Set-Location $PyDir
    & $vp -m hamid.liam9d --doctor
    Set-Location $Root

    Say "`n  پنل: http://127.0.0.1:$Port" Green
    Say "  توقف: این پنجره را ببند  ·  لاگ: $Out`n"
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:$Port"

    # حلقهٔ بی‌وقفه — هر مرگی، ده ثانیه بعد دوباره بالا.
    $n = 0
    while ($true) {
      $n++
      Set-Location $PyDir
      & $vp -m hamid.liam9d 2>&1 | Tee-Object -FilePath $Out -Append
      Set-Location $Root
      $msg = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] سرویس ایستاد (بار $n) — ده ثانیه دیگر دوباره"
      Say $msg Yellow
      Add-Content -Path $Out -Value $msg
      Start-Sleep -Seconds 10
    }
  }
}
