"""Data models for subscription and billing management."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum
import os


class SubscriptionStatus(Enum):
    """Subscription status enumeration."""
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"


class PlanType(Enum):
    """Subscription plan types."""
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


@dataclass
class SubscriptionPlan:
    """Subscription plan configuration."""
    plan_type: PlanType
    name: str
    price: float
    currency: str
    daily_email_limit: int
    stripe_price_id: Optional[str] = None
    features: List[str] = None
    
    def __post_init__(self):
        if self.features is None:
            self.features = []


@dataclass
class UserSubscription:
    """User subscription information."""
    user_id: str
    stripe_customer_id: Optional[str]
    stripe_subscription_id: Optional[str]
    plan_type: PlanType
    status: SubscriptionStatus
    current_period_start: Optional[datetime]
    current_period_end: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    canceled_at: Optional[datetime] = None
    trial_end: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            'user_id': self.user_id,
            'stripe_customer_id': self.stripe_customer_id,
            'stripe_subscription_id': self.stripe_subscription_id,
            'plan_type': self.plan_type.value,
            'status': self.status.value,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'canceled_at': self.canceled_at.isoformat() if self.canceled_at else None,
            'trial_end': self.trial_end.isoformat() if self.trial_end else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UserSubscription':
        """Create from dictionary."""
        return cls(
            user_id=data['user_id'],
            stripe_customer_id=data.get('stripe_customer_id'),
            stripe_subscription_id=data.get('stripe_subscription_id'),
            plan_type=PlanType(data['plan_type']),
            status=SubscriptionStatus(data['status']),
            current_period_start=datetime.fromisoformat(data['current_period_start']) if data.get('current_period_start') else None,
            current_period_end=datetime.fromisoformat(data['current_period_end']) if data.get('current_period_end') else None,
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at']),
            canceled_at=datetime.fromisoformat(data['canceled_at']) if data.get('canceled_at') else None,
            trial_end=datetime.fromisoformat(data['trial_end']) if data.get('trial_end') else None
        )


@dataclass
class UsageRecord:
    """Daily usage record for a user."""
    user_id: str
    date: str  # YYYY-MM-DD format
    emails_processed: int
    daily_limit: int
    plan_type: PlanType
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage."""
        return {
            'user_id': self.user_id,
            'date': self.date,
            'emails_processed': self.emails_processed,
            'daily_limit': self.daily_limit,
            'plan_type': self.plan_type.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'UsageRecord':
        """Create from dictionary."""
        return cls(
            user_id=data['user_id'],
            date=data['date'],
            emails_processed=data['emails_processed'],
            daily_limit=data['daily_limit'],
            plan_type=PlanType(data['plan_type']),
            created_at=datetime.fromisoformat(data['created_at']),
            updated_at=datetime.fromisoformat(data['updated_at'])
        )


# Predefined subscription plans
SUBSCRIPTION_PLANS = {
    PlanType.FREE: SubscriptionPlan(
        plan_type=PlanType.FREE,
        name="Free",
        price=0.0,
        currency="usd",
        daily_email_limit=10,
        features=[
            "10 emails processed per day",
            "Basic email categorization",
            "Standard Gmail integration"
        ]
    ),
    PlanType.BASIC: SubscriptionPlan(
        plan_type=PlanType.BASIC,
        name="Basic",
        price=9.99,
        currency="usd",
        daily_email_limit=100,
        stripe_price_id=os.getenv('STRIPE_BASIC_PRICE_ID', 'price_basic_monthly'),
        features=[
            "100 emails processed per day",
            "Advanced email categorization",
            "Automated responses",
            "Slack notifications",
            "Email cleanup"
        ]
    ),
    PlanType.PREMIUM: SubscriptionPlan(
        plan_type=PlanType.PREMIUM,
        name="Premium",
        price=29.99,
        currency="usd",
        daily_email_limit=1000,
        stripe_price_id=os.getenv('STRIPE_PREMIUM_PRICE_ID', 'price_premium_monthly'),
        features=[
            "1000 emails processed per day",
            "Advanced email categorization",
            "Automated responses",
            "Slack notifications",
            "Email cleanup",
            "Priority support",
            "Custom email rules",
            "Analytics dashboard"
        ]
    )
}
