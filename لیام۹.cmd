@echo off
rem لیام تریدر ۹ — همان LIAM9.cmd است، فقط با اسم فارسی.
rem اگر این فایل درست باز نشد، از LIAM9.cmd استفاده کن.
chcp 65001 >nul
cd /d "%~dp0"
title لیام تریدر ۹
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service\liam9.ps1" run
echo.
echo  سرویس بسته شد. برای روشن‌کردن دوباره، همین فایل را دوبار کلیک کن.
pause
