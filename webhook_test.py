"""
Simple webhook endpoint for testing Stripe webhooks locally.
Run this alongside your Streamlit app to test webhook events.
"""

import os
from flask import Flask, request, jsonify
import stripe
import json
from datetime import datetime

app = Flask(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Set up Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        
        print(f"\n🎯 Received webhook event: {event['type']}")
        print(f"📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🆔 Event ID: {event['id']}")
        
        # Handle different event types
        if event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            print(f"✅ Subscription created: {subscription['id']}")
            print(f"👤 Customer: {subscription['customer']}")
            print(f"📊 Status: {subscription['status']}")
            
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            print(f"🔄 Subscription updated: {subscription['id']}")
            print(f"📊 Status: {subscription['status']}")
            
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            print(f"❌ Subscription deleted: {subscription['id']}")
            
        elif event['type'] == 'invoice.payment_succeeded':
            invoice = event['data']['object']
            print(f"💰 Payment succeeded: {invoice['id']}")
            print(f"💵 Amount: ${invoice['amount_paid']/100}")
            
        elif event['type'] == 'invoice.payment_failed':
            invoice = event['data']['object']
            print(f"⚠️ Payment failed: {invoice['id']}")
            print(f"💵 Amount: ${invoice['amount_due']/100}")
            
        else:
            print(f"📋 Event type: {event['type']} (not handled)")
        
        # Pretty print the event data
        print(f"📦 Event data preview:")
        print(json.dumps(event['data']['object'], indent=2)[:500] + "...")
        print("-" * 50)
        
        return jsonify({'status': 'success'})
        
    except ValueError as e:
        print(f"❌ Invalid payload: {e}")
        return jsonify({'error': 'Invalid payload'}), 400
        
    except stripe.error.SignatureVerificationError as e:
        print(f"❌ Invalid signature: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
        
    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting Stripe webhook test server...")
    print(f"📡 Webhook endpoint: http://localhost:5000/webhook/stripe")
    print(f"🔐 Webhook secret: {webhook_secret[:20]}...")
    print("💡 Use Stripe CLI: stripe listen --forward-to localhost:5000/webhook/stripe")
    print("-" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
