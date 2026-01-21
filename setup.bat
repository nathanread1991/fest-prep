@echo off
REM Festival Playlist Generator - Setup Script Launcher (Windows)
REM This script launches the Python setup script with proper error handling

echo 🎵 Festival Playlist Generator - Setup Launcher 🎵
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is required but not found.
    echo Please install Python 3.8+ and try again.
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
echo ✅ Python %python_version% detected
echo.

REM Run the setup script
echo 🚀 Starting interactive setup...
echo.
python setup.py

if errorlevel 1 (
    echo.
    echo ❌ Setup script encountered an error.
    pause
    exit /b 1
)

echo.
echo ✨ Setup script completed!
pause