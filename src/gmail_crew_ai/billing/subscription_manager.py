"""Subscription Manager for handling subscription logic and database operations."""

import json
import os
from typing import Dict, Optional, List
from datetime import datetime
import stripe
from .models import UserSubscription, SubscriptionStatus, PlanType, SUBSCRIPTION_PLANS
from .stripe_service import StripeService


class SubscriptionManager:
    """Manages user subscriptions and database operations."""
    
    def __init__(self, stripe_service: StripeService):
        self.stripe_service = stripe_service
        self.subscriptions_file = "subscriptions.json"
        self.ensure_subscriptions_file()
    
    def ensure_subscriptions_file(self):
        """Ensure subscriptions file exists."""
        if not os.path.exists(self.subscriptions_file):
            self.save_subscriptions({})
    
    def load_subscriptions(self) -> Dict:
        """Load subscriptions from file."""
        try:
            with open(self.subscriptions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def save_subscriptions(self, subscriptions: Dict):
        """Save subscriptions to file."""
        try:
            with open(self.subscriptions_file, 'w', encoding='utf-8') as f:
                json.dump(subscriptions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving subscriptions: {e}")
    
    def get_user_subscription(self, user_id: str) -> Optional[UserSubscription]:
        """Get user subscription by user ID."""
        subscriptions = self.load_subscriptions()
        if user_id in subscriptions:
            return UserSubscription.from_dict(subscriptions[user_id])
        return None
    
    def create_user_subscription(self, user_id: str, email: str, plan_type: PlanType = PlanType.FREE) -> UserSubscription:
        """Create a new user subscription."""
        subscription = UserSubscription(
            user_id=user_id,
            stripe_customer_id=None,
            stripe_subscription_id=None,
            plan_type=plan_type,
            status=SubscriptionStatus.ACTIVE if plan_type == PlanType.FREE else SubscriptionStatus.INCOMPLETE,
            current_period_start=datetime.now() if plan_type == PlanType.FREE else None,
            current_period_end=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # For paid plans, create Stripe customer and subscription
        if plan_type != PlanType.FREE:
            try:
                customer = self.stripe_service.create_customer(email)
                subscription.stripe_customer_id = customer.id
                
                stripe_subscription = self.stripe_service.create_subscription(customer.id, plan_type)
                subscription.stripe_subscription_id = stripe_subscription.id
                
                # Update subscription status based on Stripe response
                self.stripe_service.update_subscription_status(stripe_subscription, subscription)
                
            except Exception as e:
                print(f"Error creating Stripe subscription: {e}")
                # Fall back to free plan if Stripe fails
                subscription.plan_type = PlanType.FREE
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.current_period_start = datetime.now()
        
        self.save_user_subscription(subscription)
        return subscription
    
    def save_user_subscription(self, subscription: UserSubscription):
        """Save user subscription to database."""
        subscriptions = self.load_subscriptions()
        subscriptions[subscription.user_id] = subscription.to_dict()
        self.save_subscriptions(subscriptions)
    
    def upgrade_subscription(self, user_id: str, new_plan_type: PlanType) -> bool:
        """Upgrade user subscription to a new plan."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        try:
            # Cancel existing subscription if it exists
            if subscription.stripe_subscription_id:
                self.stripe_service.cancel_subscription(subscription.stripe_subscription_id)
            
            # Create new subscription
            if new_plan_type != PlanType.FREE:
                stripe_subscription = self.stripe_service.create_subscription(
                    subscription.stripe_customer_id, 
                    new_plan_type
                )
                subscription.stripe_subscription_id = stripe_subscription.id
                self.stripe_service.update_subscription_status(stripe_subscription, subscription)
            else:
                subscription.stripe_subscription_id = None
                subscription.status = SubscriptionStatus.ACTIVE
                subscription.current_period_start = datetime.now()
                subscription.current_period_end = None
            
            subscription.plan_type = new_plan_type
            subscription.updated_at = datetime.now()
            self.save_user_subscription(subscription)
            return True
            
        except Exception as e:
            print(f"Error upgrading subscription: {e}")
            return False
    
    def cancel_subscription(self, user_id: str) -> bool:
        """Cancel user subscription."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return False
        
        try:
            if subscription.stripe_subscription_id:
                self.stripe_service.cancel_subscription(subscription.stripe_subscription_id)
            
            subscription.status = SubscriptionStatus.CANCELED
            subscription.canceled_at = datetime.now()
            subscription.updated_at = datetime.now()
            self.save_user_subscription(subscription)
            return True
            
        except Exception as e:
            print(f"Error canceling subscription: {e}")
            return False
    
    def get_user_daily_limit(self, user_id: str) -> int:
        """Get user's daily email processing limit."""
        subscription = self.get_user_subscription(user_id)
        if not subscription or subscription.status != SubscriptionStatus.ACTIVE:
            return SUBSCRIPTION_PLANS[PlanType.FREE].daily_email_limit
        
        return SUBSCRIPTION_PLANS[subscription.plan_type].daily_email_limit
    
    def is_subscription_active(self, user_id: str) -> bool:
        """Check if user has an active subscription."""
        subscription = self.get_user_subscription(user_id)
        return subscription is not None and subscription.status == SubscriptionStatus.ACTIVE
    
    def get_subscription_plan_name(self, user_id: str) -> str:
        """Get user's subscription plan name."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return SUBSCRIPTION_PLANS[PlanType.FREE].name
        
        return SUBSCRIPTION_PLANS[subscription.plan_type].name
    
    def sync_with_stripe(self, user_id: str) -> bool:
        """Sync user subscription with Stripe."""
        subscription = self.get_user_subscription(user_id)
        if not subscription or not subscription.stripe_subscription_id:
            return False
        
        try:
            stripe_subscription = self.stripe_service.retrieve_subscription(subscription.stripe_subscription_id)
            self.stripe_service.update_subscription_status(stripe_subscription, subscription)
            self.save_user_subscription(subscription)
            return True
            
        except Exception as e:
            print(f"Error syncing with Stripe: {e}")
            return False
    
    def get_all_subscriptions(self) -> List[UserSubscription]:
        """Get all user subscriptions."""
        subscriptions = self.load_subscriptions()
        return [UserSubscription.from_dict(data) for data in subscriptions.values()]
    
    def create_checkout_session(self, user_id: str, plan_type: PlanType, success_url: str, cancel_url: str) -> str:
        """Create Stripe checkout session for subscription."""
        subscription = self.get_user_subscription(user_id)
        if not subscription:
            return ""
        
        try:
            plan = SUBSCRIPTION_PLANS[plan_type]
            
            session = stripe.checkout.Session.create(
                customer=subscription.stripe_customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': plan.stripe_price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=user_id
            )
            
            return session.url
            
        except Exception as e:
            print(f"Error creating checkout session: {e}")
            return ""
