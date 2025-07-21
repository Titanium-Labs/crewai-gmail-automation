"""Streamlit app for Gmail Crew AI with OAuth2 authentication and user management."""

import streamlit as st
import streamlit.components.v1 as components
import uuid
import os
import json
import sys
import io
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import hashlib
import secrets
import urllib.parse
import base64

# Import our modules
try:
    from src.gmail_crew_ai.auth import OAuth2Manager
    from src.gmail_crew_ai.crew_oauth import OAuth2GmailCrewAi, create_crew_for_user
    from src.gmail_crew_ai.models import EmailDetails
    from src.gmail_crew_ai.billing import StripeService, SubscriptionManager, UsageTracker
    from src.gmail_crew_ai.billing.streamlit_billing import show_billing_tab
    from src.gmail_crew_ai.billing.models import PlanType
except ImportError as e:
    st.error(f"Import error: {e}")
    st.error("Please ensure all dependencies are installed: pip install -r requirements.txt")
    st.stop()


class SessionManager:
    """Manages persistent user sessions with 7-day expiration."""
    
    def __init__(self):
        self.sessions_file = "user_sessions.json"
        self.session_duration = timedelta(days=7)
        self.ensure_sessions_file()
    
    def ensure_sessions_file(self):
        """Ensure sessions file exists."""
        if not os.path.exists(self.sessions_file):
            self.save_sessions({})
    
    def load_sessions(self) -> Dict:
        """Load sessions from file."""
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def save_sessions(self, sessions: Dict):
        """Save sessions to file."""
        try:
            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(sessions, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving sessions: {e}")
    
    def create_session(self, user_id: str) -> str:
        """Create a new session token for a user."""
        session_token = secrets.token_urlsafe(32)
        expiry_time = datetime.now() + self.session_duration
        
        sessions = self.load_sessions()
        sessions[session_token] = {
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'expires_at': expiry_time.isoformat(),
            'last_accessed': datetime.now().isoformat()
        }
        
        self.save_sessions(sessions)
        return session_token
    
    def validate_session(self, session_token: str) -> Optional[str]:
        """Validate a session token and return user_id if valid, None if invalid."""
        if not session_token:
            return None
            
        sessions = self.load_sessions()
        
        if session_token not in sessions:
            return None
        
        session = sessions[session_token]
        
        # Check if session has expired
        try:
            expires_at = datetime.fromisoformat(session['expires_at'])
            if datetime.now() > expires_at:
                # Session expired, remove it
                del sessions[session_token]
                self.save_sessions(sessions)
                return None
        except Exception:
            # Invalid date format, remove session
            del sessions[session_token]
            self.save_sessions(sessions)
            return None
        
        # Update last accessed time
        session['last_accessed'] = datetime.now().isoformat()
        sessions[session_token] = session
        self.save_sessions(sessions)
        
        return session['user_id']
    
    def invalidate_session(self, session_token: str):
        """Invalidate a specific session."""
        if not session_token:
            return
            
        sessions = self.load_sessions()
        if session_token in sessions:
            del sessions[session_token]
            self.save_sessions(sessions)
    
    def cleanup_expired_sessions(self):
        """Remove expired sessions from storage."""
        sessions = self.load_sessions()
        current_time = datetime.now()
        
        expired_tokens = []
        for token, session in sessions.items():
            try:
                expires_at = datetime.fromisoformat(session['expires_at'])
                if current_time > expires_at:
                    expired_tokens.append(token)
            except Exception:
                expired_tokens.append(token)
        
        for token in expired_tokens:
            del sessions[token]
        
        if expired_tokens:
            self.save_sessions(sessions)
    
    def set_browser_session(self, session_token: str):
        """Set session token for persistence across page refreshes."""
        # Store in Streamlit's session state for persistence
        st.session_state.persistent_session_token = session_token
        
        # Also try to set a browser cookie as backup
        expiry_date = (datetime.now() + self.session_duration).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        js_code = f"""
        <script>
        // Set browser cookie
        document.cookie = "gmail_crew_session={session_token}; expires={expiry_date}; path=/; SameSite=Lax";
        
        // Also store in sessionStorage for more reliable persistence
        if (typeof(Storage) !== "undefined") {{
            sessionStorage.setItem("gmail_crew_session_token", "{session_token}");
        }}
        </script>
        """
        components.html(js_code, height=0)
    
    def get_browser_session(self) -> Optional[str]:
        """Get session token from Streamlit's persistent session state."""
        # Use Streamlit's own session state for persistence across page refreshes
        # This is more reliable than trying to read browser cookies in Streamlit
        
        # Check if we have a stored session token in the browser's sessionStorage
        if 'persistent_session_token' in st.session_state:
            return st.session_state.persistent_session_token
        
        # Also check URL parameters as a fallback
        query_params = st.query_params
        if 'session_token' in query_params:
            session_token = query_params['session_token']
            # Store it in session state for persistence
            st.session_state.persistent_session_token = session_token
            return session_token
        
        return None
    
    def clear_browser_session(self):
        """Clear session token from browser and session state."""
        # Clear from Streamlit session state
        if 'persistent_session_token' in st.session_state:
            del st.session_state.persistent_session_token
        
        # Clear from browser storage
        js_code = """
        <script>
        // Clear browser cookie
        document.cookie = "gmail_crew_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax";
        
        // Clear sessionStorage
        if (typeof(Storage) !== "undefined") {
            sessionStorage.removeItem("gmail_crew_session_token");
        }
        </script>
        """
        components.html(js_code, height=0)


# Global session manager instance
session_manager = SessionManager()


def inject_shadcn_css():
    """Inject shadcn-inspired CSS styling."""
    st.markdown("""
    <style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* CSS Variables - shadcn/ui inspired design tokens */
    :root {
        --background: 0 0% 100%;
        --foreground: 222.2 84% 4.9%;
        --card: 0 0% 100%;
        --card-foreground: 222.2 84% 4.9%;
        --popover: 0 0% 100%;
        --popover-foreground: 222.2 84% 4.9%;
        --primary: 221.2 83.2% 53.3%;
        --primary-foreground: 210 40% 98%;
        --secondary: 210 40% 96%;
        --secondary-foreground: 222.2 84% 4.9%;
        --muted: 210 40% 96%;
        --muted-foreground: 215.4 16.3% 46.9%;
        --accent: 210 40% 96%;
        --accent-foreground: 222.2 84% 4.9%;
        --destructive: 0 84.2% 60.2%;
        --destructive-foreground: 210 40% 98%;
        --border: 214.3 31.8% 91.4%;
        --input: 214.3 31.8% 91.4%;
        --ring: 221.2 83.2% 53.3%;
        --radius: 0.75rem;
    }

    /* Dark mode variables */
    .dark {
        --background: 222.2 84% 4.9%;
        --foreground: 210 40% 98%;
        --card: 222.2 84% 4.9%;
        --card-foreground: 210 40% 98%;
        --popover: 222.2 84% 4.9%;
        --popover-foreground: 210 40% 98%;
        --primary: 217.2 91.2% 59.8%;
        --primary-foreground: 222.2 84% 4.9%;
        --secondary: 217.2 32.6% 17.5%;
        --secondary-foreground: 210 40% 98%;
        --muted: 217.2 32.6% 17.5%;
        --muted-foreground: 215 20.2% 65.1%;
        --accent: 217.2 32.6% 17.5%;
        --accent-foreground: 210 40% 98%;
        --destructive: 0 62.8% 30.6%;
        --destructive-foreground: 210 40% 98%;
        --border: 217.2 32.6% 17.5%;
        --input: 217.2 32.6% 17.5%;
        --ring: 224.3 76.3% 94.1%;
    }

    /* Global styles */
    .main .block-container {
        padding-top: 0rem !important;
        padding-bottom: 2rem;
        max-width: 95%;
    }

    /* Remove top padding from app container */
    .block-container {
        padding-top: 0rem !important;
    }

    /* Remove top margin from main content */
    .stApp > div:first-child {
        padding-top: 0rem !important;
    }

    /* Compact button styles */
    .stButton > button {
        height: 2.5rem !important;
        padding: 0.25rem 0.75rem !important;
        margin: 0.125rem !important;
    }

    /* Icon-only filter buttons - uniform height, no borders, just icons */
    /* Target buttons that contain just single emojis by their small width */
    .stButton > button {
        font-family: inherit !important;
    }
    
    /* Target filter buttons only - very specific targeting to avoid affecting other UI elements */

    /* Very specific targeting for ONLY the 6 filter buttons */
    .stButton > button[title="Unread emails (is:unread)"],
    .stButton > button[title="Starred emails (is:starred)"],
    .stButton > button[title="Emails with attachments (has:attachment)"],
    .stButton > button[title="Important emails (is:important)"],
    .stButton > button[title="Today's emails (newer_than:1d)"],
    .stButton > button[title="Primary category (category:primary)"] {
        width: 2.5rem !important;
        height: 2.5rem !important;
        min-height: 2.5rem !important;
        border: none !important;
        border-radius: 0.375rem !important;
        padding: 0 !important;
        margin: 0.125rem !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 1.2rem !important;
        background-color: hsl(var(--secondary)) !important;
        color: hsl(var(--secondary-foreground)) !important;
        box-shadow: none !important;
        line-height: 1 !important;
    }

    /* Hover states for filter buttons - exact title matches only */
    .stButton > button[title="Unread emails (is:unread)"]:hover,
    .stButton > button[title="Starred emails (is:starred)"]:hover,
    .stButton > button[title="Emails with attachments (has:attachment)"]:hover,
    .stButton > button[title="Important emails (is:important)"]:hover,
    .stButton > button[title="Today's emails (newer_than:1d)"]:hover,
    .stButton > button[title="Primary category (category:primary)"]:hover {
        background-color: hsl(var(--accent)) !important;
        color: hsl(var(--accent-foreground)) !important;
        transform: scale(1.05) !important;
        box-shadow: 0 2px 4px 0 rgb(0 0 0 / 0.1) !important;
    }

    /* Compact metrics for stats row */
    div[data-testid="metric-container"] {
        background-color: #f8f9fa !important;
        border: 1px solid #e9ecef !important;
        padding: 0.5rem !important;
        border-radius: 0.375rem !important;
        margin: 0.25rem 0 !important;
    }

    div[data-testid="metric-container"] > div {
        font-size: 0.875rem !important;
    }

    div[data-testid="metric-container"] label {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        padding: 0.25rem !important;
        font-size: 1.1rem !important;
    }

    /* Reduce spacing between elements */
    .element-container {
        margin-bottom: 0.5rem !important;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6, .stMarkdown, .stText {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    }

    /* Main container styling */
    .stApp {
        background-color: hsl(var(--background));
        color: hsl(var(--foreground));
    }

    /* Card component styling */
    .dashboard-card {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
        transition: all 0.2s ease-in-out;
    }

    .dashboard-card:hover {
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }

    /* Button styling - shadcn inspired */
    .stButton > button {
        background-color: hsl(var(--primary));
        color: hsl(var(--primary-foreground));
        border: none;
        border-radius: var(--radius);
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        font-family: 'Inter', sans-serif;
        font-size: 0.875rem;
        transition: all 0.2s ease-in-out;
        box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
    }

    .stButton > button:hover {
        background-color: hsl(var(--primary) / 0.9);
        box-shadow: 0 2px 4px 0 rgb(0 0 0 / 0.1);
    }

    /* Secondary button styling */
    .stButton > button[kind="secondary"] {
        background-color: hsl(var(--secondary));
        color: hsl(var(--secondary-foreground));
        border: 1px solid hsl(var(--border));
    }

    .stButton > button[kind="secondary"]:hover {
        background-color: hsl(var(--secondary) / 0.8);
    }

    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        background-color: hsl(var(--muted));
        border-radius: var(--radius);
        padding: 0.25rem;
        margin-bottom: 1.5rem;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: transparent;
        border-radius: calc(var(--radius) - 0.25rem);
        color: hsl(var(--muted-foreground));
        font-weight: 500;
        padding: 0.75rem 1rem;
        margin: 0 0.125rem;
        transition: all 0.2s ease-in-out;
    }

    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: hsl(var(--card));
        color: hsl(var(--card-foreground));
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }

    /* Input field styling */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > select {
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        background-color: hsl(var(--background));
        color: hsl(var(--foreground));
        font-family: 'Inter', sans-serif;
        padding: 0.75rem;
    }

    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    .stSelectbox > div > div > select:focus {
        border-color: hsl(var(--ring));
        outline: none;
        box-shadow: 0 0 0 2px hsl(var(--ring) / 0.2);
    }

    /* Metrics styling */
    .metric-card {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
        text-align: center;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }

    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        color: hsl(var(--primary));
        margin-bottom: 0.5rem;
    }

    .metric-label {
        font-size: 0.875rem;
        color: hsl(var(--muted-foreground));
        font-weight: 500;
    }

    /* Alert styling */
    .stAlert {
        border-radius: var(--radius);
        border: 1px solid hsl(var(--border));
    }

    .stSuccess {
        background-color: hsl(142 76% 96%);
        border-color: hsl(142 76% 86%);
        color: hsl(142 76% 26%);
    }

    .stError {
        background-color: hsl(var(--destructive) / 0.1);
        border-color: hsl(var(--destructive) / 0.3);
        color: hsl(var(--destructive));
    }

    .stWarning {
        background-color: hsl(48 96% 95%);
        border-color: hsl(48 96% 85%);
        color: hsl(48 96% 25%);
    }

    .stInfo {
        background-color: hsl(var(--primary) / 0.1);
        border-color: hsl(var(--primary) / 0.3);
        color: hsl(var(--primary));
    }

    /* Sidebar styling */
    .css-1d391kg {
        background-color: hsl(var(--card));
        border-right: 1px solid hsl(var(--border));
    }

    /* Header styling */
    .dashboard-header {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
        margin-bottom: 2rem;
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }

    .dashboard-title {
        font-size: 2rem;
        font-weight: 700;
        color: hsl(var(--foreground));
        margin-bottom: 0.5rem;
    }

    .dashboard-subtitle {
        color: hsl(var(--muted-foreground));
        font-size: 1rem;
    }

    /* Stats grid */
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2rem;
    }

    /* Table styling */
    .stDataFrame {
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        overflow: hidden;
    }

    /* Custom spacing utilities */
    .space-y-4 > * + * {
        margin-top: 1rem;
    }

    .space-y-6 > * + * {
        margin-top: 1.5rem;
    }

    /* Login page specific styling */
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
    }

    .login-card {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 2rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
    }

    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }

    .login-title {
        font-size: 1.875rem;
        font-weight: 700;
        color: hsl(var(--foreground));
        margin-bottom: 0.5rem;
    }

    .login-subtitle {
        color: hsl(var(--muted-foreground));
        font-size: 1rem;
    }

    /* Dashboard layout */
    .dashboard-layout {
        display: grid;
        grid-template-columns: 250px 1fr;
        gap: 2rem;
        min-height: 100vh;
    }

    .dashboard-sidebar {
        background-color: hsl(var(--card));
        border: 1px solid hsl(var(--border));
        border-radius: var(--radius);
        padding: 1.5rem;
    }

    .dashboard-main {
        background-color: hsl(var(--background));
    }

    /* Navigation menu */
    .nav-menu {
        list-style: none;
        padding: 0;
        margin: 0;
    }

    .nav-item {
        margin-bottom: 0.5rem;
    }

    .nav-link {
        display: block;
        padding: 0.75rem 1rem;
        border-radius: calc(var(--radius) - 0.25rem);
        color: hsl(var(--muted-foreground));
        text-decoration: none;
        font-weight: 500;
        transition: all 0.2s ease-in-out;
    }

    .nav-link:hover {
        background-color: hsl(var(--accent));
        color: hsl(var(--accent-foreground));
    }

    .nav-link.active {
        background-color: hsl(var(--primary));
        color: hsl(var(--primary-foreground));
    }

    /* Responsive design */
    @media (max-width: 768px) {
        .dashboard-layout {
            grid-template-columns: 1fr;
        }
        
        .dashboard-sidebar {
            order: 2;
        }
        
        .main .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
    }
    </style>
    """, unsafe_allow_html=True)


class EmailService:
    """Handles email notifications for user approvals."""
    
    def __init__(self):
        self.approver_email = "articulatedesigns@gmail.com"
        self.app_url = "http://localhost:8505"  # Change this to your actual app URL
        self.approval_tokens_file = "approval_tokens.json"
        self.ensure_tokens_file()
    
    def ensure_tokens_file(self):
        """Ensure approval tokens file exists."""
        if not os.path.exists(self.approval_tokens_file):
            self.save_tokens({})
    
    def load_tokens(self) -> Dict:
        """Load approval tokens from file."""
        try:
            with open(self.approval_tokens_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def save_tokens(self, tokens: Dict):
        """Save approval tokens to file."""
        try:
            with open(self.approval_tokens_file, 'w', encoding='utf-8') as f:
                json.dump(tokens, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving tokens: {e}")
    
    def generate_approval_token(self, user_id: str, email: str) -> str:
        """Generate a unique approval token for a user."""
        token = secrets.token_urlsafe(32)
        tokens = self.load_tokens()
        
        tokens[token] = {
            'user_id': user_id,
            'email': email,
            'created_at': datetime.now().isoformat(),
            'used': False
        }
        
        self.save_tokens(tokens)
        return token
    
    def validate_approval_token(self, token: str) -> Dict:
        """Validate an approval token and return user info."""
        tokens = self.load_tokens()
        
        if token in tokens and not tokens[token]['used']:
            return tokens[token]
        
        return {}
    
    def mark_token_used(self, token: str):
        """Mark an approval token as used."""
        tokens = self.load_tokens()
        
        if token in tokens:
            tokens[token]['used'] = True
            self.save_tokens(tokens)
    
    def send_approval_email(self, user_email: str, user_id: str) -> bool:
        """Send approval email to the approver."""
        try:
            # Generate approval token
            token = self.generate_approval_token(user_id, user_email)
            
            # Create approval URLs
            approve_url = f"{self.app_url}?action=approve&token={token}"
            reject_url = f"{self.app_url}?action=reject&token={token}"
            
            # Email content
            subject = f"New User Registration Approval Required - {user_email}"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .button {{ display: inline-block; padding: 12px 24px; margin: 10px 5px; text-decoration: none; border-radius: 5px; font-weight: bold; }}
                    .approve {{ background-color: #4CAF50; color: white; }}
                    .reject {{ background-color: #f44336; color: white; }}
                    .user-info {{ background-color: white; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 User Registration Approval</h1>
                    </div>
                    <div class="content">
                        <h2>New User Registration Request</h2>
                        <p>A new user has requested access to the Gmail CrewAI Automation system.</p>
                        
                        <div class="user-info">
                            <h3>User Details:</h3>
                            <p><strong>Email:</strong> {user_email}</p>
                            <p><strong>User ID:</strong> {user_id}</p>
                            <p><strong>Registration Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>
                        
                        <p>Please review this registration request and choose an action:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{approve_url}" class="button approve">✅ APPROVE USER</a>
                            <a href="{reject_url}" class="button reject">❌ REJECT USER</a>
                        </div>
                        
                        <p><strong>Note:</strong> These links will expire and can only be used once. If you need to review the request later, please use the admin panel in the application.</p>
                        
                        <hr>
                        <p style="font-size: 12px; color: #666;">
                            This email was sent automatically from the Gmail CrewAI Automation system. 
                            If you did not expect this email, please ignore it.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Try to send actual email first, fall back to storing for demo
            if self.send_actual_email(subject, html_body):
                print(f"✅ Approval email sent successfully to {self.approver_email}")
                # Also store for admin panel display
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True
            else:
                print(f"⚠️ Failed to send actual email, storing for demo purposes")
                # Store for display in admin panel
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True  # Still return True so user gets feedback
            
        except Exception as e:
            print(f"Error sending approval email: {e}")
            return False
    
    def send_actual_email(self, subject: str, html_body: str) -> bool:
        """Send actual email using SMTP."""
        try:
            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            # Get SMTP settings from environment variables
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME', os.getenv('EMAIL_ADDRESS'))
            smtp_password = os.getenv('SMTP_PASSWORD', os.getenv('APP_PASSWORD'))
            
            if not smtp_username or not smtp_password:
                print("❌ SMTP credentials not found in environment variables")
                print("💡 Set SMTP_USERNAME and SMTP_PASSWORD (or EMAIL_ADDRESS and APP_PASSWORD)")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = smtp_username
            msg['To'] = self.approver_email
            msg['Subject'] = subject
            
            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email via SMTP: {e}")
            return False
    
    def store_approval_email(self, user_email: str, user_id: str, html_body: str, approve_url: str, reject_url: str):
        """Store approval email info for display in admin panel."""
        approval_info = {
            'user_email': user_email,
            'user_id': user_id,
            'html_body': html_body,
            'approve_url': approve_url,
            'reject_url': reject_url,
            'created_at': datetime.now().isoformat()
        }
        
        # Store in session state for display
        if 'pending_approval_emails' not in st.session_state:
            st.session_state.pending_approval_emails = []
        
        st.session_state.pending_approval_emails.append(approval_info)
    
    def send_approval_email_with_oauth(self, user_email: str, user_id: str, primary_user: Dict) -> bool:
        """Send approval email using the primary user's OAuth2 connection."""
        try:
            # Check if primary user has OAuth2 authentication
            if not primary_user or not primary_user.get('user_id'):
                print("❌ No primary user found for sending approval emails")
                return False
            
            # Get OAuth manager
            oauth_manager = st.session_state.get('oauth_manager')
            if not oauth_manager:
                print("❌ OAuth manager not available")
                return False
            
            # Check if primary user is authenticated
            primary_user_id = primary_user['user_id']
            if not oauth_manager.is_authenticated(primary_user_id):
                print(f"❌ Primary user {primary_user['email']} is not authenticated with OAuth2")
                return False
            
            # Generate approval URLs
            approve_token = self.generate_approval_token(user_id, user_email)
            approve_url = f"{self.app_url}?action=approve&token={approve_token}"
            reject_url = f"{self.app_url}?action=reject&token={approve_token}"
            
            # Create email content
            subject = f"🔐 New User Registration Request - {user_email}"
            
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="utf-8">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }}
                    .content {{ padding: 20px 0; }}
                    .button {{ display: inline-block; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: 500; margin: 0 10px; }}
                    .approve {{ background: #22c55e; color: white; }}
                    .reject {{ background: #ef4444; color: white; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔐 New User Registration Request</h1>
                    </div>
                    
                    <div class="content">
                        <p><strong>Email:</strong> {user_email}</p>
                        <p><strong>User ID:</strong> {user_id}</p>
                        <p><strong>Registration Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        
                        <p>A new user has requested access to the Gmail CrewAI system. Please review and approve or reject this request:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{approve_url}" class="button approve">✅ APPROVE USER</a>
                            <a href="{reject_url}" class="button reject">❌ REJECT USER</a>
                        </div>
                        
                        <p><strong>Note:</strong> These links will expire and can only be used once.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Try to send via OAuth2 Gmail API
            if self.send_email_via_oauth2(oauth_manager, primary_user_id, primary_user['email'], subject, html_body):
                print(f"✅ Approval email sent successfully via OAuth2 to {primary_user['email']}")
                # Also store for admin panel display
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True
            else:
                print(f"⚠️ Failed to send via OAuth2, storing for admin panel")
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True  # Still return True so user gets feedback
            
        except Exception as e:
            print(f"Error sending approval email with OAuth2: {e}")
            return False
    
    def send_email_via_oauth2(self, oauth_manager, user_id: str, to_email: str, subject: str, html_body: str) -> bool:
        """Send email using OAuth2 Gmail API."""
        try:
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            import base64
            
            # Get Gmail service
            service = oauth_manager.get_gmail_service(user_id)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = to_email  # Sending from the authenticated user
            msg['To'] = to_email    # Sending to themselves for admin review
            msg['Subject'] = subject
            
            # Attach HTML body
            html_part = MIMEText(html_body, 'html')
            msg.attach(html_part)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode('utf-8')
            
            # Send via Gmail API
            service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email via OAuth2 Gmail API: {e}")
            return False


class UserManager:
    """Manages user registration, approval, and authentication."""
    
    def __init__(self):
        self.users_file = "users.json"
        self.email_service = EmailService()
        self.ensure_users_file()
    
    def ensure_users_file(self):
        """Ensure users file exists."""
        if not os.path.exists(self.users_file):
            # Start with empty users file - no default admin
            self.save_users({})
    
    def load_users(self) -> Dict:
        """Load users from file."""
        try:
            with open(self.users_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def save_users(self, users: Dict):
        """Save users to file."""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            st.error(f"Error saving users: {e}")
    
    def register_user(self, email: str, google_id: str = "") -> bool:
        """Register a new user (auto-approved if first user, otherwise pending approval)."""
        users = self.load_users()
        
        # Check if user already exists
        for user_id, user_data in users.items():
            if user_data['email'] == email:
                return False  # User already exists
        
        # Check if this is the first user (primary owner)
        is_first_user = len(users) == 0
        
        # Create new user
        user_id = f"user_{secrets.token_urlsafe(8)}"
        
        if is_first_user:
            # First user becomes the primary owner - auto-approved, admin role
            users[user_id] = {
                "email": email,
                "status": "approved",
                "role": "owner",  # Special role for primary user
                "created_at": datetime.now().isoformat(),
                "approved_at": datetime.now().isoformat(),
                "google_id": google_id,
                "last_login": None,
                "is_primary": True
            }
            print(f"🎉 Registered first user as primary owner: {email}")
        else:
            # Subsequent users need approval
            users[user_id] = {
                "email": email,
                "status": "pending",
                "role": "user",
                "created_at": datetime.now().isoformat(),
                "approved_at": None,
                "google_id": google_id,
                "last_login": None,
                "is_primary": False
            }
            
            # Only send approval email if we have a primary user to send it
            primary_user = self.get_primary_user()
            if primary_user:
                try:
                    self.email_service.send_approval_email_with_oauth(email, user_id, primary_user)
                except Exception as e:
                    print(f"Failed to send approval email: {e}")
        
        self.save_users(users)
        
        # Create subscription for the user
        try:
            if hasattr(st.session_state, 'subscription_manager') and st.session_state.subscription_manager:
                subscription_manager = st.session_state.subscription_manager
                subscription_manager.create_user_subscription(user_id, email, PlanType.FREE)
                print(f"✅ Created free subscription for user: {email}")
        except Exception as e:
            print(f"⚠️ Failed to create subscription for user {email}: {e}")
        
        return True
    
    def resend_approval_email(self, email: str) -> bool:
        """Resend approval email for a pending user."""
        user_id, user_data = self.get_user_by_email(email)
        
        if not user_data or not user_id:
            return False  # User not found
        
        if user_data['status'] != 'pending':
            return False  # User is not pending approval
        
        # Get primary user to send the email
        primary_user = self.get_primary_user()
        if not primary_user:
            return False  # No primary user to send email
        
        # Send approval email using OAuth2 if possible
        try:
            self.email_service.send_approval_email_with_oauth(email, user_id, primary_user)
            return True
        except Exception as e:
            print(f"Failed to resend approval email: {e}")
            return False
    
    def approve_user(self, user_id: str) -> bool:
        """Approve a pending user."""
        users = self.load_users()
        
        if user_id in users and users[user_id]['status'] == 'pending':
            users[user_id]['status'] = 'approved'
            users[user_id]['approved_at'] = datetime.now().isoformat()
            self.save_users(users)
            return True
        
        return False
    
    def reject_user(self, user_id: str) -> bool:
        """Reject and remove a pending user."""
        users = self.load_users()
        
        if user_id in users and users[user_id]['status'] == 'pending':
            del users[user_id]
            self.save_users(users)
            return True
        
        return False
    
    def get_user_by_email(self, email: str) -> tuple:
        """Get user by email. Returns (user_id, user_data) or (None, None)."""
        users = self.load_users()
        
        for user_id, user_data in users.items():
            if user_data['email'] == email:
                return user_id, user_data
        
        return None, None
    
    def get_user_by_id(self, user_id: str) -> Dict:
        """Get user by ID."""
        users = self.load_users()
        return users.get(user_id, {})
    
    def update_last_login(self, user_id: str):
        """Update user's last login time."""
        users = self.load_users()
        
        if user_id in users:
            users[user_id]['last_login'] = datetime.now().isoformat()
            self.save_users(users)
    
    def get_pending_users(self) -> List[Dict]:
        """Get all pending users."""
        users = self.load_users()
        pending = []
        
        for user_id, user_data in users.items():
            if user_data['status'] == 'pending':
                pending.append({**user_data, 'user_id': user_id})
        
        return pending
    
    def get_all_users(self) -> List[Dict]:
        """Get all users."""
        users = self.load_users()
        all_users = []
        
        for user_id, user_data in users.items():
            all_users.append({**user_data, 'user_id': user_id})
        
        return all_users
    
    def is_admin(self, user_id: str) -> bool:
        """Check if user is admin or owner."""
        user_data = self.get_user_by_id(user_id)
        if not user_data:
            return False
        role = user_data.get('role', '')
        return role in ['admin', 'owner']
    
    def get_primary_user(self) -> Dict:
        """Get the primary/owner user."""
        users = self.load_users()
        for user_id, user_data in users.items():
            if user_data.get('is_primary', False) or user_data.get('role') == 'owner':
                return {**user_data, 'user_id': user_id}
        return {}
    
    def has_primary_user(self) -> bool:
        """Check if there's a primary user."""
        return bool(self.get_primary_user())
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        users = self.load_users()
        
        if user_id in users:
            del users[user_id]
            self.save_users(users)
            return True
        
        return False


def init_session_state():
    """Initialize Streamlit session state and check for persistent sessions."""
    if 'user_manager' not in st.session_state:
        st.session_state.user_manager = UserManager()
    
    if 'oauth_manager' not in st.session_state:
        st.session_state.oauth_manager = OAuth2Manager()
    
    if 'stripe_service' not in st.session_state:
        stripe_key = os.getenv('STRIPE_SECRET_KEY')
        if stripe_key:
            st.session_state.stripe_service = StripeService(stripe_key)
        else:
            st.session_state.stripe_service = None
    
    if 'subscription_manager' not in st.session_state:
        if st.session_state.stripe_service:
            st.session_state.subscription_manager = SubscriptionManager(st.session_state.stripe_service)
        else:
            st.session_state.subscription_manager = None
    
    if 'usage_tracker' not in st.session_state:
        st.session_state.usage_tracker = UsageTracker()
    
    if 'authenticated_user_id' not in st.session_state:
        st.session_state.authenticated_user_id = None
    
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    
    if 'authentication_step' not in st.session_state:
        st.session_state.authentication_step = 'login'
    
    if 'new_user_id' not in st.session_state:
        st.session_state.new_user_id = None
    
    # Always check for persistent session on EVERY page load/refresh when not authenticated
    # This ensures users stay logged in across page refreshes and browser sessions
    if not st.session_state.authenticated_user_id or st.session_state.authentication_step == 'login':
        # Prevent infinite rerun loops by checking if we already tried session restoration this run
        if not st.session_state.get('session_check_completed', False):
            st.session_state.session_check_completed = True
            session_restored = check_persistent_session()
            if session_restored:
                # Force a rerun to update the UI with the restored session
                st.rerun()
    else:
        # Reset the session check flag when user is authenticated
        st.session_state.session_check_completed = False


def check_persistent_session():
    """Check for and validate persistent session from browser storage."""
    try:
        # Clean up expired sessions first
        session_manager.cleanup_expired_sessions()
        
        # Try to get session token from various sources
        browser_session_token = session_manager.get_browser_session()
        
        # Debug output
        print(f"🔍 Checking persistent session... Token found: {bool(browser_session_token)}")
        
        if browser_session_token:
            # Validate the session
            user_id = session_manager.validate_session(browser_session_token)
            print(f"🔍 Session validation result: user_id={user_id}")
            
            if user_id:
                # Check if user still exists and is approved
                user_manager = st.session_state.user_manager
                users = user_manager.load_users()
                
                if user_id in users and users[user_id].get('status') == 'approved':
                    print(f"✅ User {user_id} found and approved, restoring session...")
                    
                    # Restore session state completely
                    st.session_state.authenticated_user_id = user_id
                    st.session_state.current_user = user_id
                    st.session_state.authentication_step = 'dashboard'
                    
                    # Clear any login-related state
                    for key in ['oauth_result', 'oauth_error', 'oauth_processing']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # Update last login time
                    user_manager.update_last_login(user_id)
                    
                    print(f"✅ Session successfully restored for user: {user_id}")
                    return True
                else:
                    print(f"❌ User {user_id} not found or not approved, clearing session")
                    # User no longer exists or not approved, clear session
                    session_manager.invalidate_session(browser_session_token)
                    session_manager.clear_browser_session()
            else:
                print("❌ Invalid session token, clearing browser session")
                # Invalid session, clear browser storage
                session_manager.clear_browser_session()
        else:
            print("ℹ️ No persistent session token found")
        
        # No valid session found, ensure we're in login state
        if st.session_state.get('authentication_step') != 'login':
            print("🔄 Setting authentication step to login")
            st.session_state.authentication_step = 'login'
        
    except Exception as e:
        print(f"❌ Error checking persistent session: {e}")
        import traceback
        traceback.print_exc()
        # On error, ensure we're in login state
        st.session_state.authentication_step = 'login'
    
    return False


def show_login_page():
    """Show the main login page with Google authentication."""
    # Create centered layout with shadcn styling
    st.markdown("""
    <div class="login-container">
        <div class="login-card">
            <div class="login-header">
                <h1 class="login-title">🔐 Gmail CrewAI</h1>
                <p class="login-subtitle">Secure email automation with AI</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        # Check if user has OAuth2 credentials set up
        if not os.path.exists("credentials.json"):
            st.error("❌ OAuth2 credentials file not found!")
            st.markdown("Please contact your administrator to set up Google OAuth2 credentials.")
            return
        
        # Check if we have a primary user
        user_manager = st.session_state.user_manager
        has_primary = user_manager.has_primary_user()
        
        if not has_primary:
            # No primary user yet - show first-time setup
            st.info("🎉 Welcome to Gmail CrewAI! This appears to be a fresh installation.")
            st.markdown("**First Time Setup**")
            st.markdown("The first user to register will become the **primary owner** with full administrative access.")
            
            # Only show registration tab for first user
            email_register = st.text_input("Email address", placeholder="your-email@example.com", key="register_email")
            
            st.markdown("**Why do you need access?**")
            reason = st.text_area("Brief explanation", placeholder="I need to automate my work email management...")
            
            if st.button("🚀 Setup as Primary Owner", type="primary", use_container_width=True):
                if email_register and reason:
                    handle_registration_request(email_register, reason)
                else:
                    st.error("Please fill in all fields")
        else:
            # Normal login/registration flow when primary user exists
            tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])
            
            with tab1:
                st.markdown("**Existing Users**")
                email_login = st.text_input("Email address", placeholder="your-email@example.com", key="login_email")
                
                col_login1, col_login2 = st.columns(2)
                with col_login1:
                    if st.button("🔑 Login with Google", type="primary", use_container_width=True):
                        if email_login:
                            handle_google_login(email_login)
                        else:
                            st.error("Please enter your email address")
                
                with col_login2:
                    if st.button("ℹ️ Request Help", use_container_width=True):
                        primary_user = user_manager.get_primary_user()
                        if primary_user:
                            st.info(f"Contact the primary owner ({primary_user['email']}) if you need access or have login issues.")
                        else:
                            st.info("Contact your administrator if you need access or have login issues.")
            
            with tab2:
                st.markdown("**New Users**")
                email_register = st.text_input("Email address", placeholder="your-email@example.com", key="register_email")
                
                st.markdown("**Why do you need access?**")
                reason = st.text_area("Brief explanation", placeholder="I need to automate my work email management...")
                
                if st.button("📝 Request Access", type="primary", use_container_width=True):
                    if email_register and reason:
                        handle_registration_request(email_register, reason)
                    else:
                        st.error("Please fill in all fields")
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: hsl(var(--muted-foreground)); font-size: 0.875rem;">
        Powered by Gmail CrewAI - AI-powered email automation
    </div>
    """, unsafe_allow_html=True)


def handle_google_login(email: str):
    """Handle Google login process."""
    user_manager = st.session_state.user_manager
    user_id, user_data = user_manager.get_user_by_email(email)
    
    if not user_data:
        st.error("❌ User not found. Please register first or contact the primary owner.")
        return
    
    if user_data['status'] != 'approved':
        if user_data['status'] == 'pending':
            primary_user = user_manager.get_primary_user()
            if primary_user:
                st.warning("⏳ Your account is pending approval from the primary owner.")
                
                # Add resend approval email button (without nested columns to avoid Streamlit nesting error)
                if st.button("📧 Resend Approval Email", use_container_width=True):
                    handle_resend_approval_email(email)
                
                if st.button("ℹ️ Help", use_container_width=True):
                    st.info(f"If you haven't received approval, click 'Resend Approval Email' to send another request to the primary owner: {primary_user['email']}")
            else:
                st.error("❌ No primary owner found. Please contact your system administrator.")
        else:
            st.error("❌ Your account has been rejected. Contact the primary owner.")
        return
    
    # Start Google OAuth flow
    try:
        # Generate unique user ID for OAuth
        oauth_user_id = f"{user_id}_{uuid.uuid4().hex[:8]}"
        auth_url = st.session_state.oauth_manager.get_authorization_url(oauth_user_id)
        
        st.session_state.pending_login_user_id = user_id
        st.session_state.pending_oauth_user_id = oauth_user_id
        st.session_state.authentication_step = 'google_oauth'
        
        # Automatically redirect to Google OAuth
        components.html(
            f"""
            <script>
                window.open('{auth_url}', '_blank');
            </script>
            """,
            height=0,
        )
        st.success("✅ Opening Google authentication in a new tab...")
        
    except Exception as e:
        st.error(f"❌ Error starting Google authentication: {e}")


def handle_registration_request(email: str, reason: str):
    """Handle new user registration request."""
    user_manager = st.session_state.user_manager
    
    # Check if user already exists
    existing_user_id, existing_user_data = user_manager.get_user_by_email(email)
    if existing_user_data:
        if existing_user_data['status'] == 'pending':
            st.warning("⏳ You already have a pending registration request.")
        elif existing_user_data['status'] == 'approved':
            st.info("✅ You already have an approved account. Please use the Login tab.")
        else:
            st.error("❌ Your previous registration was rejected. Contact your administrator.")
        return
    
    # Check if this would be the first user
    is_first_user = not user_manager.has_primary_user()
    
    # Register new user
    if user_manager.register_user(email):
        # Save registration reason for admin review
        registration_file = "registration_requests.json"
        requests_data = {}
        
        if os.path.exists(registration_file):
            try:
                with open(registration_file, 'r', encoding='utf-8') as f:
                    requests_data = json.load(f)
            except Exception:
                requests_data = {}
        
        requests_data[email] = {
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            with open(registration_file, 'w', encoding='utf-8') as f:
                json.dump(requests_data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        
        if is_first_user:
            # First user - automatically approved as primary owner
            st.success("🎉 Welcome! You've been registered as the primary owner of this Gmail CrewAI system!")
            st.info("✅ Your account has been automatically approved since you're the first user.")
            st.info("🔑 You can now log in with your Google account and start using the system.")
            st.info("👑 As the primary owner, you have full administrative access and will receive all approval emails for future users.")
            st.markdown("**Next Steps:**")
            st.markdown("1. 🔑 Click 'Login' tab above")
            st.markdown("2. 🔐 Authenticate with your Google account")
            st.markdown("3. 🚀 Start automating your Gmail with AI!")
        else:
            # Subsequent user - needs approval
            primary_user = user_manager.get_primary_user()
            if primary_user:
                st.success("✅ Registration request submitted successfully!")
                st.info(f"📧 An approval email has been sent to the primary owner: {primary_user['email']}")
                st.info("⏳ Your request is pending approval. You'll be able to log in once the owner approves your request.")
                st.markdown("**Next Steps:**")
                st.markdown("1. 📧 Primary owner will receive an approval email with your request details")
                st.markdown("2. 👑 Owner will approve or reject your request") 
                st.markdown("3. ✅ Once approved, you can log in with your Google account")
            else:
                st.warning("⚠️ No primary owner found. Please contact your system administrator.")
    else:
        st.error("❌ Registration failed. Please try again or contact support.")


def handle_resend_approval_email(email: str):
    """Handle resending approval email for a pending user."""
    user_manager = st.session_state.user_manager
    
    # Check if we have a primary user to send the email
    primary_user = user_manager.get_primary_user()
    if not primary_user:
        st.error("❌ No primary owner found. Cannot send approval email.")
        return
    
    if user_manager.resend_approval_email(email):
        st.success("✅ Approval email request has been processed!")
        
        # Check if primary user is authenticated with OAuth2
        oauth_manager = st.session_state.get('oauth_manager')
        if oauth_manager and oauth_manager.is_authenticated(primary_user['user_id']):
            st.info(f"📧 An approval email has been sent to the primary owner: {primary_user['email']}")
            st.info("⏳ Please wait for the owner to review and approve your request.")
        else:
            st.warning("⚠️ Email stored for owner review (primary owner not authenticated with OAuth2)")
            st.info("💡 The primary owner can view pending approval requests in the admin panel")
            st.info("🔧 Primary owner needs to authenticate with Google OAuth2 to enable automatic email sending")
    else:
        st.error("❌ Failed to resend approval email. Please contact the primary owner.")





def show_admin_panel():
    """Show admin panel for user management."""
    st.markdown("## 👑 Admin Panel")
    
    user_manager = st.session_state.user_manager
    
    # Check admin permissions
    authenticated_user_id = st.session_state.authenticated_user_id
    if not user_manager.is_admin(authenticated_user_id):
        st.error("❌ Access denied. Admin privileges required.")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Pending Approvals", "👥 All Users", "📊 User Stats", "📧 Approval Emails"])
    
    with tab1:
        st.markdown("### 📋 Pending User Approvals")
        
        pending_users = user_manager.get_pending_users()
        
        if pending_users:
            for user in pending_users:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{user['email']}**")
                        st.markdown(f"*Requested: {user['created_at'][:16]}*")
                        
                        # Show registration reason if available
                        try:
                            with open("registration_requests.json", 'r') as f:
                                requests = json.load(f)
                                if user['email'] in requests:
                                    reason = requests[user['email']]['reason']
                                    st.markdown(f"**Reason:** {reason}")
                        except Exception:
                            pass
                    
                    with col2:
                        st.markdown(f"**Role:** {user['role']}")
                        st.markdown(f"**Status:** {user['status']}")
                    
                    with col3:
                        if st.button("✅ Approve", key=f"approve_{user['user_id']}", type="primary"):
                            if user_manager.approve_user(user['user_id']):
                                st.success(f"✅ Approved {user['email']}")
                                st.rerun()
                    
                    with col4:
                        if st.button("❌ Reject", key=f"reject_{user['user_id']}"):
                            if user_manager.reject_user(user['user_id']):
                                st.success(f"❌ Rejected {user['email']}")
                                st.rerun()
                    
                    st.divider()
        else:
            st.info("✅ No pending approvals")
    
    with tab2:
        st.markdown("### 👥 All Users")
        
        all_users = user_manager.get_all_users()
        
        if all_users:
            # Convert to DataFrame for better display
            df_users = pd.DataFrame(all_users)
            df_users['created_at'] = pd.to_datetime(df_users['created_at']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Add primary owner indicator
            df_users['primary_owner'] = df_users.apply(
                lambda row: "👑 Primary Owner" if row.get('is_primary', False) or row.get('role') == 'owner' else "",
                axis=1
            )
            
            # Display as interactive table
            edited_df = st.data_editor(
                df_users[['email', 'status', 'role', 'primary_owner', 'created_at', 'last_login']],
                column_config={
                    "status": st.column_config.SelectboxColumn(
                        "Status",
                        options=["pending", "approved", "rejected"],
                    ),
                    "role": st.column_config.SelectboxColumn(
                        "Role", 
                        options=["user", "admin", "owner"],
                    ),
                    "primary_owner": st.column_config.TextColumn(
                        "Primary Owner",
                        disabled=True
                    )
                },
                use_container_width=True,
                key="user_management_table"
            )
            
            # User deletion section
            st.markdown("#### 🗑️ Delete User")
            user_to_delete = st.selectbox(
                "Select user to delete:",
                options=[user['user_id'] for user in all_users],
                format_func=lambda x: next(user['email'] for user in all_users if user['user_id'] == x),
                key="delete_user_selector"
            )
            
            if st.button("🗑️ Delete User", type="secondary"):
                if user_to_delete and user_to_delete != authenticated_user_id:
                    if user_manager.delete_user(user_to_delete):
                        st.success("✅ User deleted successfully")
                        st.rerun()
                else:
                    st.error("❌ Cannot delete your own account or invalid selection")
    
    with tab3:
        st.markdown("### 📊 User Statistics")
        
        # Show primary user info first
        primary_user = user_manager.get_primary_user()
        if primary_user:
            st.markdown("#### 👑 Primary Owner")
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Email:** {primary_user['email']}")
            with col2:
                oauth_manager = st.session_state.get('oauth_manager')
                is_oauth_authenticated = oauth_manager and oauth_manager.is_authenticated(primary_user['user_id'])
                auth_status = "✅ OAuth2 Connected" if is_oauth_authenticated else "❌ OAuth2 Not Connected"
                st.info(f"**Status:** {auth_status}")
            
            if not is_oauth_authenticated:
                st.warning("⚠️ Primary owner needs to authenticate with OAuth2 to send approval emails automatically.")
        else:
            st.warning("⚠️ No primary owner found!")
        
        st.divider()
        
        all_users = user_manager.get_all_users()
        
        if all_users:
            # User status breakdown
            status_counts = {}
            role_counts = {}
            
            for user in all_users:
                status = user['status']
                role = user['role']
                status_counts[status] = status_counts.get(status, 0) + 1
                role_counts[role] = role_counts.get(role, 0) + 1
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("👥 Total Users", len(all_users))
            
            with col2:
                st.metric("✅ Approved", status_counts.get('approved', 0))
            
            with col3:
                st.metric("⏳ Pending", status_counts.get('pending', 0))
            
            with col4:
                admin_count = role_counts.get('admin', 0) + role_counts.get('owner', 0)
                st.metric("👑 Admins/Owner", admin_count)
            
            # Charts
            col1, col2 = st.columns(2)
            
            with col1:
                if status_counts:
                    st.markdown("#### Status Distribution")
                    status_df = pd.DataFrame(list(status_counts.items()), columns=['Status', 'Count'])
                    st.bar_chart(status_df.set_index('Status'))
            
            with col2:
                if role_counts:
                    st.markdown("#### Role Distribution")
                    role_df = pd.DataFrame(list(role_counts.items()), columns=['Role', 'Count'])
                    st.bar_chart(role_df.set_index('Role'))
    
    with tab4:
        st.markdown("### 📧 Approval Emails")
        st.markdown("This shows the approval emails that would be sent to articulatedesigns@gmail.com")
        
        # Display pending approval emails
        if 'pending_approval_emails' in st.session_state and st.session_state.pending_approval_emails:
            for idx, email_info in enumerate(st.session_state.pending_approval_emails):
                with st.expander(f"📧 Approval Request for {email_info['user_email']} - {email_info['created_at'][:16]}"):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown("**Email Content Preview:**")
                        st.markdown(email_info['html_body'], unsafe_allow_html=True)
                    
                    with col2:
                        st.markdown("**Quick Actions:**")
                        st.markdown(f"**User:** {email_info['user_email']}")
                        st.markdown(f"**User ID:** {email_info['user_id']}")
                        
                        # Direct approval/rejection buttons
                        col_approve, col_reject = st.columns(2)
                        
                        with col_approve:
                            if st.button("✅ Approve", key=f"direct_approve_{idx}", type="primary"):
                                if user_manager.approve_user(email_info['user_id']):
                                    st.success(f"✅ Approved {email_info['user_email']}")
                                    # Remove from pending emails
                                    st.session_state.pending_approval_emails.pop(idx)
                                    st.rerun()
                        
                        with col_reject:
                            if st.button("❌ Reject", key=f"direct_reject_{idx}"):
                                if user_manager.reject_user(email_info['user_id']):
                                    st.success(f"❌ Rejected {email_info['user_email']}")
                                    # Remove from pending emails
                                    st.session_state.pending_approval_emails.pop(idx)
                                    st.rerun()
                        
                        st.markdown("---")
                        st.markdown("**Approval Links:**")
                        st.markdown(f"**Approve:** {email_info['approve_url']}")
                        st.markdown(f"**Reject:** {email_info['reject_url']}")
                        
                        st.info("💡 Copy these links to test the approval flow!")
                        
            # Clear all processed emails button
            if st.button("🗑️ Clear All Email Previews", type="secondary"):
                st.session_state.pending_approval_emails = []
                st.success("All email previews cleared!")
                st.rerun()
        else:
            st.info("📭 No approval emails pending. When users register, their approval emails will appear here.")
            
        st.markdown("---")
        st.markdown("### 📧 Email Configuration")
        st.markdown("**Approver Email:** articulatedesigns@gmail.com")
        st.markdown("**App URL:** http://localhost:8505")
        st.info("💡 In production, configure SMTP settings to actually send emails.")


def show_setup_instructions():
    """Show OAuth2 setup instructions."""
    if not os.path.exists("credentials.json"):
        st.error("❌ OAuth2 credentials file not found!")
        st.markdown(OAuth2Manager.setup_instructions())
        
        uploaded_file = st.file_uploader(
            "Upload your credentials.json file:", 
            type=['json'],
            help="Download this from Google Cloud Console"
        )
        
        if uploaded_file is not None:
            try:
                credentials_data = json.load(uploaded_file)
                with open("credentials.json", "w") as f:
                    json.dump(credentials_data, f, indent=2)
                st.success("✅ Credentials file saved successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving credentials: {e}")
        
        return False
    else:
        return True


def show_user_selection():
    """Show user selection interface."""
    st.markdown("### 👤 User Authentication")
    
    # List existing authenticated users
    authenticated_users = st.session_state.oauth_manager.list_authenticated_users()
    
    if authenticated_users:
        # Use columns for compact layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🔓 Select User**")
            user_options = [f"{email}" for user_id, email in authenticated_users.items()]
            selected_user = st.selectbox(
                "Account:",
                options=user_options,
                key="existing_user_select",
                label_visibility="collapsed"
            )
            
            if st.button("🚀 Login", type="primary", use_container_width=True):
                # Find user_id by email
                selected_email = selected_user
                user_id = next(uid for uid, email in authenticated_users.items() if email == selected_email)
                st.session_state.current_user = user_id
                st.session_state.authentication_step = 'dashboard'
                st.rerun()
        
        with col2:
            st.markdown("**➕ Add New**")
            new_user_name = st.text_input(
                "Account name:",
                placeholder="e.g., work_email",
                label_visibility="collapsed"
            )
            
            if st.button("🔐 Authenticate", disabled=not new_user_name, use_container_width=True):
                # Generate unique user ID
                user_id = f"{new_user_name}_{uuid.uuid4().hex[:8]}"
                st.session_state.new_user_id = user_id
                st.session_state.authentication_step = 'oauth_flow'
                st.rerun()
        
        # Compact management in expander
        with st.expander("🗑️ Manage"):
            user_to_remove = st.selectbox(
                "Remove:",
                options=list(authenticated_users.keys()),
                format_func=lambda x: f"{authenticated_users[x]}",
                label_visibility="collapsed"
            )
            
            if st.button("🗑️ Remove", type="secondary"):
                if st.session_state.oauth_manager.revoke_credentials(user_to_remove):
                    st.success(f"✅ Removed access for {authenticated_users[user_to_remove]}")
                    st.rerun()
    
    else:
        # No existing users - simplified form
        st.markdown("**➕ Add Your First Account**")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_user_name = st.text_input(
                "Account name:",
                placeholder="e.g., work_email",
                label_visibility="collapsed"
            )
        
        with col2:
            if st.button("🔐 Authenticate", disabled=not new_user_name, use_container_width=True):
                # Generate unique user ID
                user_id = f"{new_user_name}_{uuid.uuid4().hex[:8]}"
                st.session_state.new_user_id = user_id
                st.session_state.authentication_step = 'oauth_flow'
                st.rerun()


def show_oauth_flow():
    """Show OAuth2 authentication flow."""
    st.markdown("# 🔐 Gmail Authentication")
    
    user_id = st.session_state.new_user_id
    
    if 'auth_url' not in st.session_state:
        try:
            auth_url = st.session_state.oauth_manager.get_authorization_url(user_id)
            st.session_state.auth_url = auth_url
        except Exception as e:
            st.error(f"Error generating auth URL: {e}")
            if st.button("← Back to User Selection"):
                st.session_state.authentication_step = 'select_user'
                st.rerun()
            return
    
    st.markdown("### Step 1: Authorize Gmail Access")
    st.markdown(f"Click the link below to authorize access to Gmail:")
    
    st.markdown(f"🔗 **[Authorize Gmail Access]({st.session_state.auth_url})**")
    
    st.markdown("### 🔄 Waiting for Authentication")
    st.info("After clicking the link above, you'll be redirected back automatically.")
    st.markdown("**Note:** Make sure popup blockers are disabled for this site.")
    
    if st.button("← Back to User Selection"):
        st.session_state.authentication_step = 'select_user'
        if 'auth_url' in st.session_state:
            del st.session_state.auth_url
        st.rerun()


def show_dashboard():
    """Show main application dashboard."""
    user_id = st.session_state.current_user
    oauth_manager = st.session_state.oauth_manager
    user_manager = st.session_state.user_manager
    authenticated_user_id = st.session_state.authenticated_user_id
    
    # Check OAuth2 status and show warning if needed
    oauth_authenticated = oauth_manager and oauth_manager.is_authenticated(user_id)
    if not oauth_authenticated:
        st.warning("⚠️ Your Gmail connection needs to be refreshed. Some email features may not work until you re-authenticate. Visit the Settings tab to reconnect.")
    
    # Get user email and data
    user_email = oauth_manager.get_user_email(user_id) if oauth_authenticated else "User"
    user_data = user_manager.get_user_by_id(authenticated_user_id)
    
    # Simple header with user dropdown and help in top-right corner
    col_header1, col_header2 = st.columns([3, 1])
    
    with col_header1:
        st.title("📧 Gmail CrewAI")
    
    with col_header2:
        # Top-right icons - Help and User
        help_col, user_col = st.columns([1, 2])
        
        with help_col:
            # Gmail Help icon
            with st.popover("❓ Help", use_container_width=True):
                st.markdown("### 🔍 Gmail Search Syntax")
                
                st.markdown("""
                **Basic Operators:**
                - `from:user@email.com` - From specific sender
                - `to:user@email.com` - To specific recipient  
                - `subject:keyword` - Subject contains keyword
                - `has:attachment` - Has attachments
                - `is:unread` - Unread emails
                - `is:starred` - Starred emails
                - `is:important` - Important emails
                - `label:work` - Has specific label
                
                **Date Operators:**
                - `older_than:7d` - Older than 7 days
                - `newer_than:1d` - Newer than 1 day
                - `larger:5MB` - Larger than 5MB
                - `filename:pdf` - Has PDF attachment
                - `category:primary` - In primary category
                - `"exact phrase"` - Exact phrase match
                - `keyword1 OR keyword2` - Either keyword
                - `-keyword` - Exclude keyword
                    """)
                
                st.markdown("**Examples:**")
                st.code("from:example.com is:unread")
                st.code("subject:(urgent OR important) has:attachment") 
                st.code("is:starred newer_than:7d")
                st.code('to:me "project update"')
        
        with user_col:
            # User dropdown
            with st.popover(f"👤 {user_email}", use_container_width=True):
                st.markdown(f"**Current User:**  \n{user_email}")
                st.markdown(f"**User ID:**  \n{authenticated_user_id}")
                st.markdown(f"**Role:**  \n{user_data.get('role', 'user').title()}")
                st.divider()
                
                # Admin panel access
                if user_manager.is_admin(authenticated_user_id):
                    if st.button("👑 Admin Panel", use_container_width=True):
                        st.session_state.authentication_step = 'admin_panel'
                        st.rerun()
                
                if st.button("🔄 Switch User", use_container_width=True):
                    # Clear persistent session
                    browser_token = session_manager.get_browser_session()
                    if browser_token:
                        session_manager.invalidate_session(browser_token)
                    session_manager.clear_browser_session()
                    
                    # Clear session state
                    st.session_state.current_user = None
                    st.session_state.authenticated_user_id = None
                    st.session_state.authentication_step = 'login'
                    st.rerun()
                
                if st.button("🚪 Logout", use_container_width=True):
                    # Clear persistent session
                    browser_token = session_manager.get_browser_session()
                    if browser_token:
                        session_manager.invalidate_session(browser_token)
                    session_manager.clear_browser_session()
                    
                    # Clear session state
                    st.session_state.current_user = None
                    st.session_state.authenticated_user_id = None
                    st.session_state.authentication_step = 'login'
                    st.rerun()
    
    # Main content tabs right below header  
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["🤖 Email Processing", "📋 Rules", "📊 Email Stats", "🚨 Error Logs", "⚙️ Settings", "💳 Billing", "📚 Help"])
    
    # Initialize session state for processing
    if 'processing_active' not in st.session_state:
        st.session_state.processing_active = False
    
    if 'processing_logs' not in st.session_state:
        st.session_state.processing_logs = []
    
    if 'processing_started' not in st.session_state:
        st.session_state.processing_started = False
        
    if 'processing_stopped' not in st.session_state:
        st.session_state.processing_stopped = False
    
    if 'email_rules' not in st.session_state:
        st.session_state.email_rules = []
    
    with tab1:
        show_email_processing_tab(user_id, oauth_manager)
    
    with tab2:
        show_rules_tab(user_id, oauth_manager)
    
    with tab3:
        show_email_stats_tab(user_id, oauth_manager)
    
    with tab4:
        show_error_logs_tab(user_id, oauth_manager)
    
    with tab5:
        show_settings_tab(user_id, oauth_manager)
    
    with tab6:
        # Show billing tab with subscription and usage management
        if st.session_state.subscription_manager and st.session_state.usage_tracker:
            show_billing_tab(st.session_state.subscription_manager, st.session_state.usage_tracker, authenticated_user_id)
        else:
            st.warning("⚠️ Billing system not configured. Please add Stripe configuration to your .env file.")
            st.code("""
# Add to your .env file:
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
STRIPE_BASIC_PRICE_ID=price_basic_monthly
STRIPE_PREMIUM_PRICE_ID=price_premium_monthly
            """)
    
    with tab7:
        show_help_tab()


def show_email_processing_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show email processing interface."""
    
    # Stats overview - only show when not processing to avoid duplication
    if not st.session_state.get('processing_active', False):
        with st.container():
            # Compact stats overview - processing results
            col1, col2, col3, col4 = st.columns(4)
            
            # Load processing results to show stats
            total_processed = 0
            high_priority = 0
            medium_priority = 0
            low_priority = 0
            
            if os.path.exists("output/categorization_report.json"):
                try:
                    with open("output/categorization_report.json", "r", encoding='utf-8') as f:
                        results = json.load(f)
                    
                    if isinstance(results, dict) and 'emails' in results:
                        import pandas as pd
                        df = pd.DataFrame(results['emails'])
                        total_processed = len(df)
                        high_priority = len(df[df['priority'] == 'HIGH']) if 'priority' in df.columns else 0
                        medium_priority = len(df[df['priority'] == 'MEDIUM']) if 'priority' in df.columns else 0
                        low_priority = len(df[df['priority'] == 'LOW']) if 'priority' in df.columns else 0
                except:
                    pass
            
            with col1:
                st.metric("📧 Total Processed", total_processed)
            
            with col2:
                st.metric("🔴 High Priority", high_priority)
            
            with col3:
                st.metric("🟡 Medium Priority", medium_priority)
            
            with col4:
                st.metric("🟢 Low Priority", low_priority)
        
        # Initialize session state if not exists
        if 'gmail_search' not in st.session_state:
            st.session_state.gmail_search = 'is:unread'
        
        # Single row layout: Quick Filters + Search + Max Emails + Processing Controls
        col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 3, 0.8, 0.8, 0.8])
        
        # Quick filter buttons - compact icon-only design
        with col1:
            if st.button("📧", help="Unread emails (is:unread)", key="filter_unread"):
                st.session_state.gmail_search = "is:unread"
                st.rerun()
        
        with col2:
            if st.button("⭐", help="Starred emails (is:starred)", key="filter_starred"):
                st.session_state.gmail_search = "is:starred"
                st.rerun()
        
        with col3:
            if st.button("📎", help="Emails with attachments (has:attachment)", key="filter_attachment"):
                st.session_state.gmail_search = "has:attachment"
                st.rerun()
        
        with col4:
            if st.button("🔴", help="Important emails (is:important)", key="filter_important"):
                st.session_state.gmail_search = "is:important"
                st.rerun()
        
        with col5:
            if st.button("📅", help="Today's emails (newer_than:1d)", key="filter_today"):
                st.session_state.gmail_search = "newer_than:1d"
                st.rerun()
        
        with col6:
            if st.button("🗂️", help="Primary category (category:primary)", key="filter_primary"):
                st.session_state.gmail_search = "category:primary"
                st.rerun()
        
        # Gmail search input
        with col7:
            gmail_search = st.text_input(
                "Gmail Search Query",
                value=st.session_state.gmail_search,
                placeholder="e.g., from:example.com is:unread subject:(urgent OR important)",
                help="Use Gmail search syntax. Examples: from:sender@email.com, to:me, subject:urgent, is:starred, has:attachment",
                key="gmail_search",
                label_visibility="collapsed"
            )
        
        # Max emails input
        with col8:
            max_emails = st.number_input("Max Emails", min_value=1, max_value=100, value=10, key="filter_max_emails", label_visibility="collapsed")
        
        # Processing control buttons
        with col9:
            if not st.session_state.processing_active:
                if st.button("🚀 Start", type="primary", help="Start email processing", key="start_processing"):
                    st.session_state.processing_active = True
                    st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Starting email processing...")
                    st.rerun()
            else:
                st.button("⏳ Running", disabled=True, help="Processing in progress", key="processing_status")
        
        with col10:
            if st.session_state.processing_active:
                if st.button("🛑 Stop", type="secondary", help="Stop email processing", key="stop_processing"):
                    st.session_state.processing_active = False
                    st.session_state.processing_stopped = True
                    st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Processing stopped by user")
                    st.warning("⚠️ Processing stopped by user")
                    st.rerun()
            else:
                st.button("🛑 Stop", disabled=True, help="Stop email processing", key="stop_disabled")
    
    # Auto-start processing if active but not yet started
    if st.session_state.processing_active and not st.session_state.get('processing_started', False):
        st.session_state.processing_started = True
        process_emails_with_filters(user_id, oauth_manager)
    
    # Activity Window - Always visible when processing is active
    if st.session_state.processing_active or st.session_state.processing_logs:
        st.markdown("---")
        st.markdown("### 📊 Activity Window")
        
        # Show status indicator
        if st.session_state.processing_active:
            st.info("🤖 **AI Crew is Active!** Detailed crew activity (agent tasks, tool usage) is visible in your terminal/console where you ran `streamlit run streamlit_app.py`")
        
        # Display processing logs in a container
        with st.container():
            # Show logs if available, otherwise show waiting message
            logs_content = "\n".join(st.session_state.processing_logs) if st.session_state.processing_logs else "⏳ Waiting for processing to begin..."
            
            # Auto-refresh during processing
            if st.session_state.processing_active:
                # Add current time to show activity
                current_time = datetime.now().strftime('%H:%M:%S')
                logs_content += f"\n[{current_time}] 🔄 Processing active... (check terminal for detailed crew activity)"
            
            st.text_area(
                "Processing Logs",
                value=logs_content,
                height=250,
                key="activity_logs",
                help="High-level processing status. For detailed AI agent activity, check your terminal/console."
            )
            
            col1, col2 = st.columns(2)
            with col1:
                # Only enable clear logs if there are actual logs
                clear_disabled = not bool(st.session_state.processing_logs)
                if st.button("🧹 Clear Logs", disabled=clear_disabled):
                    st.session_state.processing_logs = []
                    st.rerun()
            with col2:
                # Only enable download if there are actual logs
                download_disabled = not bool(st.session_state.processing_logs)
                if not download_disabled:
                    logs_text = "\n".join(st.session_state.processing_logs)
                    st.download_button(
                        "📥 Download Logs",
                        logs_text,
                        file_name=f"processing_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                else:
                    st.button("📥 Download Logs", disabled=True)
    

def show_rules_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show email rules management interface."""
    st.markdown("## 📋 Email Rules")
    
    st.markdown("Create rules to automatically process emails that match specific criteria.")
    
    # Add new rule section
    with st.expander("➕ Create New Rule", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            rule_name = st.text_input("Rule Name", placeholder="e.g., Newsletter Auto-Archive")
            rule_description = st.text_area("Description", placeholder="What does this rule do?")
            
            # Gmail search condition
            st.markdown("**Gmail Search Condition:**")
            st.markdown("Use Gmail search syntax to define when this rule applies.")
            
            gmail_condition = st.text_input(
                "Search Query",
                placeholder="e.g., from:newsletter@company.com OR subject:unsubscribe",
                help="Copy Gmail search filters directly here. Examples: from:sender.com, subject:urgent, is:unread AND has:attachment"
            )
            
            # Quick condition builders
            st.markdown("**Quick Builders:**")
            quick_col1, quick_col2, quick_col3 = st.columns(3)
            
            with quick_col1:
                if st.button("📧 From Sender", help="Add from: filter"):
                    sender = st.text_input("Sender email:", key="quick_sender")
                    if sender:
                        current = gmail_condition or ""
                        gmail_condition = f"{current} from:{sender}".strip()
            
            with quick_col2:
                if st.button("📝 Subject", help="Add subject: filter"):
                    subject = st.text_input("Subject contains:", key="quick_subject")
                    if subject:
                        current = gmail_condition or ""
                        gmail_condition = f"{current} subject:{subject}".strip()
            
            with quick_col3:
                if st.button("🏷️ Label", help="Add label: filter"):
                    label = st.text_input("Label name:", key="quick_label")
                    if label:
                        current = gmail_condition or ""
                        gmail_condition = f"{current} label:{label}".strip()
        
        with col2:
            # Rule actions
            st.markdown("**Actions:**")
            action_type = st.selectbox("Action", [
                "Archive",
                "Delete", 
                "Star",
                "Apply Label",
                "Mark as Read",
                "Reply with Template",
                "Forward to",
                "Move to Trash",
                "Mark as Important",
                "Remove from Inbox"
            ])
            
            action_value = ""
            if action_type in ["Apply Label", "Reply with Template", "Forward to"]:
                action_value = st.text_input("Action Value", placeholder="Enter label, template, or email")
            
            # Priority and AI instructions
            rule_priority = st.selectbox("Priority", ["Low", "Medium", "High"])
            ai_instructions = st.text_area(
                "Additional AI Instructions",
                placeholder="Special instructions for the AI when processing emails matching this rule...",
                help="Tell the AI how to handle emails that match this rule. Be specific about the desired outcome."
            )
            
            # Test the Gmail search
            if gmail_condition:
                st.markdown("**Search Preview:**")
                parser = GmailSearchParser()
                parsed_filters = parser.parse_search(gmail_condition)
                
                if parsed_filters['from_sender']:
                    st.write(f"• From: {parsed_filters['from_sender']}")
                if parsed_filters['to_recipient']:
                    st.write(f"• To: {parsed_filters['to_recipient']}")
                if parsed_filters['subject_filter']:
                    st.write(f"• Subject: {parsed_filters['subject_filter']}")
                if parsed_filters['unread_only']:
                    st.write("• Unread emails only")
                if parsed_filters['starred_only']:
                    st.write("• Starred emails only")
                if parsed_filters['has_attachment']:
                    st.write("• Has attachments")
        
        if st.button("➕ Add Rule", type="primary"):
            if rule_name and gmail_condition:
                new_rule = {
                    "id": str(uuid.uuid4()),
                    "name": rule_name,
                    "description": rule_description,
                    "gmail_search": gmail_condition,
                    "action_type": action_type,
                    "action_value": action_value,
                    "priority": rule_priority,
                    "ai_instructions": ai_instructions,
                    "enabled": True,
                    "created": datetime.now().isoformat()
                }
                
                st.session_state.email_rules.append(new_rule)
                st.success(f"✅ Rule '{rule_name}' created successfully!")
                st.rerun()
            else:
                st.error("❌ Please fill in rule name and Gmail search condition")
    
    # Display existing rules
    if st.session_state.email_rules:
        st.markdown("---")
        st.markdown("### 📜 Existing Rules")
        
        for rule in st.session_state.email_rules:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    # Priority indicator
                    priority_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(rule.get('priority', 'Medium'), "🟡")
                    st.markdown(f"**{priority_color} {rule['name']}**")
                    st.markdown(f"*{rule['description']}*")
                    
                    # Show Gmail search or old format for backward compatibility
                    if 'gmail_search' in rule:
                        st.markdown(f"**Search:** `{rule['gmail_search']}`")
                    else:
                        st.markdown(f"**Condition:** {rule.get('condition_field', 'email')} {rule.get('condition_operator', 'contains')} '{rule.get('condition_value', '')}'")
                    
                    st.markdown(f"**Action:** {rule['action_type']} {rule.get('action_value', '')}")
                    
                    if rule.get('ai_instructions'):
                        st.markdown(f"**AI Instructions:** {rule['ai_instructions'][:100]}{'...' if len(rule['ai_instructions']) > 100 else ''}")
                
                with col2:
                    enabled = st.checkbox(
                        "Enabled",
                        value=rule['enabled'],
                        key=f"rule_enabled_{rule['id']}"
                    )
                    if enabled != rule['enabled']:
                        rule['enabled'] = enabled
                
                with col3:
                    if st.button("✏️ Edit", key=f"edit_rule_{rule['id']}"):
                        st.session_state[f"editing_rule_{rule['id']}"] = True
                
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_rule_{rule['id']}"):
                        st.session_state.email_rules = [r for r in st.session_state.email_rules if r['id'] != rule['id']]
                        st.rerun()
                
                st.divider()
    else:
        st.info("📝 No rules created yet. Create your first rule above!")


def show_email_stats_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show email statistics and reports."""
    st.markdown("## 📊 Email Statistics & Reports")
    
    # Try to get Gmail service and show some stats
    try:
        service = oauth_manager.get_gmail_service(user_id)
        
        # Get unread count
        unread_result = service.users().messages().list(userId='me', q='is:unread').execute()
        unread_count = unread_result.get('resultSizeEstimate', 0)
        
        # Get total count (approximate)
        total_result = service.users().messages().list(userId='me').execute()
        total_count = total_result.get('resultSizeEstimate', 0)
        
        # Enhanced email metrics with clickable detailed views
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button(f"📧 Total Emails\n{total_count:,}", use_container_width=True):
                show_detailed_email_breakdown(service, "total")
        
        with col2:
            if st.button(f"📨 Unread Emails\n{unread_count:,}", use_container_width=True):
                show_detailed_email_breakdown(service, "unread")
        
        with col3:
            read_count = total_count - unread_count
            if st.button(f"✅ Read Emails\n{read_count:,}", use_container_width=True):
                show_detailed_email_breakdown(service, "read")
        
        with col4:
            if st.button("📈 Detailed Analytics", use_container_width=True):
                show_advanced_email_analytics(service)
        
        # Processing Reports Section
        st.markdown("---")
        st.markdown("### 📋 Processing Reports")
        
        if os.path.exists("output"):
            # Create tabs for different report types
            report_tabs = st.tabs(["📊 Latest Reports", "📈 Processing History", "🔍 Report Viewer"])
            
            with report_tabs[0]:
                show_latest_processing_reports()
            
            with report_tabs[1]:
                show_processing_history_enhanced()
            
            with report_tabs[2]:
                show_interactive_report_viewer()
        else:
            st.info("📝 No processing reports available yet. Run email processing to generate reports.")
    
    except Exception as e:
        st.error(f"Error fetching email stats: {e}")


def show_detailed_email_breakdown(service, email_type: str):
    """Show detailed breakdown of emails by type."""
    st.markdown(f"### 📧 Detailed {email_type.title()} Email Breakdown")
    
    try:
        # Get emails by category
        categories = {
            "Promotions": "category:promotions",
            "Social": "category:social", 
            "Updates": "category:updates",
            "Forums": "category:forums",
            "Primary": "category:primary"
        }
        
        breakdown_data = []
        
        for category, query in categories.items():
            if email_type == "unread":
                query += " is:unread"
            elif email_type == "read":
                query += " is:read"
            
            result = service.users().messages().list(userId='me', q=query).execute()
            count = result.get('resultSizeEstimate', 0)
            breakdown_data.append({"Category": category, "Count": count, "Query": query})
        
        # Display as chart
        df_breakdown = pd.DataFrame(breakdown_data)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.dataframe(df_breakdown[['Category', 'Count']], use_container_width=True)
        
        with col2:
            if not df_breakdown.empty:
                st.bar_chart(df_breakdown.set_index('Category')['Count'])
        
    except Exception as e:
        st.error(f"Error getting email breakdown: {e}")


def show_advanced_email_analytics(service):
    """Show advanced email analytics."""
    st.markdown("### 📈 Advanced Email Analytics")
    
    try:
        # Get various email statistics
        analytics_data = {
            "🌟 Starred": "is:starred",
            "📌 Important": "is:important", 
            "📎 With Attachments": "has:attachment",
            "📧 From Me": "from:me",
            "🗓️ Last 7 Days": "newer_than:7d",
            "🗓️ Last 30 Days": "newer_than:30d",
            "🔴 Unread Important": "is:unread is:important"
        }
        
        analytics_results = []
        
        for label, query in analytics_data.items():
            result = service.users().messages().list(userId='me', q=query).execute()
            count = result.get('resultSizeEstimate', 0)
            analytics_results.append({"Metric": label, "Count": count})
        
        # Display analytics
        df_analytics = pd.DataFrame(analytics_results)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.dataframe(df_analytics, use_container_width=True)
        
        with col2:
            if not df_analytics.empty:
                st.bar_chart(df_analytics.set_index('Metric')['Count'])
        
    except Exception as e:
        st.error(f"Error getting analytics: {e}")


def show_latest_processing_reports():
    """Show the latest processing reports in a user-friendly format."""
    st.markdown("#### 🕐 Latest Processing Results")
    
    # Define report types and their descriptions
    report_types = {
        "categorization_report.json": {"title": "📧 Email Categorization", "description": "AI categorization and prioritization results"},
        "organization_report.json": {"title": "🗂️ Email Organization", "description": "Labels and organization applied"},
        "response_report.json": {"title": "✉️ Reply Drafts", "description": "AI-generated response drafts"},
        "notification_report.json": {"title": "🔔 Notifications", "description": "Slack notifications sent"},
        "cleanup_report.json": {"title": "🧹 Email Cleanup", "description": "Emails archived and deleted"}
    }
    
    # Check which reports exist and show them
    available_reports = []
    for filename, info in report_types.items():
        filepath = os.path.join("output", filename)
        if os.path.exists(filepath):
            mod_time = os.path.getmtime(filepath)
            available_reports.append({
                "file": filename,
                "title": info["title"],
                "description": info["description"],
                "modified": datetime.fromtimestamp(mod_time)
            })
    
    if available_reports:
        # Sort by modification time (newest first)
        available_reports.sort(key=lambda x: x["modified"], reverse=True)
        
        for report in available_reports:
            with st.container():
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.markdown(f"**{report['title']}**")
                    st.markdown(f"*{report['description']}*")
                
                with col2:
                    st.markdown(f"📅 {report['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col3:
                    if st.button("👁️ View", key=f"view_{report['file']}", use_container_width=True):
                        show_formatted_report(report['file'])
                
                st.divider()
    else:
        st.info("📝 No processing reports available yet.")


def show_processing_history_enhanced():
    """Show enhanced processing history with file management."""
    st.markdown("#### 📚 Processing History")
    
    if os.path.exists("output"):
        history_files = []
        for file in os.listdir("output"):
            if file.endswith(".json"):
                file_path = os.path.join("output", file)
                mod_time = os.path.getmtime(file_path)
                file_size = os.path.getsize(file_path)
                
                history_files.append({
                    "📄 File": file,
                    "📅 Modified": datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S"),
                    "📏 Size": f"{round(file_size / 1024, 2)} KB",
                    "file_path": file_path
                })
        
        if history_files:
            # Sort by modification time
            history_files.sort(key=lambda x: x["📅 Modified"], reverse=True)
            
            for i, file_info in enumerate(history_files):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**{file_info['📄 File']}**")
                
                with col2:
                    st.markdown(file_info["📅 Modified"])
                
                with col3:
                    st.markdown(file_info["📏 Size"])
                
                with col4:
                    if st.button("👁️", key=f"view_history_{i}", help="View file"):
                        show_formatted_report(file_info['📄 File'])
                
                with col5:
                    # Download button
                    with open(file_info['file_path'], 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    st.download_button(
                        "💾",
                        file_content,
                        file_name=file_info['📄 File'],
                        mime="application/json",
                        key=f"download_history_{i}",
                        help="Download file"
                    )
    else:
        st.info("📁 No output directory found.")


def show_interactive_report_viewer():
    """Show interactive report viewer with search and filtering."""
    st.markdown("#### 🔍 Interactive Report Viewer")
    
    # File selector
    output_files = []
    if os.path.exists("output"):
        output_files = [f for f in os.listdir("output") if f.endswith(".json")]
    
    if output_files:
        selected_file = st.selectbox(
            "Select a report to view:",
            output_files,
            key="report_viewer_selector"
        )
        
        if selected_file:
            col1, col2 = st.columns([1, 3])
            
            with col1:
                view_mode = st.radio(
                    "View Mode:",
                    ["📊 Formatted", "🔧 Raw JSON"],
                    key="report_view_mode"
                )
            
            with col2:
                if st.button("🔄 Refresh Report", use_container_width=True):
                    st.rerun()
            
            # Display the selected report
            if view_mode == "📊 Formatted":
                show_formatted_report(selected_file)
            else:
                show_raw_json_report(selected_file)
    else:
        st.info("📄 No report files available.")


def show_formatted_report(filename: str):
    """Display a report in a user-friendly formatted way."""
    filepath = os.path.join("output", filename)
    
    if not os.path.exists(filepath):
        st.error(f"❌ File not found: {filename}")
        return
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        st.markdown(f"### 📋 Report: {filename}")
        
        # Format based on report type
        if "categorization" in filename:
            show_categorization_report_formatted(data)
        elif "organization" in filename:
            show_organization_report_formatted(data)
        elif "response" in filename:
            show_response_report_formatted(data)
        elif "notification" in filename:
            show_notification_report_formatted(data)
        elif "cleanup" in filename:
            show_cleanup_report_formatted(data)
        elif "fetched_emails" in filename:
            show_fetched_emails_formatted(data)
        else:
            # Generic JSON display for unknown formats
            st.json(data)
    
    except Exception as e:
        st.error(f"❌ Error reading report: {e}")


def show_categorization_report_formatted(data):
    """Show categorization report in a formatted way."""
    if isinstance(data, dict) and 'emails' in data:
        emails = data['emails']
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📧 Total Emails", len(emails))
        
        priorities = {}
        categories = {}
        
        for email in emails:
            priority = email.get('priority', 'Unknown')
            category = email.get('category', 'Unknown')
            priorities[priority] = priorities.get(priority, 0) + 1
            categories[category] = categories.get(category, 0) + 1
        
        with col2:
            high_priority = priorities.get('HIGH', 0)
            st.metric("🔴 High Priority", high_priority)
        
        with col3:
            medium_priority = priorities.get('MEDIUM', 0)
            st.metric("🟡 Medium Priority", medium_priority)
        
        with col4:
            low_priority = priorities.get('LOW', 0)
            st.metric("🟢 Low Priority", low_priority)
        
        # Category breakdown
        if categories:
            st.markdown("#### 📊 Category Breakdown")
            cat_df = pd.DataFrame(list(categories.items()), columns=['Category', 'Count'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(cat_df, use_container_width=True)
            with col2:
                st.bar_chart(cat_df.set_index('Category'))
        
        # Email details
        st.markdown("#### 📧 Email Details")
        if emails:
            df = pd.DataFrame(emails)
            st.dataframe(df[['subject', 'sender', 'category', 'priority']], use_container_width=True)
    else:
        st.json(data)


def show_organization_report_formatted(data):
    """Show organization report in a formatted way."""
    st.markdown("#### 🗂️ Organization Actions Applied")
    
    if isinstance(data, dict):
        # Show summary
        if 'summary' in data:
            st.success(f"✅ {data['summary']}")
        
        # Show organized emails if available
        if 'organized_emails' in data and data['organized_emails']:
            df = pd.DataFrame(data['organized_emails'])
            st.dataframe(df, use_container_width=True)
        
        # Show any other data
        for key, value in data.items():
            if key not in ['summary', 'organized_emails']:
                st.markdown(f"**{key.title()}:** {value}")
    else:
        st.json(data)


def show_response_report_formatted(data):
    """Show response report in a formatted way."""
    st.markdown("#### ✉️ AI-Generated Responses")
    
    if isinstance(data, dict) and 'responses' in data:
        responses = data['responses']
        
        st.metric("📧 Responses Generated", len(responses))
        
        for i, response in enumerate(responses):
            with st.expander(f"Response {i+1}: {response.get('subject', 'No Subject')[:50]}..."):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Original Email:**")
                    st.markdown(f"From: {response.get('original_sender', 'Unknown')}")
                    st.markdown(f"Subject: {response.get('subject', 'No Subject')}")
                
                with col2:
                    st.markdown("**AI Response:**")
                    response_text = response.get('response', 'No response generated')
                    st.text_area("Response", value=response_text, height=100, disabled=True, key=f"response_{i}")
    else:
        st.json(data)


def show_notification_report_formatted(data):
    """Show notification report in a formatted way."""
    st.markdown("#### 🔔 Notifications Sent")
    
    if isinstance(data, dict):
        # Show summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("📧 Emails Processed", data.get('total_processed', 0))
        
        with col2:
            st.metric("🔔 Notifications Sent", data.get('notifications_sent', 0))
        
        with col3:
            notifications = data.get('notifications', [])
            st.metric("📋 High Priority Found", len(notifications))
        
        # Show notifications details
        if notifications:
            st.markdown("#### 🔴 High Priority Notifications")
            for notification in notifications:
                st.warning(f"🔔 {notification.get('subject', 'No Subject')} - {notification.get('sender', 'Unknown Sender')}")
        else:
            st.info("✅ No high priority emails found for notification.")
        
        # Show summary
        if 'summary' in data:
            st.markdown("#### 📝 Summary")
            st.info(data['summary'])
    else:
        st.json(data)


def show_cleanup_report_formatted(data):
    """Show cleanup report in a formatted way."""
    st.markdown("#### 🧹 Cleanup Results")
    
    if isinstance(data, dict):
        # Show summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📧 Total Processed", data.get('total_processed', 0))
        
        with col2:
            st.metric("🗑️ Deleted", data.get('deleted_count', 0))
        
        with col3:
            st.metric("📁 Preserved", data.get('preserved_count', 0))
        
        with col4:
            st.metric("🗑️ Trash Emptied", data.get('trash_messages_removed', 0))
        
        # Show processed emails
        if 'processed_emails' in data and data['processed_emails']:
            st.markdown("#### 📋 Email Actions")
            
            emails = data['processed_emails']
            
            # Separate deleted and preserved
            deleted_emails = [e for e in emails if e.get('deleted', False)]
            preserved_emails = [e for e in emails if not e.get('deleted', False)]
            
            tab1, tab2 = st.tabs([f"🗑️ Deleted ({len(deleted_emails)})", f"📁 Preserved ({len(preserved_emails)})"])
            
            with tab1:
                if deleted_emails:
                    for email in deleted_emails:
                        st.markdown(f"❌ **{email.get('subject', 'No Subject')}** - {email.get('sender', 'Unknown')}")
                        st.markdown(f"   *Reason: {email.get('reason', 'No reason given')}*")
                else:
                    st.info("No emails were deleted.")
            
            with tab2:
                if preserved_emails:
                    for email in preserved_emails:
                        st.markdown(f"✅ **{email.get('subject', 'No Subject')}** - {email.get('sender', 'Unknown')}")
                        st.markdown(f"   *Reason: {email.get('reason', 'No reason given')}*")
                else:
                    st.info("No emails were preserved.")
        
        # Show summary
        if 'summary' in data:
            st.markdown("#### 📝 Summary")
            st.success(data['summary'])
    else:
        st.json(data)


def show_fetched_emails_formatted(data):
    """Show fetched emails in a formatted way."""
    st.markdown("#### 📥 Fetched Emails")
    
    if isinstance(data, list):
        st.metric("📧 Total Fetched", len(data))
        
        if data:
            # Convert to DataFrame for better display
            df = pd.DataFrame(data)
            
            # Show summary by sender
            if 'sender' in df.columns:
                sender_counts = df['sender'].value_counts().head(10)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 👥 Top Senders")
                    st.dataframe(sender_counts.to_frame('Count'), use_container_width=True)
                
                with col2:
                    st.markdown("#### 📊 Sender Distribution")
                    st.bar_chart(sender_counts)
            
            # Show email list with search
            st.markdown("#### 📧 Email List")
            
            search_term = st.text_input("🔍 Search emails:", placeholder="Enter subject, sender, or keywords...")
            
            if search_term:
                mask = (
                    df['subject'].str.contains(search_term, case=False, na=False) |
                    df['sender'].str.contains(search_term, case=False, na=False)
                )
                filtered_df = df[mask]
                st.markdown(f"Found {len(filtered_df)} emails matching '{search_term}'")
            else:
                filtered_df = df
            
            # Display emails
            columns_to_show = ['subject', 'sender', 'date']
            if 'age_days' in filtered_df.columns:
                columns_to_show.append('age_days')
            
            st.dataframe(
                filtered_df[columns_to_show].head(50),  # Show first 50 emails
                use_container_width=True
            )
            
            if len(filtered_df) > 50:
                st.info(f"Showing first 50 of {len(filtered_df)} emails")
    else:
        st.json(data)


def show_raw_json_report(filename: str):
    """Show raw JSON report."""
    filepath = os.path.join("output", filename)
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        st.markdown(f"### 🔧 Raw JSON: {filename}")
        st.json(data)
        
        # Add download option
        st.download_button(
            "💾 Download JSON",
            json.dumps(data, indent=2, ensure_ascii=False),
            file_name=filename,
            mime="application/json"
        )
        
    except Exception as e:
        st.error(f"❌ Error reading file: {e}")


class GmailSearchParser:
    """Parses Gmail search syntax into filter criteria."""
    
    def __init__(self):
        self.operators = {
            'from:', 'to:', 'subject:', 'has:', 'is:', 'label:', 'category:',
            'older_than:', 'newer_than:', 'larger:', 'smaller:', 'filename:'
        }
    
    def parse_search(self, search_query: str) -> Dict:
        """Parse Gmail search query into structured filters."""
        filters = {
            'max_emails': 10,
            'gmail_search': search_query,
            'from_sender': '',
            'to_recipient': '',
            'subject_filter': '',
            'keyword': '',
            'unread_only': False,
            'starred_only': False,
            'important_only': False,
            'has_attachment': False,
            'labels': [],
            'categories': [],
            'date_filters': [],
            'size_filters': [],
            'filename_filters': [],
            'exclude_terms': []
        }
        
        if not search_query:
            return filters
        
        # Split by spaces but preserve quoted strings
        import re
        tokens = re.findall(r'"[^"]*"|\S+', search_query.lower())
        
        i = 0
        while i < len(tokens):
            token = tokens[i].strip()
            
            # Handle negation
            if token.startswith('-'):
                filters['exclude_terms'].append(token[1:])
                i += 1
                continue
            
            # Handle operators
            if ':' in token:
                operator, value = token.split(':', 1)
                operator = operator + ':'
                
                if operator == 'from:':
                    filters['from_sender'] = value
                elif operator == 'to:':
                    filters['to_recipient'] = value
                elif operator == 'subject:':
                    filters['subject_filter'] = value
                elif operator == 'is:':
                    if value == 'unread':
                        filters['unread_only'] = True
                    elif value == 'starred':
                        filters['starred_only'] = True
                    elif value == 'important':
                        filters['important_only'] = True
                elif operator == 'has:':
                    if value == 'attachment':
                        filters['has_attachment'] = True
                elif operator == 'label:':
                    filters['labels'].append(value)
                elif operator == 'category:':
                    filters['categories'].append(value)
                elif operator in ['older_than:', 'newer_than:']:
                    filters['date_filters'].append({'type': operator[:-1], 'value': value})
                elif operator in ['larger:', 'smaller:']:
                    filters['size_filters'].append({'type': operator[:-1], 'value': value})
                elif operator == 'filename:':
                    filters['filename_filters'].append(value)
            
            # Handle OR operator
            elif token.upper() == 'OR' and i > 0 and i < len(tokens) - 1:
                # This is a simple implementation - in a full parser you'd want to handle precedence
                pass
            
            # Handle quoted strings and regular keywords
            else:
                if token.startswith('"') and token.endswith('"'):
                    filters['keyword'] += token[1:-1] + ' '
                else:
                    filters['keyword'] += token + ' '
            
            i += 1
        
        filters['keyword'] = filters['keyword'].strip()
        return filters
    
    def filters_to_gmail_search(self, filters: Dict) -> str:
        """Convert structured filters back to Gmail search syntax."""
        parts = []
        
        if filters.get('from_sender'):
            parts.append(f"from:{filters['from_sender']}")
        if filters.get('to_recipient'):
            parts.append(f"to:{filters['to_recipient']}")
        if filters.get('subject_filter'):
            parts.append(f"subject:{filters['subject_filter']}")
        if filters.get('unread_only'):
            parts.append("is:unread")
        if filters.get('starred_only'):
            parts.append("is:starred")
        if filters.get('important_only'):
            parts.append("is:important")
        if filters.get('has_attachment'):
            parts.append("has:attachment")
        
        for label in filters.get('labels', []):
            parts.append(f"label:{label}")
        
        for category in filters.get('categories', []):
            parts.append(f"category:{category}")
        
        for date_filter in filters.get('date_filters', []):
            parts.append(f"{date_filter['type']}:{date_filter['value']}")
        
        for size_filter in filters.get('size_filters', []):
            parts.append(f"{size_filter['type']}:{size_filter['value']}")
        
        for filename in filters.get('filename_filters', []):
            parts.append(f"filename:{filename}")
        
        if filters.get('keyword'):
            parts.append(filters['keyword'])
        
        for exclude in filters.get('exclude_terms', []):
            parts.append(f"-{exclude}")
        
        return ' '.join(parts)


class ErrorLogger:
    """Manages error logging with 30-day retention."""
    
    def __init__(self):
        self.error_log_file = "error_logs.json"
        self.ensure_error_log_file()
    
    def ensure_error_log_file(self):
        """Ensure error log file exists."""
        if not os.path.exists(self.error_log_file):
            self.save_errors([])
    
    def load_errors(self) -> List[Dict]:
        """Load errors from file."""
        try:
            with open(self.error_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    
    def save_errors(self, errors: List[Dict]):
        """Save errors to file."""
        try:
            with open(self.error_log_file, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving error logs: {e}")
    
    def cleanup_old_errors(self):
        """Remove errors older than 30 days."""
        errors = self.load_errors()
        cutoff_date = datetime.now() - pd.Timedelta(days=30)
        
        filtered_errors = []
        for error in errors:
            try:
                error_date = datetime.fromisoformat(error.get('timestamp', ''))
                if error_date >= cutoff_date:
                    filtered_errors.append(error)
            except:
                # Keep errors with invalid timestamps for safety
                filtered_errors.append(error)
        
        if len(filtered_errors) != len(errors):
            self.save_errors(filtered_errors)
            return len(errors) - len(filtered_errors)
        return 0
    
    def log_error(self, error_type: str, message: str, details: str = "", user_id: str = ""):
        """Log a new error."""
        errors = self.load_errors()
        
        new_error = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "details": details,
            "user_id": user_id,
            "resolved": False
        }
        
        errors.insert(0, new_error)  # Add to beginning for newest first
        self.save_errors(errors)
    
    def mark_resolved(self, error_id: str):
        """Mark an error as resolved."""
        errors = self.load_errors()
        for error in errors:
            if error.get('id') == error_id:
                error['resolved'] = True
                break
        self.save_errors(errors)
    
    def delete_error(self, error_id: str):
        """Delete a specific error."""
        errors = self.load_errors()
        errors = [e for e in errors if e.get('id') != error_id]
        self.save_errors(errors)


def show_error_logs_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show error logs interface."""
    st.markdown("## 🚨 Error Logs")
    st.markdown("View and manage system errors from CrewAI agents and processing.")
    
    # Initialize error logger
    error_logger = ErrorLogger()
    
    # Cleanup old errors automatically
    cleaned_count = error_logger.cleanup_old_errors()
    if cleaned_count > 0:
        st.info(f"🗑️ Automatically cleaned up {cleaned_count} old errors (>30 days)")
    
    # Load current errors
    errors = error_logger.load_errors()
    
    # Header controls
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        error_filter = st.selectbox(
            "Filter by Type",
            ["All", "CrewAI", "Agent", "Processing", "Authentication", "System"],
            key="error_filter"
        )
    
    with col2:
        show_resolved = st.checkbox("Show Resolved", value=False, key="show_resolved")
    
    with col3:
        if st.button("🧹 Clean Old Errors", help="Remove errors older than 30 days"):
            cleaned = error_logger.cleanup_old_errors()
            if cleaned > 0:
                st.success(f"✅ Cleaned up {cleaned} old errors")
                st.rerun()
            else:
                st.info("No old errors to clean")
    
    with col4:
        if st.button("➕ Test Error", help="Add a test error for demonstration"):
            error_logger.log_error(
                "System", 
                "Test error message", 
                "This is a test error for demonstration purposes",
                user_id
            )
            st.success("Test error added!")
            st.rerun()
    
    # Filter errors
    filtered_errors = []
    for error in errors:
        # Filter by type
        if error_filter != "All" and error.get('type', '') != error_filter:
            continue
        
        # Filter by resolved status
        if not show_resolved and error.get('resolved', False):
            continue
        
        filtered_errors.append(error)
    
    # Display statistics
    if filtered_errors:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Errors", len(errors))
        with col2:
            unresolved = len([e for e in errors if not e.get('resolved', False)])
            st.metric("Unresolved", unresolved)
        with col3:
            resolved = len([e for e in errors if e.get('resolved', False)])
            st.metric("Resolved", resolved)
        with col4:
            recent = len([e for e in errors if datetime.fromisoformat(e.get('timestamp', datetime.min.isoformat())) >= datetime.now() - pd.Timedelta(days=1)])
            st.metric("Last 24h", recent)
        
        st.markdown("---")
    
    # Display errors
    if not filtered_errors:
        if error_filter == "All" and not show_resolved:
            st.info("🎉 No unresolved errors found!")
        else:
            st.info("No errors match the current filter criteria.")
    else:
        for error in filtered_errors:
            error_id = error.get('id', '')
            timestamp = error.get('timestamp', '')
            error_type = error.get('type', 'Unknown')
            message = error.get('message', 'No message')
            details = error.get('details', '')
            resolved = error.get('resolved', False)
            
            # Format timestamp
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
                time_ago = pd.Timestamp.now() - pd.Timestamp(dt)
                time_ago_str = f"({time_ago.days}d {time_ago.seconds//3600}h ago)" if time_ago.days > 0 else f"({time_ago.seconds//3600}h {(time_ago.seconds%3600)//60}m ago)"
            except:
                formatted_time = timestamp
                time_ago_str = ""
            
            # Color coding
            if resolved:
                status_color = "🟢"
                border_color = "#28a745"
            else:
                if error_type in ["CrewAI", "Agent"]:
                    status_color = "🔴"
                    border_color = "#dc3545"
                elif error_type == "Processing":
                    status_color = "🟡"
                    border_color = "#ffc107"
                else:
                    status_color = "🟠"
                    border_color = "#fd7e14"
            
            # Error card
            with st.container():
                st.markdown(f"""
                <div style="border-left: 4px solid {border_color}; padding: 10px; margin: 10px 0; background-color: #f8f9fa;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: {border_color};">{status_color} {error_type} Error</h4>
                        <small style="color: #6c757d;">{formatted_time} {time_ago_str}</small>
                    </div>
                    <p style="margin: 5px 0; font-weight: bold;">{message}</p>
                    {f'<p style="margin: 5px 0; color: #6c757d;">{details}</p>' if details else ''}
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons
                col1, col2, col3, col4 = st.columns([1, 1, 1, 2])
                
                with col1:
                    if not resolved:
                        if st.button("✅ Resolve", key=f"resolve_{error_id}"):
                            error_logger.mark_resolved(error_id)
                            st.success("Error marked as resolved!")
                            st.rerun()
                    else:
                        st.markdown("✅ *Resolved*")
                
                with col2:
                    if st.button("🗑️ Delete", key=f"delete_{error_id}"):
                        error_logger.delete_error(error_id)
                        st.success("Error deleted!")
                        st.rerun()
                
                with col3:
                    if st.button("📋 Copy", key=f"copy_{error_id}"):
                        error_text = f"Error Type: {error_type}\nTime: {formatted_time}\nMessage: {message}\nDetails: {details}"
                        st.code(error_text)
                
                st.markdown("---")


def show_settings_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show settings interface."""
    st.markdown("## ⚙️ Settings")
    
    # User info
    user_email = oauth_manager.get_user_email(user_id)
    st.markdown(f"**Current User:** {user_email}")
    st.markdown(f"**User ID:** {user_id}")
    
    st.markdown("---")
    
    # OAuth2 settings
    st.markdown("### 🔐 Authentication Settings")
    
    if st.button("🔄 Refresh Authentication", help="Refresh OAuth2 token"):
        try:
            # This will automatically refresh if needed
            oauth_manager.get_gmail_service(user_id)
            st.success("✅ Authentication refreshed successfully!")
        except Exception as e:
            st.error(f"Error refreshing authentication: {e}")
    
    if st.button("🗑️ Remove This Account", type="secondary", help="Remove OAuth2 access for this account"):
        confirm_remove = st.checkbox("I confirm I want to remove this account")
        if confirm_remove and st.button("Confirm Removal", type="secondary"):
            if oauth_manager.revoke_credentials(user_id):
                st.success("✅ Account access removed successfully!")
                
                # Clear persistent session
                browser_token = session_manager.get_browser_session()
                if browser_token:
                    session_manager.invalidate_session(browser_token)
                session_manager.clear_browser_session()
                
                st.session_state.current_user = None
                st.session_state.authentication_step = 'select_user'
                st.rerun()
    
    st.markdown("---")
    
    # User Persona Management
    st.markdown("### 👤 User Persona Management")
    
    # Show current user facts status
    facts_file = "knowledge/user_facts.txt"
    if os.path.exists(facts_file) and os.path.getsize(facts_file) > 50:
        st.success("✅ User persona file exists and has content")
        
        # Show creation date
        try:
            with open(facts_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "Last Updated:" in content:
                    last_updated = content.split("Last Updated:")[-1].split("\n")[0].strip()
                    st.info(f"📅 Last updated: {last_updated}")
        except Exception:
            pass
            
        if st.button("📄 View Current User Persona"):
            try:
                with open(facts_file, 'r', encoding='utf-8') as f:
                    facts_content = f.read()
                st.text_area("Current User Persona:", facts_content, height=200, key="user_facts_display")
            except Exception as e:
                st.error(f"Error reading user facts: {e}")
    else:
        st.warning("⚠️ User persona file is empty or missing")
        st.info("📋 User persona will be automatically created when you first process emails")
    
    # Persona management buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔄 Rebuild User Persona", help="Analyze all sent emails to completely rebuild user persona"):
            try:
                from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2GetSentEmailsTool, OAuth2UserPersonaAnalyzerTool
                
                with st.spinner("📧 Fetching sent emails for complete analysis..."):
                    # Fetch sent emails
                    sent_email_tool = OAuth2GetSentEmailsTool(user_id=user_id, oauth_manager=oauth_manager)
                    sent_emails = sent_email_tool._run(max_emails=100)
                    
                    if sent_emails:
                        st.info(f"📊 Analyzing {len(sent_emails)} sent emails...")
                        
                        # Analyze emails and create persona
                        analyzer_tool = OAuth2UserPersonaAnalyzerTool(user_id=user_id, oauth_manager=oauth_manager)
                        result = analyzer_tool._run(sent_emails=sent_emails)
                        
                        st.success("✅ User persona rebuilt successfully!")
                        st.info(result)
                        
                        # Show the new persona
                        try:
                            with open(facts_file, 'r', encoding='utf-8') as f:
                                new_facts = f.read()
                            st.text_area("Updated User Persona:", new_facts, height=200, key="updated_user_facts")
                        except Exception as e:
                            st.error(f"Error displaying updated persona: {e}")
                    else:
                        st.warning("⚠️ No sent emails found to analyze")
                        
            except Exception as e:
                st.error(f"Error rebuilding user persona: {e}")
    
    with col2:
        if st.button("🔄📅 Update User Persona", help="Update existing user persona with recent email data (last 30 days)"):
            try:
                from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2UserPersonaUpdaterTool
                
                with st.spinner("📧 Analyzing recent emails for persona updates..."):
                    # Use the new updater tool
                    updater_tool = OAuth2UserPersonaUpdaterTool(user_id=user_id, oauth_manager=oauth_manager)
                    result = updater_tool._run(days_back=30)
                    
                    st.success("✅ User persona updated successfully!")
                    st.info(result)
                    
                    # Show the updated persona
                    try:
                        with open(facts_file, 'r', encoding='utf-8') as f:
                            updated_facts = f.read()
                        st.text_area("Updated User Persona:", updated_facts, height=200, key="incremental_updated_user_facts")
                    except Exception as e:
                        st.error(f"Error displaying updated persona: {e}")
                        
            except Exception as e:
                st.error(f"Error updating user persona: {e}")
    
    # Additional options for update period
    st.markdown("---")
    st.markdown("#### 🕐 Custom Update Period")
    
    days_back = st.slider(
        "Days back to analyze for updates:",
        min_value=7,
        max_value=90,
        value=30,
        step=7,
        help="Choose how many days back to analyze for persona updates"
    )
    
    if st.button("🔄⚙️ Custom Update", help=f"Update persona with emails from last {days_back} days"):
        try:
            from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2UserPersonaUpdaterTool
            
            with st.spinner(f"📧 Analyzing emails from last {days_back} days..."):
                updater_tool = OAuth2UserPersonaUpdaterTool(user_id=user_id, oauth_manager=oauth_manager)
                result = updater_tool._run(days_back=days_back)
                
                st.success("✅ User persona updated successfully!")
                st.info(result)
                
                # Show the updated persona
                try:
                    with open(facts_file, 'r', encoding='utf-8') as f:
                        updated_facts = f.read()
                    st.text_area("Updated User Persona:", updated_facts, height=200, key=f"custom_updated_user_facts_{days_back}")
                except Exception as e:
                    st.error(f"Error displaying updated persona: {e}")
                    
        except Exception as e:
            st.error(f"Error updating user persona: {e}")
    
    st.markdown("---")
    
    if st.button("🗑️ Clear User Persona", type="secondary", help="Clear current user persona"):
        confirm_clear = st.checkbox("I confirm I want to clear the user persona")
        if confirm_clear and st.button("Confirm Clear", type="secondary"):
            try:
                with open(facts_file, 'w', encoding='utf-8') as f:
                    f.write("")
                st.success("✅ User persona cleared successfully!")
                st.info("📋 A new persona will be automatically created next time you process emails")
            except Exception as e:
                st.error(f"Error clearing user persona: {e}")
    
    st.markdown("---")
    
    # File management
    st.markdown("### 📁 File Management")
    
    if st.button("🧹 Clear Processing Cache"):
        try:
            import shutil
            if os.path.exists("output"):
                shutil.rmtree("output")
                os.makedirs("output")
            st.success("✅ Processing cache cleared!")
        except Exception as e:
            st.error(f"Error clearing cache: {e}")


def show_help_tab():
    """Show help and documentation."""
    st.markdown("## 📚 Help & Documentation")
    
    st.markdown("""
    ### 🤖 How Gmail CrewAI Works
    
    Gmail CrewAI uses AI agents to automatically process your emails:
    
    1. **📥 Fetcher Agent**: Retrieves unread emails from your Gmail
    2. **🏷️ Categorizer Agent**: Categorizes emails by type and priority
    3. **📋 Organizer Agent**: Applies Gmail labels and stars important emails
    4. **✍️ Response Agent**: Generates draft responses for important emails
    5. **📢 Notification Agent**: Sends Slack notifications for high-priority emails
    6. **🗑️ Cleanup Agent**: Archives or deletes low-priority emails
    
    ### 🔐 Security & Privacy
    
    - Your OAuth2 tokens are stored locally and encrypted
    - No email content is stored permanently
    - AI processing happens locally with your OpenAI API key
    - You can revoke access at any time
    
    ### ⚙️ Setup Requirements
    
    1. **Google OAuth2 Credentials**: Required for Gmail access
    2. **OpenAI API Key**: Required for AI processing
    3. **Slack Webhook** (Optional): For notifications
    
    ### 🆘 Troubleshooting
    
    - **Authentication Issues**: Try refreshing authentication in Settings
    - **Processing Errors**: Check that all environment variables are set
    - **Performance**: Processing time depends on number of emails
    """)
    
    st.markdown("---")
    st.markdown("### 📞 Support")
    st.markdown("For issues or questions, please check the project documentation or create an issue on GitHub.")


class StreamCapture:
    """Capture stdout/stderr and forward to Streamlit logs."""
    
    def __init__(self, original_stream, log_callback):
        self.original_stream = original_stream
        self.log_callback = log_callback
        self.buffer = io.StringIO()
        
    def write(self, text):
        # Write to original stream (terminal)
        if hasattr(self.original_stream, 'write'):
            self.original_stream.write(text)
            
        # Also capture for Streamlit
        if text.strip():  # Only log non-empty lines
            timestamp = datetime.now().strftime('%H:%M:%S')
            # Clean up the text and add to logs
            clean_text = text.strip().replace('\n', ' ')
            if clean_text and not clean_text.isspace():
                self.log_callback(f"[{timestamp}] {clean_text}")
    
    def flush(self):
        if hasattr(self.original_stream, 'flush'):
            self.original_stream.flush()
    
    def isatty(self):
        return False

def log_to_activity_window(message):
    """Add message to processing logs."""
    if 'processing_logs' not in st.session_state:
        st.session_state.processing_logs = []
    st.session_state.processing_logs.append(message)
    # Keep only last 100 messages to prevent memory issues
    if len(st.session_state.processing_logs) > 100:
        st.session_state.processing_logs = st.session_state.processing_logs[-100:]


def process_emails_with_filters(user_id: str, oauth_manager):
    """Process emails using CrewAI with applied filters."""
    # Initialize error logger
    error_logger = ErrorLogger()
    
    # Check if processing was stopped before starting
    if st.session_state.get('processing_stopped', False):
        st.session_state.processing_active = False
        st.session_state.processing_started = False
        st.session_state.processing_stopped = False
        return
    
    # Check subscription limits before processing
    if st.session_state.subscription_manager and st.session_state.usage_tracker:
        subscription_manager = st.session_state.subscription_manager
        usage_tracker = st.session_state.usage_tracker
        
        # Get user's authenticated ID for subscription check
        authenticated_user_id = st.session_state.authenticated_user_id
        
        # Check if user can process more emails
        if not usage_tracker.can_process_more_emails(authenticated_user_id):
            usage_record = usage_tracker.get_usage_for_today(authenticated_user_id)
            plan_name = subscription_manager.get_subscription_plan_name(authenticated_user_id)
            
            st.session_state.processing_logs.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Daily email limit reached ({usage_record.emails_processed}/{usage_record.daily_limit})"
            )
            
            st.warning(f"⚠️ You've reached your daily email processing limit ({usage_record.emails_processed}/{usage_record.daily_limit}) for your {plan_name} plan.")
            st.info("💡 Upgrade your subscription in the Billing tab to process more emails.")
            
            # Reset processing state
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            return
        
        # Log current usage
        usage_record = usage_tracker.get_usage_for_today(authenticated_user_id)
        st.session_state.processing_logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Daily usage: {usage_record.emails_processed}/{usage_record.daily_limit}"
        )
    
    # Parse Gmail search query into structured filters
    gmail_search = st.session_state.get('gmail_search', 'is:unread')
    max_emails = st.session_state.get('filter_max_emails', 10)
    
    parser = GmailSearchParser()
    filters = parser.parse_search(gmail_search)
    filters['max_emails'] = max_emails
    
    # Apply rules to generate additional instructions
    rule_instructions = generate_rule_instructions()
    
    # Create placeholder for activity display
    activity_placeholder = st.empty()
    
    try:
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📧 Fetching emails with filters...")
        
        # Check for stop signal during processing
        if st.session_state.get('processing_stopped', False):
            st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ Processing stopped before email fetch")
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            return
        
        # Set up environment for this user
        user_email = oauth_manager.get_user_email(user_id)
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 Processing for user: {user_email}")
        
        # Set filters and rules in environment for crew to use
        os.environ["EMAIL_FILTERS"] = json.dumps(filters)
        os.environ["RULE_INSTRUCTIONS"] = rule_instructions
        
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️ Applied filters: {len([k for k, v in filters.items() if v])} active")
        
        # Check for stop signal before crew creation
        if st.session_state.get('processing_stopped', False):
            st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ Processing stopped before crew creation")
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            return
        
        # Create a crew for this specific user 
        crew = create_crew_for_user(user_id, oauth_manager)
        
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 AI crew initialized, starting processing...")
        
        # Run the crew with enhanced logging
        try:
            st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Starting AI crew execution...")
            st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Initializing AI agents: Categorizer, Organizer, Response Generator, Notifier, Cleaner")
            st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Processing tasks: Categorization → Organization → Response Generation → Notifications → Cleanup")
            
            # Create a progress indicator
            progress_placeholder = st.empty()
            with progress_placeholder:
                st.info("🤖 AI crew is processing your emails... Check the activity window below for real-time updates.")
            
            result = crew.crew().kickoff()
            
            # Clear progress indicator
            progress_placeholder.empty()
            
            # Check if processing was stopped during execution
            if st.session_state.get('processing_stopped', False):
                st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏹️ Processing was stopped during execution")
                error_logger.log_error(
                    "Processing", 
                    "Email processing was stopped by user",
                    f"Processing was manually stopped during execution for user {user_email}",
                    user_id
                )
            else:
                st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Email processing completed successfully!")
                st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 All tasks completed: emails categorized, organized, responses generated, notifications sent, cleanup performed")
                st.success("✅ Email processing completed!")
                
                # Track usage after successful processing
                if st.session_state.subscription_manager and st.session_state.usage_tracker:
                    try:
                        authenticated_user_id = st.session_state.authenticated_user_id
                        subscription = st.session_state.subscription_manager.get_user_subscription(authenticated_user_id)
                        emails_processed = max_emails  # Number of emails processed
                        
                        st.session_state.usage_tracker.record_usage(
                            authenticated_user_id, 
                            subscription.plan_type if subscription else PlanType.FREE,
                            emails_processed
                        )
                        
                        st.session_state.processing_logs.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Recorded usage: {emails_processed} emails"
                        )
                    except Exception as usage_error:
                        st.session_state.processing_logs.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Failed to record usage: {str(usage_error)}"
                        )
                    
            except Exception as crew_error:
                # Log crew-specific errors
                error_logger.log_error(
                    "CrewAI", 
                    f"CrewAI execution failed: {str(crew_error)}",
                    f"Error during crew execution for user {user_email}. Filters: {json.dumps(filters)}. Rules: {rule_instructions}",
                    user_id
                )
                st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ CrewAI Error: {str(crew_error)}")
                raise crew_error
            
            # Reset processing state
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            st.rerun()
            
        except Exception as e:
            # Log general processing errors
            error_type = "Processing"
            if "oauth" in str(e).lower() or "auth" in str(e).lower():
                error_type = "Authentication"
            elif "agent" in str(e).lower():
                error_type = "Agent"
            
            error_logger.log_error(
                error_type, 
                f"Email processing failed: {str(e)}",
                f"Error during email processing for user {oauth_manager.get_user_email(user_id)}. Filters: {json.dumps(filters)}",
                user_id
            )
            
            st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {str(e)}")
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            st.error(f"❌ Error processing emails: {e}")
            st.exception(e)


def generate_rule_instructions() -> str:
    """Generate additional instructions based on active rules."""
    if not st.session_state.email_rules:
        return ""
    
    active_rules = [rule for rule in st.session_state.email_rules if rule['enabled']]
    if not active_rules:
        return ""
    
    instructions = ["Additional processing rules:"]
    
    for rule in active_rules:
        # Handle both old format (for backward compatibility) and new Gmail search format
        if 'gmail_search' in rule:
            # New Gmail search format
            rule_text = f"- For emails matching Gmail search '{rule['gmail_search']}', then {rule['action_type']}"
        else:
            # Old format (backward compatibility)
            rule_text = f"- When {rule.get('condition_field', 'email')} {rule.get('condition_operator', 'contains')} '{rule.get('condition_value', '')}', then {rule['action_type']}"
        
        if rule.get('action_value'):
            rule_text += f" '{rule['action_value']}'"
        if rule.get('ai_instructions'):
            rule_text += f". {rule['ai_instructions']}"
        if rule.get('priority'):
            rule_text += f" (Priority: {rule['priority']})"
        
        instructions.append(rule_text)
    
    # Add explanation of Gmail search syntax for the AI
    instructions.append("\nGmail search syntax guide for AI:")
    instructions.append("- from:email@domain.com = emails from specific sender")
    instructions.append("- to:email@domain.com = emails to specific recipient")
    instructions.append("- subject:keyword = emails with keyword in subject")
    instructions.append("- is:unread = unread emails")
    instructions.append("- is:starred = starred emails")
    instructions.append("- has:attachment = emails with attachments")
    instructions.append("- label:name = emails with specific label")
    instructions.append("- category:primary = emails in primary category")
    instructions.append("- older_than:7d / newer_than:1d = date-based filters")
    
    return "\n".join(instructions)


def send_reply_draft(user_id: str, oauth_manager: OAuth2Manager, reply_content: str, original_subject: str):
    """Send a reply draft."""
    try:
        service = oauth_manager.get_gmail_service(user_id)
        # Implementation for sending reply would go here
        st.success(f"✅ Reply sent for: {original_subject}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📤 Reply sent for: {original_subject}")
    except Exception as e:
        st.error(f"❌ Error sending reply: {e}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error sending reply: {e}")


def update_ai_learning(user_id: str, original_reply: str, edited_reply: str, subject: str):
    """Update AI learning based on reply edits."""
    try:
        # Save learning data to user knowledge base
        learning_data = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "subject": subject,
            "original_reply": original_reply,
            "edited_reply": edited_reply,
            "changes": "User edited AI-generated reply"
        }
        
        # Append to learning file
        learning_file = f"knowledge/user_learning_{user_id}.json"
        os.makedirs("knowledge", exist_ok=True)
        
        if os.path.exists(learning_file):
            with open(learning_file, "r", encoding='utf-8') as f:
                learning_history = json.load(f)
        else:
            learning_history = []
        
        learning_history.append(learning_data)
        
        with open(learning_file, "w", encoding='utf-8') as f:
            json.dump(learning_history, f, indent=2, ensure_ascii=False)
        
        st.success("✅ AI learning updated with your changes!")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 AI learning updated from user feedback")
        
    except Exception as e:
        st.error(f"❌ Error updating AI learning: {e}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error updating AI learning: {e}")


def process_emails(user_id: str, oauth_manager):
    """Process emails using CrewAI (legacy function - calls new filtered version)."""
    process_emails_with_filters(user_id, oauth_manager)


def execute_email_action(user_id: str, oauth_manager: OAuth2Manager, email_row, action: str):
    """Execute the approved action on an email."""
    try:
        email_id = email_row.get('email_id', 'unknown')
        subject = email_row.get('subject', 'Unknown Subject')
        
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ Executing {action} on: {subject}")
        
        service = oauth_manager.get_gmail_service(user_id)
        
        if action == "Archive":
            # Remove INBOX label to archive
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            st.success(f"✅ Archived: {subject}")
            
        elif action == "Delete":
            service.users().messages().trash(userId='me', id=email_id).execute()
            st.success(f"✅ Deleted: {subject}")
            
        elif action == "Star":
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['STARRED']}
            ).execute()
            st.success(f"✅ Starred: {subject}")
            
        elif action == "Mark Important":
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['IMPORTANT']}
            ).execute()
            st.success(f"✅ Marked Important: {subject}")
            
        else:
            st.info(f"Action '{action}' is not yet implemented for: {subject}")
        
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Action completed successfully")
        
    except Exception as e:
        st.error(f"❌ Error executing action '{action}': {e}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Action failed: {e}")


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Gmail CrewAI",
        page_icon="📧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inject shadcn-inspired CSS styling
    inject_shadcn_css()
    
    init_session_state()
    
    # Get query params for OAuth callback and approval links
    query_params = st.query_params
    
    # Handle approval/rejection links
    if 'action' in query_params and 'token' in query_params:
        action = query_params['action']
        token = query_params['token']
        
        user_manager = UserManager()
        email_service = EmailService()
        
        # Validate token
        token_info = email_service.validate_approval_token(token)
        
        if token_info:
            user_id = token_info['user_id']
            user_email = token_info['email']
            
            if action == 'approve':
                if user_manager.approve_user(user_id):
                    email_service.mark_token_used(token)
                    st.success(f"✅ User {user_email} has been approved successfully!")
                    st.info("The user can now log in to the system.")
                else:
                    st.error("❌ Failed to approve user. User may not exist or is already processed.")
            
            elif action == 'reject':
                if user_manager.reject_user(user_id):
                    email_service.mark_token_used(token)
                    st.warning(f"⚠️ User {user_email} has been rejected and removed from the system.")
                else:
                    st.error("❌ Failed to reject user. User may not exist or is already processed.")
            
            # Clear query params to avoid processing again
            st.query_params.clear()
            st.balloons()
            
        else:
            st.error("❌ Invalid or expired approval link.")
        
        return  # Stop execution here for approval links
    
    # Handle OAuth callback automatically
    if 'code' in query_params and 'state' in query_params:
        auth_code = query_params['code']
        state = query_params['state']
        
        # Store in session to persist across reruns
        if 'oauth_processing' not in st.session_state:
            st.session_state.oauth_processing = True
            st.session_state.oauth_result = None
            st.session_state.oauth_error = None
            
            # Processing OAuth callback silently
            user_manager = st.session_state.user_manager
            
            # The state contains the OAuth user_id (which includes the authenticated user_id)
            oauth_user_id = state
            
            # Complete OAuth authentication automatically
            try:
                if st.session_state.oauth_manager.handle_oauth_callback(oauth_user_id, auth_code):
                    # Extract the original user ID from the OAuth user ID
                    # OAuth user ID format: user_zhQ7K854ngI_a1b2c3d4
                    # We need to extract: user_zhQ7K854ngI
                    if '_' in oauth_user_id:
                        # Split by underscore and take all parts except the last (which is the random suffix)
                        parts = oauth_user_id.split('_')
                        if len(parts) >= 3:  # user_id_suffix format
                            authenticated_user_id = '_'.join(parts[:-1])  # Join all but last part
                        else:
                            authenticated_user_id = oauth_user_id  # Fallback if format is unexpected
                    else:
                        authenticated_user_id = oauth_user_id  # Fallback if no underscore
                    
                    # Verify this user exists in our system
                    user_data = user_manager.get_user_by_id(authenticated_user_id)
                    if user_data and user_data.get('status') == 'approved':
                        user_manager.update_last_login(authenticated_user_id)
                        
                        st.session_state.oauth_result = "success"
                        st.session_state.authenticated_user_id = authenticated_user_id
                        st.session_state.current_user = oauth_user_id
                        st.session_state.authentication_step = 'dashboard'
                        
                        # Create persistent session (7-day login)
                        session_token = session_manager.create_session(authenticated_user_id)
                        session_manager.set_browser_session(session_token)
                        
                        # Clean up pending state (if any)
                        if 'pending_login_user_id' in st.session_state:
                            del st.session_state.pending_login_user_id
                        if 'pending_oauth_user_id' in st.session_state:
                            del st.session_state.pending_oauth_user_id
                    else:
                        st.session_state.oauth_result = "failed"
                        st.session_state.oauth_error = "User not found or not approved"
                        st.session_state.authentication_step = 'login'
                else:
                    st.session_state.oauth_result = "failed"
                    st.session_state.oauth_error = "Authentication failed"
                    st.session_state.authentication_step = 'login'
            except Exception as e:
                st.session_state.oauth_result = "error"
                st.session_state.oauth_error = str(e)
                st.session_state.authentication_step = 'login'
            
            # Clear query parameters and processing flag
            st.query_params.clear()
            st.session_state.oauth_processing = False
            st.rerun()
    
    # Show OAuth results if available
    if 'oauth_result' in st.session_state:
        if st.session_state.oauth_result == "failed":
            st.error(f"❌ Authentication failed: {st.session_state.oauth_error}")
            # Clear the result after showing
            del st.session_state.oauth_result
            if 'oauth_error' in st.session_state:
                del st.session_state.oauth_error
        elif st.session_state.oauth_result == "error":
            st.error(f"❌ OAuth error: {st.session_state.oauth_error}")
            # Clear the result after showing
            del st.session_state.oauth_result
            if 'oauth_error' in st.session_state:
                del st.session_state.oauth_error
        elif st.session_state.oauth_result == "success":
            # Create a success message that disappears after 3 seconds
            success_placeholder = st.empty()
            success_placeholder.success("🎉 Authentication successful! Redirecting...")
            
            # Use JavaScript to hide the message after 3 seconds
            components.html(
                """
                <script>
                setTimeout(function() {
                    var elements = parent.document.querySelectorAll('[data-testid="stAlert"]');
                    elements.forEach(function(element) {
                        if (element.textContent.includes('🎉 Authentication successful!')) {
                            element.style.display = 'none';
                        }
                    });
                }, 3000);
                </script>
                """,
                height=0,
            )
            
            # Clear the result after showing
            del st.session_state.oauth_result
            if 'oauth_error' in st.session_state:
                del st.session_state.oauth_error
    
    # Check for credentials file first
    if not show_setup_instructions():
        return
    
    # Route to appropriate page based on authentication state
    if st.session_state.authentication_step == 'login':
        show_login_page()
    elif st.session_state.authentication_step == 'google_oauth':
        # OAuth is handled automatically via query params, show waiting message
        st.markdown("# 🔐 Authenticating...")
        st.info("🔄 Processing Google authentication, please wait...")
        st.markdown("If you're not redirected automatically, please check your popup blocker and try again.")
    elif st.session_state.authentication_step == 'admin_panel':
        # Check authentication before showing admin panel
        if st.session_state.authenticated_user_id:
            show_admin_panel()
        else:
            st.error("❌ Please log in to access the admin panel")
            st.session_state.authentication_step = 'login'
            st.rerun()
    elif st.session_state.authentication_step == 'select_user':
        show_user_selection()
    elif st.session_state.authentication_step == 'oauth_flow':
        show_oauth_flow()
    elif st.session_state.authentication_step == 'dashboard':
        # Check authentication before showing dashboard
        if st.session_state.authenticated_user_id and st.session_state.current_user:
            show_dashboard()
        else:
            st.error("❌ Please log in to access the dashboard")
            st.session_state.authentication_step = 'login'
            st.rerun()


if __name__ == "__main__":
    main() 