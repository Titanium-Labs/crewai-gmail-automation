#!/usr/bin/env python3
"""
Test script for Stripe webhook functionality.
This script simulates webhook events that would be sent by Stripe.
"""

import os
import json
import requests
from datetime import datetime

# Test configuration
WEBHOOK_URL = "http://localhost:8505/webhook"  # Streamlit webhook endpoint
TEST_STRIPE_WEBHOOK_SECRET = "whsec_test_webhook_secret"

def test_subscription_created():
    """Test subscription.created webhook"""
    print("🧪 Testing subscription.created webhook...")
    
    payload = {
        "id": "evt_test_subscription_created",
        "object": "event",
        "api_version": "2020-08-27",
        "created": int(datetime.now().timestamp()),
        "data": {
            "object": {
                "id": "sub_test_subscription",
                "object": "subscription",
                "customer": "cus_test_customer",
                "status": "active",
                "current_period_start": int(datetime.now().timestamp()),
                "current_period_end": int(datetime.now().timestamp()) + 2592000,  # 30 days
                "items": {
                    "object": "list",
                    "data": [
                        {
                            "id": "si_test_item",
                            "object": "subscription_item",
                            "price": {
                                "id": "price_basic_monthly",
                                "object": "price",
                                "nickname": "Basic Plan"
                            }
                        }
                    ]
                }
            }
        },
        "type": "customer.subscription.created"
    }
    
    # Test environment variables (remove EMAIL_ADDRESS, APP_PASSWORD, SLACK_WEBHOOK_URL)
    test_env = {
        "OPENAI_API_KEY": "test-openai-key",
        "STRIPE_SECRET_KEY": "sk_test_your_stripe_secret_key",
        "STRIPE_PUBLISHABLE_KEY": "pk_test_your_stripe_publishable_key", 
        "STRIPE_WEBHOOK_SECRET": TEST_STRIPE_WEBHOOK_SECRET,
        "STRIPE_BASIC_PRICE_ID": "price_basic_monthly",
        "STRIPE_PREMIUM_PRICE_ID": "price_premium_monthly"
    }
    
    # Set environment variables for testing
    for key, value in test_env.items():
        os.environ[key] = value
    
    print(f"📡 Sending webhook to {WEBHOOK_URL}")
    print(f"📦 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Send the webhook
        headers = {
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={int(datetime.now().timestamp())},v1=test_signature"
        }
        
        response = requests.post(
            WEBHOOK_URL, 
            json=payload, 
            headers=headers,
            timeout=10
        )
        
        print(f"✅ Response Status: {response.status_code}")
        print(f"📄 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("🎉 Webhook test successful!")
            return True
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending webhook: {e}")
        return False

def test_subscription_updated():
    """Test subscription.updated webhook"""
    print("\n🧪 Testing subscription.updated webhook...")
    
    payload = {
        "id": "evt_test_subscription_updated",
        "object": "event", 
        "api_version": "2020-08-27",
        "created": int(datetime.now().timestamp()),
        "data": {
            "object": {
                "id": "sub_test_subscription",
                "object": "subscription",
                "customer": "cus_test_customer", 
                "status": "active",
                "current_period_start": int(datetime.now().timestamp()),
                "current_period_end": int(datetime.now().timestamp()) + 2592000,
                "items": {
                    "object": "list",
                    "data": [
                        {
                            "id": "si_test_item",
                            "object": "subscription_item",
                            "price": {
                                "id": "price_premium_monthly",
                                "object": "price",
                                "nickname": "Premium Plan"
                            }
                        }
                    ]
                }
            }
        },
        "type": "customer.subscription.updated"
    }
    
    print(f"📡 Sending webhook to {WEBHOOK_URL}")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={int(datetime.now().timestamp())},v1=test_signature"
        }
        
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers=headers, 
            timeout=10
        )
        
        print(f"✅ Response Status: {response.status_code}")
        print(f"📄 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("🎉 Webhook test successful!")
            return True
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending webhook: {e}")
        return False

def test_subscription_deleted():
    """Test subscription.deleted webhook"""
    print("\n🧪 Testing subscription.deleted webhook...")
    
    payload = {
        "id": "evt_test_subscription_deleted",
        "object": "event",
        "api_version": "2020-08-27", 
        "created": int(datetime.now().timestamp()),
        "data": {
            "object": {
                "id": "sub_test_subscription",
                "object": "subscription",
                "customer": "cus_test_customer",
                "status": "canceled",
                "canceled_at": int(datetime.now().timestamp()),
                "current_period_start": int(datetime.now().timestamp()),
                "current_period_end": int(datetime.now().timestamp()) + 2592000
            }
        },
        "type": "customer.subscription.deleted"
    }
    
    print(f"📡 Sending webhook to {WEBHOOK_URL}")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={int(datetime.now().timestamp())},v1=test_signature"
        }
        
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        print(f"✅ Response Status: {response.status_code}")
        print(f"📄 Response Body: {response.text}")
        
        if response.status_code == 200:
            print("🎉 Webhook test successful!")
            return True
        else:
            print(f"❌ Webhook test failed with status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending webhook: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting Stripe webhook tests...")
    print("⚠️  Make sure Streamlit app is running on http://localhost:8505")
    print("=" * 60)
    
    success_count = 0
    total_tests = 3
    
    # Run all tests
    if test_subscription_created():
        success_count += 1
        
    if test_subscription_updated():
        success_count += 1
        
    if test_subscription_deleted():
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("🎉 All webhook tests passed!")
    else:
        print("❌ Some tests failed. Check the output above for details.")
