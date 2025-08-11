@echo off
REM Gmail CrewAI App Monitor Script for Windows

echo Starting Gmail CrewAI App Monitor...
echo Logs will be saved to: app_monitor.log
echo Press Ctrl+C to stop monitoring
echo.

REM Start the app and redirect output
set PORT=%PORT%
if "%PORT%"=="" set PORT=8505
echo Starting Streamlit app on port %PORT%...
start /B cmd /c "streamlit run streamlit_app.py --server.port %PORT% 2>&1 | tee app_monitor.log"

REM Give it time to start
timeout /t 3 /nobreak > nul

echo.
echo App is running. Monitoring for errors...
echo Check app_monitor.log for output
echo.

REM Monitor the log file for errors
:monitor_loop
timeout /t 2 /nobreak > nul
findstr /I "error exception failed traceback critical" app_monitor.log > app_errors.log
goto monitor_loop