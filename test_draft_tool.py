#!/usr/bin/env python
"""Test script to verify OAuth2SaveDraftTool is working properly."""

import os
from dotenv import load_dotenv
from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2SaveDraftTool
from src.gmail_crew_ai.auth.oauth2_manager import OAuth2Manager

# Load environment variables
load_dotenv()

# Set user ID
user_id = os.environ.get("CURRENT_USER_ID", "user_zhQ7K854ngI")
print(f"Testing with user_id: {user_id}")

# Initialize OAuth2Manager
oauth_manager = OAuth2Manager()

# Initialize the tool
draft_tool = OAuth2SaveDraftTool(user_id=user_id, oauth_manager=oauth_manager)

# Test data from the response_report.json
test_cases = [
    {
        "recipient": "support@bionicwp.com",
        "subject": "Re: Domain Expiration - caraccidentdoctors.us",
        "body": "Hi BionicWP Support Team,\n\nThank you for the domain expiration notice regarding caraccidentdoctors.us. I've received this alert and will review the domain status promptly.\n\nI'll take the necessary action to ensure continuity.\n\nBest regards,\nMichael Smith",
        "thread_id": "1988ab25707fea1f",
        "in_reply_to": "<ff220e40c0118f1919af50b252f9bbe9@frontapp.com>",
        "references": "<ff220e40c0118f1919af50b252f9bbe9@frontapp.com>"
    },
    {
        "recipient": "eldon_meeks@hotmail.com", 
        "subject": "Re: Follow up for Spencer and Johnn from their meeting with Dr Meeks. Thanks! Dr Meeks",
        "body": "Hi Dr. Meeks,\n\nThank you for the follow-up regarding Spencer and Johnn's meeting. I've received your message and will review the details.\n\nI'll connect with the relevant parties to ensure we address any action items from the discussion. If there's anything urgent that needs immediate attention, please let me know.\n\nBest regards,\nMichael Smith",
        "thread_id": "19886f4bca04e1ec",
        "in_reply_to": "<CO6PR14MB434036CCC624C4F3FF7B8F6E892CA@CO6PR14MB4340.namprd14.prod.outlook.com>",
        "references": ""
    }
]

print("\n" + "="*60)
print("Testing OAuth2SaveDraftTool directly")
print("="*60 + "\n")

for i, test_case in enumerate(test_cases, 1):
    print(f"\nTest Case {i}: {test_case['subject']}")
    print("-" * 40)
    
    try:
        # Call the tool directly
        result = draft_tool._run(
            recipient=test_case["recipient"],
            subject=test_case["subject"],
            body=test_case["body"],
            thread_id=test_case.get("thread_id"),
            in_reply_to=test_case.get("in_reply_to"),
            references=test_case.get("references"),
            reply_all=True
        )
        
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")

print("\n" + "="*60)
print("Test complete!")
print("="*60)