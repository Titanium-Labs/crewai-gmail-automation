#!/usr/bin/env python3
"""
Log Cleanup Script

Removes log files and archived JSON files older than 30 days.
Designed to be run periodically via GitHub Actions or Windows Task Scheduler.

This script:
- Deletes .log files in the logs/ directory older than 30 days
- Removes archived .json files (error_logs_*.json, etc.) older than 30 days
- Provides detailed logging of cleanup operations
- Handles errors gracefully to prevent automation failures
"""

import os
import sys
import glob
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup basic logging for this script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cleanup_logs.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def cleanup_old_log_files(days_old: int = 30) -> int:
    """
    Remove .log files older than specified days.
    
    Args:
        days_old: Number of days to keep files (default: 30)
        
    Returns:
        Number of files removed
    """
    removed_count = 0
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    # Define log directory
    logs_dir = Path("logs")
    
    if not logs_dir.exists():
        logger.warning(f"Logs directory '{logs_dir}' does not exist")
        return 0
    
    # Find all .log files (including rotated ones)
    log_patterns = [
        "*.log",              # Current log files
        "*.log.*",            # Rotated log files with extensions
        "*-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]*"  # Date-stamped files
    ]
    
    for pattern in log_patterns:
        for log_file in logs_dir.glob(pattern):
            try:
                # Get file modification time
                file_mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    file_size = log_file.stat().st_size
                    log_file.unlink()
                    removed_count += 1
                    logger.info(f"Removed old log file: {log_file} (size: {file_size} bytes, age: {(datetime.now() - file_mtime).days} days)")
                    
            except Exception as e:
                logger.error(f"Failed to process log file {log_file}: {e}")
    
    return removed_count


def cleanup_archived_json_files(days_old: int = 30) -> int:
    """
    Remove archived .json files older than specified days.
    
    This includes files like:
    - error_logs_YYYYMMDD.json
    - Any other archived JSON files with date patterns
    
    Args:
        days_old: Number of days to keep files (default: 30)
        
    Returns:
        Number of files removed
    """
    removed_count = 0
    cutoff_date = datetime.now() - timedelta(days=days_old)
    
    # Define patterns for archived JSON files
    json_patterns = [
        "error_logs_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json",  # error_logs_YYYYMMDD.json
        "*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9].json",           # Any file with YYYYMMDD pattern
        "*_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json",         # Any file with YYYY-MM-DD pattern
    ]
    
    for pattern in json_patterns:
        for json_file in glob.glob(pattern):
            try:
                json_path = Path(json_file)
                
                # Get file modification time
                file_mtime = datetime.fromtimestamp(json_path.stat().st_mtime)
                
                if file_mtime < cutoff_date:
                    file_size = json_path.stat().st_size
                    json_path.unlink()
                    removed_count += 1
                    logger.info(f"Removed old archived JSON: {json_path} (size: {file_size} bytes, age: {(datetime.now() - file_mtime).days} days)")
                    
            except Exception as e:
                logger.error(f"Failed to process JSON file {json_file}: {e}")
    
    return removed_count


def cleanup_temp_files() -> int:
    """
    Remove temporary files that might accumulate.
    
    Returns:
        Number of files removed
    """
    removed_count = 0
    
    # Define temporary file patterns
    temp_patterns = [
        "*.tmp",
        "*.temp", 
        ".DS_Store",
        "Thumbs.db",
        "*.log.lock",  # Log file locks
        "*.log.tmp",   # Temporary log files
    ]
    
    for pattern in temp_patterns:
        for temp_file in glob.glob(pattern):
            try:
                temp_path = Path(temp_file)
                file_size = temp_path.stat().st_size
                temp_path.unlink()
                removed_count += 1
                logger.info(f"Removed temporary file: {temp_path} (size: {file_size} bytes)")
                
            except Exception as e:
                logger.error(f"Failed to remove temporary file {temp_file}: {e}")
    
    return removed_count


def get_directory_size(directory: Path) -> int:
    """
    Calculate total size of a directory.
    
    Args:
        directory: Path to directory
        
    Returns:
        Total size in bytes
    """
    total_size = 0
    try:
        for file_path in directory.rglob('*'):
            if file_path.is_file():
                total_size += file_path.stat().st_size
    except Exception as e:
        logger.error(f"Error calculating directory size for {directory}: {e}")
    
    return total_size


def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def main():
    """Main cleanup function."""
    logger.info("=" * 60)
    logger.info("Starting log cleanup process")
    logger.info(f"Cleanup started at: {datetime.now().isoformat()}")
    
    # Get initial directory sizes
    logs_dir = Path("logs")
    initial_logs_size = get_directory_size(logs_dir) if logs_dir.exists() else 0
    initial_root_size = sum(
        Path(f).stat().st_size for f in glob.glob("*.json") + glob.glob("*.log")
        if Path(f).is_file()
    )
    
    logger.info(f"Initial logs directory size: {format_size(initial_logs_size)}")
    logger.info(f"Initial root directory relevant files size: {format_size(initial_root_size)}")
    
    try:
        # Perform cleanup operations
        log_files_removed = cleanup_old_log_files(days_old=30)
        json_files_removed = cleanup_archived_json_files(days_old=30)
        temp_files_removed = cleanup_temp_files()
        
        total_removed = log_files_removed + json_files_removed + temp_files_removed
        
        # Get final directory sizes
        final_logs_size = get_directory_size(logs_dir) if logs_dir.exists() else 0
        final_root_size = sum(
            Path(f).stat().st_size for f in glob.glob("*.json") + glob.glob("*.log")
            if Path(f).is_file()
        )
        
        # Calculate space saved
        space_saved_logs = initial_logs_size - final_logs_size
        space_saved_root = initial_root_size - final_root_size
        total_space_saved = space_saved_logs + space_saved_root
        
        # Log summary
        logger.info("=" * 60)
        logger.info("Cleanup Summary:")
        logger.info(f"Log files removed: {log_files_removed}")
        logger.info(f"Archived JSON files removed: {json_files_removed}")
        logger.info(f"Temporary files removed: {temp_files_removed}")
        logger.info(f"Total files removed: {total_removed}")
        logger.info(f"Space saved: {format_size(total_space_saved)}")
        logger.info(f"Final logs directory size: {format_size(final_logs_size)}")
        logger.info(f"Cleanup completed at: {datetime.now().isoformat()}")
        logger.info("=" * 60)
        
        # Exit with appropriate code
        if total_removed > 0:
            logger.info("✅ Cleanup completed successfully with files removed")
            sys.exit(0)
        else:
            logger.info("✅ Cleanup completed - no files needed removal")
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"❌ Cleanup failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
