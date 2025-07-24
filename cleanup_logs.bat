@echo off
REM Log Cleanup Batch File for Windows
REM This script runs the Python log cleanup script and displays results

echo ============================================
echo Gmail Automation - Log Cleanup
echo ============================================
echo Starting log cleanup process...
echo.

REM Change to the script directory
cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and ensure it's accessible from command line
    pause
    exit /b 1
)

REM Check if cleanup script exists
if not exist "scripts\cleanup_logs.py" (
    echo ERROR: cleanup_logs.py script not found in scripts directory
    echo Make sure you're running this from the project root directory
    pause
    exit /b 1
)

REM Run the cleanup script
echo Running Python cleanup script...
python scripts\cleanup_logs.py

REM Check if the script completed successfully
if errorlevel 1 (
    echo.
    echo ERROR: Cleanup script failed with errors
    echo Check the output above for details
) else (
    echo.
    echo SUCCESS: Log cleanup completed successfully
)

echo.
echo ============================================
echo Cleanup process finished
echo ============================================

REM Check if cleanup log was created
if exist "cleanup_logs.log" (
    echo.
    echo Cleanup log created: cleanup_logs.log
    echo You can review this file for detailed cleanup information
)

echo.
pause
