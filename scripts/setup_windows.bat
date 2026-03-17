@echo off
REM QGen RAG Setup Launcher for Windows
REM This script launches the cross-platform setup system

echo 🚀 QGen RAG Interactive Setup Launcher
echo =====================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.9 or higher from https://python.org
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo ✅ Python %PYTHON_VERSION% detected

REM Check if we're in the right directory
if not exist "scripts\interactive_setup.py" (
    echo ❌ interactive_setup.py not found in scripts directory
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

REM Run the cross-platform launcher
echo 🌐 Starting cross-platform setup launcher...
python launch_setup.py

if %errorlevel% neq 0 (
    echo.
    echo ❌ Setup failed!
    pause
    exit /b %errorlevel%
)

echo.
echo ✅ Setup completed successfully!
pause
