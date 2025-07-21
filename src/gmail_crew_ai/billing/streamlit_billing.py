"""Streamlit billing interface components."""

import streamlit as st
from typing import Optional
from .models import PlanType, SUBSCRIPTION_PLANS, UserSubscription
from .subscription_manager import SubscriptionManager
from .usage_tracker import UsageTracker


def show_subscription_status(subscription_manager: SubscriptionManager, user_id: str):
    """Show current subscription status."""
    subscription = subscription_manager.get_user_subscription(user_id)
    
    if not subscription:
        st.error("❌ No subscription found")
        return
    
    plan = SUBSCRIPTION_PLANS[subscription.plan_type]
    
    # Current Plan Card
    st.markdown("### 📋 Current Plan")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Plan", plan.name)
    
    with col2:
        price_display = "Free" if plan.price == 0 else f"${plan.price}/month"
        st.metric("Price", price_display)
    
    with col3:
        st.metric("Email Limit", f"{plan.daily_email_limit}/day")
    
    # Subscription Details
    st.markdown("### 📊 Subscription Details")
    
    status_color = "🟢" if subscription.status.value == "active" else "🔴"
    st.markdown(f"**Status:** {status_color} {subscription.status.value.title()}")
    
    if subscription.current_period_start:
        st.markdown(f"**Period Start:** {subscription.current_period_start.strftime('%B %d, %Y')}")
    
    if subscription.current_period_end:
        st.markdown(f"**Period End:** {subscription.current_period_end.strftime('%B %d, %Y')}")
    
    if subscription.canceled_at:
        st.markdown(f"**Canceled:** {subscription.canceled_at.strftime('%B %d, %Y')}")


def show_usage_dashboard(usage_tracker: UsageTracker, user_id: str):
    """Show usage dashboard for the user."""
    usage_record = usage_tracker.get_usage_for_today(user_id)
    
    st.markdown("### 📈 Today's Usage")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Emails Processed", usage_record.emails_processed)
    
    with col2:
        st.metric("Daily Limit", usage_record.daily_limit)
    
    with col3:
        remaining = max(0, usage_record.daily_limit - usage_record.emails_processed)
        st.metric("Remaining", remaining)
    
    # Progress bar
    progress = min(1.0, usage_record.emails_processed / usage_record.daily_limit)
    st.progress(progress)
    
    # Usage status
    if usage_record.emails_processed >= usage_record.daily_limit:
        st.warning("⚠️ You've reached your daily email processing limit.")
    elif usage_record.emails_processed >= usage_record.daily_limit * 0.8:
        st.info("ℹ️ You're approaching your daily limit.")
    else:
        st.success("✅ You have plenty of emails remaining for today.")


def show_plan_comparison():
    """Show plan comparison table."""
    st.markdown("### 💰 Available Plans")
    
    plans = [SUBSCRIPTION_PLANS[plan_type] for plan_type in PlanType]
    
    # Create comparison table
    col1, col2, col3 = st.columns(3)
    
    for i, plan in enumerate(plans):
        with [col1, col2, col3][i]:
            # Plan card
            st.markdown(f"""
            <div style="border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin: 10px 0;">
                <h3 style="text-align: center; margin-top: 0;">{plan.name}</h3>
                <div style="text-align: center; font-size: 2rem; font-weight: bold; margin: 20px 0;">
                    {"Free" if plan.price == 0 else f"${plan.price}/month"}
                </div>
                <div style="text-align: center; margin: 15px 0;">
                    <strong>{plan.daily_email_limit} emails/day</strong>
                </div>
                <hr>
                <ul style="padding-left: 20px;">
            """, unsafe_allow_html=True)
            
            for feature in plan.features:
                st.markdown(f"• {feature}")
            
            st.markdown("</ul></div>", unsafe_allow_html=True)


def show_billing_management(subscription_manager: SubscriptionManager, user_id: str):
    """Show billing management interface."""
    subscription = subscription_manager.get_user_subscription(user_id)
    
    if not subscription:
        st.error("❌ No subscription found")
        return
    
    st.markdown("### ⚙️ Manage Subscription")
    
    current_plan = subscription.plan_type
    
    # Plan upgrade/downgrade
    st.markdown("#### Change Plan")
    
    plan_options = {
        PlanType.FREE: "Free - $0/month (10 emails/day)",
        PlanType.BASIC: "Basic - $9.99/month (100 emails/day)",
        PlanType.PREMIUM: "Premium - $29.99/month (1000 emails/day)"
    }
    
    new_plan = st.selectbox(
        "Select new plan:",
        options=list(PlanType),
        format_func=lambda x: plan_options[x],
        index=list(PlanType).index(current_plan)
    )
    
    if new_plan != current_plan:
        if st.button("💳 Update Plan", type="primary"):
            if new_plan == PlanType.FREE:
                # Direct downgrade to free
                if subscription_manager.upgrade_subscription(user_id, new_plan):
                    st.success("✅ Successfully downgraded to Free plan!")
                    st.rerun()
                else:
                    st.error("❌ Failed to update plan. Please try again.")
            else:
                # Redirect to Stripe for paid plans
                success_url = "http://localhost:8501?payment_success=true"
                cancel_url = "http://localhost:8501?payment_canceled=true"
                
                checkout_url = subscription_manager.create_checkout_session(
                    user_id, new_plan, success_url, cancel_url
                )
                
                if checkout_url:
                    st.markdown(f"[💳 Complete Payment on Stripe]({checkout_url})")
                    st.info("You'll be redirected to Stripe to complete the payment.")
                else:
                    st.error("❌ Failed to create checkout session. Please try again.")
    
    # Cancel subscription
    if subscription.plan_type != PlanType.FREE:
        st.markdown("#### Cancel Subscription")
        
        if st.button("🚫 Cancel Subscription", type="secondary"):
            if subscription_manager.cancel_subscription(user_id):
                st.success("✅ Subscription canceled successfully.")
                st.info("You'll continue to have access until the end of your current billing period.")
                st.rerun()
            else:
                st.error("❌ Failed to cancel subscription. Please try again.")
    
    # Sync with Stripe
    st.markdown("#### Sync with Stripe")
    if st.button("🔄 Sync with Stripe"):
        if subscription_manager.sync_with_stripe(user_id):
            st.success("✅ Successfully synced with Stripe!")
            st.rerun()
        else:
            st.error("❌ Failed to sync with Stripe.")


def show_billing_tab(subscription_manager: SubscriptionManager, usage_tracker: UsageTracker, user_id: str):
    """Show complete billing tab interface."""
    st.markdown("## 💳 Billing & Subscription")
    
    # Check for payment success/cancel parameters
    query_params = st.query_params
    
    if "payment_success" in query_params:
        st.success("🎉 Payment successful! Your subscription has been updated.")
        # Clear the parameter
        del st.query_params["payment_success"]
    
    if "payment_canceled" in query_params:
        st.info("ℹ️ Payment was canceled. Your subscription remains unchanged.")
        # Clear the parameter
        del st.query_params["payment_canceled"]
    
    # Create tabs for different billing sections
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Usage", "💰 Plans", "⚙️ Manage"])
    
    with tab1:
        show_subscription_status(subscription_manager, user_id)
    
    with tab2:
        show_usage_dashboard(usage_tracker, user_id)
    
    with tab3:
        show_plan_comparison()
    
    with tab4:
        show_billing_management(subscription_manager, user_id)
