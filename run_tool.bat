@echo off
echo ==========================================
echo   AMS2 XML Backup Tool
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in your PATH.
    echo.
    echo Please install Python 3.8 or newer from:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo Python found! Launching AMS2 XML Backup Tool...
echo.
python "%~dp0AMS2_XML_Backup_Tool.py"

pause
