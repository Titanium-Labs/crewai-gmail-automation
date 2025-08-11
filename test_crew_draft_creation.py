#!/usr/bin/env python
"""Test the crew to see if drafts are actually being created."""

import os
import json
from dotenv import load_dotenv
from src.gmail_crew_ai.crew_oauth import OAuth2GmailCrewAi
from src.gmail_crew_ai.auth.oauth2_manager import OAuth2Manager

# Load environment variables
load_dotenv()

# Set user ID
user_id = os.environ.get("CURRENT_USER_ID", "user_zhQ7K854ngI")
os.environ["CURRENT_USER_ID"] = user_id

print(f"Testing crew with user_id: {user_id}")
print("=" * 60)

# Initialize OAuth2Manager
oauth_manager = OAuth2Manager()

# Create crew
print("Creating crew...")
crew = OAuth2GmailCrewAi(user_id=user_id, oauth_manager=oauth_manager)

# Run the crew with limited emails
print("\nRunning crew with email limit of 5...")
print("Watch for '🚀 OAuth2SaveDraftTool called' messages below:")
print("-" * 60)

try:
    result = crew.crew().kickoff(inputs={'email_limit': 5})
    print("\n" + "=" * 60)
    print("Crew execution completed!")
    print("=" * 60)
    
    # Check the response report
    try:
        with open('output/response_report.json', 'r') as f:
            report = json.load(f)
            
        print("\nResponse Report Summary:")
        print(f"Total processed: {report.get('total_processed', 0)}")
        print(f"Replies created: {report.get('replies_created', 0)}")
        print(f"Marked read only: {report.get('marked_read_only', 0)}")
        
        print("\nEmails with draft_saved=true:")
        for email in report.get('emails', []):
            if email.get('draft_saved'):
                print(f"  - {email['subject'][:50]}...")
                
    except Exception as e:
        print(f"Could not read response report: {e}")
        
except Exception as e:
    print(f"\nError running crew: {e}")

print("\n" + "=" * 60)
print("Test complete! Check above for '🚀 OAuth2SaveDraftTool called' messages.")
print("If you see those messages, drafts are being created.")
print("If not, the agent is not calling the tool.")
print("=" * 60)