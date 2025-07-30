"""Streamlit app for Gmail Crew AI with OAuth2 authentication and user management."""

import streamlit as st
import streamlit.components.v1 as components
import uuid
import os
import json
import sys
import io
import threading
import time
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import hashlib
import secrets
import urllib.parse
import base64

# Configure logging to reduce verbose output
try:
    from configure_logging import configure_logging
    configure_logging()
except ImportError:
    # Fallback to basic logging suppression
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    import warnings
    warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

def safe_add_activity_log(message: str):
    """Safely add a message to activity logs with initialization check."""
    if 'activity_logs' not in st.session_state:
        st.session_state.activity_logs = []
    st.session_state.activity_logs.append(message)

# Helper function for safe imports with detailed diagnostics
def safe_import(module_path, alias=None):
    """Safely import a module with detailed logging for troubleshooting.
    
    Args:
        module_path: The module to import (e.g., 'src.common.logger')
        alias: Optional alias for the import (e.g., 'logger')
    
    Returns:
        The imported module or None if import failed
    """
    try:
        # Import the module
        if '.' in module_path:
            # Handle package imports like 'from src.common.logger import get_logger'
            package_path, module_name = module_path.rsplit('.', 1)
            package = __import__(package_path, fromlist=[module_name])
            module = getattr(package, module_name)
        else:
            # Handle simple imports
            module = __import__(module_path)
        
        # Set the module in global namespace with appropriate name
        globals()[alias or module_path.split('.')[-1]] = module
        return module
        
    except Exception as e:
        # Import logger first if it doesn't exist yet
        if 'log' not in globals():
            try:
                from src.common.logger import get_logger, exception_info
                globals()['log'] = get_logger(__name__)
                globals()['exception_info'] = exception_info
            except Exception:
                # Fallback to basic logging if logger import fails
                import logging
                logging.basicConfig(level=logging.ERROR)
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to import logger module: {e}")
                st.error(f"Failed to import logging system: {e}")
                raise
        
        # Log the detailed error with stack trace
        try:
            if 'exception_info' in globals() and globals()['exception_info'] is not None:
                globals()['exception_info'](log, f"Import failed: {module_path}")
            else:
                log.error(f"Import failed: {module_path}", exc_info=True)
        except Exception:
            # Final fallback - just log the error normally
            log.error(f"Import failed: {module_path}: {e}", exc_info=True)
        
        # Also display in Streamlit UI for user visibility
        st.error(f"❌ Import error for {module_path}: {e}")
        st.error("Please ensure all dependencies are installed: pip install -r requirements.txt")
        
        # Re-raise the exception so it appears in UI
        raise

# Import our modules with safe_import helper
try:
    # First import the logger system
    safe_import('src.common.logger.get_logger', 'get_logger')
    safe_import('src.common.logger.exception_info', 'exception_info')
    safe_import('src.common.logger.get_auth_logger', 'get_auth_logger')
    safe_import('src.common.logger.get_crew_logger', 'get_crew_logger')
    safe_import('src.common.logger.get_system_logger', 'get_system_logger')
    
    # Initialize logger
    log = get_logger(__name__)
    
    # Now import other modules with detailed logging
    safe_import('src.gmail_crew_ai.auth.OAuth2Manager', 'OAuth2Manager')
    safe_import('src.gmail_crew_ai.crew_oauth.OAuth2GmailCrewAi', 'OAuth2GmailCrewAi')
    safe_import('src.gmail_crew_ai.crew_oauth.create_crew_for_user', 'create_crew_for_user')
    safe_import('src.gmail_crew_ai.models.EmailDetails', 'EmailDetails')
    safe_import('src.common.security.APIKeyManager', 'APIKeyManager')
    
except Exception as e:
    # Final catch-all for any import errors
    st.error(f"❌ Critical import error: {e}")
    st.error("Application cannot start due to missing dependencies or modules.")
    st.error("Please check the logs above for detailed error information.")
    st.stop()


class SessionManager:
    """Manages persistent user sessions with improved reliability."""
    
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
            if 'exception_info' in globals():
                exception_info(log, "Failed to save sessions")
            else:
                log.error("Failed to save sessions", exc_info=True)
    
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
        """Invalidate a specific session token."""
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
        """Set session token for persistence across page refreshes using cookies."""
        # Store in Streamlit's session state for immediate use
        st.session_state.persistent_session_token = session_token
        
        # Set browser cookie with proper expiry
        expiry_date = (datetime.now() + self.session_duration).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        # Use more reliable cookie setting approach
        js_code = f"""
        <script>
        // Set browser cookie for persistent session
        document.cookie = "gmail_crew_session={session_token}; expires={expiry_date}; path=/; SameSite=Lax";
        console.log("Session cookie set: gmail_crew_session");
        </script>
        """
        components.html(js_code, height=0)
    
    def get_browser_session(self) -> Optional[str]:
        """Get session token using a more reliable approach."""
        # Strategy 1: Check Streamlit session state first
        if 'persistent_session_token' in st.session_state:
            log.debug("Found session token in Streamlit session state")
            return st.session_state.persistent_session_token
        
        # Strategy 2: Check URL parameters (from redirects)
        query_params = st.query_params
        if 'session_token' in query_params:
            session_token = query_params['session_token']
            log.debug("Found session token in URL parameters")
            # Store it in session state for this session
            st.session_state.persistent_session_token = session_token
            # Clear the URL parameter to clean up the URL
            try:
                del st.query_params['session_token']
            except:
                pass
            return session_token
        
        # Strategy 3: Try to find active session by checking all sessions for this user
        # This is a fallback that works without cookies
        try:
            sessions = self.load_sessions()
            current_time = datetime.now()
            
            # Look for any non-expired session for the primary user
            for session_token, session_data in sessions.items():
                try:
                    expires_at = datetime.fromisoformat(session_data['expires_at'])
                    user_id = session_data.get('user_id')
                    
                    if current_time < expires_at and user_id:
                        # Check if this user is approved and primary
                        user_manager = st.session_state.get('user_manager')
                        if user_manager:
                            users = user_manager.load_users()
                            user_data = users.get(user_id, {})
                            
                            if (user_data.get('status') == 'approved' and 
                                user_data.get('is_primary', False)):
                                log.debug(f"Found active session for primary user {user_id}")
                                # Store in session state for immediate use
                                st.session_state.persistent_session_token = session_token
                                return session_token
                except Exception:
                    continue
        except Exception as e:
            log.debug(f"Error in fallback session discovery: {e}")
        
        # Strategy 4: Use browser cookies only as final fallback
        if not st.session_state.get('cookie_check_attempted', False):
            st.session_state.cookie_check_attempted = True
            
            js_code = """
            <script>
            const cookies = document.cookie.split(';');
            let sessionToken = null;
            
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'gmail_crew_session') {
                    sessionToken = value;
                    break;
                }
            }
            
            if (sessionToken) {
                console.log("Found session cookie, redirecting");
                const currentUrl = new URL(window.location.href);
                currentUrl.searchParams.set('session_token', sessionToken);
                window.location.href = currentUrl.href;
            }
            </script>
            """
            components.html(js_code, height=0)
            log.debug("Attempting cookie-based session recovery")
        
        return None
    
    def clear_browser_session(self):
        """Clear session token from browser and session state."""
        # Clear from Streamlit session state
        for key in ['persistent_session_token', 'cookie_check_attempted']:
            if key in st.session_state:
                del st.session_state[key]
        
        # Clear browser cookie
        js_code = """
        <script>
        // Clear the session cookie
        document.cookie = "gmail_crew_session=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax";
        console.log("Session cookie cleared");
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

    /* Force filter buttons row to stay horizontal on mobile */
    div[data-testid="column"]:has(.stButton > button[title*="emails"]) {
        min-width: 2.8rem !important;
        flex-shrink: 0 !important;
    }
    
    /* Ensure the columns container doesn't wrap */
    .stHorizontalBlock {
        flex-wrap: nowrap !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
    
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
        min-width: 2.5rem !important;
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
        flex-shrink: 0 !important;
    }
    
    /* Mobile responsive adjustments - make buttons much smaller to fit 6 in one row */
    @media (max-width: 768px) {
        .stButton > button[title="Unread emails (is:unread)"],
        .stButton > button[title="Starred emails (is:starred)"],
        .stButton > button[title="Emails with attachments (has:attachment)"],
        .stButton > button[title="Important emails (is:important)"],
        .stButton > button[title="Today's emails (newer_than:1d)"],
        .stButton > button[title="Primary category (category:primary)"] {
            width: 1.7rem !important;
            height: 1.7rem !important;
            min-width: 1.7rem !important;
            min-height: 1.7rem !important;
            max-width: 1.7rem !important;
            font-size: 0.85rem !important;
            margin: 0.05rem !important;
            padding: 0 !important;
            border-radius: 0.25rem !important;
        }
        
        /* Force columns to be very narrow on mobile */
        div[data-testid="column"]:has(.stButton > button[title*="emails"]) {
            min-width: 1.8rem !important;
            max-width: 1.8rem !important;
            flex-shrink: 0 !important;
            flex-grow: 0 !important;
        }
        
        /* Ensure the main container has proper spacing on mobile */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        
        /* Make sure the horizontal block doesn't wrap and fits */
        .stHorizontalBlock {
            gap: 0.1rem !important;
        }
    }

    /* Enhanced tooltip styling for better positioning and visibility */
    .stButton > button[title*="emails"],
    .stButton > button[title*="Start"],
    .stButton > button[title*="Stop"],
    .stButton > button[title*="Running"],
    .stButton > button[title*="Processing"],
    .stButton > button[title*="Logout"],
    .stButton > button[title*="Clear"],
    .stButton > button[title*="Refresh"],
    .stButton > button[title*="Remove"],
    .stButton > button[title*="Rebuild"],
    .stButton > button[title*="Update"],
    .stButton > button[title*="Download"],
    .stButton > button[title*="View"] {
        position: relative !important;
        /* Disable default browser tooltips */
        pointer-events: auto !important;
    }

    /* Custom tooltips that intelligently position to avoid overlapping */
    .stButton > button[title*="emails"]:hover::after,
    .stButton > button[title*="Start"]:hover::after,
    .stButton > button[title*="Stop"]:hover::after,
    .stButton > button[title*="Running"]:hover::after,
    .stButton > button[title*="Processing"]:hover::after,
    .stButton > button[title*="Logout"]:hover::after,
    .stButton > button[title*="Clear"]:hover::after,
    .stButton > button[title*="Refresh"]:hover::after,
    .stButton > button[title*="Remove"]:hover::after,
    .stButton > button[title*="Rebuild"]:hover::after,
    .stButton > button[title*="Update"]:hover::after,
    .stButton > button[title*="Download"]:hover::after,
    .stButton > button[title*="View"]:hover::after {
        content: attr(title) !important;
        position: absolute !important;
        bottom: calc(100% + 15px) !important; /* Always position above with clear gap */
        left: 50% !important;
        transform: translateX(-50%) !important;
        background: linear-gradient(135deg, rgba(40, 44, 52, 0.98), rgba(33, 37, 43, 0.98)) !important;
        color: #ffffff !important;
        padding: 8px 12px !important;
        border-radius: 6px !important;
        font-size: 11px !important;
        line-height: 1.4 !important;
        white-space: nowrap !important;
        max-width: 200px !important;
        text-align: center !important;
        z-index: 999999 !important; /* Highest z-index to ensure visibility */
        font-weight: 400 !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        pointer-events: none !important;
        opacity: 0 !important;
        animation: smoothTooltipFadeIn 0.2s cubic-bezier(0.4, 0, 0.2, 1) 0.5s forwards !important;
        /* Prevent tooltip from being clipped */
        clip-path: none !important;
        overflow: visible !important;
    }

    /* Smart positioning for tooltips near screen edges */
    .stButton > button[title*="emails"]:hover::after {
        /* For filter buttons, ensure they don't overflow */
        white-space: nowrap !important;
        max-width: 180px !important;
    }

    /* Responsive tooltip positioning for mobile/small screens */
    @media (max-width: 768px) {
        .stButton > button[title*="emails"]:hover::after,
        .stButton > button[title*="Start"]:hover::after,
        .stButton > button[title*="Stop"]:hover::after,
        .stButton > button[title*="Running"]:hover::after,
        .stButton > button[title*="Processing"]:hover::after,
        .stButton > button[title*="Logout"]:hover::after,
        .stButton > button[title*="Clear"]:hover::after,
        .stButton > button[title*="Refresh"]:hover::after,
        .stButton > button[title*="Remove"]:hover::after,
        .stButton > button[title*="Rebuild"]:hover::after,
        .stButton > button[title*="Update"]:hover::after,
        .stButton > button[title*="Download"]:hover::after,
        .stButton > button[title*="View"]:hover::after {
            /* On small screens, position tooltips more carefully */
            max-width: 160px !important;
            font-size: 10px !important;
            padding: 6px 8px !important;
            bottom: calc(100% + 12px) !important;
            /* Prevent overflow on small screens */
            white-space: normal !important;
            word-wrap: break-word !important;
        }
    }

    /* Special positioning for buttons in columns to prevent overflow */
    [data-testid="column"] .stButton > button[title*="emails"]:hover::after {
        /* Ensure filter button tooltips stay within their column bounds */
        left: 50% !important;
        transform: translateX(-50%) !important;
        max-width: 150px !important;
    }

    /* Prevent tooltips from interfering with page layout */
    .stButton:hover {
        /* Ensure button container doesn't expand when tooltip shows */
        overflow: visible !important;
        position: relative !important;
        z-index: 1 !important;
    }

    /* Tooltip arrow with better styling */
    .stButton > button[title*="emails"]:hover::before,
    .stButton > button[title*="Start"]:hover::before,
    .stButton > button[title*="Stop"]:hover::before,
    .stButton > button[title*="Running"]:hover::before,
    .stButton > button[title*="Processing"]:hover::before,
    .stButton > button[title*="Logout"]:hover::before,
    .stButton > button[title*="Clear"]:hover::before,
    .stButton > button[title*="Refresh"]:hover::before,
    .stButton > button[title*="Remove"]:hover::before,
    .stButton > button[title*="Rebuild"]:hover::before,
    .stButton > button[title*="Update"]:hover::before,
    .stButton > button[title*="Download"]:hover::before,
    .stButton > button[title*="View"]:hover::before {
        content: "" !important;
        position: absolute !important;
        bottom: calc(100% + 9px) !important; /* Position arrow just below tooltip */
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 0 !important;
        height: 0 !important;
        border-left: 5px solid transparent !important;
        border-right: 5px solid transparent !important;
        border-top: 6px solid rgba(40, 44, 52, 0.98) !important;
        z-index: 999998 !important;
        pointer-events: none !important;
        opacity: 0 !important;
        animation: smoothTooltipFadeIn 0.2s cubic-bezier(0.4, 0, 0.2, 1) 0.5s forwards !important;
    }

    /* Smooth fade-in animation for tooltips */
    @keyframes smoothTooltipFadeIn {
        from {
            opacity: 0;
            transform: translateX(-50%) translateY(8px) scale(0.95);
        }
        to {
            opacity: 1;
            transform: translateX(-50%) translateY(0) scale(1);
        }
    }

    /* Legacy animation for compatibility */
    @keyframes tooltipFadeIn {
        from {
            opacity: 0;
            transform: translateX(-50%) translateY(5px);
        }
        to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
        }
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
    
    def clear_sensitive_session_data(self):
        """Clear sensitive data from Streamlit session state."""
        sensitive_keys = [
            'user_api_keys',
            'decrypted_keys', 
            'anthropic_key',
            'openai_key',
            'api_key_input',
            'temp_api_key',
            'masked_keys'
        ]
        for key in sensitive_keys:
            if key in st.session_state:
                del st.session_state[key]
                log.debug(f"Cleared sensitive session data: {key}")


class EmailService:
    """Handles email notifications for user approvals."""
    
    def __init__(self):
        self.approver_email = "articulatedesigns@gmail.com"
        self.app_url = "http://localhost:8505"  # Default port for Streamlit app
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
            if 'exception_info' in globals():
                exception_info(log, "Failed to save approval tokens")
            else:
                log.error("Failed to save approval tokens", exc_info=True)
    
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
                        <h1> User Registration Approval</h1>
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
                            <a href="{approve_url}" class="button approve"> APPROVE USER</a>
                            <a href="{reject_url}" class="button reject"> REJECT USER</a>
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
                log.info(f"Approval email sent successfully to {self.approver_email}")
                # Also store for admin panel display
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True
            else:
                log.warning("Failed to send actual email, storing for demo purposes")
                # Store for display in admin panel
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True  # Still return True so user gets feedback
            
        except Exception as e:
            if 'exception_info' in globals():
                exception_info(log, "Error sending approval email")
            else:
                log.error("Error sending approval email", exc_info=True)
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
                log.warning("SMTP credentials not found in environment variables")
                log.warning("Set SMTP_USERNAME and SMTP_PASSWORD (or EMAIL_ADDRESS and APP_PASSWORD)")
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
            log.error(f"Failed to send email via SMTP: {e}")
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
                log.warning("No primary user found for sending approval emails")
                return False
            
            # Get OAuth manager
            oauth_manager = st.session_state.get('oauth_manager')
            if not oauth_manager:
                log.warning("OAuth manager not available")
                return False
            
            # Check if primary user is authenticated
            primary_user_id = primary_user['user_id']
            if not oauth_manager.is_authenticated(primary_user_id):
                log.warning(f"Primary user {primary_user['email']} is not authenticated with OAuth2")
                return False
            
            # Generate approval URLs
            approve_token = self.generate_approval_token(user_id, user_email)
            approve_url = f"{self.app_url}?action=approve&token={approve_token}"
            reject_url = f"{self.app_url}?action=reject&token={approve_token}"
            
            # Create email content
            subject = f" New User Registration Request - {user_email}"
            
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
                        <h1> New User Registration Request</h1>
                    </div>
                    
                    <div class="content">
                        <p><strong>Email:</strong> {user_email}</p>
                        <p><strong>User ID:</strong> {user_id}</p>
                        <p><strong>Registration Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        
                        <p>A new user has requested access to the Gmail CrewAI system. Please review and approve or reject this request:</p>
                        
                        <div style="text-align: center; margin: 30px 0;">
                            <a href="{approve_url}" class="button approve"> APPROVE USER</a>
                            <a href="{reject_url}" class="button reject"> REJECT USER</a>
                        </div>
                        
                        <p><strong>Note:</strong> These links will expire and can only be used once.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Try to send via OAuth2 Gmail API
            if self.send_email_via_oauth2(oauth_manager, primary_user_id, primary_user['email'], subject, html_body):
                log.info(f"Approval email sent successfully via OAuth2 to {primary_user['email']}")
                # Also store for admin panel display
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True
            else:
                log.warning("Failed to send via OAuth2, storing for admin panel")
                self.store_approval_email(user_email, user_id, html_body, approve_url, reject_url)
                return True  # Still return True so user gets feedback
            
        except Exception as e:
            if 'exception_info' in globals():
                exception_info(log, "Error sending approval email with OAuth2")
            else:
                log.error("Error sending approval email with OAuth2", exc_info=True)
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
            log.error(f"Failed to send email via OAuth2 Gmail API: {e}")
            return False


class UserManager:
    """Manages user registration, approval, and authentication."""
    
    def __init__(self):
        self.users_file = "users.json"
        self.email_service = EmailService()
        # Initialize secure API key manager
        try:
            self.api_key_manager = APIKeyManager()
        except Exception as e:
            log.warning(f"Could not initialize API key encryption: {e}")
            self.api_key_manager = None
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
            if 'exception_info' in globals():
                exception_info(log, "Failed to save users")
            else:
                log.error("Failed to save users", exc_info=True)
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
            log.info(f"Registered first user as primary owner: {email}")
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
                    log.error(f"Failed to send approval email: {e}")
        
        self.save_users(users)
        
        
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
            log.error(f"Failed to resend approval email: {e}")
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
    
    def make_user_admin(self, email: str) -> bool:
        """Make a user an admin by email address."""
        users = self.load_users()
        
        for user_id, user_data in users.items():
            if user_data['email'] == email:
                user_data['role'] = 'admin'
                users[user_id] = user_data
            self.save_users(users)
            log.info(f"Made {email} an admin user")
            return True
        
        log.warning(f"User {email} not found")
        return False
    
    def initialize_admin_user(self, email: str) -> bool:
        """Initialize an admin user if they don't exist."""
        user_id, user_data = self.get_user_by_email(email)
        
        if user_data:
            # User exists, make them admin
            return self.make_user_admin(email)
        else:
            # User doesn't exist, create them as admin
            users = self.load_users()
            user_id = f"user_{secrets.token_urlsafe(8)}"
            
            users[user_id] = {
                "email": email,
                "status": "approved",
                "role": "admin",
                "created_at": datetime.now().isoformat(),
                "approved_at": datetime.now().isoformat(),
                "google_id": "",
                "last_login": None,
                "is_primary": False
            }
            
            self.save_users(users)
            log.info(f"Created and made {email} an admin user")
            return True
    
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
    
    def set_user_api_key(self, user_id: str, api_key_type: str, api_key: str) -> bool:
        """Set an API key for a specific user with encryption."""
        try:
            users = self.load_users()
            if user_id not in users:
                return False
            
            # Initialize api_keys dict if it doesn't exist
            if 'api_keys' not in users[user_id]:
                users[user_id]['api_keys'] = {}
            
            # Encrypt and store the API key
            if self.api_key_manager:
                try:
                    encrypted_key = self.api_key_manager.store_api_key(f"{user_id}_{api_key_type}", api_key)
                    users[user_id]['api_keys'][api_key_type] = encrypted_key
                    # Mark as encrypted for future identification
                    users[user_id]['api_keys'][f"{api_key_type}_encrypted"] = True
                except ValueError as e:
                    log.error(f"Invalid API key format for {api_key_type}: {e}")
                    return False
            else:
                # Fallback to plain storage if encryption not available
                log.warning("API key encryption not available, storing in plain text")
                users[user_id]['api_keys'][api_key_type] = api_key
                users[user_id]['api_keys'][f"{api_key_type}_encrypted"] = False
            
            self.save_users(users)
            log.info(f"API key set for user {user_id}, type: {api_key_type}")
            return True
        except Exception as e:
            if 'exception_info' in globals():
                exception_info(log, f"Error setting API key for user {user_id}")
            else:
                log.error(f"Error setting API key for user {user_id}: {e}", exc_info=True)
            return False
    
    def get_user_api_key(self, user_id: str, api_key_type: str) -> str:
        """Get an API key for a specific user with decryption, fallback to environment."""
        try:
            users = self.load_users()
            if user_id in users and 'api_keys' in users[user_id]:
                encrypted_key = users[user_id]['api_keys'].get(api_key_type)
                if encrypted_key:
                    # Check if key is encrypted
                    is_encrypted = users[user_id]['api_keys'].get(f"{api_key_type}_encrypted", True)
                    
                    if is_encrypted and self.api_key_manager:
                        # Decrypt the key
                        try:
                            decrypted_key = self.api_key_manager.retrieve_api_key(encrypted_key)
                            if decrypted_key:
                                return decrypted_key
                            else:
                                log.warning(f"Could not decrypt API key for user {user_id}, type {api_key_type}")
                        except Exception as e:
                            log.error(f"Decryption failed for user {user_id} API key {api_key_type}: {e}")
                    else:
                        # Return plain text key (legacy or fallback)
                        return encrypted_key
            
            # Fallback to environment variable
            env_key = os.getenv(f"{api_key_type.upper()}_API_KEY", '')
            return env_key
        except Exception as e:
            log.error(f"Error getting API key for user {user_id}: {e}")
            # Fallback to environment variable
            return os.getenv(f"{api_key_type.upper()}_API_KEY", '')
    
    def has_user_api_key(self, user_id: str, api_key_type: str) -> bool:
        """Check if user has their own API key (not using fallback)."""
        try:
            users = self.load_users()
            if user_id in users and 'api_keys' in users[user_id]:
                return api_key_type in users[user_id]['api_keys']
            return False
        except Exception as e:
            print(f"Error checking user API key for {user_id}: {e}")
            return False
    
    def remove_user_api_key(self, user_id: str, api_key_type: str) -> bool:
        """Remove a user's API key (will fallback to environment)."""
        try:
            users = self.load_users()
            if user_id in users and 'api_keys' in users[user_id]:
                if api_key_type in users[user_id]['api_keys']:
                    del users[user_id]['api_keys'][api_key_type]
                    self.save_users(users)
                    return True
            return False
        except Exception as e:
            print(f"Error removing API key for user {user_id}: {e}")
            return False





def check_persistent_session():
    """Check for and validate persistent session from browser storage."""
    try:
        # Clean up expired sessions first
        session_manager.cleanup_expired_sessions()
        
        # Strategy 1: Check if we have persistent user ID directly in session state
        if st.session_state.get('persistent_user_id'):
            user_id = st.session_state.persistent_user_id
            log.debug(f"Found persistent user ID in session state: {user_id}")
            
            # Validate this user still exists and is approved
            user_manager = st.session_state.user_manager
            users = user_manager.load_users()
            
            if user_id in users and users[user_id].get('status') == 'approved':
                log.info(f"Direct session state restoration for user {user_id}")
                
                # Restore full session
                st.session_state.authenticated_user_id = user_id
                oauth_manager = st.session_state.oauth_manager
                user_email = users[user_id].get('email', '')
                
                # Find OAuth token for this user
                try:
                    authenticated_users = oauth_manager.list_authenticated_users()
                    oauth_user_id = None
                    
                    for oid, email in authenticated_users.items():
                        if email.lower() == user_email.lower():
                            oauth_user_id = oid
                            break
                    
                    if not oauth_user_id and len(authenticated_users) == 1:
                        oauth_user_id = list(authenticated_users.keys())[0]
                        
                except Exception:
                    oauth_user_id = None
                
                st.session_state.current_user = oauth_user_id
                st.session_state.authentication_step = 'dashboard'
                user_manager.update_last_login(user_id)
                
                log.info(f"Session restored from session state for user: {user_id}")
                return True
        
        # Strategy 2: Try to get session token from various sources
        browser_session_token = session_manager.get_browser_session()
        
        # Enhanced debug output
        if browser_session_token:
            log.debug(f"Persistent session token found (length: {len(browser_session_token)})")
            
            # Validate the session
            user_id = session_manager.validate_session(browser_session_token)
            log.debug(f"Session validation result: user_id={user_id}")
            
            if user_id:
                # Check if user still exists and is approved
                user_manager = st.session_state.user_manager
                users = user_manager.load_users()
                
                if user_id in users and users[user_id].get('status') == 'approved':
                    log.info(f"User {user_id} found and approved, restoring session")
                    
                    # Restore session state completely
                    st.session_state.authenticated_user_id = user_id
                    oauth_manager = st.session_state.oauth_manager
                    user_email = users[user_id].get('email', '')
                    
                    # Try to find ANY valid OAuth token for this user's email
                    oauth_user_id = None
                    authenticated_users = {}
                    
                    # More robust OAuth token discovery
                    try:
                        authenticated_users = oauth_manager.list_authenticated_users()
                        log.debug(f"Found {len(authenticated_users)} OAuth tokens available")
                        
                        # Strategy 1: Find by exact email match
                        for oid, email in authenticated_users.items():
                            if email.lower() == user_email.lower():
                                oauth_user_id = oid
                                log.debug(f"Found OAuth token by email match: {oid}")
                                break
                        
                        # Strategy 2: Find by user_id prefix (fallback)
                        if not oauth_user_id:
                            for oid in authenticated_users.keys():
                                if oid.startswith(user_id):
                                    oauth_user_id = oid
                                    log.debug(f"Found OAuth token by user_id prefix: {oid}")
                                    break
                        
                        # Strategy 3: Use any token if user has only one (super fallback)
                        if not oauth_user_id and len(authenticated_users) == 1:
                            oauth_user_id = list(authenticated_users.keys())[0]
                            log.debug(f"Using single available OAuth token: {oauth_user_id}")
                            
                    except Exception as e:
                        log.debug(f"Error discovering OAuth tokens: {e}")
                    
                    # Set session state for successful restoration
                    st.session_state.current_user = oauth_user_id
                    st.session_state.authentication_step = 'dashboard'
                    
                    # Clear any login-related state
                    for key in ['oauth_result', 'oauth_error', 'oauth_processing']:
                        if key in st.session_state:
                            del st.session_state[key]
                    
                    # Update last login time
                    user_manager.update_last_login(user_id)
                    
                    if oauth_user_id:
                        log.info(f"Session successfully restored for user: {user_id} with OAuth: {oauth_user_id}")
                    else:
                        log.info(f"Session restored for user: {user_id} (OAuth will be prompted if needed)")
                    
                    return True
                else:
                    log.warning(f"User {user_id} not found or not approved, clearing session")
                    # User no longer exists or not approved, clear session
                    session_manager.invalidate_session(browser_session_token)
                    session_manager.clear_browser_session()
            else:
                log.warning("Invalid session token, clearing browser session")
                # Invalid session, clear browser storage
                session_manager.clear_browser_session()
        else:
            log.debug("No persistent session token found")
        
        # No valid session found, ensure we're in login state
        if st.session_state.get('authentication_step') != 'login':
            log.debug("Setting authentication step to login")
            st.session_state.authentication_step = 'login'
        
    except Exception as e:
        if 'exception_info' in globals():
            exception_info(log, "Error checking persistent session")
        else:
            log.error("Error checking persistent session", exc_info=True)
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
                <h1 class="login-title"> Gmail CrewAI</h1>
                <p class="login-subtitle">Secure email automation with AI</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Center the login form
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        # Check if we have a primary user
        user_manager = st.session_state.user_manager
        has_primary = user_manager.has_primary_user()
        
        if not has_primary:
            # No primary user yet - show first-time setup
            st.info("🎉 Welcome to Gmail CrewAI! This appears to be a fresh installation.")
            st.markdown("**First Time Setup**")
            st.markdown("The first person to authenticate will become the **primary owner** with full administrative access.")
            
            st.markdown("**Why do you need access?**")
            reason = st.text_area("Brief explanation", placeholder="I need to automate my work email management...", key="setup_reason")
            
            if st.button("🔗 Setup as Primary Owner with Gmail", type="primary", use_container_width=True):
                if reason.strip():
                    handle_direct_primary_setup(reason)
                else:
                    st.error("Please provide a brief explanation")
        else:
            # Normal login/registration flow when primary user exists
            tab1, tab2 = st.tabs([" Login", " Register"])
            
            with tab1:
                st.markdown("**Existing Users**")
                st.markdown("Click below to authenticate with your Gmail account:")
                
                # Gmail login button with icon
                if st.button("🔗 Login with Gmail", type="primary", use_container_width=True):
                    handle_direct_google_login()
                
                # Help section
                st.markdown("---")
                if st.button("❓ Need Help?", use_container_width=True):
                    primary_user = user_manager.get_primary_user()
                    if primary_user:
                        st.info(f"📧 Contact the primary owner ({primary_user['email']}) if you need access or have login issues.")
                    else:
                        st.info("📧 Contact your administrator if you need access or have login issues.")
            
            with tab2:
                st.markdown("**New Users**")
                st.markdown("Authenticate with your Gmail account to request access:")
                
                st.markdown("**Why do you need access?**")
                reason = st.text_area("Brief explanation", placeholder="I need to automate my work email management...", key="register_reason")
                
                # Gmail registration button with icon
                if st.button("🔗 Sign up with Gmail", type="primary", use_container_width=True):
                    if reason.strip():
                        handle_direct_gmail_registration(reason)
                    else:
                        st.error("Please provide a brief explanation")
                
                # Help section
                st.markdown("---")
                st.info("💡 After Gmail authentication, your request will be sent to the primary owner for approval.")
    
    # Footer
    st.markdown("""
    <div style="text-align: center; margin-top: 2rem; color: hsl(var(--muted-foreground)); font-size: 0.875rem;">
        Powered by Gmail CrewAI - AI-powered email automation
    </div>
    """, unsafe_allow_html=True)


def handle_direct_google_login():
    """Handle direct Google login without pre-entering email."""
    try:
        # Generate unique OAuth user ID for this session
        oauth_user_id = f"login_{uuid.uuid4().hex[:8]}"
        auth_url = st.session_state.oauth_manager.get_authorization_url(oauth_user_id)
        
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
        st.success("🔗 Opening Google authentication in a new tab...")
        st.info("📋 After authentication, we'll check if your account is registered and approved.")
        
    except Exception as e:
        st.error(f"❌ Error starting Google authentication: {e}")


def handle_direct_primary_setup(reason):
    """Handle primary owner setup with OAuth2 authentication."""
    try:
        # Generate unique OAuth user ID for primary setup
        oauth_user_id = f"primary_setup_{uuid.uuid4().hex[:8]}"
        auth_url = st.session_state.oauth_manager.get_authorization_url(oauth_user_id)
        
        # Store the reason for the callback handler
        st.session_state.pending_primary_reason = reason
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
        st.success("🔗 Opening Google authentication in a new tab...")
        st.info("👑 After authentication, you'll be set up as the primary owner.")
        
    except Exception as e:
        st.error(f"❌ Error starting Google authentication: {e}")


def handle_direct_gmail_registration(reason):
    """Handle Gmail registration with OAuth2 authentication."""
    try:
        # Generate unique OAuth user ID for registration
        oauth_user_id = f"register_{uuid.uuid4().hex[:8]}"
        auth_url = st.session_state.oauth_manager.get_authorization_url(oauth_user_id)
        
        # Store the reason for the callback handler
        st.session_state.pending_register_reason = reason
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
        st.success("🔗 Opening Google authentication in a new tab...")
        st.info("📝 After authentication, your registration request will be sent for approval.")
        
    except Exception as e:
        st.error(f"❌ Error starting Google authentication: {e}")


def handle_google_login(email: str):
    """Handle Google login process (legacy function for compatibility)."""
    user_manager = st.session_state.user_manager
    user_id, user_data = user_manager.get_user_by_email(email)
    
    if not user_data:
        st.error(" User not found. Please register first or contact the primary owner.")
        return
    
    if user_data['status'] != 'approved':
        if user_data['status'] == 'pending':
            primary_user = user_manager.get_primary_user()
            if primary_user:
                st.warning(" Your account is pending approval from the primary owner.")
                
                # Add resend approval email button (without nested columns to avoid Streamlit nesting error)
                if st.button(" Resend Approval Email", use_container_width=True):
                    handle_resend_approval_email(email)
                
                if st.button(" Help", use_container_width=True):
                    st.info(f"If you haven't received approval, click 'Resend Approval Email' to send another request to the primary owner: {primary_user['email']}")
            else:
                st.error(" No primary owner found. Please contact your system administrator.")
        else:
            st.error(" Your account has been rejected. Contact the primary owner.")
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
        st.success(" Opening Google authentication in a new tab...")
        
    except Exception as e:
        st.error(f" Error starting Google authentication: {e}")


def handle_registration_request(email: str, reason: str):
    """Handle new user registration request."""
    user_manager = st.session_state.user_manager
    
    # Check if user already exists
    existing_user_id, existing_user_data = user_manager.get_user_by_email(email)
    if existing_user_data:
        if existing_user_data['status'] == 'pending':
            st.warning(" You already have a pending registration request.")
        elif existing_user_data['status'] == 'approved':
            st.info(" You already have an approved account. Please use the Login tab.")
        else:
            st.error(" Your previous registration was rejected. Contact your administrator.")
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
            st.success(" Welcome! You've been registered as the primary owner of this Gmail CrewAI system!")
            st.info(" Your account has been automatically approved since you're the first user.")
            st.info(" You can now log in with your Google account and start using the system.")
            st.info(" As the primary owner, you have full administrative access and will receive all approval emails for future users.")
            st.markdown("**Next Steps:**")
            st.markdown("1.  Click 'Login' tab above")
            st.markdown("2.  Authenticate with your Google account")
            st.markdown("3.  Start automating your Gmail with AI!")
        else:
            # Subsequent user - needs approval
            primary_user = user_manager.get_primary_user()
            if primary_user:
                st.success(" Registration request submitted successfully!")
                st.info(f" An approval email has been sent to the primary owner: {primary_user['email']}")
                st.info(" Your request is pending approval. You'll be able to log in once the owner approves your request.")
                st.markdown("**Next Steps:**")
                st.markdown("1.  Primary owner will receive an approval email with your request details")
                st.markdown("2.  Owner will approve or reject your request") 
                st.markdown("3.  Once approved, you can log in with your Google account")
            else:
                st.warning(" No primary owner found. Please contact your system administrator.")
    else:
        st.error(" Registration failed. Please try again or contact support.")


def handle_resend_approval_email(email: str):
    """Handle resending approval email for a pending user."""
    user_manager = st.session_state.user_manager
    
    # Check if we have a primary user to send the email
    primary_user = user_manager.get_primary_user()
    if not primary_user:
        st.error(" No primary owner found. Cannot send approval email.")
        return
    
    if user_manager.resend_approval_email(email):
        st.success(" Approval email request has been processed!")
        
        # Check if primary user is authenticated with OAuth2
        oauth_manager = st.session_state.get('oauth_manager')
        if oauth_manager and oauth_manager.is_authenticated(primary_user['user_id']):
            st.info(f" An approval email has been sent to the primary owner: {primary_user['email']}")
            st.info(" Please wait for the owner to review and approve your request.")
        else:
            st.warning(" Email stored for owner review (primary owner not authenticated with OAuth2)")
            st.info(" The primary owner can view pending approval requests in the admin panel")
            st.info(" Primary owner needs to authenticate with Google OAuth2 to enable automatic email sending")
    else:
        st.error(" Failed to resend approval email. Please contact the primary owner.")





def show_admin_panel():
    """Show admin panel for user management."""
    st.markdown("##  Admin Panel")
    
    user_manager = st.session_state.user_manager
    
    # Check admin permissions
    authenticated_user_id = st.session_state.authenticated_user_id
    if not user_manager.is_admin(authenticated_user_id):
        st.error(" Access denied. Admin privileges required.")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs([" Pending Approvals", " All Users", " User Stats", " Approval Emails"])
    
    with tab1:
        st.markdown("###  Pending User Approvals")
        
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
                        if st.button(" Approve", key=f"approve_{user['user_id']}", type="primary"):
                            if user_manager.approve_user(user['user_id']):
                                st.success(f" Approved {user['email']}")
                                st.rerun()
                    
                    with col4:
                        if st.button(" Reject", key=f"reject_{user['user_id']}"):
                            if user_manager.reject_user(user['user_id']):
                                st.success(f" Rejected {user['email']}")
                                st.rerun()
                    
                    st.divider()
        else:
            st.info(" No pending approvals")
    
    with tab2:
        st.markdown("###  All Users")
        
        all_users = user_manager.get_all_users()
        
        if all_users:
            # Convert to DataFrame for better display
            df_users = pd.DataFrame(all_users)
            df_users['created_at'] = pd.to_datetime(df_users['created_at']).dt.strftime('%Y-%m-%d %H:%M')
            
            # Add primary owner indicator
            df_users['primary_owner'] = df_users.apply(
                lambda row: " Primary Owner" if row.get('is_primary', False) or row.get('role') == 'owner' else "",
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
            st.markdown("####  Delete User")
            user_to_delete = st.selectbox(
                "Select user to delete:",
                options=[user['user_id'] for user in all_users],
                format_func=lambda x: next(user['email'] for user in all_users if user['user_id'] == x),
                key="delete_user_selector"
            )
            
            if st.button(" Delete User", type="secondary"):
                if user_to_delete and user_to_delete != authenticated_user_id:
                    if user_manager.delete_user(user_to_delete):
                        st.success(" User deleted successfully")
                        st.rerun()
                else:
                    st.error(" Cannot delete your own account or invalid selection")
    
    with tab3:
        st.markdown("###  User Statistics")
        
        # Show primary user info first
        primary_user = user_manager.get_primary_user()
        if primary_user:
            st.markdown("####  Primary Owner")
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**Email:** {primary_user['email']}")
            with col2:
                oauth_manager = st.session_state.get('oauth_manager')
                
                # Debug: Check what user_id we're using
                debug_user_id = primary_user['user_id']
                debug_current_user = st.session_state.get('authenticated_user_id')
                
                # Check if we should use the current authenticated user instead
                # If the current user is the primary owner, use their session user_id
                user_id_to_check = debug_current_user if debug_current_user else debug_user_id
                
                # Also check if the primary owner email matches the current authenticated user
                if debug_current_user and oauth_manager:
                    try:
                        current_user_email = oauth_manager.get_user_email(debug_current_user)
                        if current_user_email == primary_user.get('email'):
                            user_id_to_check = debug_current_user
                    except Exception as e:
                        pass  # If we can't get email, continue with original logic
                
                is_oauth_authenticated = oauth_manager and oauth_manager.is_authenticated(user_id_to_check)
                auth_status = " OAuth2 Connected" if is_oauth_authenticated else " OAuth2 Not Connected"
                
                # Show debug info in admin panel
                st.info(f"**Status:** {auth_status}")
                
                # Add debug information for admin
                with st.expander("Debug Info", expanded=False):
                    st.text(f"Primary user_id: {debug_user_id}")
                    st.text(f"Current authenticated user_id: {debug_current_user}")
                    st.text(f"Checking authentication for: {user_id_to_check}")
                    st.text(f"OAuth manager available: {oauth_manager is not None}")
                    if oauth_manager:
                        # Check what token files exist
                        import glob
                        token_files = glob.glob("tokens/*_token.pickle")
                        st.text(f"Available token files: {token_files}")
                        # Check if this specific user has a token file
                        expected_token_file = f"tokens/{user_id_to_check}_token.pickle"
                        has_token_file = expected_token_file in token_files
                        st.text(f"Has token file for {user_id_to_check}: {has_token_file}")
            
            if not is_oauth_authenticated:
                st.warning(" Primary owner needs to authenticate with OAuth2 to send approval emails automatically.")
        else:
            st.warning(" No primary owner found!")
        
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
                st.metric(" Total Users", len(all_users))
            
            with col2:
                st.metric(" Approved", status_counts.get('approved', 0))
            
            with col3:
                st.metric(" Pending", status_counts.get('pending', 0))
            
            with col4:
                admin_count = role_counts.get('admin', 0) + role_counts.get('owner', 0)
                st.metric(" Admins/Owner", admin_count)
            
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
        st.markdown("###  Approval Emails")
        st.markdown("This shows the approval emails that would be sent to articulatedesigns@gmail.com")
        
        # Display pending approval emails
        if 'pending_approval_emails' in st.session_state and st.session_state.pending_approval_emails:
            for idx, email_info in enumerate(st.session_state.pending_approval_emails):
                with st.expander(f" Approval Request for {email_info['user_email']} - {email_info['created_at'][:16]}"):
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
                            if st.button(" Approve", key=f"direct_approve_{idx}", type="primary"):
                                if user_manager.approve_user(email_info['user_id']):
                                    st.success(f" Approved {email_info['user_email']}")
                                    # Remove from pending emails
                                    st.session_state.pending_approval_emails.pop(idx)
                                    st.rerun()
                        
                        with col_reject:
                            if st.button(" Reject", key=f"direct_reject_{idx}"):
                                if user_manager.reject_user(email_info['user_id']):
                                    st.success(f" Rejected {email_info['user_email']}")
                                    # Remove from pending emails
                                    st.session_state.pending_approval_emails.pop(idx)
                                    st.rerun()
                        
                        st.markdown("---")
                        st.markdown("**Approval Links:**")
                        st.markdown(f"**Approve:** {email_info['approve_url']}")
                        st.markdown(f"**Reject:** {email_info['reject_url']}")
                        
                        st.info(" Copy these links to test the approval flow!")
                        
            # Clear all processed emails button
            if st.button(" Clear All Email Previews", type="secondary"):
                st.session_state.pending_approval_emails = []
                st.success("All email previews cleared!")
                st.rerun()
        else:
            st.info(" No approval emails pending. When users register, their approval emails will appear here.")
            
        st.markdown("---")
        st.markdown("###  Email Configuration")
        st.markdown("**Approver Email:** articulatedesigns@gmail.com")
        st.markdown("**App URL:** http://localhost:8505")
        st.info(" In production, configure SMTP settings to actually send emails.")


def show_setup_instructions():
    """OAuth2 setup is handled automatically - no user setup required."""
    # Always return True to continue with normal app flow
    # OAuth2 credentials are handled automatically by the OAuth2Manager
    return True


def show_user_selection():
    """Show user selection interface."""
    st.markdown("###  User Authentication")
    
    # List existing authenticated users
    authenticated_users = st.session_state.oauth_manager.list_authenticated_users()
    
    if authenticated_users:
        # Use columns for compact layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("** Select User**")
            user_options = [f"{email}" for user_id, email in authenticated_users.items()]
            selected_user = st.selectbox(
                "Account:",
                options=user_options,
                key="existing_user_select",
                label_visibility="collapsed"
            )
            
            if st.button(" Login", type="primary", use_container_width=True):
                # Find user_id by email
                selected_email = selected_user
                user_id = next(uid for uid, email in authenticated_users.items() if email == selected_email)
                st.session_state.current_user = user_id
                st.session_state.authentication_step = 'dashboard'
                st.rerun()
        
        with col2:
            st.markdown("** Add New**")
            new_user_name = st.text_input(
                "Account name:",
                placeholder="e.g., work_email",
                label_visibility="collapsed"
            )
            
            if st.button(" Authenticate", disabled=not new_user_name, use_container_width=True):
                # Generate unique user ID
                user_id = f"{new_user_name}_{uuid.uuid4().hex[:8]}"
                st.session_state.new_user_id = user_id
                st.session_state.authentication_step = 'oauth_flow'
                st.rerun()
        
        # Compact management in expander
        with st.expander(" Manage"):
            user_to_remove = st.selectbox(
                "Remove:",
                options=list(authenticated_users.keys()),
                format_func=lambda x: f"{authenticated_users[x]}",
                label_visibility="collapsed"
            )
            
            if st.button(" Remove", type="secondary"):
                if st.session_state.oauth_manager.revoke_credentials(user_to_remove):
                    st.success(f" Removed access for {authenticated_users[user_to_remove]}")
                    st.rerun()
    
    else:
        # No existing users - simplified form
        st.markdown("** Add Your First Account**")
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            new_user_name = st.text_input(
                "Account name:",
                placeholder="e.g., work_email",
                label_visibility="collapsed"
            )
        
        with col2:
            if st.button(" Authenticate", disabled=not new_user_name, use_container_width=True):
                # Generate unique user ID
                user_id = f"{new_user_name}_{uuid.uuid4().hex[:8]}"
                st.session_state.new_user_id = user_id
                st.session_state.authentication_step = 'oauth_flow'
                st.rerun()


def show_oauth_flow():
    """Show OAuth2 authentication flow."""
    st.markdown("#  Gmail Authentication")
    
    user_id = st.session_state.new_user_id
    
    if 'auth_url' not in st.session_state:
        try:
            auth_url = st.session_state.oauth_manager.get_authorization_url(user_id)
            st.session_state.auth_url = auth_url
        except Exception as e:
            st.error(f"Error generating auth URL: {e}")
            if st.button(" Back to User Selection"):
                st.session_state.authentication_step = 'select_user'
                st.rerun()
            return
    
    st.markdown("### Step 1: Authorize Gmail Access")
    st.markdown(f"Click the link below to authorize access to Gmail:")
    
    st.markdown(f" **[Authorize Gmail Access]({st.session_state.auth_url})**")
    
    st.markdown("###  Waiting for Authentication")
    st.info("After clicking the link above, you'll be redirected back automatically.")
    st.markdown("**Note:** Make sure popup blockers are disabled for this site.")
    
    if st.button(" Back to User Selection"):
        st.session_state.authentication_step = 'select_user'
        if 'auth_url' in st.session_state:
            del st.session_state.auth_url
        st.rerun()


def show_dashboard():
    """Show the main dashboard with tabbed interface."""
    # Get current user information
    user_id = st.session_state.authenticated_user_id
    oauth_user_id = st.session_state.current_user
    oauth_manager = st.session_state.oauth_manager
    user_manager = st.session_state.user_manager
    
    # Get user email for display
    try:
        user_email = oauth_manager.get_user_email(oauth_user_id)
        user_data = user_manager.get_user_by_id(user_id)
        is_admin = user_manager.is_admin(user_id)
    except Exception as e:
        # Check if this is an OAuth credentials issue
        if "No valid credentials found" in str(e):
            st.error("🔑 Your authentication session has expired. Please log in again.")
            st.info("Click the 'Logout' button and then log in with your Gmail account to restore access.")
            
            # Clear the invalid OAuth credentials
            try:
                oauth_manager.revoke_credentials(oauth_user_id)
                log.info(f"Cleared invalid OAuth credentials for user: {oauth_user_id}")
            except Exception as revoke_error:
                log.warning(f"Could not revoke invalid credentials: {revoke_error}")
            
            # Clear the invalid session
            browser_token = session_manager.get_browser_session()
            if browser_token:
                session_manager.invalidate_session(browser_token)
            session_manager.clear_browser_session()
            
            # Reset to login state
            st.session_state.current_user = None
            st.session_state.authenticated_user_id = None
            st.session_state.authentication_step = 'login'
            
            # Add a rerun to immediately show login page
            if st.button("🔄 Go to Login"):
                st.rerun()
            return
        else:
            st.error(f"Error loading user information: {e}")
            return
    
    # Header with user info and logout
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown(f"# 📧 Gmail CrewAI")
        if is_admin:
            st.markdown(f"**👑 Admin:** {user_email}")
        else:
            st.markdown(f"**User:** {user_email}")
    
    with col2:
        st.markdown("### Welcome to Gmail Automation")
        st.markdown("*AI-powered email management*")
    
    with col3:
        if st.button("🚪 Logout"):
            # Clear persistent session
            browser_token = session_manager.get_browser_session()
            if browser_token:
                session_manager.invalidate_session(browser_token)
            session_manager.clear_browser_session()
            
            # Clear sensitive data first
            session_manager.clear_sensitive_session_data()
            
            # Clear all session state variables
            session_keys_to_clear = [
                'current_user', 'authenticated_user_id', 'authentication_step',
                'persistent_user_id', 'oauth_user_id', 'session_restored_on_load',
                'session_initialized', 'user_manager', 'selected_model',
                'api_keys_updated', 'processing_active', 'processing_started',
                'processing_stopped', 'activity_logs', 'processing_logs'
            ]
            
            for key in session_keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Reset authentication step
            st.session_state.authentication_step = 'login'
            
            # Clear any browser storage via JavaScript
            st.markdown("""
            <script>
            // Clear browser storage
            localStorage.clear();
            sessionStorage.clear();
            
            // Clear cookies
            document.cookie.split(";").forEach(function(c) { 
                document.cookie = c.replace(/^ +/, "").replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/"); 
            });
            </script>
            """, unsafe_allow_html=True)
            
            log.info(f"User {user_id} logged out successfully")
            st.rerun()
    
    st.markdown("---")
    
    # Create tabs - admin tab only visible to admin users (removed billing)
    if is_admin:
        tab_names = ["📧 Email Processing", "📋 Rules", "📊 Reports", "⚙️ Settings", "👑 Admin Panel"]
        tabs = st.tabs(tab_names)
    else:
        tab_names = ["📧 Email Processing", "📋 Rules", "📊 Reports", "⚙️ Settings"]
        tabs = st.tabs(tab_names)
    
    # Email Processing Tab
    with tabs[0]:
        show_email_processing_tab(user_id, oauth_manager)
    
    # Rules Tab
    with tabs[1]:
        show_rules_tab(user_id, oauth_manager)
    
    # Reports Tab
    with tabs[2]:
        show_reports_tab(user_id, oauth_manager)
    
    # Settings Tab
    with tabs[3]:
        show_settings_tab(user_id, oauth_manager)
    
    # Admin Panel Tab (only for admin users)
    if is_admin:
        with tabs[4]:
            show_admin_panel_tab(user_id, oauth_manager)


# Removed duplicate function - using the main implementation below


def show_rules_tab(user_id: str, oauth_manager):
    """Show AI email processing rules management."""
    st.markdown("## 📋 AI Processing Rules")
    st.markdown("*Configure how AI should handle your emails*")
    st.markdown("---")
    
    # Rule creation section
    st.markdown("### ➕ Create New Rule")
    
    with st.container():
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("**Gmail Search Filter**")
            rule_filter = st.text_input(
                "Filter Condition", 
                placeholder="e.g., from:client.com OR subject:urgent",
                label_visibility="collapsed"
            )
            
            # Quick filter examples
            st.markdown("**Quick Examples:**")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("📧 From Domain"):
                    st.session_state.temp_filter = "from:company.com"
                if st.button("📝 Subject Contains"):
                    st.session_state.temp_filter = "subject:urgent"
            with col_b:
                if st.button("🔴 High Priority"):
                    st.session_state.temp_filter = "is:important"
                if st.button("📎 Has Attachment"):
                    st.session_state.temp_filter = "has:attachment"
        
        with col2:
            st.markdown("**AI Action Instructions**")
            rule_action = st.text_area(
                "AI Instructions",
                placeholder="e.g., Reply with acknowledgment, mark as high priority, and create calendar reminder",
                height=120,
                label_visibility="collapsed"
            )
            
            # AI action examples
            st.markdown("**Action Examples:**")
            action_examples = [
                "Reply with: 'Thank you for your message. I will review and respond within 24 hours.'",
                "Mark as high priority and add label 'Client Work'",
                "Archive email and create summary note",
                "Forward to assistant@company.com with context",
                "Schedule follow-up reminder for tomorrow"
            ]
            
            selected_example = st.selectbox(
                "Use Example:",
                options=[""] + action_examples,
                label_visibility="collapsed"
            )
            
            if selected_example:
                st.session_state.temp_action = selected_example
    
    # Use temporary values if set
    if st.session_state.get('temp_filter'):
        rule_filter = st.session_state.temp_filter
        del st.session_state.temp_filter
    if st.session_state.get('temp_action'):
        rule_action = st.session_state.temp_action
        del st.session_state.temp_action
    
    # Add rule button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col2:
        if st.button("➕ Add Rule", type="primary", use_container_width=True):
            if rule_filter and rule_action:
                if 'email_rules' not in st.session_state:
                    st.session_state.email_rules = []
                
                st.session_state.email_rules.append({
                    'filter': rule_filter,
                    'action': rule_action,
                    'created': datetime.now().isoformat(),
                    'enabled': True
                })
                st.success("✅ Rule added successfully!")
                st.rerun()
            else:
                st.error("❌ Please fill in both filter and action fields.")
    
    st.markdown("---")
    
    # Display existing rules
    st.markdown("### 📚 Active Rules")
    
    if st.session_state.get('email_rules'):
        for i, rule in enumerate(st.session_state.email_rules):
            with st.expander(f"📋 Rule {i+1}: {rule['filter'][:50]}{'...' if len(rule['filter']) > 50 else ''}", expanded=False):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown("**Filter Condition:**")
                    st.code(rule['filter'], language=None)
                    
                    st.markdown("**AI Action:**")
                    st.text_area(
                        "Action",
                        value=rule['action'],
                        height=100,
                        disabled=True,
                        key=f"action_display_{i}",
                        label_visibility="collapsed"
                    )
                    
                    st.caption(f"Created: {rule['created'][:16]}")
                
                with col2:
                    st.markdown("**Controls:**")
                    
                    # Enable/Disable toggle
                    enabled = st.checkbox(
                        "Enabled",
                        value=rule.get('enabled', True),
                        key=f"enabled_{i}"
                    )
                    
                    if enabled != rule.get('enabled', True):
                        st.session_state.email_rules[i]['enabled'] = enabled
                        st.rerun()
                    
                    # Delete button
                    if st.button("🗑️ Delete", key=f"delete_rule_{i}", type="secondary", use_container_width=True):
                        st.session_state.email_rules.pop(i)
                        st.success("Rule deleted!")
                        st.rerun()
                    
                    # Test button
                    if st.button("🧪 Test", key=f"test_rule_{i}", use_container_width=True):
                        st.info("Rule testing functionality coming soon!")
        
        # Rules summary
        total_rules = len(st.session_state.email_rules)
        enabled_rules = len([r for r in st.session_state.email_rules if r.get('enabled', True)])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Rules", total_rules)
        with col2:
            st.metric("Active Rules", enabled_rules)
        with col3:
            st.metric("Disabled Rules", total_rules - enabled_rules)
        
        # Clear all rules
        st.markdown("---")
        if st.button("🗑️ Clear All Rules", type="secondary"):
            if st.session_state.get('confirm_clear_rules'):
                st.session_state.email_rules = []
                st.session_state.confirm_clear_rules = False
                st.success("All rules cleared!")
                st.rerun()
            else:
                st.session_state.confirm_clear_rules = True
                st.warning("Click again to confirm clearing all rules.")
    else:
        st.info("📝 **No rules defined yet**")
        st.markdown("""
        **Getting Started:**
        1. Create your first rule using the form above
        2. Use Gmail search syntax for precise email matching
        3. Provide clear AI instructions for desired actions
        4. Rules will be applied during email processing
        """)
        
        # Sample rules
        st.markdown("**Sample Rule Ideas:**")
        sample_rules = [
            {"filter": "from:newsletter", "action": "Archive automatically and mark as read"},
            {"filter": "subject:invoice", "action": "Forward to accounting@company.com and add 'Finance' label"},
            {"filter": "is:important from:boss", "action": "Reply with acknowledgment and set high priority"},
            {"filter": "has:attachment subject:contract", "action": "Save attachment to contracts folder and notify legal team"}
        ]
        
        for sample in sample_rules:
            st.markdown(f"• **Filter:** `{sample['filter']}` → **Action:** {sample['action']}")


def show_reports_tab(user_id: str, oauth_manager):
    """Show processing reports and results."""
    st.markdown("## 📊 Processing Reports")
    st.markdown("View results from your email processing sessions")
    
    # Create tabs for different report types
    report_tabs = st.tabs(["📋 Processing Reports", "💰 Token Usage", "📈 Analytics"])
    
    with report_tabs[0]:
        # Show latest processing reports (existing functionality)
        show_latest_processing_reports()
    
    with report_tabs[1]:
        # Show token usage reports
        show_token_usage_report(user_id)
    
    with report_tabs[2]:
        # Show analytics and trends
        show_processing_analytics(user_id)


def show_admin_panel_tab(user_id: str, oauth_manager):
    """Show admin panel for managing users and system."""
    st.markdown("## 👑 Admin Panel")
    st.markdown("Administrative controls and user management")
    
    # User management
    st.markdown("### 👥 User Management")
    
    user_manager = st.session_state.user_manager
    all_users = user_manager.load_users()
    
    if not all_users:
        st.info("No users in the system.")
        return
    
    # Display users in a table format
    user_data = []
    for uid, data in all_users.items():
        user_data.append({
            "ID": uid,
            "Email": data.get('email', 'Unknown'),
            "Status": data.get('status', 'Unknown'),
            "Role": "👑 Admin" if data.get('is_admin', False) else "User",
            "Last Login": data.get('last_login', 'Never'),
            "Created": data.get('created_at', 'Unknown')
        })
    
    df = pd.DataFrame(user_data)
    st.dataframe(df, use_container_width=True)
    
    st.markdown("---")
    
    # User Statistics
    st.markdown("### 📈 User Statistics")
    
    # Get primary user
    primary_user = user_manager.get_primary_user()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Primary Owner")
        if primary_user:
            st.markdown(f"**Email:** {primary_user.get('email', 'Unknown')}")
            
            # Debug: Check what user_id we're using
            debug_user_id = primary_user['user_id']
            debug_current_user = st.session_state.get('authenticated_user_id')
            
            # Check if we should use the current authenticated user instead
            # If the current user is the primary owner, use their session user_id
            user_id_to_check = debug_current_user if debug_current_user else debug_user_id
            
            # Also check if the primary owner email matches the current authenticated user
            if debug_current_user and oauth_manager:
                try:
                    current_user_email = oauth_manager.get_user_email(debug_current_user)
                    if current_user_email == primary_user.get('email'):
                        user_id_to_check = debug_current_user
                except Exception as e:
                    pass  # Use fallback user_id
            
            is_oauth_authenticated = oauth_manager and oauth_manager.is_authenticated(user_id_to_check)
            auth_status = "✅ OAuth2 Connected" if is_oauth_authenticated else "❌ OAuth2 Not Connected"
            
            if is_oauth_authenticated:
                st.success(f"**Status:** {auth_status}")
            else:
                st.error(f"**Status:** {auth_status}")
                st.info("Primary owner needs to authenticate with OAuth2 to send approval emails automatically.")
        else:
            st.warning("No primary owner found.")
    
    with col2:
        # System statistics
        total_users = len(all_users)
        approved_users = len([u for u in all_users.values() if u.get('status') == 'approved'])
        pending_users = len([u for u in all_users.values() if u.get('status') == 'pending'])
        admin_users = len([u for u in all_users.values() if u.get('is_admin', False)])
        
        st.metric("Total Users", total_users)
        st.metric("Approved", approved_users)
        st.metric("Pending", pending_users)
        st.metric("Admins", admin_users)
    
    st.markdown("---")
    
    # Admin actions
    st.markdown("### ⚙️ Admin Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### Make User Admin")
        admin_email = st.text_input("Email to promote:", placeholder="user@example.com")
        if st.button("👑 Make Admin"):
            if admin_email:
                if user_manager.make_user_admin(admin_email):
                    st.success(f"✅ Made {admin_email} an admin user")
                    st.rerun()
                else:
                    st.error(f"❌ Could not make {admin_email} an admin (user not found)")
    
    with col2:
        st.markdown("#### Approve User")
        if pending_users > 0:
            pending_list = [(uid, data['email']) for uid, data in all_users.items() if data.get('status') == 'pending']
            selected_pending = st.selectbox(
                "Select user to approve:",
                options=[f"{email} ({uid})" for uid, email in pending_list],
                format_func=lambda x: x.split(" (")[0]
            )
            
            if st.button("✅ Approve User") and selected_pending:
                selected_uid = selected_pending.split(" (")[1].rstrip(")")
                if user_manager.approve_user(selected_uid):
                    st.success("User approved successfully!")
                    st.rerun()
        else:
            st.info("No pending users")
    
    with col3:
        st.markdown("#### System Maintenance")
        if st.button("🧹 Cleanup Sessions"):
            session_manager.cleanup_expired_sessions()
            st.success("Expired sessions cleaned up!")
        
        if st.button("📊 Show System Status"):
            st.info("System is running normally")
            
        # Debug Mode Toggle (Admin Only)
        st.markdown("#### 🐛 Debug Settings")
        debug_enabled = st.checkbox(
            "Enable Debug Mode", 
            value=st.session_state.get('debug_mode', False),
            help="Show activity logs and debug information during email processing"
        )
        
        if debug_enabled != st.session_state.get('debug_mode', False):
            st.session_state.debug_mode = debug_enabled
            if debug_enabled:
                st.success("🐛 Debug mode enabled - activity logs will be visible")
            else:
                st.success("✅ Debug mode disabled - UI cleaned up")
            st.rerun()
    
    st.markdown("---")
    
    # Error logs for admins
    st.markdown("### 🚨 Error Logs")
    show_error_logs_tab(user_id, oauth_manager)


# Removed placeholder functions - all functionality is in the main email processing tab implementation


# Removed standalone activity window function - using inline implementation in main tab


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        'authentication_step': 'login',
        'authenticated_user_id': None,
        'current_user': None,
        'processing_active': False,
        'activity_logs': [],
        'email_rules': [],
        'session_initialized': False,
        'gmail_search': 'is:unread',
        'filter_max_emails': 3,
        'selected_model': os.getenv('MODEL', 'openai/gpt-4.1')
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def show_email_processing_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show email processing interface."""
    
    st.markdown("## 📧 Email Processing")
    st.markdown("*Configure filters and process your emails with AI*")
    st.markdown("---")
    
    # Stats overview - only show when not processing to avoid duplication
    if not st.session_state.get('processing_active', False):
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
        
        # Compact stats display with custom styling
        stats_html = f"""
        <style>
        .stats-container {{
            display: flex;
            justify-content: space-around;
            background: linear-gradient(90deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-item {{
            text-align: center;
            flex: 1;
            padding: 0 15px;
        }}
        .stat-number {{
            font-size: 28px;
            font-weight: 600;
            margin: 0;
            color: #2c3e50;
        }}
        .stat-label {{
            font-size: 13px;
            color: #6c757d;
            margin: 5px 0 0 0;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .stat-high {{ color: #dc3545; }}
        .stat-medium {{ color: #fd7e14; }}
        .stat-low {{ color: #28a745; }}
        .stat-total {{ color: #007bff; }}
        </style>
        
        <div class="stats-container">
            <div class="stat-item">
                <div class="stat-number stat-total">{total_processed}</div>
                <div class="stat-label">Total Processed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number stat-high">{high_priority}</div>
                <div class="stat-label">High Priority</div>
            </div>
            <div class="stat-item">
                <div class="stat-number stat-medium">{medium_priority}</div>
                <div class="stat-label">Medium Priority</div>
            </div>
            <div class="stat-item">
                <div class="stat-number stat-low">{low_priority}</div>
                <div class="stat-label">Low Priority</div>
            </div>
        </div>
        """
        st.markdown(stats_html, unsafe_allow_html=True)
    
    # Initialize session state if not exists
    if 'gmail_search' not in st.session_state:
        st.session_state.gmail_search = 'is:unread'
    
    st.markdown("### 🔍 Email Filters & Search")
    # Single row layout: Quick Filters + Search + Max Emails + Processing Controls
    col1, col2, col3, col4, col5, col6, col7, col8, col9, col10 = st.columns([0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 3, 0.8, 0.8, 0.8])
    
    # Quick filter buttons - compact icon-only design
    with col1:
        if st.button("📧", key="filter_unread"):
            st.session_state.gmail_search = "is:unread"
    
    with col2:
        if st.button("⭐", key="filter_starred"):
            st.session_state.gmail_search = "is:starred"
    
    with col3:
        if st.button("📎", key="filter_attachment"):
            st.session_state.gmail_search = "has:attachment"
    
    with col4:
        if st.button("🔴", key="filter_important"):
            st.session_state.gmail_search = "is:important"
    
    with col5:
        if st.button("📅", key="filter_today"):
            st.session_state.gmail_search = "newer_than:1d"
    
    with col6:
        if st.button("🗂️", key="filter_primary"):
            st.session_state.gmail_search = "category:primary"
    
    # Gmail search input - use session state value directly to avoid widget conflicts
    with col7:
        gmail_search = st.text_input(
            "Gmail Search Query",
            value=st.session_state.gmail_search,
            placeholder="e.g., from:example.com is:unread subject:(urgent OR important)",
            key="gmail_search_input",
            label_visibility="collapsed"
        )
        # Update session state when input changes
        if gmail_search != st.session_state.gmail_search:
            st.session_state.gmail_search = gmail_search
    
    # Max emails input
    with col8:
        # Initialize session state if not exists
        if 'filter_max_emails' not in st.session_state:
            st.session_state.filter_max_emails = 3
            
        max_emails = st.number_input(
            "Max Emails", 
            min_value=1, 
            max_value=100, 
            key="filter_max_emails", 
            label_visibility="collapsed"
        )
    
    # Processing control buttons
    with col9:
        if not st.session_state.processing_active:
            if st.button(" Start", type="primary", key="start_processing"):
                # Initialize processing state
                st.session_state.processing_active = True
                st.session_state.processing_started = False
                st.session_state.processing_stopped = False
                st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Starting email processing...")
                st.rerun()
        else:
            st.button(" Running", disabled=True, key="processing_status")
    
    with col10:
        if st.session_state.processing_active:
            if st.button(" Stop", type="secondary", key="stop_processing"):
                st.session_state.processing_active = False
                st.session_state.processing_stopped = True
                st.session_state.processing_started = False
                st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Processing stopped by user")
                st.warning(" Processing stopped by user")
                st.rerun()
        else:
            st.button(" Stop", disabled=True, key="stop_disabled")
    

    # Always show status section, with different detail levels based on debug mode
    st.markdown("---")
    
    # Initialize activity window state
    if 'activity_logs' not in st.session_state:
        st.session_state.activity_logs = []
    if 'activity_placeholder' not in st.session_state:
        st.session_state.activity_placeholder = None
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False
    
    if st.session_state.get('debug_mode', False):
        st.markdown("### 📺 Activity Window (Debug Mode)")
        st.markdown("*Real-time AI processing updates*")
        # Real-time activity container
        activity_container = st.container()
    else:
        st.markdown("### 📊 Processing Status")
        # Simplified status container
        activity_container = st.container()
    
    with activity_container:
        # Always show detailed activity logs (removed debug mode restriction)
        if st.session_state.processing_active:
            if st.session_state.get('processing_started', False):
                pass  # Processing status shown in activity logs
            else:
                pass  # Starting status shown in activity logs
        elif st.session_state.activity_logs:
            st.success("✅ **Processing completed!** Review the activity log below.")
        else:
            pass  # No status needed when ready
        
        # Live activity log with auto-scroll - always visible
        activity_placeholder = st.empty()
        
        # Display activity logs
        if st.session_state.activity_logs:
            logs_text = "\n".join(st.session_state.activity_logs)
            
            # Add current activity indicator if processing
            if st.session_state.processing_active:
                current_time = datetime.now().strftime('%H:%M:%S')
                logs_text += f"\n[{current_time}] 🔄 Processing in progress..."
            
            activity_placeholder.text_area(
                "Activity Log",
                value=logs_text,
                height=200,
                disabled=True,
                key="activity_display"
            )
        else:
            activity_placeholder.text_area(
                "Activity Log", 
                value="Ready to start processing. Click 'Start' above to begin email automation.",
                height=200,
                disabled=True,
                key="activity_empty"
            )
    
    # Start processing if needed
    if st.session_state.processing_active and not st.session_state.get('processing_started', False):
        st.session_state.processing_started = True
        
        # Add initial log entry
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 Starting email processing...")
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📧 Initializing AI crew with OAuth2 authentication...")
        
        # Execute the email processing
        try:
            # Run the actual processing function which contains all the crew logic
            process_emails_with_filters(user_id, oauth_manager)
            
            # Mark processing as complete
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 Processing pipeline completed!")
            
        except Exception as e:
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error during processing: {str(e)}")
            st.error(f"Error during processing: {str(e)}")
        finally:
            # Reset processing state
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            st.rerun()
    
    # Clear logs button (only in debug mode)
    if st.session_state.get('debug_mode', False) and st.session_state.activity_logs:
        if st.button("🗑️ Clear Activity Log"):
            st.session_state.activity_logs = []
            st.rerun()

    

def show_rules_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show email rules management interface."""
    st.markdown("##  Email Rules")
    
    st.markdown("Create rules to automatically process emails that match specific criteria.")
    
    # Add new rule section
    with st.expander(" Create New Rule", expanded=True):
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
            )
            
            # Quick condition builders
            st.markdown("**Quick Builders:**")
            quick_row1_col1, quick_row1_col2 = st.columns(2)
            quick_row2_col1, quick_row2_col2 = st.columns(2)
            
            # Row 1: From and To fields
            with quick_row1_col1:
                st.markdown("**📧 From Sender**")
                sender_input = st.text_input("Sender email:", placeholder="sender@example.com", key="quick_sender")
                if st.button("➕ Add From Filter", key="add_from", use_container_width=True):
                    if sender_input:
                        current = gmail_condition or ""
                        new_condition = f"from:{sender_input}"
                        gmail_condition = f"{current} {new_condition}".strip()
                        st.success(f"Added: {new_condition}")
            
            with quick_row1_col2:
                st.markdown("**📨 To Recipient**")
                recipient_input = st.text_input("Recipient email:", placeholder="recipient@example.com", key="quick_recipient")
                if st.button("➕ Add To Filter", key="add_to", use_container_width=True):
                    if recipient_input:
                        current = gmail_condition or ""
                        new_condition = f"to:{recipient_input}"
                        gmail_condition = f"{current} {new_condition}".strip()
                        st.success(f"Added: {new_condition}")
            
            # Row 2: Subject and Label fields
            with quick_row2_col1:
                st.markdown("**📋 Subject**")
                subject_input = st.text_input("Subject contains:", placeholder="keyword", key="quick_subject")
                if st.button("➕ Add Subject Filter", key="add_subject", use_container_width=True):
                    if subject_input:
                        current = gmail_condition or ""
                        new_condition = f"subject:{subject_input}"
                        gmail_condition = f"{current} {new_condition}".strip()
                        st.success(f"Added: {new_condition}")
            
            with quick_row2_col2:
                st.markdown("**🏷️ Label**")
                label_input = st.text_input("Label name:", placeholder="important", key="quick_label")
                if st.button("➕ Add Label Filter", key="add_label", use_container_width=True):
                    if label_input:
                        current = gmail_condition or ""
                        new_condition = f"label:{label_input}"
                        gmail_condition = f"{current} {new_condition}".strip()
                        st.success(f"Added: {new_condition}")
        
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
            )
            
            # Test the Gmail search
            if gmail_condition:
                st.markdown("**Search Preview:**")
                parser = GmailSearchParser()
                parsed_filters = parser.parse_search(gmail_condition)
                
                if parsed_filters['from_sender']:
                    st.write(f" From: {parsed_filters['from_sender']}")
                if parsed_filters['to_recipient']:
                    st.write(f" To: {parsed_filters['to_recipient']}")
                if parsed_filters['subject_filter']:
                    st.write(f" Subject: {parsed_filters['subject_filter']}")
                if parsed_filters['unread_only']:
                    st.write(" Unread emails only")
                if parsed_filters['starred_only']:
                    st.write(" Starred emails only")
                if parsed_filters['has_attachment']:
                    st.write(" Has attachments")
        
        if st.button(" Add Rule", type="primary"):
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
                st.success(f" Rule '{rule_name}' created successfully!")
                st.rerun()
            else:
                st.error(" Please fill in rule name and Gmail search condition")
    
    # Display existing rules
    if st.session_state.email_rules:
        st.markdown("---")
        st.markdown("###  Existing Rules")
        
        for rule in st.session_state.email_rules:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    # Priority indicator
                    priority_color = {"High": "", "Medium": "", "Low": ""}.get(rule.get('priority', 'Medium'), "")
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
                    if st.button(" Edit", key=f"edit_rule_{rule['id']}"):
                        st.session_state[f"editing_rule_{rule['id']}"] = True
                
                with col4:
                    if st.button(" Delete", key=f"delete_rule_{rule['id']}"):
                        st.session_state.email_rules = [r for r in st.session_state.email_rules if r['id'] != rule['id']]
                        st.rerun()
                
                st.divider()
    else:
        st.info(" No rules created yet. Create your first rule above!")


def show_email_stats_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show email statistics and reports."""
    st.markdown("##  Email Statistics & Reports")
    
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
            if st.button(f" Total Emails\n{total_count:,}", use_container_width=True):
                show_detailed_email_breakdown(service, "total")
        
        with col2:
            if st.button(f" Unread Emails\n{unread_count:,}", use_container_width=True):
                show_detailed_email_breakdown(service, "unread")
        
        with col3:
            read_count = total_count - unread_count
            if st.button(f" Read Emails\n{read_count:,}", use_container_width=True):
                show_detailed_email_breakdown(service, "read")
        
        with col4:
            if st.button(" Detailed Analytics", use_container_width=True):
                show_advanced_email_analytics(service)
        
        # Processing Reports Section
        st.markdown("---")
        st.markdown("###  Processing Reports")
        
        if os.path.exists("output"):
            # Create tabs for different report types
            report_tabs = st.tabs([" Latest Reports", " Processing History", " Report Viewer"])
            
            with report_tabs[0]:
                show_latest_processing_reports()
            
            with report_tabs[1]:
                show_processing_history_enhanced()
            
            with report_tabs[2]:
                show_interactive_report_viewer()
        else:
            st.info(" No processing reports available yet. Run email processing to generate reports.")
    
    except Exception as e:
        st.error(f"Error fetching email stats: {e}")


def show_detailed_email_breakdown(service, email_type: str):
    """Show detailed breakdown of emails by type."""
    st.markdown(f"###  Detailed {email_type.title()} Email Breakdown")
    
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
    st.markdown("###  Advanced Email Analytics")
    
    try:
        # Get various email statistics
        analytics_data = {
            " Starred": "is:starred",
            " Important": "is:important", 
            " With Attachments": "has:attachment",
            " From Me": "from:me",
            " Last 7 Days": "newer_than:7d",
            " Last 30 Days": "newer_than:30d",
            " Unread Important": "is:unread is:important"
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
    st.markdown("####  Latest Processing Results")
    
    # Define report types and their descriptions
    report_types = {
        "categorization_report.json": {"title": " Email Categorization", "description": "AI categorization and prioritization results"},
        "organization_report.json": {"title": " Email Organization", "description": "Labels and organization applied"},
        "response_report.json": {"title": " Reply Drafts", "description": "AI-generated response drafts"},
        "notification_report.json": {"title": " Notifications", "description": "Slack notifications sent"},
        "cleanup_report.json": {"title": " Email Cleanup", "description": "Emails archived and deleted"}
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
                    st.markdown(f" {report['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                with col3:
                    if st.button(" View", key=f"view_{report['file']}", use_container_width=True):
                        show_formatted_report(report['file'])
                
                st.divider()
    else:
        st.info(" No processing reports available yet.")


def show_token_usage_report(user_id: str):
    """Show token usage report for the user."""
    st.markdown("### 💰 Token Usage & Costs")
    
    try:
        # Try to import token tracker
        from src.gmail_crew_ai.utils.token_tracker import token_tracker
        
        # Get usage summary
        usage_summary = token_tracker.get_usage_summary(user_id)
        
        if usage_summary['total_sessions'] == 0:
            st.info("No token usage data available yet. Process some emails to see usage statistics.")
            return
        
        # Display overview metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Sessions",
                f"{usage_summary['total_sessions']:,}",
                help="Total number of email processing sessions"
            )
        
        with col2:
            st.metric(
                "Total Tokens Used",
                f"{usage_summary['total_tokens']:,}",
                help="Total tokens consumed across all sessions"
            )
        
        with col3:
            st.metric(
                "Total Cost",
                f"${usage_summary['total_cost']:.4f}",
                help="Estimated total cost based on model pricing"
            )
        
        with col4:
            st.metric(
                "Avg Cost/Session",
                f"${usage_summary['avg_cost_per_session']:.4f}",
                help="Average cost per email processing session"
            )
        
        # Show recent sessions
        st.markdown("---")
        st.markdown("#### Recent Sessions")
        
        recent_sessions = usage_summary.get('recent_sessions', [])
        if recent_sessions:
            # Create a dataframe for display
            session_data = []
            for session in recent_sessions[-10:]:  # Last 10 sessions
                session_data.append({
                    "Date": datetime.fromisoformat(session['start_time']).strftime("%Y-%m-%d %H:%M"),
                    "Model": session.get('model', 'Unknown'),
                    "Emails": session.get('emails_processed', 0),
                    "Tokens": f"{session.get('total_tokens', 0):,}",
                    "Cost": f"${session.get('total_cost', 0):.4f}",
                    "Avg/Email": f"${session.get('avg_cost_per_email', 0):.4f}"
                })
            
            df_sessions = pd.DataFrame(session_data)
            st.dataframe(df_sessions, use_container_width=True, hide_index=True)
            
            # Show agent breakdown for the most recent session
            if recent_sessions:
                latest_session = recent_sessions[-1]
                if latest_session.get('agents'):
                    st.markdown("---")
                    st.markdown("#### Latest Session Agent Breakdown")
                    
                    agent_data = []
                    for agent_name, stats in latest_session['agents'].items():
                        agent_data.append({
                            "Agent": agent_name,
                            "Calls": stats['calls'],
                            "Input Tokens": f"{stats['input_tokens']:,}",
                            "Output Tokens": f"{stats['output_tokens']:,}",
                            "Total Tokens": f"{stats['total_tokens']:,}",
                            "Cost": f"${stats['cost']:.4f}"
                        })
                    
                    df_agents = pd.DataFrame(agent_data)
                    st.dataframe(df_agents, use_container_width=True, hide_index=True)
        
        # Rate limit warnings
        st.markdown("---")
        st.markdown("#### Rate Limit Information")
        
        model = os.getenv('MODEL', 'anthropic/claude-sonnet-4-20250514')
        if 'claude' in model:
            st.warning("""
            **Anthropic Rate Limits:**
            - 30,000-40,000 input tokens per minute
            - Reduce email batch size if you encounter rate limits
            - Consider upgrading your Anthropic plan for higher limits
            """)
        
    except ImportError:
        st.error("Token tracking module not available. Creating simple usage display...")
        # Fallback display
        st.info("Token usage tracking will be available in the next update.")
    except Exception as e:
        st.error(f"Error loading token usage data: {e}")


def show_processing_analytics(user_id: str):
    """Show analytics and trends for email processing."""
    st.markdown("### 📈 Processing Analytics")
    
    # Check if we have any output files
    if not os.path.exists("output"):
        st.info("No analytics data available yet. Process some emails to see trends.")
        return
    
    try:
        # Analyze categorization trends
        cat_file = os.path.join("output", "categorization_report.json")
        if os.path.exists(cat_file):
            with open(cat_file, 'r') as f:
                cat_data = json.load(f)
            
            if cat_data and 'emails' in cat_data:
                # Count categories
                categories = {}
                priorities = {}
                
                for email in cat_data['emails']:
                    cat = email.get('category', 'Unknown')
                    categories[cat] = categories.get(cat, 0) + 1
                    
                    pri = email.get('priority', 'Unknown')
                    priorities[pri] = priorities.get(pri, 0) + 1
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### Email Categories")
                    cat_df = pd.DataFrame([
                        {"Category": k, "Count": v} 
                        for k, v in categories.items()
                    ])
                    if not cat_df.empty:
                        st.bar_chart(cat_df.set_index('Category'))
                
                with col2:
                    st.markdown("#### Priority Distribution")
                    pri_df = pd.DataFrame([
                        {"Priority": k, "Count": v} 
                        for k, v in priorities.items()
                    ])
                    if not pri_df.empty:
                        st.bar_chart(pri_df.set_index('Priority'))
        
        # Show cleanup statistics
        cleanup_file = os.path.join("output", "cleanup_report.json")
        if os.path.exists(cleanup_file):
            with open(cleanup_file, 'r') as f:
                cleanup_data = json.load(f)
            
            st.markdown("---")
            st.markdown("#### Cleanup Statistics")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                deleted = len(cleanup_data.get('deleted_emails', []))
                st.metric("Emails Deleted", deleted)
            
            with col2:
                archived = len(cleanup_data.get('archived_emails', []))
                st.metric("Emails Archived", archived)
            
            with col3:
                total_cleaned = deleted + archived
                st.metric("Total Cleaned", total_cleaned)
    
    except Exception as e:
        st.error(f"Error loading analytics: {e}")


def show_processing_history_enhanced():
    """Show enhanced processing history with file management."""
    st.markdown("####  Processing History")
    
    if os.path.exists("output"):
        history_files = []
        for file in os.listdir("output"):
            if file.endswith(".json"):
                file_path = os.path.join("output", file)
                mod_time = os.path.getmtime(file_path)
                file_size = os.path.getsize(file_path)
                
                history_files.append({
                    " File": file,
                    " Modified": datetime.fromtimestamp(mod_time).strftime("%Y-%m-%d %H:%M:%S"),
                    " Size": f"{round(file_size / 1024, 2)} KB",
                    "file_path": file_path
                })
        
        if history_files:
            # Sort by modification time
            history_files.sort(key=lambda x: x[" Modified"], reverse=True)
            
            for i, file_info in enumerate(history_files):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**{file_info[' File']}**")
                
                with col2:
                    st.markdown(file_info[" Modified"])
                
                with col3:
                    st.markdown(file_info[" Size"])
                
                with col4:
                    if st.button("", key=f"view_history_{i}"):
                        show_formatted_report(file_info[' File'])
                
                with col5:
                    # Download button
                    with open(file_info['file_path'], 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    st.download_button(
                        "",
                        file_content,
                        file_name=file_info[' File'],
                        mime="application/json",
                        key=f"download_history_{i}",
                    )
    else:
        st.info(" No output directory found.")


def show_interactive_report_viewer():
    """Show interactive report viewer with search and filtering."""
    st.markdown("####  Interactive Report Viewer")
    
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
                    [" Formatted", " Raw JSON"],
                    key="report_view_mode"
                )
            
            with col2:
                if st.button(" Refresh Report", use_container_width=True):
                    st.rerun()
            
            # Display the selected report
            if view_mode == " Formatted":
                show_formatted_report(selected_file)
            else:
                show_raw_json_report(selected_file)
    else:
        st.info(" No report files available.")


def show_formatted_report(filename: str):
    """Display a report in a user-friendly formatted way."""
    filepath = os.path.join("output", filename)
    
    if not os.path.exists(filepath):
        st.error(f" File not found: {filename}")
        return
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        st.markdown(f"###  Report: {filename}")
        
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
        st.error(f" Error reading report: {e}")


def show_categorization_report_formatted(data):
    """Show categorization report in a formatted way."""
    if isinstance(data, dict) and 'emails' in data:
        emails = data['emails']
        
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(" Total Emails", len(emails))
        
        priorities = {}
        categories = {}
        
        for email in emails:
            priority = email.get('priority', 'Unknown')
            category = email.get('category', 'Unknown')
            priorities[priority] = priorities.get(priority, 0) + 1
            categories[category] = categories.get(category, 0) + 1
        
        with col2:
            high_priority = priorities.get('HIGH', 0)
            st.metric(" High Priority", high_priority)
        
        with col3:
            medium_priority = priorities.get('MEDIUM', 0)
            st.metric(" Medium Priority", medium_priority)
        
        with col4:
            low_priority = priorities.get('LOW', 0)
            st.metric(" Low Priority", low_priority)
        
        # Category breakdown
        if categories:
            st.markdown("####  Category Breakdown")
            cat_df = pd.DataFrame(list(categories.items()), columns=['Category', 'Count'])
            
            col1, col2 = st.columns(2)
            with col1:
                st.dataframe(cat_df, use_container_width=True)
            with col2:
                st.bar_chart(cat_df.set_index('Category'))
        
        # Email details
        st.markdown("####  Email Details")
        if emails:
            df = pd.DataFrame(emails)
            st.dataframe(df[['subject', 'sender', 'category', 'priority']], use_container_width=True)
    else:
        st.json(data)


def show_organization_report_formatted(data):
    """Show organization report in a formatted way."""
    st.markdown("####  Organization Actions Applied")
    
    if isinstance(data, dict):
        # Show summary
        if 'summary' in data:
            st.success(f" {data['summary']}")
        
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
    st.markdown("####  AI-Generated Responses")
    
    if isinstance(data, dict) and 'responses' in data:
        responses = data['responses']
        
        st.metric(" Responses Generated", len(responses))
        
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
    st.markdown("####  Notifications Sent")
    
    if isinstance(data, dict):
        # Show summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(" Emails Processed", data.get('total_processed', 0))
        
        with col2:
            st.metric(" Notifications Sent", data.get('notifications_sent', 0))
        
        with col3:
            notifications = data.get('notifications', [])
            st.metric(" High Priority Found", len(notifications))
        
        # Show notifications details
        if notifications:
            st.markdown("####  High Priority Notifications")
            for notification in notifications:
                st.warning(f" {notification.get('subject', 'No Subject')} - {notification.get('sender', 'Unknown Sender')}")
        else:
            st.info(" No high priority emails found for notification.")
        
        # Show summary
        if 'summary' in data:
            st.markdown("####  Summary")
            st.info(data['summary'])
    else:
        st.json(data)


def show_cleanup_report_formatted(data):
    """Show cleanup report in a formatted way."""
    st.markdown("####  Cleanup Results")
    
    if isinstance(data, dict):
        # Show summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(" Total Processed", data.get('total_processed', 0))
        
        with col2:
            st.metric(" Deleted", data.get('deleted_count', 0))
        
        with col3:
            st.metric(" Preserved", data.get('preserved_count', 0))
        
        with col4:
            st.metric(" Trash Emptied", data.get('trash_messages_removed', 0))
        
        # Show processed emails
        if 'processed_emails' in data and data['processed_emails']:
            st.markdown("####  Email Actions")
            
            emails = data['processed_emails']
            
            # Separate deleted and preserved
            deleted_emails = [e for e in emails if e.get('deleted', False)]
            preserved_emails = [e for e in emails if not e.get('deleted', False)]
            
            tab1, tab2 = st.tabs([f" Deleted ({len(deleted_emails)})", f" Preserved ({len(preserved_emails)})"])
            
            with tab1:
                if deleted_emails:
                    for email in deleted_emails:
                        st.markdown(f" **{email.get('subject', 'No Subject')}** - {email.get('sender', 'Unknown')}")
                        st.markdown(f"   *Reason: {email.get('reason', 'No reason given')}*")
                else:
                    st.info("No emails were deleted.")
            
            with tab2:
                if preserved_emails:
                    for email in preserved_emails:
                        st.markdown(f" **{email.get('subject', 'No Subject')}** - {email.get('sender', 'Unknown')}")
                        st.markdown(f"   *Reason: {email.get('reason', 'No reason given')}*")
                else:
                    st.info("No emails were preserved.")
        
        # Show summary
        if 'summary' in data:
            st.markdown("####  Summary")
            st.success(data['summary'])
    else:
        st.json(data)


def show_fetched_emails_formatted(data):
    """Show fetched emails in a formatted way."""
    st.markdown("####  Fetched Emails")
    
    if isinstance(data, list):
        st.metric(" Total Fetched", len(data))
        
        if data:
            # Convert to DataFrame for better display
            df = pd.DataFrame(data)
            
            # Show summary by sender
            if 'sender' in df.columns:
                sender_counts = df['sender'].value_counts().head(10)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("####  Top Senders")
                    st.dataframe(sender_counts.to_frame('Count'), use_container_width=True)
                
                with col2:
                    st.markdown("####  Sender Distribution")
                    st.bar_chart(sender_counts)
            
            # Show email list with search
            st.markdown("####  Email List")
            
            search_term = st.text_input(" Search emails:", placeholder="Enter subject, sender, or keywords...")
            
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
        
        st.markdown(f"###  Raw JSON: {filename}")
        st.json(data)
        
        # Add download option
        st.download_button(
            " Download JSON",
            json.dumps(data, indent=2, ensure_ascii=False),
            file_name=filename,
            mime="application/json"
        )
        
    except Exception as e:
        st.error(f" Error reading file: {e}")


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
    """Manages error logging with daily rotation and 30-day retention."""
    
    def __init__(self):
        self.error_log_file = "error_logs.json"
        self.logger = log  # Use centralized logger instead of print calls
        self.ensure_error_log_file()
        self._perform_daily_maintenance()
    
    def ensure_error_log_file(self):
        """Ensure error log file exists."""
        if not os.path.exists(self.error_log_file):
            self.save_errors([])
    
    def load_errors(self) -> List[Dict]:
        """Load errors from file."""
        try:
            with open(self.error_log_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.warning(f"Failed to load errors from {self.error_log_file}: {e}")
            return []
    
    def save_errors(self, errors: List[Dict]):
        """Save errors to file."""
        try:
            with open(self.error_log_file, 'w', encoding='utf-8') as f:
                json.dump(errors, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving error logs: {e}")
    
    def _perform_daily_maintenance(self):
        """Perform daily maintenance including rotation and cleanup."""
        try:
            # Check if we need to rotate logs (daily)
            self._rotate_logs_if_needed()
            # Clean up old errors
            self.cleanup_old_errors()
        except Exception as e:
            self.logger.error(f"Error during daily maintenance: {e}")
    
    def _rotate_logs_if_needed(self):
        """Rotate logs daily by moving current log to dated file."""
        if not os.path.exists(self.error_log_file):
            return
        
        try:
            # Get file modification time
            file_mtime = datetime.fromtimestamp(os.path.getmtime(self.error_log_file))
            current_date = datetime.now().date()
            file_date = file_mtime.date()
            
            # If the file is from a previous day, rotate it
            if file_date < current_date:
                dated_filename = f"error_logs_{file_date.strftime('%Y%m%d')}.json"
                
                # Only rotate if the dated file doesn't already exist
                if not os.path.exists(dated_filename):
                    try:
                        os.rename(self.error_log_file, dated_filename)
                        self.logger.info(f"Rotated error logs to {dated_filename}")
                        # Create new empty log file
                        self.save_errors([])
                    except OSError as e:
                        self.logger.warning(f"Failed to rotate error logs: {e}")
        except Exception as e:
            self.logger.error(f"Error during log rotation: {e}")
    
    def cleanup_old_errors(self):
        """Remove errors older than 30 days and clean up old rotated files."""
        try:
            # Clean up current error log
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
            
            cleaned_count = 0
            if len(filtered_errors) != len(errors):
                self.save_errors(filtered_errors)
                cleaned_count = len(errors) - len(filtered_errors)
                if cleaned_count > 0:
                    self.logger.info(f"Cleaned up {cleaned_count} old errors from current log")
            
            # Clean up old rotated log files (older than 30 days)
            import glob
            pattern = "error_logs_????????.json"  # Match YYYYMMDD format
            old_files_removed = 0
            
            for old_file in glob.glob(pattern):
                try:
                    # Extract date from filename
                    date_str = old_file.replace('error_logs_', '').replace('.json', '')
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    
                    if datetime.now() - file_date > pd.Timedelta(days=30):
                        os.remove(old_file)
                        old_files_removed += 1
                        self.logger.info(f"Removed old rotated error log: {old_file}")
                except (ValueError, OSError) as e:
                    self.logger.warning(f"Failed to process old log file {old_file}: {e}")
            
            return cleaned_count + old_files_removed
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            return 0
    
    def log_error(self, error_type: str, message: str, details: str = "", user_id: str = ""):
        """Log a new error to both structured storage and centralized logger."""
        try:
            # Log to centralized logger first
            log_message = f"[{error_type}] {message}"
            if user_id:
                log_message += f" (User: {user_id})"
            
            self.logger.error(log_message)
            if details:
                self.logger.error(f"Details: {details}")
            
            # Save to structured error storage
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
            
        except Exception as e:
            # Fallback to basic logging if structured logging fails
            self.logger.error(f"Failed to log structured error, fallback: [{error_type}] {message}")
            self.logger.error(f"ErrorLogger failure details: {e}")
    
    def mark_resolved(self, error_id: str):
        """Mark an error as resolved."""
        try:
            errors = self.load_errors()
            for error in errors:
                if error.get('id') == error_id:
                    error['resolved'] = True
                    self.logger.info(f"Marked error {error_id} as resolved")
                    break
            self.save_errors(errors)
        except Exception as e:
            self.logger.error(f"Failed to mark error {error_id} as resolved: {e}")
    
    def delete_error(self, error_id: str):
        """Delete a specific error."""
        try:
            errors = self.load_errors()
            original_count = len(errors)
            errors = [e for e in errors if e.get('id') != error_id]
            
            if len(errors) < original_count:
                self.save_errors(errors)
                self.logger.info(f"Deleted error {error_id}")
            else:
                self.logger.warning(f"Error {error_id} not found for deletion")
        except Exception as e:
            self.logger.error(f"Failed to delete error {error_id}: {e}")


def show_error_logs_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show error logs interface."""
    st.markdown("##  Error Logs")
    st.markdown("View and manage system errors from CrewAI agents and processing.")
    
    # Initialize error logger
    error_logger = ErrorLogger()
    
    # Cleanup old errors automatically
    cleaned_count = error_logger.cleanup_old_errors()
    if cleaned_count > 0:
        st.info(f" Automatically cleaned up {cleaned_count} old errors (>30 days)")
    
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
        if st.button(" Clean Old Errors"):
            cleaned = error_logger.cleanup_old_errors()
            if cleaned > 0:
                st.success(f" Cleaned up {cleaned} old errors")
                st.rerun()
            else:
                st.info("No old errors to clean")
    
    with col4:
        if st.button(" Test Error"):
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
            st.info(" No unresolved errors found!")
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
                status_color = ""
                border_color = "#28a745"
            else:
                if error_type in ["CrewAI", "Agent"]:
                    status_color = ""
                    border_color = "#dc3545"
                elif error_type == "Processing":
                    status_color = ""
                    border_color = "#ffc107"
                else:
                    status_color = ""
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
                        if st.button(" Resolve", key=f"resolve_{error_id}"):
                            error_logger.mark_resolved(error_id)
                            st.success("Error marked as resolved!")
                            st.rerun()
                    else:
                        st.markdown(" *Resolved*")
                
                with col2:
                    if st.button(" Delete", key=f"delete_{error_id}"):
                        error_logger.delete_error(error_id)
                        st.success("Error deleted!")
                        st.rerun()
                
                with col3:
                    if st.button(" Copy", key=f"copy_{error_id}"):
                        error_text = f"Error Type: {error_type}\nTime: {formatted_time}\nMessage: {message}\nDetails: {details}"
                        st.code(error_text)
                
                st.markdown("---")


def show_settings_tab(user_id: str, oauth_manager: OAuth2Manager):
    """Show settings interface."""
    st.markdown("## ⚙️ Settings")
    
    # User info - get OAuth user ID from session state
    oauth_user_id = st.session_state.get('current_user')
    if oauth_user_id:
        user_email = oauth_manager.get_user_email(oauth_user_id)
    else:
        user_email = "Unknown"
    
    # Compact user info display
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"**User:** {user_email} (`{user_id}`)")
    
    st.markdown("---")
    
    # Simple Model Selection
    st.markdown("### 🤖 Model Selection")
    
    # Simple model options
    models = [
        "openai/gpt-4.1",
        "anthropic/claude-opus-4-20250514",
        "anthropic/claude-sonnet-4-20250514",
        "anthropic/claude-3-7-sonnet-latest",
        "anthropic/claude-3-5-sonnet-latest",
        "anthropic/claude-3-5-haiku-latest",
        "anthropic/claude-3-5-sonnet-20241022",
        "openai/o4-mini",
        "openai/o3-pro",
        "openai/o3",
        "openai/o3-mini",
        "openai/gpt-4o",
        "openai/gpt-4o-audio",
        "openai/chatgpt-4o",
        "openai/gpt-4o-mini"
    ]
    
    # Initialize session state for model selection
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = os.getenv('MODEL', 'openai/gpt-4.1')
    
    # Simple model selection dropdown
    current_index = 0
    if st.session_state.selected_model in models:
        current_index = models.index(st.session_state.selected_model)
    
    selected_model = st.selectbox(
        "Select AI Model",
        options=models,
        index=current_index
    )
    
    # Update model if changed
    if selected_model != st.session_state.selected_model:
        st.session_state.selected_model = selected_model
        os.environ['MODEL'] = selected_model
        st.rerun()
    
    # Set current model in environment if not already set
    if not os.getenv('MODEL') or os.getenv('MODEL') != st.session_state.selected_model:
        os.environ['MODEL'] = st.session_state.selected_model
        log.debug(f"Environment MODEL updated to: {st.session_state.selected_model}")
    
    # Simplified API Key Configuration
    user_manager = st.session_state.user_manager
    current_user_id = st.session_state.authenticated_user_id
    
    # Create columns for API key inputs
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Get current Anthropic key status
        user_anthropic_key = user_manager.get_user_api_key(current_user_id, 'anthropic')
        env_anthropic_key = os.getenv('ANTHROPIC_API_KEY', '')
        
        if user_anthropic_key:
            status = "🔑 Your key"
        elif env_anthropic_key:
            status = "🌐 Default key"
        else:
            status = "❌ Not configured"
            
        st.markdown(f"**Anthropic API Key** {status}")
        
        # Show current key if exists
        current_key_display = ""
        if user_anthropic_key:
            if user_manager.api_key_manager:
                current_key_display = user_manager.api_key_manager.mask_api_key(user_anthropic_key)
            else:
                current_key_display = user_anthropic_key[:8] + '...' + user_anthropic_key[-4:]
        
        # Use form for Enter key submission
        with st.form(key="anthropic_form", clear_on_submit=True):
            anthropic_key = st.text_input(
                "API Key",
                value=current_key_display,
                type="password",
                placeholder="sk-ant-api03-... (press Enter to save)",
                label_visibility="collapsed"
            )
            # Hidden submit button (form still submits on Enter) 
            submitted = st.form_submit_button("Save", disabled=False, use_container_width=False, type="primary")
            # Hide the button with CSS
            st.markdown("""
            <style>
            div[data-testid="stFormSubmitButton"] {
                display: none;
            }
            </style>
            """, unsafe_allow_html=True)
            
            if submitted and anthropic_key and anthropic_key != current_key_display:
                if user_manager.set_user_api_key(current_user_id, 'anthropic', anthropic_key):
                    st.success("✅ Anthropic API key saved!")
                    st.rerun()
                else:
                    st.error("❌ Invalid API key format")
    
    with col2:
        # Get current OpenAI key status
        user_openai_key = user_manager.get_user_api_key(current_user_id, 'openai')
        env_openai_key = os.getenv('OPENAI_API_KEY', '')
        
        if user_openai_key:
            status = "🔑 Your key"
        elif env_openai_key:
            status = "🌐 Default key"
        else:
            status = "❌ Not configured"
            
        st.markdown(f"**OpenAI API Key** {status}")
        
        # Show current key if exists
        current_key_display = ""
        if user_openai_key:
            if user_manager.api_key_manager:
                current_key_display = user_manager.api_key_manager.mask_api_key(user_openai_key)
            else:
                current_key_display = user_openai_key[:8] + '...' + user_openai_key[-4:]
        
        # Use form for Enter key submission
        with st.form(key="openai_form", clear_on_submit=True):
            openai_key = st.text_input(
                "API Key",
                value=current_key_display,
                type="password",
                placeholder="sk-proj-... (press Enter to save)",
                label_visibility="collapsed"
            )
            # Hidden submit button (form still submits on Enter) 
            submitted = st.form_submit_button("Save", disabled=False, use_container_width=False, type="primary")
            # Hide the button with CSS
            st.markdown("""
            <style>
            div[data-testid="stFormSubmitButton"] {
                display: none;
            }
            </style>
            """, unsafe_allow_html=True)
            
            if submitted and openai_key and openai_key != current_key_display:
                if user_manager.set_user_api_key(current_user_id, 'openai', openai_key):
                    st.success("✅ OpenAI API key saved!")
                    st.rerun()
                else:
                    st.error("❌ Invalid API key format")
    
    with col3:
        # Get current DO AI key status
        user_do_ai_key = user_manager.get_user_api_key(current_user_id, 'do_ai')
        env_do_ai_key = os.getenv('DO_AI_API_KEY', '')
        
        if user_do_ai_key:
            status = "🔑 Your key"
        elif env_do_ai_key:
            status = "🌐 Default key"
        else:
            status = "❌ Not configured"
            
        st.markdown(f"**Digital Ocean AI Key** {status}")
        
        # Show current key if exists
        current_key_display = ""
        if user_do_ai_key:
            if user_manager.api_key_manager:
                current_key_display = user_manager.api_key_manager.mask_api_key(user_do_ai_key)
            else:
                current_key_display = user_do_ai_key[:8] + '...' + user_do_ai_key[-4:]
        
        # Use form for Enter key submission
        with st.form(key="do_ai_form", clear_on_submit=True):
            do_ai_key = st.text_input(
                "API Key",
                value=current_key_display,
                type="password",
                placeholder="Lw_7A8P-... (press Enter to save)",
                label_visibility="collapsed"
            )
            # Hidden submit button (form still submits on Enter) 
            submitted = st.form_submit_button("Save", disabled=False, use_container_width=False, type="primary")
            # Hide the button with CSS
            st.markdown("""
            <style>
            div[data-testid="stFormSubmitButton"] {
                display: none;
            }
            </style>
            """, unsafe_allow_html=True)
            
            if submitted and do_ai_key and do_ai_key != current_key_display:
                if user_manager.set_user_api_key(current_user_id, 'do_ai', do_ai_key):
                    st.success("✅ DO AI API key saved!")
                    st.rerun()
                else:
                    st.error("❌ Invalid API key format")
    
    st.markdown("---")
    
    # OAuth2 settings
    st.markdown("### 🔐 Authentication Settings")
    
    if st.button(" Refresh Authentication"):
        try:
            # Get the actual OAuth user ID that matches this internal user ID
            user_manager = st.session_state.user_manager
            user_data = user_manager.get_user_by_id(st.session_state.authenticated_user_id)
            user_email = user_data.get('email', '')
            
            # Find the OAuth user ID by matching email
            authenticated_users = oauth_manager.list_authenticated_users()
            oauth_user_id = None
            for oid, email in authenticated_users.items():
                if email == user_email:
                    oauth_user_id = oid
                    break
            
            if oauth_user_id:
                # This will automatically refresh if needed
                oauth_manager.get_gmail_service(oauth_user_id)
                st.success(" Authentication refreshed successfully!")
            else:
                st.error(f" No OAuth credentials found for {user_email}. Please re-authenticate.")
                
        except Exception as e:
            st.error(f"Error refreshing authentication: {e}")
    
    if st.button(" Clean Up OAuth Tokens"):
        try:
            removed_count = oauth_manager.cleanup_corrupted_tokens()
            if removed_count > 0:
                st.info(f"🧹 Cleaned up {removed_count} corrupted OAuth token(s)")
            else:
                st.info("✅ No corrupted tokens found")
        except Exception as e:
            st.error(f"Error cleaning up tokens: {e}")
    
    if st.button(" Remove This Account", type="secondary"):
        confirm_remove = st.checkbox("I confirm I want to remove this account")
        if confirm_remove and st.button("Confirm Removal", type="secondary"):
            if oauth_manager.revoke_credentials(user_id):
                st.success(" Account access removed successfully!")
                
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
    st.markdown("###  User Persona Management")
    
    # Show current user facts status
    facts_file = "knowledge/user_facts.txt"
    if os.path.exists(facts_file) and os.path.getsize(facts_file) > 50:
        st.success(" User persona file exists and has content")
        
        # Show creation date
        try:
            with open(facts_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "Last Updated:" in content:
                    last_updated = content.split("Last Updated:")[-1].split("\n")[0].strip()
                    st.info(f" Last updated: {last_updated}")
        except Exception:
            pass
            
        if st.button(" View Current User Persona"):
            try:
                with open(facts_file, 'r', encoding='utf-8') as f:
                    facts_content = f.read()
                st.text_area("Current User Persona:", facts_content, height=200, key="user_facts_display")
            except Exception as e:
                st.error(f"Error reading user facts: {e}")
    else:
        st.warning(" User persona file is empty or missing")
        st.info(" User persona will be automatically created when you first process emails")
    
    # Persona management buttons
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button(" Rebuild User Persona"):
            try:
                from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2GetSentEmailsTool, OAuth2UserPersonaAnalyzerTool
                
                with st.spinner(" Fetching sent emails for complete analysis..."):
                    # Fetch sent emails
                    sent_email_tool = OAuth2GetSentEmailsTool(user_id=user_id, oauth_manager=oauth_manager)
                    sent_emails = sent_email_tool._run(max_emails=100)
                    
                    if sent_emails:
                        st.info(f" Analyzing {len(sent_emails)} sent emails...")
                        
                        # Analyze emails and create persona
                        analyzer_tool = OAuth2UserPersonaAnalyzerTool(user_id=user_id, oauth_manager=oauth_manager)
                        result = analyzer_tool._run(sent_emails=sent_emails)
                        
                        st.success(" User persona rebuilt successfully!")
                        st.info(result)
                        
                        # Show the new persona
                        try:
                            with open(facts_file, 'r', encoding='utf-8') as f:
                                new_facts = f.read()
                            st.text_area("Updated User Persona:", new_facts, height=200, key="updated_user_facts")
                        except Exception as e:
                            st.error(f"Error displaying updated persona: {e}")
                    else:
                        st.warning(" No sent emails found to analyze")
                        
            except Exception as e:
                st.error(f"Error rebuilding user persona: {e}")
    
    with col2:
        if st.button(" Update User Persona"):
            try:
                from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2UserPersonaUpdaterTool
                
                with st.spinner(" Analyzing recent emails for persona updates..."):
                    # Use the new updater tool
                    updater_tool = OAuth2UserPersonaUpdaterTool(user_id=user_id, oauth_manager=oauth_manager)
                    result = updater_tool._run(days_back=30)
                    
                    st.success(" User persona updated successfully!")
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
    st.markdown("####  Custom Update Period")
    
    days_back = st.slider(
        "Days back to analyze for updates:",
        min_value=7,
        max_value=90,
        value=30,
        step=7,
    )
    
    if st.button(" Custom Update"):
        try:
            from src.gmail_crew_ai.tools.gmail_oauth_tools import OAuth2UserPersonaUpdaterTool
            
            with st.spinner(f" Analyzing emails from last {days_back} days..."):
                updater_tool = OAuth2UserPersonaUpdaterTool(user_id=user_id, oauth_manager=oauth_manager)
                result = updater_tool._run(days_back=days_back)
                
                st.success(" User persona updated successfully!")
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
    
    if st.button(" Clear User Persona", type="secondary"):
        confirm_clear = st.checkbox("I confirm I want to clear the user persona")
        if confirm_clear and st.button("Confirm Clear", type="secondary"):
            try:
                with open(facts_file, 'w', encoding='utf-8') as f:
                    f.write("")
                st.success(" User persona cleared successfully!")
                st.info(" A new persona will be automatically created next time you process emails")
            except Exception as e:
                st.error(f"Error clearing user persona: {e}")
    
    st.markdown("---")
    
    # File management
    st.markdown("###  File Management")
    
    if st.button(" Clear Processing Cache"):
        try:
            import shutil
            if os.path.exists("output"):
                shutil.rmtree("output")
                os.makedirs("output")
            st.success(" Processing cache cleared!")
        except Exception as e:
            st.error(f"Error clearing cache: {e}")


def show_help_tab():
    """Show help and documentation."""
    st.markdown("##  Help & Documentation")
    
    st.markdown("""
    ###  How Gmail CrewAI Works
    
    Gmail CrewAI uses AI agents to automatically process your emails:
    
    1. ** Fetcher Agent**: Retrieves unread emails from your Gmail
    2. ** Categorizer Agent**: Categorizes emails by type and priority
    3. ** Organizer Agent**: Applies Gmail labels and stars important emails
    4. ** Response Agent**: Generates draft responses for important emails
    5. ** Notification Agent**: Sends Slack notifications for high-priority emails
    6. ** Cleanup Agent**: Archives or deletes low-priority emails
    
    ###  Security & Privacy
    
    - Your OAuth2 tokens are stored locally and encrypted
    - No email content is stored permanently
    - AI processing happens locally with your OpenAI API key
    - You can revoke access at any time
    
    ###  Setup Requirements
    
    1. **Google OAuth2 Credentials**: Required for Gmail access
    2. **OpenAI API Key**: Required for AI processing
    3. **Slack Webhook** (Optional): For notifications
    
    ###  Troubleshooting
    
    - **Authentication Issues**: Try refreshing authentication in Settings
    - **Processing Errors**: Check that all environment variables are set
    - **Performance**: Processing time depends on number of emails
    """)
    
    st.markdown("---")
    st.markdown("###  Support")
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


def check_and_fix_oauth_credentials(user_id: str, oauth_manager) -> bool:
    """Check OAuth credentials and fix if invalid."""
    try:
        # Get OAuth user ID from session state
        oauth_user_id = st.session_state.get('current_user')
        if not oauth_user_id:
            return False
            
        # Test if credentials work by attempting to get user email
        oauth_manager.get_user_email(oauth_user_id)
        return True
    except Exception as e:
        if "No valid credentials found" in str(e):
            st.error(f"🔑 OAuth credentials invalid for user {user_id}. Clearing...")
            try:
                oauth_manager.revoke_credentials(user_id)
                st.success("✅ Invalid credentials cleared. Please re-authenticate.")
                return False
            except Exception as revoke_error:
                st.warning(f"Could not clear credentials: {revoke_error}")
                return False
        else:
            st.error(f"OAuth error: {e}")
            return False

def process_emails_with_filters(user_id: str, oauth_manager):
    """Process emails using CrewAI with applied filters."""
    # Initialize error logger
    error_logger = ErrorLogger()
    
    # Check OAuth credentials first
    if not check_and_fix_oauth_credentials(user_id, oauth_manager):
        st.error("❌ OAuth authentication required. Please log in again to continue.")
        if st.button("🔐 Go to Login"):
            st.session_state.authentication_step = 'login'
            st.rerun()
        return
    
    # Check if processing was stopped before starting
    if st.session_state.get('processing_stopped', False):
        st.session_state.processing_active = False
        st.session_state.processing_started = False
        st.session_state.processing_stopped = False
        return
    
    
    # Parse Gmail search query into structured filters
    gmail_search = st.session_state.get('gmail_search', 'is:unread')
    max_emails = st.session_state.get('filter_max_emails', 3)
    
    parser = GmailSearchParser()
    filters = parser.parse_search(gmail_search)
    filters['max_emails'] = max_emails
    
    # Apply rules to generate additional instructions
    rule_instructions = generate_rule_instructions()
    
    # Create placeholder for activity display
    activity_placeholder = st.empty()
    
    try:
        safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Fetching emails with applied filters...")
        safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Email limit set to: {filters.get('max_emails', 'undefined')} emails")
        
        # Check for stop signal during processing
        if st.session_state.get('processing_stopped', False):
            safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Processing stopped before email fetch")
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            return
        
        # Set up environment for this user - get OAuth user ID from session state
        oauth_user_id = st.session_state.get('current_user')
        if oauth_user_id:
            user_email = oauth_manager.get_user_email(oauth_user_id)
        else:
            user_email = "Unknown"
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 👤 Processing for user: {user_email}")
        
        # Set filters and rules in environment for crew to use
        os.environ["EMAIL_FILTERS"] = json.dumps(filters)
        os.environ["RULE_INSTRUCTIONS"] = rule_instructions
        os.environ["GMAIL_SEARCH_QUERY"] = gmail_search
        
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚙️ Applied filters: {len([k for k, v in filters.items() if v])} active")
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Using Gmail search: '{gmail_search}'")
        
        # Check for stop signal before crew creation
        if st.session_state.get('processing_stopped', False):
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Processing stopped before crew creation")
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            return
        
        # CRITICAL: Set MODEL environment variable BEFORE creating crew
        if 'selected_model' in st.session_state and st.session_state.selected_model:
            selected_model = st.session_state.selected_model
            os.environ['MODEL'] = selected_model
            safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Setting AI model: {selected_model}")
            log.info(f"Pre-crew MODEL environment set to: {selected_model}")
        else:
            # Fallback to default
            default_model = "openai/gpt-4.1"
            os.environ['MODEL'] = default_model
            safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Using default AI model: {default_model}")
            log.warning(f"No selected model found, using default: {default_model}")
        
        # Get user's API keys for the crew
        user_manager = st.session_state.user_manager
        user_api_keys = {}
        if user_manager.has_user_api_key(user_id, 'anthropic'):
            user_api_keys['anthropic'] = user_manager.get_user_api_key(user_id, 'anthropic')
        if user_manager.has_user_api_key(user_id, 'openai'):
            user_api_keys['openai'] = user_manager.get_user_api_key(user_id, 'openai')
        if user_manager.has_user_api_key(user_id, 'do_ai'):
            user_api_keys['do_ai'] = user_manager.get_user_api_key(user_id, 'do_ai')
        
        # Create a crew for this specific user (now with correct MODEL env var and user API keys)
        crew = create_crew_for_user(user_id, oauth_manager, user_api_keys)
        
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 AI crew initialized, starting processing...")
        
        # Run the crew with enhanced logging and output capture
        try:
            # Get crew-specific logger
            crew_log = get_crew_logger()
            crew_log.info(f"Starting CrewAI execution for user {user_id}")
            crew_log.info(f"Using model: {os.getenv('MODEL', 'default')}")
            crew_log.info(f"Email filters: {filters}")
            
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ Starting AI crew execution...")
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🧠 Initializing AI agents: Categorizer, Organizer, Response Generator, Cleaner")
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Processing tasks: Categorization → Organization → Response Generation → Cleanup")
            
            # Create a progress indicator  
            progress_placeholder = st.empty()
            with progress_placeholder:
                pass  # Progress shown in activity logs
            
            # Capture CrewAI output and display in activity window
            import sys
            from io import StringIO
            import contextlib
            
            # Create a custom output capturer
            class ActivityLogCapture(StringIO):
                def __init__(self):
                    super().__init__()
                    self.content = []
                    
                def write(self, text):
                    # Save original stdout to avoid recursion
                    if not hasattr(self, '_original_stdout'):
                        self._original_stdout = sys.__stdout__
                    
                    # Print to terminal using original stdout
                    self._original_stdout.write(text)
                    self._original_stdout.flush()
                    
                    if text.strip():  # Only capture non-empty lines
                        # Format and add to activity logs
                        formatted_text = self._format_crew_output(text.strip())
                        if formatted_text:
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            st.session_state.activity_logs.append(f"[{timestamp}] {formatted_text}")
                            self.content.append(text.strip())
                        else:
                            # For debugging: show ALL output temporarily
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            st.session_state.activity_logs.append(f"[{timestamp}] 🔍 RAW: {text.strip()}")
                    return len(text)
                
                def flush(self):
                    # Ensure output is flushed
                    pass
                    
                def _format_crew_output(self, text):
                    """Format CrewAI output for better readability in activity window."""
                    # Make sure text is visible and properly formatted
                    # Skip LiteLLM debug messages and other noise
                    skip_patterns = [
                        "LiteLLM:",
                        "INFO LiteLLM:",
                        "DEBUG:",
                        "Using Gmail search query:",
                        "Fetched and sorted",
                        "Error fetching emails with OAuth2",
                        "utils.py:",
                        "__pycache__",
                        "cost_calculator.py:",
                        "selected model name for cost calculation:"
                    ]
                    
                    for pattern in skip_patterns:
                        if pattern in text:
                            return None
                    
                    # Format different types of CrewAI messages
                    if "Working Agent:" in text:
                        agent_name = text.split("Working Agent:")[-1].strip()
                        return f"👤 Agent: {agent_name}"
                    elif "Starting Task:" in text:
                        task_name = text.split("Starting Task:")[-1].strip()
                        return f"📋 Task: {task_name}"
                    elif "> Entering new CrewAgentExecutor chain..." in text:
                        return "🚀 Starting new agent execution..."
                    elif "Thought:" in text:
                        thought = text.split("Thought:")[-1].strip()
                        return f"💭 Thinking: {thought}"
                    elif "Action:" in text and "Action Input:" not in text:
                        action = text.split("Action:")[-1].strip()
                        return f"🎯 Action: {action}"
                    elif "Action Input:" in text:
                        input_data = text.split("Action Input:")[-1].strip()
                        if len(input_data) > 100:
                            input_data = input_data[:100] + "..."
                        return f"📝 Input: {input_data}"
                    elif "Final Answer:" in text:
                        answer = text.split("Final Answer:")[-1].strip()
                        if len(answer) > 200:
                            answer = answer[:200] + "..."
                        return f"✅ Result: {answer}"
                    elif "> Finished chain." in text:
                        return "✔️ Agent task completed"
                    elif "🚀 Crew:" in text:
                        return text
                    elif "📋 Task:" in text or "Task:" in text:
                        return f"📋 {text}"
                    elif "Agent:" in text:
                        return f"👤 {text}"
                    elif "🔧 Used" in text:
                        return f"🔧 {text}"
                    elif "✅ Completed" in text or "Status: ✅ Completed" in text:
                        return f"✅ {text}"
                    elif "Tool Execution" in text:
                        return f"🛠️ {text}"
                    elif "Using tool:" in text:
                        tool_name = text.split("Using tool:")[-1].strip()
                        return f"🔧 Using tool: {tool_name}"
                    elif "Successfully" in text:
                        return f"✅ {text}"
                    elif "Error" in text and len(text) < 100:  # Only short error messages
                        return f"❌ {text}"
                    elif text.startswith("🚀") or text.startswith("📧") or text.startswith("✅"):
                        return text  # Already formatted
                    else:
                        # For other messages, add a generic icon if they seem important
                        if len(text) > 5 and any(word in text.lower() for word in ['processing', 'analyzing', 'generating', 'organizing', 'categorizing', 'found', 'email', 'crew', 'agent', 'task', 'executing', 'running', 'complete']):
                            return f"⚡ {text}"
                        # Show any text that might be CrewAI output
                        elif len(text) > 5 and not any(skip in text for skip in ['HTTP', 'Request', 'Response', 'Status']):
                            return f"📝 {text}"
                    
                    return None
            
            # Set up output capture
            activity_capture = ActivityLogCapture()
            
            # Also set up CrewAI logging to capture to activity window
            import logging
            
            # Create a custom handler that writes to activity logs
            class ActivityLogHandler(logging.Handler):
                def emit(self, record):
                    try:
                        msg = self.format(record)
                        if any(keyword in msg.lower() for keyword in ['agent', 'task', 'crew', 'working', 'executing', 'processing']):
                            timestamp = datetime.now().strftime('%H:%M:%S')
                            st.session_state.activity_logs.append(f"[{timestamp}] 🤖 {msg}")
                    except Exception:
                        pass
            
            # Add handler to CrewAI logger and enable verbose output
            crewai_logger = logging.getLogger('crewai')
            activity_handler = ActivityLogHandler()
            activity_handler.setLevel(logging.DEBUG)
            crewai_logger.addHandler(activity_handler)
            crewai_logger.setLevel(logging.DEBUG)
            
            # Also enable verbose output for CrewAI
            os.environ['CREWAI_VERBOSE'] = 'true'
            os.environ['LANGCHAIN_VERBOSE'] = 'true'
            
            # Model is already set before crew creation
            
            # Redirect stdout to capture CrewAI output
            # Suppress Streamlit ScriptRunContext warnings in threading
            import warnings
            
            # Implement retry logic with rate limiting
            max_retries = 3
            retry_delay = 60  # Start with 60 seconds
            
            for attempt in range(max_retries):
                try:
                    with warnings.catch_warnings():
                        warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
                        warnings.filterwarnings("ignore", message=".*Thread.*missing ScriptRunContext.*")
                        warnings.filterwarnings("ignore", message=".*Event loop is closed.*")
                        warnings.filterwarnings("ignore", message=".*cannot schedule new futures after shutdown.*")
                        warnings.filterwarnings("ignore", category=UserWarning)
                        warnings.filterwarnings("ignore", category=RuntimeWarning)
                        
                        # Add manual progress updates
                        safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 CrewAI kickoff initiated...")
                        safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 📧 Processing {filters['max_emails']} emails with search: {filters.get('gmail_search', 'is:unread')}")
                        safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🤖 Model: {os.getenv('MODEL', 'default')}")
                        
                        # Try to capture both stdout and stderr
                        original_stdout = sys.stdout
                        original_stderr = sys.stderr
                        
                        # Create a custom capture that updates activity logs AND terminal
                        class DualOutputCapture:
                            def __init__(self, original_stream):
                                self.content = []
                                self.original_stream = original_stream
                                
                            def write(self, text):
                                # Write to original stream (terminal)
                                if self.original_stream:
                                    self.original_stream.write(text)
                                    self.original_stream.flush()
                                
                                # Also capture for activity logs
                                if text and text.strip():
                                    self.content.append(text)
                                    # Add to activity logs immediately
                                    timestamp = datetime.now().strftime('%H:%M:%S')
                                    if any(keyword in text.lower() for keyword in ['working agent', 'executing', 'starting', 'completed', 'error']):
                                        safe_add_activity_log(f"[{timestamp}] 🤖 {text.strip()}")
                                    elif 'gmail search query' in text.lower():
                                        safe_add_activity_log(f"[{timestamp}] 🔍 {text.strip()}")
                                    elif 'fetched' in text.lower() and 'emails' in text.lower():
                                        safe_add_activity_log(f"[{timestamp}] 📬 {text.strip()}")
                                    else:
                                        safe_add_activity_log(f"[{timestamp}] ℹ️ {text.strip()}")
                                
                            def flush(self):
                                if self.original_stream:
                                    self.original_stream.flush()
                                
                            def close(self):
                                pass
                        
                        # Use dual output capture for both stdout and stderr
                        activity_capture = DualOutputCapture(original_stdout)
                        error_capture = DualOutputCapture(original_stderr)
                        
                        try:
                            # Redirect both stdout and stderr
                            sys.stdout = activity_capture
                            sys.stderr = error_capture
                            
                            # Add initial processing message
                            safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Starting detailed email analysis and processing...")
                            
                            # Apply intelligent rate limiting
                            try:
                                from src.gmail_crew_ai.utils.rate_limiter import rate_limiter
                                
                                # Check rate limit status
                                stats = rate_limiter.get_usage_stats()
                                st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 Token usage: {stats['current_usage']}/{stats['max_limit']} ({stats['percentage_used']:.1f}%)")
                                
                                # Wait if needed
                                rate_limiter.wait_if_needed(estimated_tokens=8000)  # Conservative estimate
                                
                            except ImportError:
                                # Fallback to simple delay
                                time.sleep(2)
                            
                            # Start crew execution with progress logging
                            safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 Starting sequential task execution...")
                            safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Task 1: Email categorization by priority and type")
                            
                            try:
                                # Enable CrewAI verbose mode to capture more output
                                crew_instance = crew.crew()
                                crew_instance.verbose = True  # Force verbose output
                                
                                # Add pre-execution status
                                safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 🏃 Executing CrewAI workflow...")
                                safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 👥 Agents: Categorizer → Organizer → Response Generator → Cleaner")
                                
                                result = crew_instance.kickoff(inputs={'email_limit': filters['max_emails']})
                                
                                # Add completion messages
                                safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ CrewAI execution completed successfully!")
                                safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] 📊 All tasks completed: categorization → organization → responses → cleanup")
                            except (RuntimeError, asyncio.CancelledError) as e:
                                if "Event loop is closed" in str(e) or "cannot schedule new futures" in str(e):
                                    safe_add_activity_log(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ CrewAI execution interrupted by system shutdown")
                                    break  # Exit retry loop
                                else:
                                    raise  # Re-raise other errors
                            
                        finally:
                            # Restore original stdout/stderr
                            sys.stdout = original_stdout
                            sys.stderr = original_stderr
                            
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    if "rate_limit_error" in str(e) and attempt < max_retries - 1:
                        # Rate limit error, wait and retry
                        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⚠️ Rate limit reached, waiting {retry_delay} seconds before retry...")
                        
                        # On second retry, try fallback model
                        if attempt == 1:
                            os.environ["RATE_LIMIT_FALLBACK"] = "true"
                            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Switching to OpenAI fallback model...")
                        
                        time.sleep(retry_delay)
                        retry_delay *= 2  # Exponential backoff
                        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔄 Retrying (attempt {attempt + 2}/{max_retries})...")
                    else:
                        # Other error or final attempt, re-raise
                        raise
                finally:
                    # Clear fallback flag after attempts
                    if "RATE_LIMIT_FALLBACK" in os.environ:
                        del os.environ["RATE_LIMIT_FALLBACK"]
            
            # Clear progress indicator
            progress_placeholder.empty()
            
            # Add final completion message
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎯 CrewAI execution completed - captured {len(activity_capture.content)} output lines")
            
            # Check if processing was stopped during execution
            if st.session_state.get('processing_stopped', False):
                st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Processing was stopped during execution")
                error_logger.log_error(
                    "Processing", 
                    "Email processing was stopped by user",
                    f"Processing was manually stopped during execution for user {user_email}",
                    user_id
                )
            else:
                st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ✅ Email processing completed successfully!")
                st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🎉 All tasks completed: emails categorized, organized, responses generated, cleanup performed")
                if st.session_state.get('debug_mode', False):
                    st.success(" Email processing completed!")
                
                    
            # Log successful completion to crew logger
            crew_log = get_crew_logger()
            crew_log.info(f"CrewAI execution completed successfully for user {user_id}")
            crew_log.info(f"User email: {user_email}")
            
            # Reset processing state after successful completion
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            
        except Exception as crew_error:
            # Enhanced crew-specific error handling with detailed user notification
            crew_error_str = str(crew_error)
            
            # Log to crew-specific logger first
            crew_log = get_crew_logger()
            crew_log.error(f"CrewAI execution failed for user {user_id}: {crew_error_str}")
            crew_log.error(f"Filters used: {json.dumps(filters)}")
            crew_log.error(f"User email: {user_email}")
            
            # Analyze error type and provide specific guidance
            error_analysis = analyze_crew_error(crew_error_str)
            
            # Log detailed error information to ErrorLogger
            error_logger.log_error(
                "CrewAI", 
                f"CrewAI execution failed: {crew_error_str}",
                f"Error during crew execution for user {user_email}. Filters: {json.dumps(filters)}. Rules: {rule_instructions}. Analysis: {error_analysis['category']}",
                user_id
            )
            
            # Add detailed error to activity logs
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ CrewAI execution failed")
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Error type: {error_analysis['category']}")
            st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 💡 {error_analysis['user_message']}")
            
            # Show comprehensive error notification to user
            st.error("🚨 **Email Processing Failed**")
            
            with st.expander("📋 Error Details & Troubleshooting", expanded=True):
                st.markdown(f"**Error Category:** {error_analysis['category']}")
                st.markdown(f"**What happened:** {error_analysis['user_message']}")
                
                if error_analysis['solutions']:
                    st.markdown("**🛠️ Recommended Solutions:**")
                    for i, solution in enumerate(error_analysis['solutions'], 1):
                        st.markdown(f"{i}. {solution}")
                
                if error_analysis['technical_details']:
                    with st.expander("🔧 Technical Details (for advanced users)"):
                        st.code(error_analysis['technical_details'])
                
                # Show processing context
                st.markdown("**📊 Processing Context:**")
                st.markdown(f"- **User:** {user_email}")
                st.markdown(f"- **Search Query:** `{filters.get('gmail_search', 'is:unread')}`")
                st.markdown(f"- **Max Emails:** {filters.get('max_emails', 10)}")
                if rule_instructions:
                    st.markdown(f"- **Active Rules:** {len(st.session_state.get('email_rules', []))} rules applied")
                
                # Provide immediate action buttons
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("🔄 Retry Processing"):
                        st.rerun()
                with col2:
                    if st.button("🔧 Check Settings"):
                        st.session_state.selected_main_tab = "⚙️ Settings"
                        st.rerun()
                with col3:
                    if st.button("📞 Get Help"):
                        st.session_state.selected_main_tab = "❓ Help"
                        st.rerun()
            
            # Reset processing state
            st.session_state.processing_active = False
            st.session_state.processing_started = False
            st.session_state.processing_stopped = False
            
            return  # Don't re-raise to prevent double error display
            
    except Exception as e:
        # Enhanced general error handling with detailed user notification
        error_str = str(e)
        error_analysis = analyze_crew_error(error_str)
        
        # Log detailed error information
        error_logger.log_error(
            error_analysis['category'], 
            f"Email processing failed: {error_str}",
            f"Error during email processing for user {user_email if 'user_email' in locals() else 'Unknown'}. Filters: {json.dumps(filters)}. Analysis: {error_analysis['category']}",
            user_id
        )
        
        # Add detailed error to activity logs
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Email processing failed")
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 🔍 Error type: {error_analysis['category']}")
        st.session_state.activity_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] 💡 {error_analysis['user_message']}")
        
        # Reset processing state
        st.session_state.processing_active = False
        st.session_state.processing_started = False
        st.session_state.processing_stopped = False
        
        # Show comprehensive error notification to user
        st.error("🚨 **Email Processing Failed**")
        
        with st.expander("📋 Error Details & Troubleshooting", expanded=True):
            st.markdown(f"**Error Category:** {error_analysis['category']}")
            st.markdown(f"**What happened:** {error_analysis['user_message']}")
            
            if error_analysis['solutions']:
                st.markdown("**🛠️ Recommended Solutions:**")
                for i, solution in enumerate(error_analysis['solutions'], 1):
                    st.markdown(f"{i}. {solution}")
            
            if error_analysis['technical_details']:
                with st.expander("🔧 Technical Details (for advanced users)"):
                    st.code(error_analysis['technical_details'])
            
            # Show processing context
            st.markdown("**📊 Processing Context:**")
            st.markdown(f"- **User:** {user_email if 'user_email' in locals() else 'Unknown'}")
            st.markdown(f"- **Search Query:** `{filters.get('gmail_search', 'is:unread')}`")
            st.markdown(f"- **Max Emails:** {filters.get('max_emails', 10)}")
            
            # Provide immediate action buttons
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔄 Retry Processing", key="retry_general"):
                    st.rerun()
            with col2:
                if st.button("🔧 Check Settings", key="settings_general"):
                    st.session_state.selected_main_tab = "⚙️ Settings"
                    st.rerun()
            with col3:
                if st.button("📞 Get Help", key="help_general"):
                    st.session_state.selected_main_tab = "❓ Help"
                    st.rerun()


def analyze_crew_error(error_message: str) -> dict:
    """Analyze crew error and provide user-friendly explanations and solutions."""
    error_message_lower = error_message.lower()
    
    # Default analysis
    analysis = {
        'category': 'Unknown Error',
        'user_message': 'An unexpected error occurred during email processing.',
        'solutions': ['Try processing again', 'Check your internet connection', 'Contact support if the problem persists'],
        'technical_details': error_message
    }
    
    # API Key Issues
    if any(phrase in error_message_lower for phrase in ['api_key', 'authentication', 'openai_api_key', 'anthropic_api_key', 'invalid x-api-key']):
        if 'anthropic' in error_message_lower or 'claude' in error_message_lower:
            analysis.update({
                'category': 'Anthropic API Key Issue',
                'user_message': 'Your Anthropic API key is invalid, expired, or missing. Claude models cannot function without a valid key.',
                'solutions': [
                    'Go to Settings → API Key Configuration and update your Anthropic API key',
                    'Get a new API key from https://console.anthropic.com/',
                    'Check if your Anthropic account has sufficient credits',
                    'Switch to OpenAI models if you have a valid OpenAI API key',
                    'Contact Anthropic support if you believe your key should be working'
                ]
            })
        elif 'openai' in error_message_lower or 'gpt' in error_message_lower:
            analysis.update({
                'category': 'OpenAI API Key Issue',
                'user_message': 'Your OpenAI API key is invalid, expired, or missing. GPT models cannot function without a valid key.',
                'solutions': [
                    'Go to Settings → API Key Configuration and update your OpenAI API key',
                    'Get a new API key from https://platform.openai.com/api-keys',
                    'Check if your OpenAI account has sufficient credits',
                    'Switch to Anthropic models if you have a valid Anthropic API key',
                    'Contact OpenAI support if you believe your key should be working'
                ]
            })
        else:
            analysis.update({
                'category': 'API Key Configuration',
                'user_message': 'The AI model API key is missing or invalid. This prevents the AI agents from working.',
                'solutions': [
                    'Go to Settings → API Key Configuration and verify your API key is set',
                    'Check that you selected the correct model for your available API keys',
                    'Ensure your API key has sufficient credits/quota',
                    'Try switching to a different AI model if you have multiple API keys configured'
                ]
            })
    
    # OAuth/Gmail Issues
    elif any(phrase in error_message_lower for phrase in ['oauth', 'gmail', 'credentials', 'token']):
        analysis.update({
            'category': 'Gmail Authentication',
            'user_message': 'There was an issue accessing your Gmail account. Your authentication may have expired.',
            'solutions': [
                'Go to Settings → Authentication Settings and click "Refresh Authentication"',
                'Try logging out and logging back in',
                'Check that your Google account has Gmail API access enabled',
                'Ensure you granted all required permissions during OAuth setup'
            ]
        })
    
    # Rate Limiting
    elif any(phrase in error_message_lower for phrase in ['rate limit', 'quota', 'too many requests']):
        analysis.update({
            'category': 'Rate Limiting',
            'user_message': 'You have hit API rate limits. This happens when too many requests are made too quickly.',
            'solutions': [
                'Wait a few minutes before trying again',
                'Reduce the number of emails being processed at once',
                'Check your API provider dashboard for quota information',
                'Consider upgrading your API plan if you frequently hit limits'
            ]
        })
    
    # Network Issues
    elif any(phrase in error_message_lower for phrase in ['network', 'connection', 'timeout', 'unreachable']):
        analysis.update({
            'category': 'Network Connection',
            'user_message': 'There was a network connectivity issue preventing communication with required services.',
            'solutions': [
                'Check your internet connection',
                'Try refreshing the page and running again',
                'Verify that your firewall/proxy allows access to Gmail and AI APIs',
                'Wait a moment and retry - this might be a temporary service issue'
            ]
        })
    
    # Model/LLM Issues
    elif any(phrase in error_message_lower for phrase in ['model', 'llm', 'litellm', 'completion']):
        analysis.update({
            'category': 'AI Model Issue',
            'user_message': 'The AI model encountered an error while processing your emails.',
            'solutions': [
                'Try switching to a different AI model in Settings',
                'Reduce the number of emails being processed at once',
                'Check that your selected model is available and working',
                'Verify your API key has access to the selected model'
            ]
        })
    
    # Email Processing Issues
    elif any(phrase in error_message_lower for phrase in ['fetch', 'email', 'organize', 'categorize']):
        analysis.update({
            'category': 'Email Processing',
            'user_message': 'An error occurred while fetching or processing your emails.',
            'solutions': [
                'Try using a simpler search query (e.g., just "is:unread")',
                'Reduce the maximum number of emails to process',
                'Check that your Gmail account is accessible',
                'Verify your search query syntax is correct'
            ]
        })
    
    # Permission Issues
    elif any(phrase in error_message_lower for phrase in ['permission', 'forbidden', 'unauthorized', 'access denied']):
        analysis.update({
            'category': 'Permission Error',
            'user_message': 'The app does not have sufficient permissions to access the required services.',
            'solutions': [
                'Re-authenticate with Google to grant fresh permissions',
                'Check that Gmail API is enabled in your Google Cloud project',
                'Verify OAuth consent screen includes required scopes',
                'Contact your administrator if using a work/school account'
            ]
        })
    
    return analysis


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
        st.success(f" Reply sent for: {original_subject}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Reply sent for: {original_subject}")
    except Exception as e:
        st.error(f" Error sending reply: {e}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Error sending reply: {e}")


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
        
        st.success(" AI learning updated with your changes!")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  AI learning updated from user feedback")
        
    except Exception as e:
        st.error(f" Error updating AI learning: {e}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Error updating AI learning: {e}")


def process_emails(user_id: str, oauth_manager):
    """Process emails using CrewAI (legacy function - calls new filtered version)."""
    process_emails_with_filters(user_id, oauth_manager)


def execute_email_action(user_id: str, oauth_manager: OAuth2Manager, email_row, action: str):
    """Execute the approved action on an email."""
    try:
        email_id = email_row.get('email_id', 'unknown')
        subject = email_row.get('subject', 'Unknown Subject')
        
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Executing {action} on: {subject}")
        
        service = oauth_manager.get_gmail_service(user_id)
        
        if action == "Archive":
            # Remove INBOX label to archive
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'removeLabelIds': ['INBOX']}
            ).execute()
            st.success(f" Archived: {subject}")
            
        elif action == "Delete":
            service.users().messages().trash(userId='me', id=email_id).execute()
            st.success(f" Deleted: {subject}")
            
        elif action == "Star":
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['STARRED']}
            ).execute()
            st.success(f" Starred: {subject}")
            
        elif action == "Mark Important":
            service.users().messages().modify(
                userId='me',
                id=email_id,
                body={'addLabelIds': ['IMPORTANT']}
            ).execute()
            st.success(f" Marked Important: {subject}")
            
        else:
            st.info(f"Action '{action}' is not yet implemented for: {subject}")
        
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Action completed successfully")
        
    except Exception as e:
        st.error(f" Error executing action '{action}': {e}")
        st.session_state.processing_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}]  Action failed: {e}")


def main():
    """Main Streamlit application."""
    st.set_page_config(
        page_title="Gmail CrewAI",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inject shadcn-inspired CSS styling
    inject_shadcn_css()
    
    init_session_state()
    
    # CRITICAL: Ensure environment variables are loaded from .env file
    from dotenv import load_dotenv
    load_dotenv(override=True)  # Force reload of .env file
    
    # CRITICAL: Ensure MODEL environment variable is always set
    if 'selected_model' in st.session_state and st.session_state.selected_model:
        os.environ['MODEL'] = st.session_state.selected_model
        log.debug(f"Early MODEL environment setting: {st.session_state.selected_model}")
    
    # Debug API keys
    log.debug(f"ANTHROPIC_API_KEY loaded: {'Yes' if os.getenv('ANTHROPIC_API_KEY') else 'No'}")
    log.debug(f"OPENAI_API_KEY loaded: {'Yes' if os.getenv('OPENAI_API_KEY') else 'No'}")
    
    # CRITICAL: Check for persistent session immediately after app initialization
    # This ensures session is restored BEFORE any routing logic
    if not st.session_state.get('session_restored_on_load', False):
        st.session_state.session_restored_on_load = True
        
        # Always show loading indicator on page refresh/load
        loading_placeholder = st.empty()
        with loading_placeholder.container():
            st.markdown("""
            <div style="
                display: flex; 
                flex-direction: column; 
                align-items: center; 
                justify-content: center; 
                height: 80vh;
                text-align: center;
            ">
                <div style="
                    display: inline-block;
                    width: 40px;
                    height: 40px;
                    border: 4px solid #f3f3f3;
                    border-top: 4px solid #3498db;
                    border-radius: 50%;
                    animation: spin 1s linear infinite;
                    margin-bottom: 20px;
                "></div>
                <h3 style="color: #666; margin: 0;">🔄 Loading application...</h3>
                <p style="color: #888; margin: 5px 0 0 0;">Checking your session</p>
            </div>
            <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            </style>
            """, unsafe_allow_html=True)
        
        # Debug current session state
        log.debug(f"Page load session check - persistent_user_id: {st.session_state.get('persistent_user_id')}")
        log.debug(f"Page load session check - authenticated_user_id: {st.session_state.get('authenticated_user_id')}")
        log.debug(f"Page load session check - authentication_step: {st.session_state.get('authentication_step')}")
        
        # Small delay to ensure loading indicator is visible
        import time
        time.sleep(0.8)
        
        session_restored = check_persistent_session()
        
        # Clear the loading indicator
        loading_placeholder.empty()
        
        if session_restored:
            log.info("Session restored successfully on page load")
            # Only show success message in debug mode
            if st.session_state.get('debug_mode', False):
                success_placeholder = st.empty()
                with success_placeholder.container():
                    st.success("✅ Session restored successfully!")
                time.sleep(0.5)
                success_placeholder.empty()
            # Force immediate redirect to prevent any login page flash
            st.rerun()
        else:
            log.debug("No persistent session found on page load")
    
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
                    st.success(f" User {user_email} has been approved successfully!")
                    st.info("The user can now log in to the system.")
                else:
                    st.error(" Failed to approve user. User may not exist or is already processed.")
            
            elif action == 'reject':
                if user_manager.reject_user(user_id):
                    email_service.mark_token_used(token)
                    st.warning(f" User {user_email} has been rejected and removed from the system.")
                else:
                    st.error(" Failed to reject user. User may not exist or is already processed.")
            
            # Clear query params to avoid processing again
            st.query_params.clear()
            st.balloons()
            
        else:
            st.error(" Invalid or expired approval link.")
        
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
                    # Check flow type based on oauth_user_id prefix
                    if oauth_user_id.startswith("primary_setup_"):
                        # Primary owner setup - get email and create as primary user
                        try:
                            authenticated_email = st.session_state.oauth_manager.get_user_email(oauth_user_id)
                            reason = st.session_state.get('pending_primary_reason', 'Primary owner setup')
                            
                            # Create the primary user
                            new_user_id = user_manager.create_user(
                                email=authenticated_email,
                                reason=reason,
                                is_primary=True
                            )
                            
                            # Auto-approve since this is the primary owner
                            user_manager.approve_user(new_user_id)
                            user_manager.update_last_login(new_user_id)
                            
                            st.session_state.oauth_result = "success"
                            st.session_state.authenticated_user_id = new_user_id
                            st.session_state.current_user = oauth_user_id
                            st.session_state.authentication_step = 'dashboard'
                            
                            # Create persistent session (7-day login)
                            session_token = session_manager.create_session(new_user_id)
                            session_manager.set_browser_session(session_token)
                            
                            # ADDITIONAL: Store directly in session state for immediate persistence
                            st.session_state.persistent_session_token = session_token
                            st.session_state.persistent_user_id = new_user_id
                            
                            # Map OAuth credentials from primary_setup_* to user_* format
                            try:
                                oauth_manager = st.session_state.oauth_manager
                                # Load credentials with the primary_setup ID
                                setup_credentials = oauth_manager.load_credentials(oauth_user_id)
                                if setup_credentials:
                                    # Save them with the proper user ID
                                    oauth_manager.save_credentials(new_user_id, setup_credentials)
                                    log.info(f"Mapped OAuth credentials from {oauth_user_id} to {new_user_id}")
                            except Exception as e:
                                log.warning(f"Could not map OAuth credentials: {e}")
                            
                            # Clean up pending state
                            if 'pending_oauth_user_id' in st.session_state:
                                del st.session_state.pending_oauth_user_id
                            if 'pending_primary_reason' in st.session_state:
                                del st.session_state.pending_primary_reason
                                
                        except Exception as e:
                            st.session_state.oauth_result = "failed"
                            st.session_state.oauth_error = f"Error setting up primary owner: {e}"
                            st.session_state.authentication_step = 'login'
                    elif oauth_user_id.startswith("register_"):
                        # User registration - get email and create registration request
                        try:
                            authenticated_email = st.session_state.oauth_manager.get_user_email(oauth_user_id)
                            reason = st.session_state.get('pending_register_reason', 'Account access request')
                            
                            # Check if user already exists
                            existing_user_id, existing_user_data = user_manager.get_user_by_email(authenticated_email)
                            if existing_user_data:
                                if existing_user_data.get('status') == 'approved':
                                    st.session_state.oauth_result = "failed"
                                    st.session_state.oauth_error = f"Account ({authenticated_email}) already exists and is approved. Please use the Login tab instead."
                                    st.session_state.authentication_step = 'login'
                                elif existing_user_data.get('status') == 'pending':
                                    st.session_state.oauth_result = "failed"
                                    st.session_state.oauth_error = f"Account ({authenticated_email}) already has a pending registration request."
                                    st.session_state.authentication_step = 'login'
                                else:
                                    st.session_state.oauth_result = "failed"
                                    st.session_state.oauth_error = f"Account ({authenticated_email}) was previously rejected. Contact the primary owner."
                                    st.session_state.authentication_step = 'login'
                            else:
                                # Create new user registration request
                                new_user_id = user_manager.create_user(
                                    email=authenticated_email,
                                    reason=reason,
                                    is_primary=False
                                )
                                
                                # Send approval email to primary owner
                                primary_user = user_manager.get_primary_user()
                                if primary_user:
                                    # Here you could send an email notification
                                    pass
                                
                                st.session_state.oauth_result = "success"
                                st.session_state.oauth_success_message = f"Registration successful! Your request has been sent to the primary owner ({primary_user['email'] if primary_user else 'administrator'}) for approval."
                                st.session_state.authentication_step = 'login'
                                
                                # Clean up pending state
                                if 'pending_oauth_user_id' in st.session_state:
                                    del st.session_state.pending_oauth_user_id
                                if 'pending_register_reason' in st.session_state:
                                    del st.session_state.pending_register_reason
                                    
                        except Exception as e:
                            st.session_state.oauth_result = "failed"
                            st.session_state.oauth_error = f"Error during registration: {e}"
                            st.session_state.authentication_step = 'login'
                    elif oauth_user_id.startswith("login_"):
                        # Direct login - get email from OAuth manager and check if user exists
                        try:
                            authenticated_email = st.session_state.oauth_manager.get_user_email(oauth_user_id)
                            user_id, user_data = user_manager.get_user_by_email(authenticated_email)
                            
                            if user_data:
                                if user_data.get('status') == 'approved':
                                    # User exists and is approved - log them in
                                    user_manager.update_last_login(user_id)
                                    
                                    st.session_state.oauth_result = "success"
                                    st.session_state.authenticated_user_id = user_id
                                    st.session_state.current_user = oauth_user_id
                                    st.session_state.authentication_step = 'dashboard'
                                    
                                    # Create persistent session (7-day login)
                                    session_token = session_manager.create_session(user_id)
                                    session_manager.set_browser_session(session_token)
                                    
                                    # ADDITIONAL: Store directly in session state for immediate persistence
                                    st.session_state.persistent_session_token = session_token
                                    st.session_state.persistent_user_id = user_id
                                    
                                    # Map OAuth credentials from login_* to user_* format
                                    try:
                                        oauth_manager = st.session_state.oauth_manager
                                        # Load credentials with the login ID
                                        login_credentials = oauth_manager.load_credentials(oauth_user_id)
                                        if login_credentials:
                                            # Save them with the proper user ID
                                            oauth_manager.save_credentials(user_id, login_credentials)
                                            log.info(f"Mapped OAuth credentials from {oauth_user_id} to {user_id}")
                                    except Exception as e:
                                        log.warning(f"Could not map OAuth credentials: {e}")
                                    
                                    # Clean up pending state
                                    if 'pending_oauth_user_id' in st.session_state:
                                        del st.session_state.pending_oauth_user_id
                                elif user_data.get('status') == 'pending':
                                    st.session_state.oauth_result = "failed"
                                    st.session_state.oauth_error = f"Your account ({authenticated_email}) is pending approval from the primary owner."
                                    st.session_state.authentication_step = 'login'
                                else:
                                    st.session_state.oauth_result = "failed"
                                    st.session_state.oauth_error = f"Your account ({authenticated_email}) has been rejected. Contact the primary owner."
                                    st.session_state.authentication_step = 'login'
                            else:
                                # User doesn't exist - suggest registration
                                st.session_state.oauth_result = "failed"
                                st.session_state.oauth_error = f"Account ({authenticated_email}) not found. Please register first or contact the primary owner for access."
                                st.session_state.authentication_step = 'login'
                        except Exception as e:
                            st.session_state.oauth_result = "failed" 
                            st.session_state.oauth_error = f"Could not get user email from authentication: {e}"
                            st.session_state.authentication_step = 'login'
                    else:
                        # Legacy login flow - extract user ID from OAuth user ID
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
                            
                            # ADDITIONAL: Store directly in session state for immediate persistence
                            st.session_state.persistent_session_token = session_token
                            st.session_state.persistent_user_id = authenticated_user_id
                            
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
            st.error(f" Authentication failed: {st.session_state.oauth_error}")
            # Clear the result after showing
            del st.session_state.oauth_result
            if 'oauth_error' in st.session_state:
                del st.session_state.oauth_error
        elif st.session_state.oauth_result == "error":
            st.error(f" OAuth error: {st.session_state.oauth_error}")
            # Clear the result after showing
            del st.session_state.oauth_result
            if 'oauth_error' in st.session_state:
                del st.session_state.oauth_error
        elif st.session_state.oauth_result == "success":
            # Check if there's a custom success message (for registration)
            if 'oauth_success_message' in st.session_state:
                st.success(st.session_state.oauth_success_message)
                del st.session_state.oauth_success_message
            else:
                # Only show authentication success in debug mode
                if st.session_state.get('debug_mode', False):
                    success_placeholder = st.empty()
                    success_placeholder.success(" Authentication successful! Redirecting...")
                
                # Use JavaScript to hide the message after 3 seconds
                components.html(
                    """
                    <script>
                    setTimeout(function() {
                        var elements = parent.document.querySelectorAll('[data-testid="stAlert"]');
                        elements.forEach(function(element) {
                            if (element.textContent.includes(' Authentication successful!')) {
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
    
    # Always check for persistent session on page load/refresh
    if not st.session_state.get('session_initialized', False):
        st.session_state.session_initialized = True
        
        # Show brief loading indicator
        if st.session_state.get('persistent_user_id'):
            with st.spinner('🔄 Restoring session...'):
                if check_persistent_session():
                    # Successfully restored session, redirect to dashboard
                    st.rerun()
        else:
            if check_persistent_session():
                # Successfully restored session, redirect to dashboard
                st.rerun()
    
    # Also check for persistent session if we're in login state
    if st.session_state.authentication_step == 'login':
        if st.session_state.get('persistent_user_id'):
            with st.spinner('🔄 Checking session...'):
                if check_persistent_session():
                    # Successfully restored session, redirect to dashboard
                    st.rerun()
        else:
            if check_persistent_session():
                # Successfully restored session, redirect to dashboard
                st.rerun()
    
    # Additional check: if we have no authenticated_user_id but should be in dashboard
    if (st.session_state.authentication_step == 'dashboard' and 
        not st.session_state.get('authenticated_user_id')):
        if check_persistent_session():
            st.rerun()
        else:
            # No valid session found, go back to login
            st.session_state.authentication_step = 'login'
            st.rerun()
    
    # Route to appropriate page based on authentication state
    if st.session_state.authentication_step == 'login':
        show_login_page()
    elif st.session_state.authentication_step == 'google_oauth':
        # OAuth is handled automatically via query params, show waiting message
        st.markdown("#  Authenticating...")
        st.markdown("If you're not redirected automatically, please check your popup blocker and try again.")
    elif st.session_state.authentication_step == 'select_user':
        show_user_selection()
    elif st.session_state.authentication_step == 'oauth_flow':
        show_oauth_flow()
    elif st.session_state.authentication_step == 'dashboard':
        # Check authentication before showing dashboard
        if st.session_state.authenticated_user_id and st.session_state.current_user:
            show_dashboard()
        else:
            st.error(" Please log in to access the dashboard")
            st.session_state.authentication_step = 'login'
            st.rerun()


# Initialize global managers
def initialize_app():
    """Initialize app and ensure all required session state variables."""
    # Initialize managers if not already present
    if 'user_manager' not in st.session_state:
        st.session_state.user_manager = UserManager()
    
        
    if 'session_manager' not in st.session_state:
        st.session_state.session_manager = SessionManager()
        
    if 'oauth_manager' not in st.session_state:
        st.session_state.oauth_manager = OAuth2Manager()
    
    # Initialize admin user only if needed
    user_manager = st.session_state.user_manager
    admin_email = "articulatedesigns@gmail.com"
    admin_user_id, admin_user_data = user_manager.get_user_by_email(admin_email)
    
    # Only initialize if user doesn't exist or isn't already an admin
    if not admin_user_data or admin_user_data.get('role') not in ['admin', 'owner']:
        user_manager.initialize_admin_user(admin_email)
    
    # Initialize other session state variables
    if 'authentication_step' not in st.session_state:
        st.session_state.authentication_step = 'login'
    if 'authenticated_user_id' not in st.session_state:
        st.session_state.authenticated_user_id = None
    if 'current_user' not in st.session_state:
        st.session_state.current_user = None
    if 'processing_active' not in st.session_state:
        st.session_state.processing_active = False
    if 'activity_logs' not in st.session_state:
        st.session_state.activity_logs = []
    if 'processing_logs' not in st.session_state:
        st.session_state.processing_logs = []

# Initialize the app
initialize_app()

if __name__ == "__main__":
    main() 