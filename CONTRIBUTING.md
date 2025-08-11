# Contributing to Gmail CrewAI Automation

Thank you for your interest in contributing to the Gmail CrewAI Automation project! This document provides guidelines and information to help you contribute effectively.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Logging & Troubleshooting](#logging--troubleshooting)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [PowerShell Module Requirements](#powershell-module-requirements)

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/crewai-gmail-automation.git`
3. Install dependencies: `pip install -r requirements.txt`
4. Set up your environment variables (see README.md)
5. Run the application: `streamlit run streamlit_app.py --server.port ${PORT:-8505}`

## Development Setup

### Prerequisites

- Python 3.8+
- Git
- PowerShell (Windows users)
- Gmail API credentials
- Streamlit

### Environment Configuration

Copy `.env.example` to `.env` and configure your settings:
- Gmail API credentials
- Stripe keys (for billing features)
- SMTP settings (for approval emails)

## Logging & Troubleshooting

This project implements a comprehensive logging system designed to help developers and administrators monitor, debug, and troubleshoot the application effectively.

### Log Levels

The application uses standard Python logging levels:

- **DEBUG**: Detailed diagnostic information, typically only of interest when diagnosing problems
- **INFO**: General information about program execution and important events
- **WARNING**: Indication that something unexpected happened, but the software is still working
- **ERROR**: A more serious problem occurred; the software couldn't perform some function
- **CRITICAL**: A serious error occurred; the program itself may be unable to continue running

### Log Files and Locations

The system maintains **5 separate log files** for organized logging:

#### Primary Log Files (in `logs/` directory):

1. **`logs/app.log`** - General application logs (INFO level and above)
   - Main application flow
   - User interactions
   - General system events

2. **`logs/system.log`** - System warnings and errors (WARNING level and above)
   - Configuration issues
   - Resource problems
   - System-level errors

3. **`logs/auth.log`** - Authentication related logs (INFO level and above)
   - OAuth2 authentication flows
   - User login/logout events
   - Token management activities

4. **`logs/billing.log`** - Billing and subscription logs (INFO level and above)
   - Stripe integration events
   - Subscription changes
   - Usage tracking

5. **`logs/crew.log`** - CrewAI processing logs (INFO level and above)
   - AI agent execution
   - Email processing workflows
   - CrewAI-specific operations

#### Error Log Files:

- **`error_logs.json`** - Current day's structured error logs
- **`error_logs_YYYYMMDD.json`** - Daily rotated error archives

### Log Rotation

#### Automatic Daily Rotation

- **When**: Daily at midnight
- **Retention**: 14 days for application logs, 30 days for error logs
- **Format**: Files are rotated with YYYY-MM-DD suffix (e.g., `app.log.2024-01-15`)
- **Encoding**: UTF-8 for international character support

#### Example Rotated File Structure:
```
logs/
├── app.log                    # Current day
├── app.log.2024-01-15        # Yesterday's logs
├── app.log.2024-01-14        # 2 days ago
├── system.log                # Current day
├── system.log.2024-01-15     # Yesterday's logs
└── ...
```

#### Cleanup Automation

The system includes automated cleanup via:

1. **GitHub Actions**: Daily at 2 AM UTC (`.github/workflows/cleanup-logs.yml`)
2. **Windows Task Scheduler**: For local installations (see `docs/WINDOWS_TASK_SCHEDULER_SETUP.md`)
3. **Manual cleanup**: `python scripts/cleanup_logs.py`

### Viewing Logs in Streamlit Admin Panel

Administrators can view logging information through the Streamlit web interface:

#### Accessing the Admin Panel

1. **Login** as an admin user to the Streamlit application
2. Navigate to the **"👑 Admin Panel"** tab (visible only to admin users)
3. Use the various admin tabs to view system information

#### Admin Panel Features for Logging:

- **User Statistics**: Shows OAuth2 connection status and authentication state
- **System Status**: Displays current system health and configuration
- **Debug Information**: For administrators to troubleshoot authentication and logging issues

#### Viewing Error Logs:

The admin panel provides access to:
- **Current Error Status**: Live error monitoring and recent issues
- **User Authentication Status**: OAuth2 connection status for automatic email sending
- **System Configuration**: Verification of logging and system setup

### Troubleshooting Common Issues

#### 1. Log Rotation Not Working

**Symptoms**: Log files growing indefinitely, no dated backup files
**Solutions**:
- Check file permissions on the `logs/` directory
- Verify the application runs past midnight for rotation to trigger
- Check for file locks preventing rotation
- Review cleanup automation setup

#### 2. Missing Log Files

**Symptoms**: Expected log files not appearing
**Solutions**:
- Verify the `logs/` directory exists and has write permissions
- Check if the logging configuration is properly initialized
- Ensure the application is actually generating log events

#### 3. OAuth2 Authentication Issues

**Symptoms**: "OAuth2 Not Connected" in admin panel
**Solutions**:
- Check if token files exist in `tokens/` directory
- Verify the user has completed Google OAuth2 authentication
- Review the `auth.log` file for authentication errors
- Ensure proper Gmail API credentials are configured

#### 4. Error Logging Not Working

**Symptoms**: Errors not appearing in `error_logs.json`
**Solutions**:
- Verify the ErrorLogger class is properly initialized
- Check that exception handlers are calling `ErrorLogger.log_error()`
- Review the centralized logger integration
- Check file permissions for the error log files

#### 5. Admin Panel Not Accessible

**Symptoms**: Admin tab not visible or access denied
**Solutions**:
- Verify the user has admin privileges in the user management system
- Check if the user is the primary owner (first registered user)
- Review user status and permissions in the admin panel
- Ensure proper authentication and session management

### Log Analysis and Monitoring

#### Manual Log Review

```bash
# View recent application logs
tail -f logs/app.log

# Search for specific errors
grep -i "error" logs/system.log

# View error patterns
grep -A 5 -B 5 "exception" logs/app.log
```

#### Structured Error Analysis

Error logs are stored in JSON format for easy parsing:

```python
import json

# Load and analyze error logs
with open('error_logs.json', 'r') as f:
    errors = json.load(f)

# Analyze error patterns
for error in errors:
    print(f"Type: {error['error_type']}")
    print(f"Message: {error['message']}")
    print(f"User: {error.get('user_id', 'N/A')}")
    print(f"Time: {error['timestamp']}")
    print("---")
```

#### Performance Monitoring

Monitor log file sizes and cleanup effectiveness:

```bash
# Check log directory size
du -sh logs/

# List rotated files
ls -la logs/*.log.*

# View cleanup history
cat cleanup_logs.log
```

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to all functions and classes
- Include type hints where appropriate
- Add logging statements for important operations

### Logging Best Practices

When adding new code, follow these logging conventions:

```python
from src.common.logger import get_logger, exception_info

logger = get_logger(__name__)

def your_function():
    logger.info("Starting important operation")
    
    try:
        # Your code here
        result = perform_operation()
        logger.info(f"Operation completed successfully: {result}")
        return result
    except Exception as e:
        # This logs to both centralized logger AND ErrorLogger
        exception_info(logger, "Operation failed during processing")
        raise
```

## Testing

- Write unit tests for new functionality
- Ensure all tests pass before submitting PR
- Add integration tests for complex features
- Test logging functionality with provided test scripts

### Testing Logging

Use the provided test script to verify logging configuration:

```bash
python test_logging.py
```

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with appropriate logging
3. Add/update tests as needed
4. Ensure all tests pass
5. Update documentation if needed
6. Submit a pull request with a clear description

## PowerShell Module Requirements

### Required PowerShell Module: PSReadLine

This project requires PSReadLine for proper PowerShell integration, especially when using Warp terminal.

#### Installation Steps

The project includes automated fixes for PSReadLine compatibility issues:

##### Option 1: Automated Installation (Recommended)

```bash
# Run the batch installer
install-profile.bat

# OR use PowerShell directly
powershell.exe -ExecutionPolicy Bypass -File install-profile.ps1
```

##### Option 2: Manual Installation

1. **Check Current PSReadLine Version**:
   ```powershell
   Get-Module PSReadLine -ListAvailable
   ```

2. **Install/Update PSReadLine** (if needed):
   ```powershell
   Install-Module -Name PSReadLine -Force -SkuipPublisherCheck
   ```

3. **Copy Profile**:
   ```powershell
   Copy-Item "profile.ps1" $PROFILE -Force
   ```

#### Common PSReadLine Issues

**Error**: `Set-PSReadLineOption: A parameter cannot be found that matches parameter name 'PredictionSource'`

**Solution**: This occurs with PSReadLine 2.0. The project includes smart profile detection that automatically uses compatible parameters based on your PSReadLine version.

#### Features Provided by PowerShell Profile

- **Version Detection**: Automatically detects PSReadLine version
- **Compatible Options**: Uses appropriate parameters for your PSReadLine version
- **Warp Integration**: Enhanced Warp terminal experience
- **Error Prevention**: Graceful handling of version compatibility issues

#### Troubleshooting PowerShell Setup

1. **Profile Not Loading**:
   - Check execution policy: `Get-ExecutionPolicy`
   - Set execution policy: `Set-ExecutionPolicy RemoteSigned -CurrentUser`

2. **Permission Issues**:
   - Run PowerShell as Administrator
   - Use the provided batch file installer

3. **Warp-Specific Issues**:
   - Restart Warp terminal after profile installation
   - Check if profile location is correct: `$PROFILE`

For detailed troubleshooting, see `PSREADLINE_FIX_SUMMARY.md`.

---

Thank you for contributing to the Gmail CrewAI Automation project! Your contributions help make email automation more accessible and powerful for everyone.
