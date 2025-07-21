"""Stripe Service for handling subscriptions and payments."""

import stripe
from typing import Dict, Optional
from .models import UserSubscription, SubscriptionStatus, PlanType, SUBSCRIPTION_PLANS
from datetime import datetime


class StripeService:
    """Service class to handle Stripe customer and subscription management."""

    def __init__(self, api_key: str):
        stripe.api_key = api_key

    def create_customer(self, email: str) -> stripe.Customer:
        """Create a new Stripe customer."""
        return stripe.Customer.create(email=email)

    def create_subscription(self, customer_id: str, plan_type: PlanType) -> stripe.Subscription:
        """Create a subscription for a customer."""
        plan = SUBSCRIPTION_PLANS[plan_type]
        return stripe.Subscription.create(
            customer=customer_id,
            items=[{
                'price': plan.stripe_price_id
            }],
            expand=['latest_invoice.payment_intent']
        )

    def cancel_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Cancel a subscription."""
        return stripe.Subscription.delete(subscription_id)

    def retrieve_subscription(self, subscription_id: str) -> stripe.Subscription:
        """Retrieve subscription details."""
        return stripe.Subscription.retrieve(subscription_id)

    def update_subscription_status(self, subscription: stripe.Subscription, user_subscription: UserSubscription) -> None:
        """Update the user subscription status based on Stripe subscription data."""
        user_subscription.status = SubscriptionStatus(subscription.status)
        user_subscription.current_period_start = datetime.fromtimestamp(subscription.current_period_start)
        user_subscription.current_period_end = datetime.fromtimestamp(subscription.current_period_end)
        user_subscription.updated_at = datetime.now()


# Usage Example (Don't forget to replace '{{{STRIPE_API_KEY}}}' with your actual API key):
# stripe_service = StripeService('{{{STRIPE_API_KEY}}}')
# customer = stripe_service.create_customer('user@example.com')
# subscription = stripe_service.create_subscription(customer.id, PlanType.BASIC)

