"""
Windows-safe rotating file handler that handles file locking issues.
"""

import os
import time
from logging.handlers import TimedRotatingFileHandler


class WindowsSafeTimedRotatingFileHandler(TimedRotatingFileHandler):
    """
    TimedRotatingFileHandler that handles Windows file locking issues during rotation.
    
    On Windows, when multiple processes/threads try to access the same log file,
    rotation can fail with PermissionError. This handler implements retry logic
    and safer file operations.
    """
    
    def __init__(self, *args, **kwargs):
        # Force delay=True to avoid immediate file opening
        kwargs['delay'] = True
        super().__init__(*args, **kwargs)
        self._rotation_lock = False
    
    def rotate(self, source, dest):
        """
        Override rotate to handle Windows file locking issues.
        
        Implements retry logic and safer file operations for Windows.
        """
        # Skip if another rotation is in progress
        if self._rotation_lock:
            return
            
        self._rotation_lock = True
        max_retries = 5
        retry_delay = 0.1  # Start with 100ms delay
        
        try:
            for attempt in range(max_retries):
                try:
                    # Close the file stream before rotation
                    if self.stream:
                        self.stream.close()
                        self.stream = None
                    
                    # Give Windows time to release file handles
                    time.sleep(0.05)
                    
                    # Remove destination file if it exists
                    if os.path.exists(dest):
                        try:
                            os.remove(dest)
                        except PermissionError:
                            # If we can't remove dest, try appending timestamp
                            timestamp = time.strftime("%H%M%S")
                            dest = f"{dest}.{timestamp}"
                    
                    # Try to rename the file
                    if os.path.exists(source):
                        os.rename(source, dest)
                    
                    # Success - break out of retry loop
                    break
                    
                except PermissionError as e:
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        time.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        # Final attempt failed - try alternative approach
                        self._fallback_rotation(source, dest)
                        
        finally:
            self._rotation_lock = False
    
    def _fallback_rotation(self, source, dest):
        """
        Fallback rotation method when standard rename fails.
        
        This method copies content instead of renaming, which is slower
        but more reliable on Windows when files are locked.
        """
        try:
            # Close any open streams
            if self.stream:
                self.stream.close()
                self.stream = None
            
            # Read source file content
            if os.path.exists(source):
                try:
                    with open(source, 'rb') as src_file:
                        content = src_file.read()
                    
                    # Write to destination
                    with open(dest, 'wb') as dst_file:
                        dst_file.write(content)
                    
                    # Clear source file instead of deleting
                    with open(source, 'w') as src_file:
                        src_file.truncate(0)
                        
                except Exception:
                    # If all else fails, just continue without rotation
                    # Better to lose rotation than crash the application
                    pass
                    
        except Exception:
            # Silently continue on any error
            pass
    
    def doRollover(self):
        """
        Override doRollover to ensure file is properly closed before rotation.
        """
        # Close the stream before attempting rotation
        if self.stream:
            self.stream.close()
            self.stream = None
        
        try:
            # Call parent's doRollover
            super().doRollover()
        except PermissionError:
            # If rotation fails, ensure we can still write logs
            # by opening a new stream to the base filename
            self.stream = self._open()