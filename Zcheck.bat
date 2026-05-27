@echo off
title Zcheck - email OSINT
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
set PYTHONIOENCODING=utf-8

if not exist ".venv\Scripts\zcheck.exe" (
    echo [Zcheck] First run - setting up venv...
    python -m venv .venv
    if errorlevel 1 (
        echo [Zcheck] ERROR creating venv. Is Python on PATH?
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 (
        echo [Zcheck] ERROR pip install failed.
        pause
        exit /b 1
    )
)

".venv\Scripts\zcheck.exe" %*

echo.
pause
