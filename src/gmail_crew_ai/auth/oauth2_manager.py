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
        # Support Docker data directory structure
        if os.path.exists("/app/data"):
            self.credentials_file = f"/app/data/{credentials_file}"
            self.tokens_dir = Path("/app/data/tokens")
        else:
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
        
        port = os.getenv('PORT', '8505')
        flow = Flow.from_client_secrets_file(
            self.credentials_file,
            scopes=self.SCOPES,
            redirect_uri=f'http://localhost:{port}'  # Use PORT from env
        )
        
        # Store flow in session state for later use
        st.session_state[f'oauth_flow_{user_id}'] = flow
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',  # Force consent screen to ensure refresh token
            state=user_id
        )
        
        return auth_url
    
    def handle_oauth_callback(self, user_id: str, authorization_code: str) -> bool:
        """Handle OAuth2 callback and save credentials."""
        try:
            print(f"🔐 Processing OAuth callback for user: {user_id}")
            flow_key = f'oauth_flow_{user_id}'
            flow = st.session_state.get(flow_key)
            
            if not flow:
                print(f"⚠️ No cached OAuth flow found for {user_id}, recreating...")
                # Try to recreate the flow
                try:
                    port = os.getenv('PORT', '8505')
                    flow = Flow.from_client_secrets_file(
                        self.credentials_file,
                        scopes=self.SCOPES,
                        redirect_uri=f'http://localhost:{port}'
                    )
                    print("✅ OAuth flow recreated successfully")
                except Exception as recreate_error:
                    print(f"❌ Failed to recreate OAuth flow: {recreate_error}")
                    st.error(f"Failed to recreate OAuth flow: {recreate_error}")
                    return False
            else:
                print("✅ Using cached OAuth flow")
            
            # Exchange authorization code for credentials with proper parameters
            print("🔄 Exchanging authorization code for credentials...")
            flow.fetch_token(
                code=authorization_code,
                # Ensure we request offline access for refresh token
                include_granted_scopes=True
            )
            credentials = flow.credentials
            
            # Validate credentials have essential fields
            if not hasattr(credentials, 'token') or credentials.token is None:
                print("OAuth credentials missing access token")
                st.error("🚫 OAuth authentication failed: No access token received")
                return False
            
            # Check for refresh token (warn but don't fail)
            if not hasattr(credentials, 'refresh_token') or credentials.refresh_token is None:
                print("⚠️ OAuth credentials missing refresh token - token won't auto-refresh")
                st.warning("⚠️ Login successful, but refresh token missing. You may need to re-authenticate more frequently.")
                st.info("For better experience, revoke app access in Google Account settings and re-authenticate.")
                # Continue with authentication even without refresh token
            
            # Log warnings for optional fields that are missing (but don't fail)
            optional_fields = ['token_uri', 'client_id', 'client_secret']
            missing_optional = []
            for field in optional_fields:
                if not hasattr(credentials, field) or getattr(credentials, field) is None:
                    missing_optional.append(field)
            
            if missing_optional:
                print(f"OAuth credentials missing optional fields (will be populated from client): {', '.join(missing_optional)}")
                # Try to populate missing fields from the flow
                try:
                    if hasattr(flow, 'client_config') and 'client_id' in flow.client_config:
                        if not hasattr(credentials, 'client_id') or credentials.client_id is None:
                            credentials._client_id = flow.client_config['client_id']
                        if not hasattr(credentials, 'client_secret') or credentials.client_secret is None:
                            credentials._client_secret = flow.client_config['client_secret']
                        if not hasattr(credentials, 'token_uri') or credentials.token_uri is None:
                            credentials._token_uri = flow.client_config.get('token_uri', 'https://oauth2.googleapis.com/token')
                except Exception as populate_error:
                    print(f"Could not populate missing fields from flow: {populate_error}")
                    # Continue anyway - the essential fields are present
            
            # Save credentials
            self.save_credentials(user_id, credentials)
            
            # Verify saved credentials can be loaded
            loaded_creds = self.load_credentials(user_id)
            if not loaded_creds:
                st.error("Failed to save OAuth credentials properly")
                return False
            
            # Clean up session state
            if flow_key in st.session_state:
                del st.session_state[flow_key]
            
            print(f"✅ OAuth credentials saved successfully for user: {user_id}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ OAuth callback failed for user {user_id}: {error_msg}")
            
            # Provide more specific error messages
            if "invalid_grant" in error_msg.lower():
                st.error("🔑 Authorization code expired or already used. Please try logging in again.")
            elif "credentials" in error_msg.lower():
                st.error("🔐 OAuth credentials file issue. Please check your credentials.json file.")
            elif "client_id" in error_msg.lower() or "client_secret" in error_msg.lower():
                st.error("🔧 OAuth client configuration error. Please check your Google Cloud Console settings.")
            elif "redirect_uri" in error_msg.lower():
                st.error("🌐 OAuth redirect URI mismatch. Please check your OAuth configuration.")
            else:
                st.error(f"🚫 Authentication failed: {error_msg}")
            
            # Only show full exception in debug mode
            if os.getenv("DEBUG") == "true":
                st.exception(e)
            
            return False
    
    def save_credentials(self, user_id: str, credentials: Credentials):
        """Save user credentials securely."""
        token_file = self.tokens_dir / f"{user_id}_token.pickle"
        
        with open(token_file, 'wb') as token:
            pickle.dump(credentials, token)
    
    def load_credentials(self, user_id: str) -> Optional[Credentials]:
        """Load user credentials."""
        # First try the standard pattern
        token_file = self.tokens_dir / f"{user_id}_token.pickle"
        
        # If not found, look for files with the user_id prefix (handles session-based naming)
        if not token_file.exists():
            # Look for files that start with user_id
            for file_path in self.tokens_dir.glob(f"{user_id}_*_token.pickle"):
                token_file = file_path
                break
            
            # Also check for login_* patterns that might map to this user
            if not token_file.exists():
                # Look for any login_* token files that might belong to this user
                for file_path in self.tokens_dir.glob("login_*_token.pickle"):
                    try:
                        # Try to load and check if this token belongs to our user
                        with open(file_path, 'rb') as f:
                            test_credentials = pickle.load(f)
                        
                        # If we can load it and it has a token, copy it to the expected location
                        if hasattr(test_credentials, 'token') and test_credentials.token:
                            expected_file = self.tokens_dir / f"{user_id}_token.pickle"
                            # Copy the token file to the expected location
                            import shutil
                            shutil.copy2(file_path, expected_file)
                            token_file = expected_file
                            print(f"Mapped OAuth token from {file_path.name} to {expected_file.name}")
                            break
                    except Exception:
                        continue
        
        if not token_file.exists():
            return None
        
        try:
            with open(token_file, 'rb') as token:
                credentials = pickle.load(token)
            
            # Validate that credentials have access token (essential)
            if not hasattr(credentials, 'token') or credentials.token is None:
                print(f"OAuth credentials missing access token for user {user_id}")
                # Delete corrupted credentials file
                token_file.unlink()
                return None
            
            # Check for other fields (warn but don't delete)
            optional_fields = ['refresh_token', 'token_uri', 'client_id', 'client_secret']
            missing_fields = []
            
            for field in optional_fields:
                if not hasattr(credentials, field) or getattr(credentials, field) is None:
                    missing_fields.append(field)
            
            if missing_fields:
                print(f"OAuth credentials missing optional fields for user {user_id}: {', '.join(missing_fields)}")
                # Don't delete - these can be missing
            
            # Refresh credentials if expired
            if credentials and credentials.expired and credentials.refresh_token:
                try:
                    credentials.refresh(Request())
                    self.save_credentials(user_id, credentials)
                except Exception as refresh_error:
                    print(f"Error refreshing OAuth credentials for user {user_id}: {refresh_error}")
                    # Delete corrupted credentials file
                    token_file.unlink()
                    return None
            
            return credentials
            
        except Exception as e:
            print(f"Error loading credentials for user {user_id}: {str(e)}")
            # Delete corrupted credentials file
            try:
                token_file.unlink()
            except:
                pass
            return None
    
    def is_authenticated(self, user_id: str) -> bool:
        """Check if user is authenticated."""
        credentials = self.load_credentials(user_id)
        if not credentials:
            return False
        
        # load_credentials already handles validation and refresh
        # so if we get credentials back, they should be valid
        return credentials.valid
    
    def get_gmail_service(self, user_id: str):
        """Get Gmail API service for authenticated user."""
        credentials = self.load_credentials(user_id)
        if not credentials:
            raise ValueError(f"No valid credentials found for user: {user_id}")
        
        return build('gmail', 'v1', credentials=credentials, cache_discovery=False)
    
    def get_user_email(self, user_id: str) -> str:
        """Get the email address of the authenticated user."""
        try:
            service = self.get_gmail_service(user_id)
            profile = service.users().getProfile(userId='me').execute()
            return profile['emailAddress']
        except Exception as e:
            # Check if this is a credentials issue that requires re-authentication
            error_msg = str(e).lower()
            if "credentials" in error_msg or "refresh" in error_msg or "authentication" in error_msg:
                print(f"OAuth credentials invalid for user {user_id}: {str(e)}")
                # Mark credentials as invalid so user will be prompted to re-authenticate
                self.revoke_credentials(user_id)
                return ""
            else:
                # Don't show error in UI for this specific case - just log it
                print(f"Warning: Could not get user email: {str(e)}")
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
            
            # Delete all token files for this user (including session-based ones)
            for token_file in self.tokens_dir.glob(f"{user_id}*_token.pickle"):
                try:
                    token_file.unlink()
                    print(f"Deleted OAuth token file: {token_file.name}")
                except Exception as e:
                    print(f"Could not delete token file {token_file.name}: {e}")
            
            # Also delete standard token file
            token_file = self.tokens_dir / f"{user_id}_token.pickle"
            if token_file.exists():
                token_file.unlink()
                print(f"Deleted standard OAuth token file for user: {user_id}")
            
            return True
            
        except Exception as e:
            print(f"Error revoking credentials for user {user_id}: {str(e)}")
            return False
    
    def cleanup_corrupted_tokens(self) -> int:
        """Clean up any corrupted token files and return count of removed files."""
        removed_count = 0
        
        for token_file in self.tokens_dir.glob("*_token.pickle"):
            try:
                with open(token_file, 'rb') as f:
                    credentials = pickle.load(f)
                
                # Check if credentials have required fields
                required_fields = ['token', 'refresh_token', 'token_uri', 'client_id', 'client_secret']
                missing_fields = []
                
                for field in required_fields:
                    if not hasattr(credentials, field) or getattr(credentials, field) is None:
                        missing_fields.append(field)
                
                if missing_fields:
                    print(f"Removing corrupted token file {token_file.name}: missing {', '.join(missing_fields)}")
                    token_file.unlink()
                    removed_count += 1
                    
            except Exception as e:
                print(f"Removing corrupted token file {token_file.name}: {e}")
                try:
                    token_file.unlink()
                    removed_count += 1
                except:
                    pass
        
        return removed_count
    
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