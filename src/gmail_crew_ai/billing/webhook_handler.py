"""Webhook handler for Stripe subscription events."""

import json
import os
from typing import Dict, Any
import stripe
from datetime import datetime
from .models import SubscriptionStatus, PlanType
from .subscription_manager import SubscriptionManager


class StripeWebhookHandler:
    """Handles Stripe webhook events for subscription management."""
    
    def __init__(self, subscription_manager: SubscriptionManager):
        self.subscription_manager = subscription_manager
        self.webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
    
    def verify_webhook_signature(self, payload: str, sig_header: str) -> bool:
        """Verify webhook signature for security."""
        try:
            stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return True
        except ValueError:
            # Invalid payload
            return False
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            return False
    
    def handle_webhook_event(self, payload: Dict[str, Any]) -> bool:
        """Handle incoming webhook events from Stripe."""
        event_type = payload.get('type')
        data = payload.get('data', {})
        obj = data.get('object', {})
        
        try:
            if event_type == 'customer.subscription.created':
                return self._handle_subscription_created(obj)
            
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(obj)
            
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(obj)
            
            elif event_type == 'invoice.payment_succeeded':
                return self._handle_payment_succeeded(obj)
            
            elif event_type == 'invoice.payment_failed':
                return self._handle_payment_failed(obj)
            
            else:
                print(f"Unhandled webhook event type: {event_type}")
                return True  # Return True for unknown events to acknowledge receipt
                
        except Exception as e:
            print(f"Error handling webhook event {event_type}: {e}")
            return False
    
    def _handle_subscription_created(self, subscription: Dict[str, Any]) -> bool:
        """Handle subscription creation event."""
        try:
            customer_id = subscription.get('customer')
            subscription_id = subscription.get('id')
            status = subscription.get('status')
            
            # Find user by customer ID
            user_subscription = self._find_user_by_customer_id(customer_id)
            if not user_subscription:
                print(f"No user found for customer ID: {customer_id}")
                return False
            
            # Update subscription details
            user_subscription.stripe_subscription_id = subscription_id
            user_subscription.status = SubscriptionStatus(status)
            user_subscription.current_period_start = datetime.fromtimestamp(subscription.get('current_period_start', 0))
            user_subscription.current_period_end = datetime.fromtimestamp(subscription.get('current_period_end', 0))
            user_subscription.updated_at = datetime.now()
            
            # Determine plan type from price ID
            items = subscription.get('items', {}).get('data', [])
            if items:
                price_id = items[0].get('price', {}).get('id')
                user_subscription.plan_type = self._get_plan_type_from_price_id(price_id)
            
            self.subscription_manager.save_user_subscription(user_subscription)
            print(f"Subscription created for user: {user_subscription.user_id}")
            return True
            
        except Exception as e:
            print(f"Error handling subscription created: {e}")
            return False
    
    def _handle_subscription_updated(self, subscription: Dict[str, Any]) -> bool:
        """Handle subscription update event."""
        try:
            subscription_id = subscription.get('id')
            status = subscription.get('status')
            
            # Find user by subscription ID
            user_subscription = self._find_user_by_subscription_id(subscription_id)
            if not user_subscription:
                print(f"No user found for subscription ID: {subscription_id}")
                return False
            
            # Update subscription details
            user_subscription.status = SubscriptionStatus(status)
            user_subscription.current_period_start = datetime.fromtimestamp(subscription.get('current_period_start', 0))
            user_subscription.current_period_end = datetime.fromtimestamp(subscription.get('current_period_end', 0))
            user_subscription.updated_at = datetime.now()
            
            # Check if subscription was canceled
            if status == 'canceled':
                user_subscription.canceled_at = datetime.now()
            
            self.subscription_manager.save_user_subscription(user_subscription)
            print(f"Subscription updated for user: {user_subscription.user_id}")
            return True
            
        except Exception as e:
            print(f"Error handling subscription updated: {e}")
            return False
    
    def _handle_subscription_deleted(self, subscription: Dict[str, Any]) -> bool:
        """Handle subscription deletion event."""
        try:
            subscription_id = subscription.get('id')
            
            # Find user by subscription ID
            user_subscription = self._find_user_by_subscription_id(subscription_id)
            if not user_subscription:
                print(f"No user found for subscription ID: {subscription_id}")
                return False
            
            # Update subscription to canceled
            user_subscription.status = SubscriptionStatus.CANCELED
            user_subscription.canceled_at = datetime.now()
            user_subscription.updated_at = datetime.now()
            
            # Revert to free plan
            user_subscription.plan_type = PlanType.FREE
            
            self.subscription_manager.save_user_subscription(user_subscription)
            print(f"Subscription deleted for user: {user_subscription.user_id}")
            return True
            
        except Exception as e:
            print(f"Error handling subscription deleted: {e}")
            return False
    
    def _handle_payment_succeeded(self, invoice: Dict[str, Any]) -> bool:
        """Handle successful payment event."""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return True  # Not a subscription invoice
            
            # Find user by subscription ID
            user_subscription = self._find_user_by_subscription_id(subscription_id)
            if not user_subscription:
                print(f"No user found for subscription ID: {subscription_id}")
                return False
            
            # Update subscription status to active if payment succeeded
            user_subscription.status = SubscriptionStatus.ACTIVE
            user_subscription.updated_at = datetime.now()
            
            self.subscription_manager.save_user_subscription(user_subscription)
            print(f"Payment succeeded for user: {user_subscription.user_id}")
            return True
            
        except Exception as e:
            print(f"Error handling payment succeeded: {e}")
            return False
    
    def _handle_payment_failed(self, invoice: Dict[str, Any]) -> bool:
        """Handle failed payment event."""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return True  # Not a subscription invoice
            
            # Find user by subscription ID
            user_subscription = self._find_user_by_subscription_id(subscription_id)
            if not user_subscription:
                print(f"No user found for subscription ID: {subscription_id}")
                return False
            
            # Update subscription status to past due
            user_subscription.status = SubscriptionStatus.PAST_DUE
            user_subscription.updated_at = datetime.now()
            
            self.subscription_manager.save_user_subscription(user_subscription)
            print(f"Payment failed for user: {user_subscription.user_id}")
            return True
            
        except Exception as e:
            print(f"Error handling payment failed: {e}")
            return False
    
    def _find_user_by_customer_id(self, customer_id: str):
        """Find user subscription by Stripe customer ID."""
        subscriptions = self.subscription_manager.get_all_subscriptions()
        for sub in subscriptions:
            if sub.stripe_customer_id == customer_id:
                return sub
        return None
    
    def _find_user_by_subscription_id(self, subscription_id: str):
        """Find user subscription by Stripe subscription ID."""
        subscriptions = self.subscription_manager.get_all_subscriptions()
        for sub in subscriptions:
            if sub.stripe_subscription_id == subscription_id:
                return sub
        return None
    
    def _get_plan_type_from_price_id(self, price_id: str) -> PlanType:
        """Determine plan type from Stripe price ID."""
        basic_price_id = os.getenv('STRIPE_BASIC_PRICE_ID', 'price_basic_monthly')
        premium_price_id = os.getenv('STRIPE_PREMIUM_PRICE_ID', 'price_premium_monthly')
        
        if price_id == basic_price_id:
            return PlanType.BASIC
        elif price_id == premium_price_id:
            return PlanType.PREMIUM
        else:
            return PlanType.FREE
