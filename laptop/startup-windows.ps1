# استارتاپ لپ‌تاپ — فقط پنج چیز (دستور حمید، ۲۸ اوت)
#
# «لپ‌تاپ روشن شد پنل من باید بیاد بالا، فقط: پنل/داشبورد لیام ۹،
#  AuraLiam Max، کلود، چت‌جی‌پی‌تی، وی‌اس‌کد. دیگر هیچ چیزی ران نشود.»
#
# این اسکریپت دو کار می‌کند:
#   ۱) میان‌برِ همان پنج مورد را در پوشهٔ Startup ویندوز می‌گذارد
#   ۲) بقیهٔ ورودی‌های استارتاپِ کاربر را **فهرست و غیرفعال** می‌کند
#      (پاک نمی‌کند — به backup منتقل می‌شود که برگشت‌پذیر باشد)
#
# اجرا (یک بار، PowerShell عادی — نیازی به Administrator نیست):
#   Set-ExecutionPolicy -Scope Process Bypass -Force
#   .\startup-windows.ps1            # فقط گزارش می‌دهد، چیزی عوض نمی‌کند
#   .\startup-windows.ps1 -Apply     # واقعاً اعمال می‌کند
#
# برگشت به حالت قبل:
#   .\startup-windows.ps1 -Restore

param([switch]$Apply, [switch]$Restore)

$ErrorActionPreference = "Stop"
$Startup = [Environment]::GetFolderPath("Startup")
$Backup  = Join-Path $Startup "_disabled-backup"
$RunKey  = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$RunBak  = "HKCU:\Software\Liam9\StartupBackup"

# آدرس پنل — همان جایی که سرو می‌شود
$PanelUrl = "https://auraliam.github.io/Liam-Trader-9/aura/"

# پنج موردِ مجاز. مسیرها اگر نبودند رد می‌شوند و گزارش داده می‌شود؛
# هیچ‌چیز حدس زده نمی‌شود.
$Wanted = @(
  @{ Name = "لیام تریدر ۹ (پنل)"; Kind = "url";  Target = $PanelUrl },
  @{ Name = "AuraLiam Max";       Kind = "app";  Candidates = @(
       "$env:LOCALAPPDATA\Programs\AuraLiamMax\AuraLiamMax.exe",
       "$env:LOCALAPPDATA\AuraLiamMax\AuraLiamMax.exe") },
  @{ Name = "Claude";             Kind = "app";  Candidates = @(
       "$env:LOCALAPPDATA\AnthropicClaude\claude.exe",
       "$env:LOCALAPPDATA\Programs\Claude\Claude.exe") },
  @{ Name = "ChatGPT";            Kind = "app";  Candidates = @(
       "$env:LOCALAPPDATA\Programs\ChatGPT\ChatGPT.exe",
       "$env:PROGRAMFILES\OpenAI\ChatGPT\ChatGPT.exe") },
  @{ Name = "VS Code";            Kind = "app";  Candidates = @(
       "$env:LOCALAPPDATA\Programs\Microsoft VS Code\Code.exe",
       "$env:PROGRAMFILES\Microsoft VS Code\Code.exe") }
)

function New-Shortcut($Path, $Target, $Args) {
  $sh = New-Object -ComObject WScript.Shell
  $lnk = $sh.CreateShortcut($Path)
  $lnk.TargetPath = $Target
  if ($Args) { $lnk.Arguments = $Args }
  $lnk.Save()
}

if ($Restore) {
  if (Test-Path $Backup) {
    Get-ChildItem $Backup | ForEach-Object {
      Move-Item $_.FullName (Join-Path $Startup $_.Name) -Force
      Write-Host "برگشت: $($_.Name)"
    }
  }
  if (Test-Path $RunBak) {
    (Get-Item $RunBak).Property | ForEach-Object {
      $v = (Get-ItemProperty $RunBak).$_
      Set-ItemProperty $RunKey -Name $_ -Value $v
      Write-Host "برگشت رجیستری: $_"
    }
  }
  Write-Host "`nاستارتاپ به حالت قبل برگشت." -ForegroundColor Green
  exit 0
}

Write-Host "`n=== وضعیت فعلی استارتاپ ===" -ForegroundColor Cyan
$existing = @(Get-ChildItem $Startup -File -ErrorAction SilentlyContinue |
              Where-Object { $_.Name -ne "desktop.ini" })
$runEntries = @()
if (Test-Path $RunKey) {
  $runEntries = (Get-Item $RunKey).Property
}
Write-Host "پوشهٔ Startup: $($existing.Count) مورد"
$existing | ForEach-Object { Write-Host "   • $($_.Name)" }
Write-Host "رجیستری Run: $($runEntries.Count) مورد"
$runEntries | ForEach-Object { Write-Host "   • $_" }

Write-Host "`n=== پنج موردِ مجاز ===" -ForegroundColor Cyan
$plan = @()
foreach ($w in $Wanted) {
  if ($w.Kind -eq "url") {
    $plan += @{ Name = $w.Name; Target = $w.Target; IsUrl = $true }
    Write-Host "   ✓ $($w.Name) → $($w.Target)"
  } else {
    $found = $w.Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($found) {
      $plan += @{ Name = $w.Name; Target = $found; IsUrl = $false }
      Write-Host "   ✓ $($w.Name) → $found"
    } else {
      Write-Host "   ✗ $($w.Name) — پیدا نشد؛ مسیرش را داخل اسکریپت اضافه کن" -ForegroundColor Yellow
    }
  }
}

if (-not $Apply) {
  Write-Host "`n(حالت گزارش — چیزی عوض نشد. برای اعمال: -Apply)" -ForegroundColor Yellow
  exit 0
}

# ۱) بقیه را غیرفعال کن — منتقل به backup، نه حذف
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
foreach ($f in $existing) {
  Move-Item $f.FullName (Join-Path $Backup $f.Name) -Force
  Write-Host "غیرفعال شد: $($f.Name)"
}
if ($runEntries.Count -gt 0) {
  New-Item -Path $RunBak -Force | Out-Null
  foreach ($name in $runEntries) {
    $val = (Get-ItemProperty $RunKey).$name
    Set-ItemProperty $RunBak -Name $name -Value $val
    Remove-ItemProperty $RunKey -Name $name
    Write-Host "غیرفعال شد (رجیستری): $name"
  }
}

# ۲) پنج موردِ مجاز را بگذار
foreach ($p in $plan) {
  $lnk = Join-Path $Startup ("Liam9 - " + $p.Name + ".lnk")
  if ($p.IsUrl) {
    # پنل در مرورگر پیش‌فرض، پنجرهٔ اپ‌مانند
    $edge = "$env:PROGRAMFILES(x86)\Microsoft\Edge\Application\msedge.exe"
    if (Test-Path $edge) { New-Shortcut $lnk $edge "--app=$($p.Target)" }
    else { New-Shortcut $lnk "explorer.exe" $p.Target }
  } else {
    New-Shortcut $lnk $p.Target $null
  }
  Write-Host "استارتاپ: $($p.Name)" -ForegroundColor Green
}

Write-Host "`nتمام. بعد از ری‌استارت فقط همین موارد بالا می‌آیند." -ForegroundColor Green
Write-Host "برگشت به قبل: .\startup-windows.ps1 -Restore"
