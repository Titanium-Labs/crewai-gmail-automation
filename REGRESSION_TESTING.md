# Regression Testing Documentation

This document provides comprehensive instructions for running regression tests to verify the logging system and PSReadLine fix implementation.

## Overview

The regression test suite verifies:

1. **Logging System Integration**: Tests that exceptions create entries in both `logs/app.log` and `error_logs.json`
2. **PSReadLine Fix**: Verifies that the PowerShell profile fix prevents "PredictionSource" parameter errors
3. **End-to-End Integration**: Ensures both systems work together correctly

## Test Structure

```
tests/
├── test_logging.py              # Python pytest suite for logging system
├── Test-PSReadLineFix.Tests.ps1 # PowerShell Pester tests for PSReadLine fix
└── README.md                    # This documentation
```

## Prerequisites

### Python Tests

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   This includes pytest and other required packages.

2. **Project Structure**: Ensure the following files exist:
   - `src/common/logger.py` - Main logging implementation
   - `logs/` directory (created automatically)
   - `error_logs.json` (created automatically during tests)

### PowerShell Tests

1. **Install Pester** (if not already installed):
   ```powershell
   Install-Module -Name Pester -Force -SkipPublisherCheck
   ```

2. **Required Files**: Ensure these PowerShell files exist:
   - `profile.ps1` - Main PowerShell profile with PSReadLine fix
   - `install-profile.ps1` - Installation script
   - `install-profile.bat` - Batch installer
   - `setup-powershell-profile.ps1` - Advanced setup script

## Running Tests

### 1. Python Logging Tests

#### Run All Logging Tests
```bash
pytest tests/test_logging.py -v
```

#### Run Specific Test Categories
```bash
# Test only the logging system integration
pytest tests/test_logging.py::TestLoggingSystem -v

# Test only PSReadLine file validation
pytest tests/test_logging.py::TestPSReadLineFix -v

# Test documentation completeness
pytest tests/test_logging.py::TestDocumentation -v
```

#### Run Individual Tests
```bash
# Test that exceptions create app.log entries
pytest tests/test_logging.py::TestLoggingSystem::test_dummy_exception_creates_app_log_entry -v

# Test that exceptions create error_logs.json records
pytest tests/test_logging.py::TestLoggingSystem::test_dummy_exception_creates_error_json_record -v

# Test integrated logging (both systems)
pytest tests/test_logging.py::TestLoggingSystem::test_integrated_logging_both_systems -v
```

#### Expected Output
```
============================= test session starts ==============================
collecting ... collected 8 items

tests/test_logging.py::TestLoggingSystem::test_dummy_exception_creates_app_log_entry PASSED
tests/test_logging.py::TestLoggingSystem::test_dummy_exception_creates_error_json_record PASSED
tests/test_logging.py::TestLoggingSystem::test_integrated_logging_both_systems PASSED
tests/test_logging.py::TestLoggingSystem::test_logger_configuration PASSED
tests/test_logging.py::TestPSReadLineFix::test_powershell_profile_exists PASSED
tests/test_logging.py::TestPSReadLineFix::test_install_scripts_exist PASSED
tests/test_logging.py::TestPSReadLineFix::test_psreadline_documentation PASSED
tests/test_logging.py::TestDocumentation::test_pytest_execution_documented PASSED

============================== 8 passed in 2.31s ==============================
```

### 2. PowerShell PSReadLine Tests

#### Run All PowerShell Tests
```powershell
Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose
```

#### Run Specific Test Contexts
```powershell
# Test only profile file validation
Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Tag "ProfileValidation" -Verbose

# Test only error prevention
Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Tag "ErrorPrevention" -Verbose
```

#### Expected Output
```
Starting discovery in 1 files.
Discovery found 12 tests in 52ms.
Running tests.

Describing PSReadLine Fix Regression Tests
  Context Profile File Validation
    [+] Should have profile.ps1 file in project root 23ms (15ms|8ms)
    [+] Should contain PSReadLine version detection 16ms (12ms|4ms)
    [+] Should contain PredictionSource parameter handling 12ms (9ms|3ms)
    [+] Should contain error handling (try-catch blocks) 11ms (8ms|3ms)
    [+] Should contain version comparison logic 10ms (7ms|3ms)
  Context Installation Scripts Validation
    [+] Should have install-profile.ps1 script 8ms (5ms|3ms)
    [+] Should have install-profile.bat script 7ms (4ms|3ms)
    [+] Should have setup-powershell-profile.ps1 script 6ms (4ms|2ms)
  Context Profile Syntax and Execution
    [+] Should have valid PowerShell syntax 45ms (38ms|7ms)
    [+] Should execute without errors in isolated session 234ms (198ms|36ms)
  Context PSReadLine Module Detection
    [+] Should detect PSReadLine module availability 67ms (59ms|8ms)
    [+] Should handle PSReadLine 2.0 compatibility 156ms (142ms|14ms)

Tests completed in 612ms
Tests Passed: 12, Failed: 0, Skipped: 0 NotRun: 0
```

## Test Details

### Python Logging Tests

#### `test_dummy_exception_creates_app_log_entry`
- **Purpose**: Verifies that raising an exception creates a new line in `logs/app.log`
- **Process**: 
  1. Records initial log file size
  2. Triggers a dummy exception (ValueError)
  3. Logs the exception using the logger
  4. Verifies new log entry contains expected content and traceback

#### `test_dummy_exception_creates_error_json_record`
- **Purpose**: Verifies that exceptions create JSON records in `error_logs.json`
- **Process**:
  1. Mocks the ErrorLogger functionality
  2. Triggers a dummy exception (ZeroDivisionError)
  3. Uses `exception_info()` helper to log to JSON
  4. Verifies JSON structure and content

#### `test_integrated_logging_both_systems`
- **Purpose**: Tests that both logging systems capture the same exception
- **Process**:
  1. Records initial state of both log files
  2. Triggers a RuntimeError
  3. Uses `exception_info()` to log to both systems
  4. Verifies both `logs/app.log` and `error_logs.json` are updated

#### `test_logger_configuration`
- **Purpose**: Validates logger configuration and handlers
- **Process**:
  1. Gets logger instance
  2. Verifies handlers are configured
  3. Tests logging functionality
  4. Confirms log format and content

### PowerShell PSReadLine Tests

#### Profile File Validation
- Tests existence of `profile.ps1`
- Validates PSReadLine version detection code
- Confirms PredictionSource parameter handling
- Verifies error handling implementation

#### Installation Scripts Validation
- Confirms all installation scripts exist
- Tests script accessibility and basic syntax

#### Profile Syntax and Execution
- Validates PowerShell syntax correctness
- Tests profile execution in isolated sessions
- Ensures no syntax or runtime errors

#### Error Prevention (Core Test)
- **Critical Test**: Installs profile and tests new PowerShell session
- Verifies no PredictionSource parameter errors occur
- Tests graceful handling of parameter unavailability

## Manual Verification

### PSReadLine Fix Manual Testing

The automated tests provide comprehensive coverage, but manual verification is still valuable:

1. **Install the Profile**:
   ```powershell
   # Choose one installation method:
   powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1
   # OR
   .\install-profile.bat
   ```

2. **Test PowerShell Startup**:
   - Open a new PowerShell session or Warp terminal
   - Verify NO error message appears about 'PredictionSource' parameter
   - Confirm PSReadLine functionality works (arrow keys, history, tab completion)

3. **Expected Result**: PowerShell starts cleanly without errors

## Troubleshooting

### Common Issues

#### Python Tests

**Issue**: `ImportError: No module named 'common.logger'`
```bash
# Solution: Ensure you're running from project root
cd /path/to/crewai-gmail-automation
pytest tests/test_logging.py -v
```

**Issue**: `FileNotFoundError: [Errno 2] No such file or directory: 'logs/app.log'`
```bash
# Solution: Tests create temporary directories, but if this occurs:
mkdir logs
pytest tests/test_logging.py -v
```

**Issue**: Mock-related failures
```bash
# Solution: Ensure pytest and mock are installed
pip install pytest unittest-mock
```

#### PowerShell Tests

**Issue**: `Cannot find module 'Pester'`
```powershell
# Solution: Install Pester
Install-Module -Name Pester -Force -SkipPublisherCheck
```

**Issue**: `Execution Policy` errors
```powershell
# Solution: Set execution policy for current session
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

**Issue**: Profile backup/restore issues
```powershell
# Solution: Check PowerShell profile location
$PROFILE.CurrentUserCurrentHost
# Manually restore if needed
```

## Continuous Integration

### For CI/CD Pipelines

#### Python Tests in CI
```yaml
# Example GitHub Actions workflow
- name: Run Python Logging Tests
  run: |
    pip install -r requirements.txt
    pytest tests/test_logging.py -v --junit-xml=test-results.xml
```

#### PowerShell Tests in CI (Windows)
```yaml
# Example GitHub Actions workflow  
- name: Run PowerShell Tests
  run: |
    Install-Module -Name Pester -Force -SkipPublisherCheck
    Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -OutputFormat NUnitXml -OutputFile pester-results.xml
  shell: powershell
```

## Test Coverage

### Current Coverage

- ✅ **Logging System**: Exception handling, file creation, JSON structure
- ✅ **Integration**: Both logging systems working together
- ✅ **PSReadLine Fix**: Profile validation, installation scripts, error prevention
- ✅ **Documentation**: Test instructions and usage guides

### Areas for Future Enhancement

- **Performance Tests**: Large log file handling, rotation testing
- **Security Tests**: Log injection prevention, file permissions
- **Cross-Platform**: Linux/macOS PowerShell Core compatibility
- **Load Testing**: High-volume exception scenarios

## Summary

This regression test suite provides comprehensive coverage of both the logging system and PSReadLine fix:

1. **Run Python tests**: `pytest tests/test_logging.py -v`
2. **Run PowerShell tests**: `Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose`
3. **Manual verification**: Install profile and test new PowerShell session

The tests ensure that:
- Exceptions properly create entries in `logs/app.log`
- ErrorLogger creates JSON records in `error_logs.json`
- Both systems work together seamlessly
- PowerShell sessions start without PredictionSource errors

Regular execution of these tests will catch regressions and ensure the stability of both logging and PowerShell integration features.
