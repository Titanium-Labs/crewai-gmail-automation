"""OAuth2 authentication manager for Gmail access."""

import os
import json
import pickle
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import streamlit as st
from pathlib import Path


class OAuth2Manager:
    """Manages OAuth2 authentication for Gmail access."""
    
    # Gmail API scopes (including additional scopes that Google may grant)
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.compose',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/drive.readonly',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/calendar.readonly',
        'https://www.googleapis.com/auth/calendar.events',
        'openid'
    ]
    
    def __init__(self, credentials_file: str = "credentials.json"):
        """Initialize OAuth2 manager."""
        self.credentials_file = credentials_file
        self.tokens_dir = Path("tokens")
        self.tokens_dir.mkdir(exist_ok=True)
        
    def get_authorization_url(self, user_id: str) -> str:
        """Get authorization URL for OAuth2 flow."""
        if not os.path.exists(self.credentials_file):
            raise FileNotFoundError(
                f"OAuth2 credentials file not found: {self.credentials_file}\n"
                "Please download it from Google Cloud Console and save as 'credentials.json'"
            )
        
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES,
            redirect_uri='http://localhost:8505'  # Streamlit port
        )
        
        # Store flow in session state for later use
        st.session_state[f'oauth_flow_{user_id}'] = flow
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=user_id
        )
        
        return auth_url
    
    def handle_oauth_callback(self, user_id: str, authorization_code: str) -> bool:
        """Handle OAuth2 callback and save credentials."""
        try:
            flow_key = f'oauth_flow_{user_id}'
            flow = st.session_state.get(flow_key)
            
            if not flow:
                # Try to recreate the flow
                try:
                    flow = Flow.from_client_secrets_file(
                        self.credentials_file,
                        scopes=self.SCOPES,
                        redirect_uri='http://localhost:8505'
                    )
                except Exception as recreate_error:
                    st.error(f"Failed to recreate OAuth flow: {recreate_error}")
                    return False
            
            # Exchange authorization code for credentials
            flow.fetch_token(code=authorization_code)
            credentials = flow.credentials
            
            # Save credentials
            self.save_credentials(user_id, credentials)
            
            # Clean up session state
            if flow_key in st.session_state:
                del st.session_state[flow_key]
            
            return True
            
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")
            st.exception(e)  # Show full stack trace
            return False
    
    def save_credentials(self, user_id: str, credentials: Credentials):
        """Save user credentials securely."""
        token_file = self.tokens_dir / f"{user_id}_token.pickle"
        
        with open(token_file, 'wb') as token:
            pickle.dump(credentials, token)
    
    def load_credentials(self, user_id: str) -> Optional[Credentials]:
        """Load user credentials."""
        token_file = self.tokens_dir / f"{user_id}_token.pickle"
        
        if not token_file.exists():
            return None
        
        try:
            with open(token_file, 'rb') as token:
                credentials = pickle.load(token)
            
            # Refresh credentials if expired
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self.save_credentials(user_id, credentials)
            
            return credentials
            
        except Exception as e:
            st.error(f"Error loading credentials: {str(e)}")
            return None
    
    def is_authenticated(self, user_id: str) -> bool:
        """Check if user is authenticated."""
        credentials = self.load_credentials(user_id)
        return credentials is not None and credentials.valid
    
    def get_gmail_service(self, user_id: str):
        """Get Gmail API service for authenticated user."""
        credentials = self.load_credentials(user_id)
        if not credentials:
            raise ValueError(f"No valid credentials found for user: {user_id}")
        
        return build('gmail', 'v1', credentials=credentials)
    
    def get_user_email(self, user_id: str) -> str:
        """Get the email address of the authenticated user."""
        try:
            service = self.get_gmail_service(user_id)
            profile = service.users().getProfile(userId='me').execute()
            return profile['emailAddress']
        except Exception as e:
            st.error(f"Error getting user email: {str(e)}")
            return ""
    
    def revoke_credentials(self, user_id: str) -> bool:
        """Revoke and delete user credentials."""
        try:
            credentials = self.load_credentials(user_id)
            if credentials:
                # Try to revoke the credentials
                try:
                    if hasattr(credentials, 'revoke'):
                        credentials.revoke(Request())
                except Exception:
                    pass  # Continue with token deletion even if revoke fails
            
            # Delete token file
            token_file = self.tokens_dir / f"{user_id}_token.pickle"
            if token_file.exists():
                token_file.unlink()
            
            return True
            
        except Exception as e:
            st.error(f"Error revoking credentials: {str(e)}")
            return False
    
    def list_authenticated_users(self) -> Dict[str, str]:
        """List all authenticated users with their email addresses."""
        users = {}
        
        for token_file in self.tokens_dir.glob("*_token.pickle"):
            user_id = token_file.stem.replace("_token", "")
            
            if self.is_authenticated(user_id):
                email = self.get_user_email(user_id)
                if email:
                    users[user_id] = email
        
        return users
    
    @staticmethod
    def setup_instructions() -> str:
        """Return setup instructions for OAuth2 credentials."""
        return """
        ## 🔧 OAuth2 Setup Instructions
        
        To use Gmail OAuth2 authentication, you need to:
        
        1. **Go to Google Cloud Console**: https://console.cloud.google.com/
        
        2. **Create or select a project**
        
        3. **Enable Gmail API**:
           - Go to "APIs & Services" > "Library"
           - Search for "Gmail API" and enable it
        
        4. **Create OAuth2 Credentials**:
           - Go to "APIs & Services" > "Credentials"
           - Click "Create Credentials" > "OAuth 2.0 Client ID"
           - Choose "Desktop Application"
           - Download the JSON file
        
        5. **Save credentials file**:
           - Rename the downloaded file to `credentials.json`
           - Place it in your project root directory
        
        6. **Configure OAuth Consent Screen**:
           - Add your email as a test user
           - Add required scopes: gmail.readonly, gmail.modify, gmail.compose
        
        **⚠️ Important**: Make sure `credentials.json` is in your `.gitignore` file for security!
        """ 