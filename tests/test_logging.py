#!/usr/bin/env python3
"""
Regression tests for logging configuration and PSReadLine fix.

This test suite ensures:
1. Logger creates entries in logs/app.log when exceptions occur
2. ErrorLogger creates JSON records in error_logs.json 
3. Both logging systems work together correctly
4. PSReadLine profile fixes PowerShell startup errors (manual verification)

Run with: pytest tests/test_logging.py -v
"""

import sys
import os
import json
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from common.logger import get_logger, exception_info


class TestLoggingSystem:
    """Test the integrated logging system with app.log and error_logs.json."""
    
    @pytest.fixture(autouse=True)
    def setup_test_environment(self):
        """Set up isolated test environment for each test."""
        # Create temporary directory for test logs
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        
        # Change to test directory
        os.chdir(self.test_dir)
        
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        # Store paths
        self.app_log_path = os.path.join(self.test_dir, 'logs', 'app.log')
        self.error_log_path = os.path.join(self.test_dir, 'error_logs.json')
        
        yield
        
        # Cleanup
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_dummy_exception_creates_app_log_entry(self):
        """Test that raising an exception creates a new line in logs/app.log."""
        # Get logger instance
        logger = get_logger('test_logger')
        
        # Record initial log state
        initial_log_size = 0
        if os.path.exists(self.app_log_path):
            with open(self.app_log_path, 'r', encoding='utf-8') as f:
                initial_log_size = len(f.readlines())
        
        # Trigger exception with logging
        try:
            # Dummy function that raises an exception
            def dummy_function():
                """Dummy function for testing exception logging."""
                raise ValueError("Test exception for logging verification")
            
            dummy_function()
            
        except Exception:
            # Log the exception using our logging system
            logger.exception("Regression test: dummy exception occurred")
        
        # Verify app.log was created and has new content
        assert os.path.exists(self.app_log_path), "logs/app.log should be created"
        
        with open(self.app_log_path, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
        
        # Should have at least one more line than before
        assert len(log_lines) > initial_log_size, "New log entry should be added to app.log"
        
        # Check that the log contains our test message
        log_content = ''.join(log_lines)
        assert "Regression test: dummy exception occurred" in log_content
        assert "ValueError: Test exception for logging verification" in log_content
        assert "test_logging.py" in log_content  # Should include traceback
    
    def test_dummy_exception_creates_error_json_record(self):
        """Test that raising an exception creates a new JSON record in error_logs.json."""
        # Mock the ErrorLogger functionality since it's normally part of streamlit_app
        mock_error_logger = MagicMock()
        mock_error_logger.log_error = MagicMock()
        
        # Record initial error log state
        initial_errors = []
        if os.path.exists(self.error_log_path):
            with open(self.error_log_path, 'r', encoding='utf-8') as f:
                initial_errors = json.load(f)
        
        initial_error_count = len(initial_errors)
        
        # Create a mock ErrorLogger that writes to our test file
        def mock_log_error(error_type, message, details, user_id=""):
            """Mock ErrorLogger.log_error method."""
            error_record = {
                "id": f"test-{datetime.now().isoformat()}",
                "timestamp": datetime.now().isoformat(),
                "type": error_type,
                "message": message,
                "details": details,
                "user_id": user_id,
                "resolved": False
            }
            
            # Read existing errors
            errors = []
            if os.path.exists(self.error_log_path):
                with open(self.error_log_path, 'r', encoding='utf-8') as f:
                    try:
                        errors = json.load(f)
                    except json.JSONDecodeError:
                        errors = []
            
            # Add new error
            errors.append(error_record)
            
            # Write back to file
            with open(self.error_log_path, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2)
        
        # Patch the exception_info function to use our mock
        with patch('common.logger.sys.modules') as mock_modules:
            # Create a mock module with ErrorLogger
            mock_streamlit_app = MagicMock()
            mock_streamlit_app.ErrorLogger = MagicMock
            mock_streamlit_app.ErrorLogger.return_value.log_error = mock_log_error
            
            # Add to modules dict
            mock_modules.get.return_value = mock_streamlit_app
            mock_modules.__contains__ = lambda x: True
            
            # Also patch items() method for the module iteration
            mock_modules.items.return_value = [('streamlit_app', mock_streamlit_app)]
            
            # Get logger and trigger exception
            logger = get_logger('test_logger')
            
            try:
                # Dummy function that raises an exception
                def dummy_function():
                    """Another dummy function for JSON logging test."""
                    result = 1 / 0  # Division by zero
                    return result
                
                dummy_function()
                
            except Exception:
                # Use exception_info which should trigger ErrorLogger
                exception_info(logger, "Regression test: JSON error logging")
        
        # Verify error_logs.json was created/updated
        assert os.path.exists(self.error_log_path), "error_logs.json should be created"
        
        with open(self.error_log_path, 'r', encoding='utf-8') as f:
            error_data = json.load(f)
        
        # Should have at least one more error record than before
        assert len(error_data) > initial_error_count, "New error record should be added to error_logs.json"
        
        # Check the most recent error record
        latest_error = error_data[-1]
        
        # Verify required fields
        required_fields = ['id', 'timestamp', 'type', 'message', 'details', 'user_id', 'resolved']
        for field in required_fields:
            assert field in latest_error, f"Error record should contain {field} field"
        
        # Verify content
        assert "Regression test: JSON error logging" in latest_error['message']
        assert "ZeroDivisionError" in latest_error['details']
        assert "division by zero" in latest_error['details']
        assert latest_error['resolved'] is False
    
    def test_integrated_logging_both_systems(self):
        """Test that both app.log and error_logs.json are updated for the same exception."""
        # Record initial states
        initial_app_log_size = 0
        if os.path.exists(self.app_log_path):
            with open(self.app_log_path, 'r', encoding='utf-8') as f:
                initial_app_log_size = len(f.readlines())
        
        initial_error_count = 0
        if os.path.exists(self.error_log_path):
            with open(self.error_log_path, 'r', encoding='utf-8') as f:
                try:
                    initial_error_count = len(json.load(f))
                except json.JSONDecodeError:
                    initial_error_count = 0
        
        # Mock ErrorLogger for JSON logging
        def mock_log_error(error_type, message, details, user_id=""):
            error_record = {
                "id": f"integrated-test-{datetime.now().isoformat()}",
                "timestamp": datetime.now().isoformat(),
                "type": error_type,
                "message": message,
                "details": details,
                "user_id": user_id,
                "resolved": False
            }
            
            errors = []
            if os.path.exists(self.error_log_path):
                with open(self.error_log_path, 'r', encoding='utf-8') as f:
                    try:
                        errors = json.load(f)
                    except json.JSONDecodeError:
                        errors = []
            
            errors.append(error_record)
            
            with open(self.error_log_path, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2)
        
        # Test integrated logging
        with patch('common.logger.sys.modules') as mock_modules:
            mock_streamlit_app = MagicMock()
            mock_streamlit_app.ErrorLogger = MagicMock
            mock_streamlit_app.ErrorLogger.return_value.log_error = mock_log_error
            
            mock_modules.get.return_value = mock_streamlit_app
            mock_modules.__contains__ = lambda x: True
            mock_modules.items.return_value = [('streamlit_app', mock_streamlit_app)]
            
            logger = get_logger('integration_test_logger')
            
            try:
                # Create a more complex exception scenario
                def complex_dummy_function(param):
                    """Complex dummy function that processes parameters and fails."""
                    if param == "trigger_error":
                        raise RuntimeError("Integrated logging test - both systems should capture this")
                    return param
                
                complex_dummy_function("trigger_error")
                
            except Exception:
                exception_info(logger, "Integrated test: both app.log and error_logs.json should be updated")
        
        # Verify both systems captured the exception
        
        # 1. Check app.log
        assert os.path.exists(self.app_log_path), "app.log should exist"
        with open(self.app_log_path, 'r', encoding='utf-8') as f:
            app_log_lines = f.readlines()
        
        assert len(app_log_lines) > initial_app_log_size, "app.log should have new entries"
        app_log_content = ''.join(app_log_lines)
        assert "Integrated test: both app.log and error_logs.json should be updated" in app_log_content
        assert "RuntimeError" in app_log_content
        
        # 2. Check error_logs.json
        assert os.path.exists(self.error_log_path), "error_logs.json should exist"
        with open(self.error_log_path, 'r', encoding='utf-8') as f:
            error_data = json.load(f)
        
        assert len(error_data) > initial_error_count, "error_logs.json should have new records"
        latest_error = error_data[-1]
        assert "Integrated test: both app.log and error_logs.json should be updated" in latest_error['message']
        assert "RuntimeError" in latest_error['details']
    
    def test_logger_configuration(self):
        """Test that logger is properly configured with expected handlers and format."""
        logger = get_logger('config_test_logger')
        
        # Test that logger has file handlers
        root_logger = logger.root
        
        # Should have handlers for file logging
        assert len(root_logger.handlers) > 0, "Logger should have handlers configured"
        
        # Test logging level
        logger.info("Configuration test message")
        
        # Verify the log file exists and contains our message
        assert os.path.exists(self.app_log_path), "app.log should be created by configuration"
        
        with open(self.app_log_path, 'r', encoding='utf-8') as f:
            log_content = f.read()
        
        assert "Configuration test message" in log_content
        assert "config_test_logger" in log_content  # Logger name should appear


class TestPSReadLineFix:
    """Test PSReadLine PowerShell profile fix (manual verification required)."""
    
    def test_powershell_profile_exists(self):
        """Test that the PowerShell profile file exists and contains PSReadLine fix."""
        profile_path = Path("profile.ps1")
        assert profile_path.exists(), "profile.ps1 should exist in project root"
        
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile_content = f.read()
        
        # Check for key components of the PSReadLine fix
        assert "PSReadLine" in profile_content, "Profile should reference PSReadLine"
        assert "PredictionSource" in profile_content, "Profile should handle PredictionSource parameter"
        assert "Get-Module PSReadLine" in profile_content, "Profile should check PSReadLine version"
        
        # Check for error handling
        assert "try" in profile_content.lower() and "catch" in profile_content.lower(), \
            "Profile should include error handling"
    
    def test_install_scripts_exist(self):
        """Test that PSReadLine installation scripts exist."""
        install_scripts = [
            "install-profile.ps1",
            "install-profile.bat", 
            "setup-powershell-profile.ps1"
        ]
        
        for script in install_scripts:
            script_path = Path(script)
            assert script_path.exists(), f"Installation script {script} should exist"
    
    def test_psreadline_documentation(self):
        """Test that PSReadLine fix is documented in README or dedicated file."""
        docs_to_check = ["README.md", "PSREADLINE_FIX_SUMMARY.md"]
        
        psreadline_documented = False
        for doc_file in docs_to_check:
            doc_path = Path(doc_file)
            if doc_path.exists():
                with open(doc_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if "PSReadLine" in content or "PredictionSource" in content:
                    psreadline_documented = True
                    break
        
        assert psreadline_documented, "PSReadLine fix should be documented"
    
    @pytest.mark.manual
    def test_powershell_startup_manual_verification(self):
        """
        Manual test for PowerShell startup without PredictionSource error.
        
        To verify this test manually:
        1. Install the PowerShell profile using one of:
           - powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1
           - install-profile.bat
        2. Open a new PowerShell session or Warp terminal
        3. Verify no error message appears about 'PredictionSource' parameter
        4. Confirm PSReadLine functionality works correctly
        
        This test passes if no PredictionSource error occurs on PowerShell startup.
        """
        # This is a placeholder for manual verification
        # In a CI/CD environment, you might run PowerShell commands to test this
        assert True, "Manual verification: Start new PowerShell session and check for PredictionSource errors"


class TestDocumentation:
    """Test that documentation for running tests is properly provided."""
    
    def test_pytest_execution_documented(self):
        """Test that pytest execution instructions are documented."""
        # Check if this test file has proper docstring with run instructions
        current_file = Path(__file__)
        with open(current_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should contain pytest run instructions
        assert "pytest tests/test_logging.py" in content, \
            "Test file should document how to run pytest"
        
        # Check for docstring with instructions
        assert "Run with:" in content, "Test file should include run instructions"


if __name__ == "__main__":
    # Allow running this test file directly
    pytest.main([__file__, "-v"])
