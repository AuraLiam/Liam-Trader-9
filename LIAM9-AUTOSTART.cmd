@echo off
rem همیشه‌روشن — بعد از این، با هر بار روشن‌شدن ویندوز خودش بالا می‌آید.
rem یک بار کافی است. برای لغو: در Task Scheduler ویندوز، LiamTrader9 را حذف کن.
chcp 65001 >nul
cd /d "%~dp0"
title لیام تریدر ۹ — همیشه روشن
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service\liam9.ps1" boot
