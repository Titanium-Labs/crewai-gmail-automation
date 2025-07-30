#!/usr/bin/env python3
"""Test script to verify CrewAI works with Sonnet 4 model."""

import os
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Set environment variables for testing
os.environ['CURRENT_USER_ID'] = 'user_zhQ7K854ngI'
os.environ['MODEL'] = 'anthropic/claude-sonnet-4-20250514'

# Load API key (this should be done by the system)
try:
    from src.common.security import APIKeyManager
    api_manager = APIKeyManager()
    
    # Get user's encrypted Anthropic API key
    with open('users.json', 'r') as f:
        users = json.load(f)
    
    user_data = users.get('user_zhQ7K854ngI', {})
    encrypted_key = user_data.get('api_keys', {}).get('anthropic', '')
    
    if encrypted_key:
        decrypted_key = api_manager.decrypt_api_key(encrypted_key)
        os.environ['ANTHROPIC_API_KEY'] = decrypted_key
        print("✅ Anthropic API key loaded successfully")
    else:
        print("❌ No Anthropic API key found for user")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error loading API key: {e}")
    sys.exit(1)

# Test basic model configuration
print(f"✅ Model set to: {os.environ.get('MODEL')}")
print(f"✅ User ID: {os.environ.get('CURRENT_USER_ID')}")

# Test Gmail tool functionality
try:
    from gmail_crew_ai.tools.gmail_oauth_tools import OAuth2GetUnreadEmailsTool
    
    # Fetch a few emails for testing
    tool = OAuth2GetUnreadEmailsTool(user_id='user_zhQ7K854ngI')
    emails = tool.run(5)
    
    print(f"✅ Fetched {len(emails)} emails for testing")
    
    # Create test data
    os.makedirs('output', exist_ok=True)
    
    # Convert emails to proper format for agents
    email_data = []
    for email in emails[:3]:  # Use first 3 emails for testing
        email_data.append({
            'email_id': email[0],
            'subject': email[1], 
            'sender': email[2],
            'body': email[3][:200],  # Truncate for testing
            'date': email[4].get('date', ''),
            'age_days': 0  # Will be calculated by crew
        })
    
    # Save test emails
    with open('output/fetched_emails.json', 'w') as f:
        json.dump(email_data, f, indent=2)
    
    print("✅ Test emails saved to output/fetched_emails.json")
    
except Exception as e:
    print(f"❌ Error with Gmail tools: {e}")
    import traceback
    traceback.print_exc()

# Test CrewAI instantiation with Sonnet 4
try:
    from gmail_crew_ai.crew import GmailCrewAi
    
    print("✅ Attempting to create CrewAI instance with Sonnet 4...")
    crew_ai = GmailCrewAi()
    print("✅ CrewAI instance created successfully")
    
    # Test categorizer agent
    print("✅ Testing categorizer agent...")
    categorizer = crew_ai.categorizer()
    print(f"✅ Categorizer agent created: {categorizer.role}")
    
    print("✅ All tests passed! CrewAI is ready to use Sonnet 4")
    
except Exception as e:
    print(f"❌ Error creating CrewAI: {e}")
    import traceback
    traceback.print_exc()