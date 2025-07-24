"""
Example usage of the common logging utility.

This file demonstrates how to use the centralized logging system
throughout the project.
"""

from common.logger import get_logger, exception_info

# Get a logger instance for this module
logger = get_logger(__name__)

def example_function():
    """Example function demonstrating logging usage."""
    logger.info("Starting example function")
    
    try:
        # Some business logic
        result = perform_calculation(10, 5)
        logger.info(f"Calculation completed successfully: {result}")
        return result
    except Exception:
        # Use exception_info for comprehensive error logging
        exception_info(logger, "Failed to perform calculation")
        raise

def perform_calculation(a: int, b: int) -> float:
    """Example calculation function."""
    logger.debug(f"Performing calculation with a={a}, b={b}")
    
    if b == 0:
        logger.warning("Division by zero attempted")
        raise ValueError("Cannot divide by zero")
    
    result = a / b
    logger.debug(f"Calculation result: {result}")
    return result

def example_with_different_log_levels():
    """Demonstrate different log levels."""
    logger.debug("This is a debug message (not shown by default)")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

if __name__ == "__main__":
    logger.info("Running logger example")
    
    # Example of normal usage
    result = example_function()
    print(f"Result: {result}")
    
    # Example of different log levels
    example_with_different_log_levels()
    
    # Example of exception logging
    try:
        perform_calculation(10, 0)
    except ValueError:
        exception_info(logger, "Expected error occurred in example")
    
    logger.info("Logger example completed")
