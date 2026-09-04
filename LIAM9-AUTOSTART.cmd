@echo off
rem Liam Trader 9 - start automatically at every Windows logon.
rem Run once. To undo:  schtasks /Delete /TN LiamTrader9 /F
cd /d "%~dp0"
call "%~dp0LIAM9.cmd" boot
