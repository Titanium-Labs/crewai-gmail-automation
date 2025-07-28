# Gmail CrewAI App Monitor Script for PowerShell

Write-Host "🚀 Starting Gmail CrewAI App Monitor..." -ForegroundColor Green
Write-Host "📝 Logs will be saved to: app_monitor.log" -ForegroundColor Yellow
Write-Host "🛑 Press Ctrl+C to stop monitoring" -ForegroundColor Red
Write-Host ""

# Start the Streamlit app
$logFile = "app_monitor.log"
$errorLog = "app_errors.log"

Write-Host "Starting Streamlit app on port 8505..." -ForegroundColor Cyan
$appProcess = Start-Process -FilePath "streamlit" -ArgumentList "run", "streamlit_app.py", "--server.port", "8505" -RedirectStandardOutput $logFile -RedirectStandardError $logFile -PassThru -NoNewWindow

# Monitor for errors
Write-Host "Monitoring for errors..." -ForegroundColor Yellow
Write-Host ""

# Continuous monitoring
while ($true) {
    Start-Sleep -Seconds 2
    
    if (Test-Path $logFile) {
        # Search for errors
        $errors = Select-String -Path $logFile -Pattern "error|exception|failed|traceback|critical" -SimpleMatch
        
        if ($errors) {
            $errors | ForEach-Object {
                Write-Host "[ERROR DETECTED] $_" -ForegroundColor Red
                $_ | Out-File -Append $errorLog
            }
        }
        
        # Also check for warnings
        $warnings = Select-String -Path $logFile -Pattern "warning|warn" -SimpleMatch
        if ($warnings) {
            $warnings | ForEach-Object {
                Write-Host "[WARNING] $_" -ForegroundColor Yellow
            }
        }
    }
}