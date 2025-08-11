"""Email tracking system to prevent duplicate processing."""

import json
import os
from datetime import datetime, timedelta
from typing import Set, Dict, List, Optional
from pathlib import Path
import threading


class EmailTracker:
    """Tracks processed email IDs to prevent duplicate processing."""
    
    def __init__(self, user_id: str, tracking_file: Optional[str] = None):
        """
        Initialize email tracker for a specific user.
        
        Args:
            user_id: Unique identifier for the user
            tracking_file: Optional custom path for tracking file
        """
        self.user_id = user_id
        self.lock = threading.Lock()
        
        # Set tracking file path
        if tracking_file:
            self.tracking_file = tracking_file
        else:
            # Default to data directory structure
            if os.path.exists("/app/data"):
                self.tracking_file = f"/app/data/tracking/email_tracking_{user_id}.json"
            else:
                self.tracking_file = f"tracking/email_tracking_{user_id}.json"
        
        # Ensure tracking directory exists
        Path(os.path.dirname(self.tracking_file)).mkdir(parents=True, exist_ok=True)
        
        # Load existing tracking data
        self.tracking_data = self._load_tracking_data()
    
    def _load_tracking_data(self) -> Dict:
        """Load existing tracking data from file."""
        if os.path.exists(self.tracking_file):
            try:
                with open(self.tracking_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                # If file is corrupted, start fresh
                return self._get_default_data()
        return self._get_default_data()
    
    def _get_default_data(self) -> Dict:
        """Get default tracking data structure."""
        return {
            "user_id": self.user_id,
            "processed_emails": {},  # email_id -> processing info
            "last_updated": None,
            "statistics": {
                "total_processed": 0,
                "duplicates_skipped": 0,
                "last_cleanup": None
            }
        }
    
    def _save_tracking_data(self) -> None:
        """Save tracking data to file."""
        with self.lock:
            self.tracking_data["last_updated"] = datetime.now().isoformat()
            try:
                with open(self.tracking_file, 'w') as f:
                    json.dump(self.tracking_data, f, indent=2)
            except IOError as e:
                print(f"Warning: Could not save tracking data: {e}")
    
    def is_processed(self, email_id: str) -> bool:
        """
        Check if an email has already been processed.
        
        Args:
            email_id: Gmail email ID
            
        Returns:
            True if email was already processed, False otherwise
        """
        return email_id in self.tracking_data["processed_emails"]
    
    def mark_as_processed(self, email_id: str, metadata: Optional[Dict] = None) -> None:
        """
        Mark an email as processed.
        
        Args:
            email_id: Gmail email ID
            metadata: Optional metadata about the processing
        """
        with self.lock:
            if email_id not in self.tracking_data["processed_emails"]:
                self.tracking_data["statistics"]["total_processed"] += 1
            
            self.tracking_data["processed_emails"][email_id] = {
                "processed_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            self._save_tracking_data()
    
    def mark_batch_as_processed(self, email_ids: List[str], metadata: Optional[Dict] = None) -> None:
        """
        Mark multiple emails as processed in a single operation.
        
        Args:
            email_ids: List of Gmail email IDs
            metadata: Optional metadata about the processing
        """
        with self.lock:
            timestamp = datetime.now().isoformat()
            for email_id in email_ids:
                if email_id not in self.tracking_data["processed_emails"]:
                    self.tracking_data["statistics"]["total_processed"] += 1
                
                self.tracking_data["processed_emails"][email_id] = {
                    "processed_at": timestamp,
                    "metadata": metadata or {}
                }
            self._save_tracking_data()
    
    def filter_unprocessed(self, email_ids: List[str]) -> List[str]:
        """
        Filter a list of email IDs to return only unprocessed ones.
        
        Args:
            email_ids: List of Gmail email IDs to check
            
        Returns:
            List of email IDs that haven't been processed yet
        """
        unprocessed = []
        for email_id in email_ids:
            if not self.is_processed(email_id):
                unprocessed.append(email_id)
            else:
                self.tracking_data["statistics"]["duplicates_skipped"] += 1
        
        if self.tracking_data["statistics"]["duplicates_skipped"] > 0:
            self._save_tracking_data()
        
        return unprocessed
    
    def cleanup_old_entries(self, days_to_keep: int = 30) -> int:
        """
        Remove tracking entries older than specified days.
        
        Args:
            days_to_keep: Number of days to keep tracking data
            
        Returns:
            Number of entries removed
        """
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        emails_to_remove = []
        
        with self.lock:
            for email_id, info in self.tracking_data["processed_emails"].items():
                try:
                    processed_date = datetime.fromisoformat(info["processed_at"])
                    if processed_date < cutoff_date:
                        emails_to_remove.append(email_id)
                except (KeyError, ValueError):
                    # If date is missing or invalid, mark for removal
                    emails_to_remove.append(email_id)
            
            # Remove old entries
            for email_id in emails_to_remove:
                del self.tracking_data["processed_emails"][email_id]
            
            if emails_to_remove:
                self.tracking_data["statistics"]["last_cleanup"] = datetime.now().isoformat()
                self._save_tracking_data()
        
        return len(emails_to_remove)
    
    def get_statistics(self) -> Dict:
        """
        Get tracking statistics.
        
        Returns:
            Dictionary with tracking statistics
        """
        return {
            "user_id": self.user_id,
            "total_tracked": len(self.tracking_data["processed_emails"]),
            "total_processed": self.tracking_data["statistics"]["total_processed"],
            "duplicates_skipped": self.tracking_data["statistics"]["duplicates_skipped"],
            "last_updated": self.tracking_data.get("last_updated"),
            "last_cleanup": self.tracking_data["statistics"].get("last_cleanup")
        }
    
    def reset(self) -> None:
        """Reset all tracking data for this user."""
        with self.lock:
            self.tracking_data = self._get_default_data()
            self._save_tracking_data()
    
    def get_processed_emails_since(self, since_date: datetime) -> List[str]:
        """
        Get list of email IDs processed since a specific date.
        
        Args:
            since_date: Date to check from
            
        Returns:
            List of email IDs processed since the date
        """
        processed_since = []
        
        for email_id, info in self.tracking_data["processed_emails"].items():
            try:
                processed_date = datetime.fromisoformat(info["processed_at"])
                if processed_date >= since_date:
                    processed_since.append(email_id)
            except (KeyError, ValueError):
                continue
        
        return processed_since