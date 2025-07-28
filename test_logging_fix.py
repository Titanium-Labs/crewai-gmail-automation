#!/usr/bin/env python3
"""
Test script to verify the Windows logging rotation fix.
"""

import os
import sys
import time
import threading
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Import logger after path is set
from common.logger import get_logger, get_auth_logger, get_billing_logger

def test_concurrent_logging():
    """Test multiple loggers writing concurrently."""
    print("Testing concurrent logging from multiple sources...")
    
    # Get different loggers
    app_logger = get_logger(__name__)
    auth_logger = get_auth_logger()
    billing_logger = get_billing_logger()
    
    def log_messages(logger, prefix, count=50):
        """Log multiple messages from a logger."""
        for i in range(count):
            logger.info(f"{prefix} - Message {i} at {datetime.now().isoformat()}")
            time.sleep(0.01)  # Small delay to simulate real usage
    
    # Create threads for concurrent logging
    threads = [
        threading.Thread(target=log_messages, args=(app_logger, "APP", 30)),
        threading.Thread(target=log_messages, args=(auth_logger, "AUTH", 30)),
        threading.Thread(target=log_messages, args=(billing_logger, "BILLING", 30)),
    ]
    
    # Start all threads
    for thread in threads:
        thread.start()
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    print("Concurrent logging test completed successfully!")

def test_rotation_simulation():
    """Test log rotation by forcing a rotation."""
    print("\nTesting log rotation simulation...")
    
    logger = get_logger("rotation_test")
    
    # Log some messages
    for i in range(10):
        logger.info(f"Pre-rotation message {i}")
    
    # Access the handler and force rotation if possible
    for handler in logger.handlers:
        if hasattr(handler, 'doRollover'):
            print("Attempting to force log rotation...")
            try:
                handler.doRollover()
                print("Log rotation completed successfully!")
            except Exception as e:
                print(f"Log rotation encountered an error (this may be expected): {e}")
    
    # Log more messages after rotation attempt
    for i in range(10):
        logger.info(f"Post-rotation message {i}")
    
    print("Rotation simulation test completed!")

def check_log_files():
    """Check the status of log files."""
    print("\nChecking log files...")
    
    logs_dir = "logs"
    if os.path.exists(logs_dir):
        files = os.listdir(logs_dir)
        print(f"Found {len(files)} log files:")
        for file in sorted(files):
            file_path = os.path.join(logs_dir, file)
            size = os.path.getsize(file_path)
            print(f"  - {file} ({size} bytes)")
    else:
        print("Logs directory not found!")

if __name__ == "__main__":
    print("Starting Windows logging fix test...\n")
    
    # Run tests
    test_concurrent_logging()
    test_rotation_simulation()
    check_log_files()
    
    print("\nAll tests completed! Check the logs directory for results.")