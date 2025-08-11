#!/bin/bash

# Gmail CrewAI App Monitor Script
# This script runs the app and monitors for errors

echo "🚀 Starting Gmail CrewAI App Monitor..."
echo "📝 Logs will be saved to: app_monitor.log"
echo "🛑 Press Ctrl+C to stop monitoring"
echo ""

# Set up log file
LOG_FILE="app_monitor.log"
ERROR_LOG="app_errors.log"

# Function to extract errors
monitor_errors() {
    tail -f "$LOG_FILE" | while read line; do
        # Check for error patterns
        if echo "$line" | grep -iE "error|exception|failed|traceback|critical" > /dev/null; then
            echo "[ERROR DETECTED] $line" | tee -a "$ERROR_LOG"
            echo "$line" >> "$ERROR_LOG"
        fi
        
        # Also display warnings
        if echo "$line" | grep -iE "warning|warn" > /dev/null; then
            echo "[WARNING] $line"
        fi
    done
}

# Start the app and monitor
PORT=${PORT:-8505}
echo "Starting Streamlit app on port $PORT..."
streamlit run streamlit_app.py --server.port $PORT 2>&1 | tee "$LOG_FILE" &
APP_PID=$!

# Give it a moment to start
sleep 3

# Start error monitoring in background
monitor_errors &
MONITOR_PID=$!

# Wait for user to stop
echo ""
echo "App is running. Monitoring for errors..."
echo "Check $ERROR_LOG for captured errors"
echo ""
read -p "Press Enter to stop monitoring..."

# Cleanup
kill $MONITOR_PID 2>/dev/null
kill $APP_PID 2>/dev/null

echo ""
echo "✅ Monitoring stopped"
echo "📊 Summary:"
if [ -f "$ERROR_LOG" ]; then
    ERROR_COUNT=$(wc -l < "$ERROR_LOG")
    echo "   Errors captured: $ERROR_COUNT"
else
    echo "   No errors detected"
fi