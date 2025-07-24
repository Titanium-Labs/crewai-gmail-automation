# Common Logging Utility

This directory contains the project-wide logging utility that provides centralized, consistent logging across all modules.

## Features

- **Single Configuration**: Logging is configured once per application run
- **File Rotation**: Daily log rotation with 14-day retention (`logs/app.log`)
- **Streamlit Integration**: Automatic detection and integration with Streamlit UI
- **ErrorLogger Integration**: Seamless integration with existing ErrorLogger system
- **Consistent Formatting**: Standardized timestamp and message format across all modules

## Quick Start

```python
from common.logger import get_logger, exception_info

# Get a logger for your module
logger = get_logger(__name__)

# Basic logging
logger.info("Operation started")
logger.warning("Something might be wrong")
logger.error("Something went wrong")

# Exception logging with ErrorLogger integration
try:
    risky_operation()
except Exception:
    exception_info(logger, "Failed to perform risky operation")
```

## Functions

### `get_logger(name: str) -> logging.Logger`

Returns a configured logger instance. Call this once per module with `__name__` as the parameter.

**Features:**
- Configures logging system on first call
- Returns standard Python logger with project-wide configuration
- Thread-safe singleton pattern for configuration

### `exception_info(logger: logging.Logger, msg: str)`

Logs exception information and records it with the existing ErrorLogger system.

**Features:**
- Logs full traceback to file and console/Streamlit
- Automatically records error in ErrorLogger system for UI display
- Safe error handling - won't fail if ErrorLogger is unavailable

## Configuration Details

### Log Format
```
%(asctime)s %(levelname)s %(name)s: %(message)s
```

Example: `2025-01-23 10:30:45,123 INFO module.name: Operation completed`

### File Rotation
- **Location**: `logs/app.log`
- **Rotation**: Daily at midnight
- **Retention**: 14 days
- **Backup naming**: `app.log.YYYY-MM-DD`

### Output Destinations

1. **File**: Always logs to `logs/app.log` with rotation
2. **Streamlit**: When running in Streamlit context, logs appear in the UI
3. **Console**: When not in Streamlit, logs to stdout

### Streamlit Integration

The logger automatically detects when running in Streamlit and routes log messages appropriately:

- `ERROR` → `st.error()`
- `WARNING` → `st.warning()`  
- `INFO` → `st.info()`
- `DEBUG` → `st.write()`

## Usage Examples

### Basic Module Setup

```python
# At the top of your module
from common.logger import get_logger

logger = get_logger(__name__)

def your_function():
    logger.info("Function started")
    # Your code here
    logger.info("Function completed")
```

### Exception Handling

```python
from common.logger import get_logger, exception_info

logger = get_logger(__name__)

def risky_function():
    try:
        # Code that might raise an exception
        result = some_operation()
        logger.info("Operation successful")
        return result
    except Exception:
        # This logs to both standard logging AND ErrorLogger
        exception_info(logger, "Operation failed")
        raise  # Re-raise if needed
```

### Different Log Levels

```python
logger.debug("Detailed information for debugging")     # Not shown by default
logger.info("General information about program flow")  # Shown
logger.warning("Something unexpected happened")         # Shown
logger.error("An error occurred")                      # Shown
```

## Integration with Existing Code

To integrate the common logger into existing modules:

1. **Import the logger**:
   ```python
   from common.logger import get_logger, exception_info
   ```

2. **Get a logger instance**:
   ```python
   logger = get_logger(__name__)
   ```

3. **Replace print statements**:
   ```python
   # Before
   print("Operation started")
   
   # After  
   logger.info("Operation started")
   ```

4. **Replace exception handling**:
   ```python
   # Before
   except Exception as e:
       print(f"Error: {e}")
   
   # After
   except Exception:
       exception_info(logger, "Operation failed")
   ```

## File Structure

```
src/common/
├── __init__.py          # Package initialization
├── logger.py            # Main logging utility
├── logger_example.py    # Usage examples
└── README.md           # This documentation
```

## Log File Location

Logs are written to `logs/app.log` in the project root directory. The directory is created automatically if it doesn't exist.

## Thread Safety

The logging utility is thread-safe and can be used safely in multi-threaded applications, including with Streamlit's threading model.
