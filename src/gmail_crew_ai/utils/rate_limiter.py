"""Rate limiter for CrewAI to prevent API rate limits."""

import os
import time
import json
from datetime import datetime, timedelta
from typing import Dict


class RateLimiter:
    """Intelligent rate limiter for API calls."""
    
    def __init__(self, max_tokens_per_minute: int = 20000):
        self.max_tokens_per_minute = max_tokens_per_minute
        self.usage_window = []  # Track usage in sliding window
        self.usage_file = "rate_limiter_usage.json"
        
    def load_recent_usage(self):
        """Load recent API usage from file."""
        try:
            if os.path.exists(self.usage_file):
                with open(self.usage_file, 'r') as f:
                    data = json.load(f)
                # Filter to last minute
                cutoff = datetime.now() - timedelta(minutes=1)
                self.usage_window = [
                    entry for entry in data 
                    if datetime.fromisoformat(entry['timestamp']) > cutoff
                ]
        except:
            self.usage_window = []
    
    def save_usage(self):
        """Save current usage window."""
        try:
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_window, f)
        except:
            pass
    
    def get_current_usage(self) -> int:
        """Get token usage in current minute."""
        self.load_recent_usage()
        return sum(entry.get('tokens', 0) for entry in self.usage_window)
    
    def can_make_request(self, estimated_tokens: int) -> bool:
        """Check if request can be made without hitting rate limit."""
        current_usage = self.get_current_usage()
        return (current_usage + estimated_tokens) <= self.max_tokens_per_minute
    
    def wait_if_needed(self, estimated_tokens: int = 5000):
        """Wait if needed to avoid rate limits."""
        current_usage = self.get_current_usage()
        
        if (current_usage + estimated_tokens) > self.max_tokens_per_minute:
            # Calculate wait time based on oldest entry in window
            if self.usage_window:
                oldest_entry = min(self.usage_window, key=lambda x: x['timestamp'])
                oldest_time = datetime.fromisoformat(oldest_entry['timestamp'])
                wait_until = oldest_time + timedelta(minutes=1)
                wait_seconds = max(0, (wait_until - datetime.now()).total_seconds())
                
                if wait_seconds > 0:
                    print(f"⏳ Rate limit protection: waiting {wait_seconds:.1f} seconds...")
                    time.sleep(wait_seconds)
    
    def record_usage(self, tokens_used: int):
        """Record API usage."""
        self.usage_window.append({
            'timestamp': datetime.now().isoformat(),
            'tokens': tokens_used
        })
        self.save_usage()
    
    def get_usage_stats(self) -> Dict:
        """Get current usage statistics."""
        self.load_recent_usage()
        current_usage = sum(entry.get('tokens', 0) for entry in self.usage_window)
        
        return {
            'current_usage': current_usage,
            'max_limit': self.max_tokens_per_minute,
            'percentage_used': (current_usage / self.max_tokens_per_minute) * 100,
            'requests_in_window': len(self.usage_window),
            'can_make_request': current_usage < self.max_tokens_per_minute * 0.8  # 80% threshold
        }


# Global rate limiter instance
rate_limiter = RateLimiter(max_tokens_per_minute=20000)  # Conservative limit