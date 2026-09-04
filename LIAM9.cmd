@echo off
rem ===================================================================
rem  Liam Trader 9 - double-click this file. That's all.
rem
rem  ASCII ONLY on purpose. On 2026-09-04 the previous PowerShell
rem  launcher died on Hamid's laptop with a wall of parser errors:
rem  Windows PowerShell 5.1 reads a BOM-less script as ANSI, so every
rem  Persian character turned into garbage bytes and broke the parser.
rem  So: no PowerShell, no non-ASCII here. This file only finds Python
rem  and hands over to win_start.py, where UTF-8 is native.
rem ===================================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "ARG=%~1"
if "%ARG%"=="" set "ARG=run"

rem --- find a working Python -------------------------------------------
set "PY="
py -3 -c "print(1)" >nul 2>&1 && set "PY=py -3"
if not defined PY (python -c "print(1)" >nul 2>&1 && set "PY=python")
if not defined PY (
  echo.
  echo   Python is not installed on this Windows.
  echo.
  echo   Open PowerShell ^(NOT as administrator^) and paste this line:
  echo.
  echo       winget install -e --id Python.Python.3.12
  echo.
  echo   Then close this window and double-click LIAM9.cmd again.
  echo.
  pause
  exit /b 1
)

rem --- one-time environment --------------------------------------------
if not exist ".venv\Scripts\python.exe" (
  echo   Creating Python environment ^(first run only, about a minute^)...
  %PY% -m venv .venv
)
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" set "VPY=python"

"%VPY%" -c "import requests,matplotlib,arabic_reshaper,bidi,yaml" >nul 2>&1
if errorlevel 1 (
  echo   Installing libraries ^(first run only, a few minutes^)...
  "%VPY%" -m pip install -q --upgrade pip
  "%VPY%" -m pip install -q -r requirements-ci.txt
)

rem --- hand over: all logic and all Persian text live in Python ---------
"%VPY%" -X utf8 "claude-liam-signal\python\win_start.py" %ARG%

echo.
echo   Service stopped. Double-click LIAM9.cmd to start it again.
pause
