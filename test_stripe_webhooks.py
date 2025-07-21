"""
Quick setup script for testing Stripe webhooks locally.
This script will help you test the webhook integration.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

def check_stripe_cli():
    """Check if Stripe CLI is available."""
    stripe_exe = Path("stripe.exe")
    if stripe_exe.exists():
        print("✅ Found stripe.exe in current directory")
        return "./stripe.exe"
    else:
        print("❌ stripe.exe not found in current directory")
        return None

def check_env_file():
    """Check if .env file exists and has necessary variables."""
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️ .env file not found. Creating a template...")
        create_env_template()
        return False
    
    # Read and check for required variables
    with open(env_file, 'r') as f:
        content = f.read()
    
    required_vars = ['STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET']
    missing_vars = []
    
    for var in required_vars:
        if var not in content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"⚠️ Missing environment variables: {', '.join(missing_vars)}")
        return False
    
    print("✅ .env file contains required Stripe variables")
    return True

def create_env_template():
    """Create a template .env file."""
    template = """# OpenAI Model
MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=your_openai_api_key

# Gmail credentials
EMAIL_ADDRESS=your_email_address@gmail.com
APP_PASSWORD=your_app_password

# Slack Webhook URL
SLACK_WEBHOOK_URL=your_slack_webhook_url

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Stripe Price IDs (create these in your Stripe dashboard)
STRIPE_BASIC_PRICE_ID=price_basic_monthly
STRIPE_PREMIUM_PRICE_ID=price_premium_monthly
"""
    
    with open('.env', 'w') as f:
        f.write(template)
    
    print("📝 Created .env template file")
    print("🔧 Please update it with your actual Stripe keys")

def start_webhook_test_server():
    """Start the webhook test server."""
    print("\n🚀 Starting webhook test server...")
    print("📡 Server will run on: http://localhost:5000/webhook/stripe")
    print("🛑 Press Ctrl+C to stop the server")
    print("-" * 50)
    
    try:
        subprocess.run([sys.executable, "webhook_test.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Webhook test server stopped")
    except FileNotFoundError:
        print("❌ webhook_test.py not found. Make sure it's in the current directory.")

def show_stripe_commands(stripe_exe):
    """Show useful Stripe CLI commands."""
    print(f"\n🎯 Useful Stripe CLI Commands:")
    print(f"1. Login to Stripe:")
    print(f"   {stripe_exe} login")
    print(f"\n2. Start webhook forwarding:")
    print(f"   {stripe_exe} listen --forward-to localhost:5000/webhook/stripe")
    print(f"\n3. Trigger test events (in another terminal):")
    print(f"   {stripe_exe} trigger customer.subscription.created")
    print(f"   {stripe_exe} trigger invoice.payment_succeeded")
    print(f"   {stripe_exe} trigger customer.subscription.deleted")
    print(f"\n4. View your Stripe account:")
    print(f"   {stripe_exe} open")

def main():
    """Main setup function."""
    print("🔧 Stripe Webhook Testing Setup")
    print("=" * 40)
    
    # Check Stripe CLI
    stripe_exe = check_stripe_cli()
    if not stripe_exe:
        print("\n❌ Please make sure stripe.exe is in the current directory")
        return
    
    # Check environment file
    env_ready = check_env_file()
    
    # Show commands
    show_stripe_commands(stripe_exe)
    
    if not env_ready:
        print("\n⚠️ Please update your .env file with Stripe keys before proceeding")
        return
    
    print("\n" + "="*50)
    print("🎯 NEXT STEPS:")
    print("1. Make sure you've logged into Stripe CLI")
    print("2. Run the webhook test server: python webhook_test.py")
    print("3. In another terminal, start forwarding:")
    print(f"   {stripe_exe} listen --forward-to localhost:5000/webhook/stripe")
    print("4. Copy the webhook secret from the CLI output to your .env file")
    print("5. Test with: ./stripe.exe trigger customer.subscription.created")
    print("="*50)
    
    # Ask if they want to start the webhook server
    try:
        choice = input("\n🚀 Start webhook test server now? (y/n): ").lower().strip()
        if choice in ['y', 'yes']:
            start_webhook_test_server()
    except KeyboardInterrupt:
        print("\n👋 Setup complete!")

if __name__ == "__main__":
    main()
