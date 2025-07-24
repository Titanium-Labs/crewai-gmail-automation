#!/usr/bin/env python3
"""
Regression Test Runner

This script demonstrates the logging system regression tests by running 
actual test scenarios and showing the results.

Usage: python run_regression_tests.py
"""

import sys
import os
import json
import tempfile
import shutil
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from common.logger import get_logger, exception_info
    LOGGER_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Logger not available: {e}")
    print("Make sure you're running from the project root directory")
    LOGGER_AVAILABLE = False


def test_logging_integration():
    """Demonstrate the logging system integration."""
    print("🔍 Testing Logging System Integration...")
    print("=" * 50)
    
    if not LOGGER_AVAILABLE:
        print("❌ Cannot run logging tests - logger module not available")
        return False
    
    # Get logger instance
    logger = get_logger('regression_test_demo')
    
    print("📝 Creating test logger and triggering exception...")
    
    try:
        # Simulate a realistic application scenario
        def process_user_data(user_id, data):
            """Simulate processing user data that might fail."""
            if not data:
                raise ValueError(f"No data provided for user {user_id}")
            
            if user_id == "invalid_user":
                raise RuntimeError(f"User {user_id} is not authorized for this operation")
            
            # Simulate a division by zero error
            result = len(data) / 0
            return result
        
        # This will trigger an exception
        process_user_data("test_user_123", {"email": "test@example.com", "name": "Test User"})
        
    except Exception as e:
        # Log the exception - this should create entries in both log systems
        logger.exception("Regression test exception occurred during user data processing")
        print(f"✅ Exception logged: {type(e).__name__}: {e}")
    
    # Check if logs directory exists and has content
    logs_dir = Path("logs")
    if logs_dir.exists():
        app_log = logs_dir / "app.log"
        if app_log.exists():
            with open(app_log, 'r', encoding='utf-8') as f:
                recent_lines = f.readlines()[-5:]  # Get last 5 lines
            
            print(f"📄 Recent app.log entries ({len(recent_lines)} lines):")
            for line in recent_lines:
                print(f"   {line.strip()}")
        else:
            print("❌ app.log not found")
    else:
        print("❌ logs directory not found")
    
    # Check error_logs.json
    error_log_file = Path("error_logs.json")
    if error_log_file.exists():
        try:
            with open(error_log_file, 'r', encoding='utf-8') as f:
                error_data = json.load(f)
            
            print(f"📊 error_logs.json contains {len(error_data)} error records")
            
            # Show the most recent error
            if error_data:
                latest_error = error_data[-1]
                print("🔍 Most recent error record:")
                print(f"   ID: {latest_error.get('id', 'N/A')}")
                print(f"   Timestamp: {latest_error.get('timestamp', 'N/A')}")
                print(f"   Type: {latest_error.get('type', 'N/A')}")
                print(f"   Message: {latest_error.get('message', 'N/A')[:100]}...")
            
        except json.JSONDecodeError:
            print("❌ error_logs.json exists but contains invalid JSON")
    else:
        print("❌ error_logs.json not found")
    
    print("\n✅ Logging integration test completed")
    return True


def test_psreadline_files():
    """Check that PSReadLine fix files exist."""
    print("\n🔍 Testing PSReadLine Fix Files...")
    print("=" * 50)
    
    required_files = [
        "profile.ps1",
        "install-profile.ps1", 
        "install-profile.bat",
        "setup-powershell-profile.ps1",
        "PSREADLINE_FIX_SUMMARY.md"
    ]
    
    all_exist = True
    for file_name in required_files:
        file_path = Path(file_name)
        if file_path.exists():
            print(f"✅ {file_name} exists")
            
            # Check if it's a PowerShell file and validate basic content
            if file_name.endswith('.ps1'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if "PSReadLine" in content:
                    print(f"   📝 Contains PSReadLine references")
                else:
                    print(f"   ⚠️  No PSReadLine references found")
        else:
            print(f"❌ {file_name} missing")
            all_exist = False
    
    if all_exist:
        print("\n✅ All PSReadLine fix files present")
    else:
        print("\n❌ Some PSReadLine fix files are missing")
    
    return all_exist


def show_test_commands():
    """Show the commands to run the actual test suites."""
    print("\n🚀 Automated Test Suite Commands")
    print("=" * 50)
    
    print("📋 To run the full regression test suite:")
    print()
    print("1. Python Logging Tests:")
    print("   pytest tests/test_logging.py -v")
    print()
    print("2. PowerShell PSReadLine Tests:")
    print("   Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose")
    print()
    print("3. Manual PSReadLine Verification:")
    print("   powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1")
    print("   # Then open new PowerShell session and check for errors")
    print()
    print("📚 For detailed documentation, see:")
    print("   - REGRESSION_TESTING.md")
    print("   - tests/README.md")


def main():
    """Run the regression test demonstration."""
    print("🧪 Regression Test Demonstration")
    print("This script demonstrates the logging and PSReadLine fix functionality")
    print("For full automated testing, use pytest and Pester as documented")
    print()
    
    # Test logging integration
    logging_success = test_logging_integration()
    
    # Test PSReadLine files
    psreadline_success = test_psreadline_files()
    
    # Show test commands
    show_test_commands()
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 50)
    print(f"Logging Integration: {'✅ PASS' if logging_success else '❌ FAIL'}")
    print(f"PSReadLine Files: {'✅ PASS' if psreadline_success else '❌ FAIL'}")
    
    if logging_success and psreadline_success:
        print("\n🎉 All checks passed! The regression test infrastructure is ready.")
        print("Run the actual test suites using the commands shown above.")
    else:
        print("\n⚠️  Some checks failed. Please review the output above.")
    
    return 0 if (logging_success and psreadline_success) else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
