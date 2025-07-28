#!/usr/bin/env python3
"""Script to set the CURRENT_USER_ID environment variable for the primary user."""

import os
import json

def set_primary_user_env():
    """Set the CURRENT_USER_ID environment variable to the primary user."""
    
    # Load users.json to find primary user
    try:
        with open('users.json', 'r') as f:
            users = json.loads(f.read())
        
        # Find primary user
        primary_user = None
        for user_id, user_data in users.items():
            if user_data.get('is_primary', False):
                primary_user = user_id
                break
        
        if not primary_user:
            # Get first approved user if no primary
            for user_id, user_data in users.items():
                if user_data.get('status') == 'approved':
                    primary_user = user_id
                    break
        
        if primary_user:
            # Set environment variable
            os.environ['CURRENT_USER_ID'] = primary_user
            
            # Also create a shell script for persistence
            with open('set_env.sh', 'w') as f:
                f.write(f'#!/bin/bash\nexport CURRENT_USER_ID="{primary_user}"\necho "Set CURRENT_USER_ID to {primary_user}"\n')
            
            # Make it executable
            os.chmod('set_env.sh', 0o755)
            
            print(f"✅ Set CURRENT_USER_ID to: {primary_user}")
            print(f"   User email: {users[primary_user].get('email', 'unknown')}")
            print(f"   Run this to set in your shell: source set_env.sh")
            
            return primary_user
        else:
            print("❌ No primary or approved user found in users.json")
            return None
            
    except Exception as e:
        print(f"❌ Error setting user environment: {e}")
        return None

if __name__ == "__main__":
    set_primary_user_env()