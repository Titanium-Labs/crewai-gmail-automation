#!/usr/bin/env python
"""
Run the Streamlit app with proper configuration to avoid file watcher errors.
"""

import os
import sys
import subprocess

def main():
    # Set environment variables to reduce file watching issues
    os.environ['STREAMLIT_SERVER_FILE_WATCHER_TYPE'] = 'none'
    
    # Disable Python bytecode generation to prevent __pycache__ issues
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    
    # Run Streamlit with the app
    cmd = [
        sys.executable, '-m', 'streamlit', 'run',
        'streamlit_app.py',
        '--server.port', '8505',
        '--server.fileWatcherType', 'none',
        '--server.headless', 'true',
        '--browser.gatherUsageStats', 'false'
    ]
    
    print("🚀 Starting Gmail CrewAI App...")
    print("📝 File watching disabled to prevent cache errors")
    print("🌐 App will be available at http://localhost:8505")
    print("🛑 Press Ctrl+C to stop\n")
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
        sys.exit(0)

if __name__ == "__main__":
    main()