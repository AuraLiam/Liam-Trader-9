@echo off
rem لیام تریدر ۹ — روی همین فایل دوبار کلیک کن. همین.
rem اولین بار محیط را می‌سازد (~۱ دقیقه)، بعدش مستقیم بالا می‌آید.
cd /d "%~dp0"
title لیام تریدر ۹
powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0service\liam9.ps1" %*
