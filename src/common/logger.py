"""
Project-wide logging utility.

Provides centralized logging configuration with:
- File rotation (daily rotation, 14-day retention)
- Streamlit integration when running in Streamlit context
- Integration with existing ErrorLogger for exceptions
- Consistent formatting across the project
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

# Global flag to track if logging has been configured
_logging_configured = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with project-wide configuration.
    
    Configures logging only once per application run with:
    - INFO level logging
    - Consistent timestamp format
    - File rotation (daily, 14-day retention)
    - Streamlit integration when available
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    global _logging_configured
    
    # Configure logging only once
    if not _logging_configured:
        _configure_logging()
        _logging_configured = True
    
    return logging.getLogger(name)


def _configure_logging():
    """Configure the root logger with handlers and formatting."""
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s'
    )
    
    # Clear any existing handlers to avoid duplicates
    logger = logging.getLogger()
    logger.handlers.clear()
    
    # Create common formatter
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
    
    # Define log files with their respective handlers
    log_files = {
        'logs/app.log': logging.INFO,      # General application logs
        'logs/system.log': logging.WARNING, # System warnings and errors
        'logs/auth.log': logging.INFO,     # Authentication related logs
        'logs/billing.log': logging.INFO,  # Billing and subscription logs
        'logs/crew.log': logging.INFO,     # CrewAI processing logs
    }
    
    # Add file handlers with rotation for each log file
    for log_file, level in log_files.items():
        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when='midnight',
            backupCount=14,  # Keep 14 days of logs
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        
        # Set suffix for rotated files (YYYY-MM-DD format)
        file_handler.suffix = "%Y-%m-%d"
        
        logger.addHandler(file_handler)
    
    # Add Streamlit handler if running in Streamlit context
    if _is_streamlit_running():
        streamlit_handler = StreamlitHandler()
        streamlit_handler.setLevel(logging.INFO)
        streamlit_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        logger.addHandler(streamlit_handler)
    else:
        # Add console handler when not in Streamlit
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        logger.addHandler(console_handler)


def _is_streamlit_running() -> bool:
    """
    Check if code is running in Streamlit context.
    
    Returns:
        True if running in Streamlit, False otherwise
    """
    try:
        import streamlit as st
        return hasattr(st, '_is_running_with_streamlit') and st._is_running_with_streamlit
    except ImportError:
        return False
    except AttributeError:
        # Fallback check for older Streamlit versions
        try:
            import streamlit as st
            # Try to access streamlit's session state as a way to detect if we're in streamlit
            _ = st.session_state
            return True
        except:
            return False


class StreamlitHandler(logging.Handler):
    """Custom logging handler that routes log messages to Streamlit."""
    
    def emit(self, record):
        """Emit a log record to Streamlit."""
        try:
            import streamlit as st
            msg = self.format(record)
            
            # Route different log levels to appropriate Streamlit methods
            if record.levelno >= logging.ERROR:
                st.error(msg)
            elif record.levelno >= logging.WARNING:
                st.warning(msg)
            elif record.levelno >= logging.INFO:
                st.info(msg)
            else:
                st.write(msg)
                
        except Exception:
            # Fallback to print if Streamlit is not available
            print(self.format(record))


def exception_info(logger: logging.Logger, msg: str):
    """
    Log exception information and record it with ErrorLogger.
    
    This helper function combines standard logging with the existing
    ErrorLogger system for comprehensive error tracking.
    
    Args:
        logger: Logger instance to use for logging
        msg: Message to log with the exception
    """
    # Log the exception with traceback using standard logging
    logger.exception(msg)
    
    # Also record with ErrorLogger if available
    try:
        # Import here to avoid circular imports
        import sys
        import traceback
        
        # Get the current exception info
        exc_type, exc_value, exc_traceback = sys.exc_info()
        if exc_type is not None:
            # Format the exception details
            details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
            
            # Try to get ErrorLogger from streamlit_app module
            try:
                # Try direct import from streamlit_app
                try:
                    # First attempt: try to import streamlit_app directly
                    import streamlit_app
                    if hasattr(streamlit_app, 'ErrorLogger'):
                        error_logger = streamlit_app.ErrorLogger()
                        error_logger.log_error(
                            error_type="System",
                            message=msg,
                            details=details,
                            user_id=""  # Will be empty unless we can determine user context
                        )
                        return  # Successfully logged with ErrorLogger
                except ImportError:
                    pass  # Try alternative methods
                
                # Alternative: Dynamic import from __main__ module
                module_globals = sys.modules.get('__main__', None)
                if module_globals and hasattr(module_globals, 'ErrorLogger'):
                    error_logger_class = getattr(module_globals, 'ErrorLogger')
                    error_logger = error_logger_class()
                    error_logger.log_error(
                        error_type="System",
                        message=msg,
                        details=details,
                        user_id=""  # Will be empty unless we can determine user context
                    )
                    return  # Successfully logged with ErrorLogger
                
                # Alternative: Look for any module with ErrorLogger
                streamlit_module = None
                for module_name, module in sys.modules.items():
                    if hasattr(module, 'ErrorLogger') and ('streamlit' in module_name.lower() or module_name == '__main__'):
                        streamlit_module = module
                        break
                
                if streamlit_module:
                    error_logger = streamlit_module.ErrorLogger()
                    error_logger.log_error(
                        error_type="System",
                        message=msg,
                        details=details,
                        user_id=""
                    )
                    return  # Successfully logged with ErrorLogger
                
                # If ErrorLogger is not available, just log to standard logger
                logger.warning("ErrorLogger not available, exception logged to standard logger only")
                        
            except Exception as e:
                # If there's any issue with ErrorLogger, don't fail the logging
                logger.warning(f"Failed to record exception with ErrorLogger: {e}")
                # Ensure we log the original exception details to standard logger
                logger.error(f"Exception details: {details}")
                
    except Exception as e:
        # Ensure we don't fail if there are any issues with exception logging
        logger.warning(f"Error in exception_info helper: {e}")
