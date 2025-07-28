"""Gmail tools using OAuth2 authentication - Deprecated in favor of gmail_oauth_tools.py

This module is maintained for backward compatibility but all tools now use OAuth2.
All IMAP/SMTP functionality has been removed and replaced with Gmail API calls.
"""

import os
import json
from typing import List, Tuple, Optional, Dict, Any, Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# Import OAuth2 tools
from .gmail_oauth_tools import (
    OAuth2GetUnreadEmailsTool,
    OAuth2GmailOrganizeTool,
    OAuth2GmailDeleteTool,
    OAuth2SaveDraftTool,
    OAuth2EmptyTrashTool,
    OAuth2GetSentEmailsTool,
    OAuth2UserPersonaAnalyzerTool,
    OAuth2UserPersonaUpdaterTool,
    OAuth2GmailToolBase
)


# Legacy schemas - maintained for backward compatibility
class GetUnreadEmailsSchema(BaseModel):
    """Schema for GetUnreadEmailsTool input."""
    limit: Optional[int] = Field(
        default=5,
        description="Maximum number of unread emails to retrieve. Defaults to 5.",
        ge=1
    )


class SaveDraftSchema(BaseModel):
    """Schema for SaveDraftTool input."""
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")
    recipient: str = Field(..., description="Recipient email address")
    thread_info: Optional[Dict[str, Any]] = Field(None, description="Thread information for replies")


class GmailOrganizeSchema(BaseModel):
    """Schema for GmailOrganizeTool input."""
    email_id: str = Field(..., description="Email ID to organize")
    category: str = Field(..., description="Category assigned by agent (Urgent/Response Needed/etc)")
    priority: str = Field(..., description="Priority level (High/Medium/Low)")
    should_star: bool = Field(default=False, description="Whether to star the email")
    labels: List[str] = Field(default_factory=list, description="Labels to apply")


class GmailDeleteSchema(BaseModel):
    """Schema for GmailDeleteTool input."""
    email_id: str = Field(..., description="Email ID to delete")
    reason: str = Field(..., description="Reason for deletion")


# Legacy tool classes that now wrap OAuth2 implementations
class GmailToolBase(BaseTool):
    """Base class for Gmail tools - now uses OAuth2."""
    
    name: str = "gmail_tool_base"
    description: str = "Base class for Gmail tools"
    
    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Check for OAuth2 user ID, with auto-detection fallback
        self.user_id = os.environ.get("CURRENT_USER_ID") or self._get_primary_user_id()
        if not self.user_id:
            raise ValueError("No authenticated user found. Please authenticate first or set CURRENT_USER_ID environment variable.")
    
    def _get_primary_user_id(self) -> Optional[str]:
        """Auto-detect primary user ID from users.json file."""
        try:
            # Try to load users.json to find primary user
            if os.path.exists('users.json'):
                with open('users.json', 'r') as f:
                    users = json.loads(f.read())
                
                # Find primary user
                for user_id, user_data in users.items():
                    if user_data.get('is_primary', False):
                        print(f"Auto-detected primary user: {user_id} ({user_data.get('email', 'unknown')})")
                        return user_id
                
                # If no primary user, get the first approved user
                for user_id, user_data in users.items():
                    if user_data.get('status') == 'approved':
                        print(f"Using first approved user: {user_id} ({user_data.get('email', 'unknown')})")
                        return user_id
        except Exception as e:
            print(f"Error auto-detecting user: {e}")
        
        return None


class GetUnreadEmailsTool(GmailToolBase):
    """Tool to get unread emails from Gmail - now uses OAuth2."""
    name: str = "get_unread_emails"
    description: str = "Gets unread emails from Gmail using OAuth2 authentication"
    args_schema: Type[BaseModel] = GetUnreadEmailsSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create OAuth2 tool instance
        self._oauth_tool = OAuth2GetUnreadEmailsTool(user_id=self.user_id)
    
    def _run(self, limit: Optional[int] = 5) -> List[Tuple[str, str, str, str, Dict]]:
        """Get unread emails using OAuth2."""
        # Map legacy limit to OAuth2 max_emails parameter
        return self._oauth_tool._run(max_emails=limit)


class SaveDraftTool(BaseTool):
    """Tool to save an email as a draft - now uses OAuth2."""
    name: str = "save_email_draft"
    description: str = "Saves an email as a draft in Gmail using OAuth2 authentication"
    args_schema: Type[BaseModel] = SaveDraftSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_id = os.environ.get("CURRENT_USER_ID") or self._get_primary_user_id()
        if not self.user_id:
            raise ValueError("No authenticated user found. Please authenticate first or set CURRENT_USER_ID environment variable.")
        self._oauth_tool = OAuth2SaveDraftTool(user_id=self.user_id)
    
    def _get_primary_user_id(self) -> Optional[str]:
        """Auto-detect primary user ID from users.json file."""
        try:
            if os.path.exists('users.json'):
                with open('users.json', 'r') as f:
                    users = json.loads(f.read())
                for user_id, user_data in users.items():
                    if user_data.get('is_primary', False):
                        return user_id
                for user_id, user_data in users.items():
                    if user_data.get('status') == 'approved':
                        return user_id
        except Exception:
            pass
        return None

    def _run(self, subject: str, body: str, recipient: str, thread_info: Optional[Dict[str, Any]] = None) -> str:
        """Save draft using OAuth2."""
        # Extract in_reply_to from thread_info if available
        in_reply_to = None
        if thread_info and thread_info.get('message_id'):
            in_reply_to = thread_info['message_id']
        
        return self._oauth_tool._run(
            recipient=recipient,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to
        )


class GmailOrganizeTool(GmailToolBase):
    """Tool to organize emails - now uses OAuth2."""
    name: str = "organize_email"
    description: str = "Organizes emails using Gmail's features via OAuth2 authentication"
    args_schema: Type[BaseModel] = GmailOrganizeSchema

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._oauth_tool = OAuth2GmailOrganizeTool(user_id=self.user_id)

    def _run(self, email_id: str, category: str, priority: str, should_star: bool = False, labels: List[str] = None) -> str:
        """Organize an email using OAuth2."""
        if labels is None:
            labels = []
        
        # Map legacy parameters to OAuth2 parameters
        labels_to_add = labels.copy()
        
        # Add category/priority based labels
        if category == "Urgent Response Needed" and priority == "High":
            if "URGENT" not in labels_to_add:
                labels_to_add.append("URGENT")
        
        return self._oauth_tool._run(
            email_id=email_id,
            labels_to_add=labels_to_add,
            star=should_star,
            mark_read=True  # Mark all processed emails as read
        )


class GmailDeleteTool(BaseTool):
    """Tool to delete an email - now uses OAuth2."""
    name: str = "delete_email"
    description: str = "Deletes an email from Gmail using OAuth2 authentication"
    args_schema: Type[BaseModel] = GmailDeleteSchema
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_id = os.environ.get("CURRENT_USER_ID") or self._get_primary_user_id()
        if not self.user_id:
            raise ValueError("No authenticated user found. Please authenticate first or set CURRENT_USER_ID environment variable.")
        self._oauth_tool = OAuth2GmailDeleteTool(user_id=self.user_id)
    
    def _get_primary_user_id(self) -> Optional[str]:
        """Auto-detect primary user ID from users.json file."""
        try:
            if os.path.exists('users.json'):
                with open('users.json', 'r') as f:
                    users = json.loads(f.read())
                for user_id, user_data in users.items():
                    if user_data.get('is_primary', False):
                        return user_id
                for user_id, user_data in users.items():
                    if user_data.get('status') == 'approved':
                        return user_id
        except Exception:
            pass
        return None
    
    def _run(self, email_id: str, reason: str) -> str:
        """Delete an email using OAuth2."""
        # OAuth2 tool doesn't use reason parameter, but we log it
        print(f"Deleting email {email_id}. Reason: {reason}")
        result = self._oauth_tool._run(email_id=email_id)
        
        # Append reason to result for backward compatibility
        if "Successfully" in result:
            return f"{result}. Reason: {reason}"
        return result


class EmptyTrashTool(BaseTool):
    """Tool to empty Gmail trash - now uses OAuth2."""
    name: str = "empty_gmail_trash"
    description: str = "Empties the Gmail trash folder using OAuth2 authentication"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_id = os.environ.get("CURRENT_USER_ID") or self._get_primary_user_id()
        if not self.user_id:
            raise ValueError("No authenticated user found. Please authenticate first or set CURRENT_USER_ID environment variable.")
        self._oauth_tool = OAuth2EmptyTrashTool(user_id=self.user_id)
    
    def _get_primary_user_id(self) -> Optional[str]:
        """Auto-detect primary user ID from users.json file."""
        try:
            if os.path.exists('users.json'):
                with open('users.json', 'r') as f:
                    users = json.loads(f.read())
                for user_id, user_data in users.items():
                    if user_data.get('is_primary', False):
                        return user_id
                for user_id, user_data in users.items():
                    if user_data.get('status') == 'approved':
                        return user_id
        except Exception:
            pass
        return None
    
    def _run(self) -> str:
        """Empty Gmail trash using OAuth2."""
        return self._oauth_tool._run()


# Export all tools for backward compatibility
__all__ = [
    'GetUnreadEmailsTool',
    'SaveDraftTool',
    'GmailOrganizeTool',
    'GmailDeleteTool',
    'EmptyTrashTool',
    'GmailToolBase'
]