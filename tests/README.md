# Regression Tests Quick Reference

This directory contains regression tests for the logging system and PSReadLine fix.

## Quick Start

### Python Logging Tests
```bash
# Install dependencies
pip install pytest

# Run all logging tests
pytest tests/test_logging.py -v

# Run specific test
pytest tests/test_logging.py::TestLoggingSystem::test_dummy_exception_creates_app_log_entry -v
```

### PowerShell PSReadLine Tests
```powershell
# Install Pester (if needed)
Install-Module -Name Pester -Force -SkipPublisherCheck

# Run PowerShell tests
Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose
```

## What These Tests Verify

1. **Logging Integration**: 
   - Exceptions create entries in `logs/app.log`
   - ErrorLogger creates JSON records in `error_logs.json`
   - Both systems work together correctly

2. **PSReadLine Fix**: 
   - PowerShell profile prevents "PredictionSource" parameter errors
   - Installation scripts exist and work correctly
   - Profile handles different PSReadLine versions

## Files

- `test_logging.py` - Python pytest suite for logging system
- `Test-PSReadLineFix.Tests.ps1` - PowerShell Pester tests for PSReadLine fix
- `README.md` - This quick reference

## Manual Verification

For PSReadLine fix, also test manually:

1. Install profile: `powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1`
2. Open new PowerShell session
3. Verify no "PredictionSource" error appears

## Full Documentation

See `../REGRESSION_TESTING.md` for comprehensive documentation and troubleshooting.
