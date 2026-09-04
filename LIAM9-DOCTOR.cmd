@echo off
rem معاینه — فقط می‌گوید این لپ‌تاپ آماده هست یا نه. چیزی را روشن نمی‌کند.
chcp 65001 >nul
cd /d "%~dp0"
title لیام تریدر ۹ — معاینه
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0service\liam9.ps1" doctor
