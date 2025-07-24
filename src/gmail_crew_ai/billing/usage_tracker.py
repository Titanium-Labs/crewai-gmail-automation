"""Usage Tracker for monitoring email processing limits."""

import json
import os
from datetime import datetime, date
from typing import Dict
from .models import UsageRecord, PlanType


class UsageTracker:
    """Tracks user email processing usage."""

    def __init__(self):
        self.usage_file = "usage.json"
        self.ensure_usage_file()

    def ensure_usage_file(self):
        """Ensure usage file exists."""
        if not os.path.exists(self.usage_file):
            self.save_usage({})

    def load_usage(self) -> Dict:
        """Load usage records from file."""
        try:
            with open(self.usage_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def save_usage(self, usage: Dict):
        """Save usage records to file."""
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(usage, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving usage: {e}")

    def record_usage(self, user_id: str, plan_type: PlanType, emails_processed: int, user_manager=None):
        """Record usage for a user."""
        usage = self.load_usage()
        today_str = date.today().isoformat()

        if user_id not in usage:
            usage[user_id] = {}

        if today_str not in usage[user_id]:
            # Set daily limit (unlimited for admins)
            daily_limit = self.determine_daily_limit(plan_type)
            if user_manager and user_manager.is_admin(user_id):
                daily_limit = 999999  # Effectively unlimited
                
            usage[user_id][today_str] = UsageRecord(
                user_id=user_id,
                date=today_str,
                emails_processed=0,
                daily_limit=daily_limit,
                plan_type=plan_type,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ).to_dict()

        record = UsageRecord.from_dict(usage[user_id][today_str])
        record.emails_processed += emails_processed
        
        # Ensure daily limit is set correctly (including for admin users)
        if not record.daily_limit or record.daily_limit == 0:
            record.daily_limit = self.determine_daily_limit(plan_type)
            if user_manager and user_manager.is_admin(user_id):
                record.daily_limit = 999999  # Effectively unlimited
                
        record.updated_at = datetime.now()

        usage[user_id][today_str] = record.to_dict()
        self.save_usage(usage)

    def determine_daily_limit(self, plan_type: PlanType) -> int:
        """Determine daily limit based on plan type."""
        from .models import SUBSCRIPTION_PLANS
        
        try:
            return SUBSCRIPTION_PLANS[plan_type].daily_email_limit
        except KeyError:
            # Try to find the plan by value if direct key lookup fails
            for plan_key, plan_info in SUBSCRIPTION_PLANS.items():
                if plan_key.value == plan_type.value:
                    return plan_info.daily_email_limit
            
            # Fallback to FREE plan limit
            return 10  # Default FREE plan limit

    def get_usage_for_today(self, user_id: str, user_manager=None) -> UsageRecord:
        """Get today's usage record for a user."""
        usage = self.load_usage()
        today_str = date.today().isoformat()

        if user_id in usage and today_str in usage[user_id]:
            record = UsageRecord.from_dict(usage[user_id][today_str])
            # Set unlimited limit for admin users
            if user_manager and user_manager.is_admin(user_id):
                record.daily_limit = 999999  # Effectively unlimited
            return record

        # Create new record - set unlimited limit for admin users
        daily_limit = self.determine_daily_limit(PlanType.FREE)
        if user_manager and user_manager.is_admin(user_id):
            daily_limit = 999999  # Effectively unlimited
            
        return UsageRecord(
            user_id=user_id,
            date=today_str,
            emails_processed=0,
            daily_limit=daily_limit,
            plan_type=PlanType.FREE,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    def can_process_more_emails(self, user_id: str, user_manager=None) -> bool:
        """Check if user can process more emails today."""
        # Check if user is admin (unlimited emails)
        if user_manager and user_manager.is_admin(user_id):
            return True
        
        usage_record = self.get_usage_for_today(user_id)
        return usage_record.emails_processed < usage_record.daily_limit

