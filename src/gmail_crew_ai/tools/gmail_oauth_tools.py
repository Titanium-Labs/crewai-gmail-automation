"""Gmail tools that use OAuth2 authentication instead of app passwords."""

import os
import email
from email.header import decode_header
from typing import List, Tuple, Optional, Dict, Any
import re
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
from datetime import datetime

try:
    from googleapiclient.discovery import build
    from google.oauth2.credentials import Credentials
    from ..auth import OAuth2Manager
except ImportError:
    # Fallback for when dependencies aren't installed yet
    build = None
    Credentials = None
    OAuth2Manager = None


def decode_header_safe(header):
    """Safely decode email headers that might contain encoded words or non-ASCII characters."""
    if not header:
        return ""
    
    try:
        decoded_parts = []
        for decoded_str, charset in decode_header(header):
            if isinstance(decoded_str, bytes):
                if charset:
                    decoded_parts.append(decoded_str.decode(charset or 'utf-8', errors='replace'))
                else:
                    decoded_parts.append(decoded_str.decode('utf-8', errors='replace'))
            else:
                decoded_parts.append(str(decoded_str))
        return ' '.join(decoded_parts)
    except Exception as e:
        return str(header)


def clean_email_body(email_body: str, max_length: int = 300) -> str:
    """Clean the email body by removing HTML tags, excessive whitespace, and limit length."""
    if not email_body:
        return ""
    
    try:
        # Handle encoding issues by replacing problematic characters
        email_body = email_body.encode('utf-8', errors='replace').decode('utf-8')
        
        soup = BeautifulSoup(email_body, "html.parser")
        text = soup.get_text(separator=" ")
    except Exception as e:
        print(f"Error parsing HTML: {e}")
        text = email_body

    # Remove excessive whitespace and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove common problematic unicode characters
    text = re.sub(r'[\u200c\u200d\u00ad]+', '', text)  # Remove zero-width and soft hyphen chars
    text = re.sub(r'[^\x00-\x7F\u00A0-\u024F\u1E00-\u1EFF]+', ' ', text)  # Keep basic Latin chars
    
    # Truncate if too long, keeping first part which usually has most important content
    if len(text) > max_length:
        text = text[:max_length] + "... [Content truncated for processing]"
    
    return text


class OAuth2GmailToolBase(BaseTool):
    """Base class for OAuth2 Gmail tools."""
    
    class Config:
        arbitrary_types_allowed = True

    user_id: Optional[str] = Field(None, description="User ID for OAuth2 authentication")
    oauth_manager: Optional[Any] = Field(None, description="OAuth2 manager instance")

    def __init__(self, user_id: Optional[str] = None, oauth_manager: Any = None, description: str = "", name: str = "OAuth2GmailTool"):
        super().__init__(name=name, description=description)
        
        # Get user ID from environment if not provided
        if user_id is None:
            user_id = os.environ.get("CURRENT_USER_ID")
        
        # Initialize OAuth2 manager if not provided
        if oauth_manager is None and OAuth2Manager:
            oauth_manager = OAuth2Manager()
        
        self.user_id = user_id or ""
        self.oauth_manager = oauth_manager

        if not self.user_id:
            raise ValueError("User ID must be provided or set in CURRENT_USER_ID environment variable")

    def _get_gmail_service(self):
        """Get Gmail API service for the authenticated user."""
        if not self.oauth_manager:
            raise ValueError("OAuth2 manager not available")
        
        return self.oauth_manager.get_gmail_service(self.user_id)

    def _gmail_message_to_email_format(self, message_data: Dict) -> Tuple[str, str, str, str, Dict]:
        """Convert Gmail API message to email format."""
        headers = message_data['payload'].get('headers', [])
        
        # Extract basic info
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
        sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
        date_header = next((h['value'] for h in headers if h['name'].lower() == 'date'), '')
        message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), '')
        
        # Extract body
        body = self._extract_body_from_payload(message_data['payload'])
        
        # Create thread info
        thread_info = {
            'message_id': message_id,
            'date': date_header,
            'raw_date': date_header,
            'email_id': message_data['id'],
            'thread_id': message_data.get('threadId', ''),
            'in_reply_to': next((h['value'] for h in headers if h['name'].lower() == 'in-reply-to'), ''),
            'references': next((h['value'] for h in headers if h['name'].lower() == 'references'), ''),
        }
        
        return subject, sender, body, message_data['id'], thread_info

    def _extract_body_from_payload(self, payload: Dict) -> str:
        """Extract email body from Gmail API payload."""
        body = ""
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain' and 'data' in part['body']:
                    decoded_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                    # Limit each part to prevent massive concatenation
                    if len(decoded_body) > 200:
                        decoded_body = decoded_body[:200] + "... [Part truncated]"
                    body += decoded_body
                elif part['mimeType'] == 'text/html' and 'data' in part['body']:
                    html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
                    cleaned_body = clean_email_body(html_body, max_length=200)
                    body += cleaned_body
        else:
            if payload['mimeType'] == 'text/plain' and 'data' in payload['body']:
                body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
            elif payload['mimeType'] == 'text/html' and 'data' in payload['body']:
                html_body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')
                body = clean_email_body(html_body, max_length=200)
        
        # Final safety check - ensure body doesn't exceed 250 chars total per email
        if len(body) > 250:
            body = body[:250] + "... [Email truncated]"
        
        return body.strip()


class OAuth2GetUnreadEmailsToolSchema(BaseModel):
    """Schema for OAuth2GetUnreadEmailsTool input."""
    max_emails: int = Field(
        default=50,
        description="Maximum number of unread emails to retrieve",
        ge=1, le=100
    )

class OAuth2GetUnreadEmailsTool(OAuth2GmailToolBase):
    """OAuth2 version of the Gmail emails fetcher with flexible search."""
    
    name: str = "OAuth2GetUnreadEmailsTool"
    description: str = "Fetch emails from Gmail using OAuth2 authentication with flexible search queries"
    args_schema: type[BaseModel] = OAuth2GetUnreadEmailsToolSchema

    def _run(self, max_emails: int = 50) -> List[Tuple[str, str, str, str, Dict]]:
        """Fetch emails using Gmail API with user-specified search query."""
        # Get search query from environment, fallback to 'is:unread'
        search_query = os.environ.get('GMAIL_SEARCH_QUERY', 'is:unread')
        print(f"Using Gmail search query: {search_query}")
        
        try:
            service = self._get_gmail_service()
            
            # Get messages based on user's filter selection
            results = service.users().messages().list(
                userId='me',
                q=search_query,
                maxResults=max_emails
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                # Get full message
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # Convert to email format
                email_data = self._gmail_message_to_email_format(message)
                emails.append(email_data)
            
            print(f"Fetched {len(emails)} emails using OAuth2 with query: {search_query}")
            return emails
            
        except Exception as e:
            print(f"Error fetching emails with OAuth2 using query '{search_query}': {e}")
            return []


class OAuth2GmailOrganizeToolSchema(BaseModel):
    """Schema for OAuth2GmailOrganizeTool input."""
    email_id: str = Field(description="ID of the email to organize")
    labels_to_add: Optional[List[str]] = Field(default=None, description="List of labels to add to the email")
    labels_to_remove: Optional[List[str]] = Field(default=None, description="List of labels to remove from the email")
    star: bool = Field(default=False, description="Whether to star the email")
    unstar: bool = Field(default=False, description="Whether to unstar the email")
    mark_read: bool = Field(default=False, description="Whether to mark the email as read")
    mark_unread: bool = Field(default=False, description="Whether to mark the email as unread")

class OAuth2GmailOrganizeTool(OAuth2GmailToolBase):
    """OAuth2 version of the Gmail organizer tool."""
    
    name: str = "OAuth2GmailOrganizeTool"
    description: str = "Organize emails in Gmail using OAuth2 authentication"
    args_schema: type[BaseModel] = OAuth2GmailOrganizeToolSchema

    def _run(self, email_id: str, labels_to_add: Optional[List[str]] = None, labels_to_remove: Optional[List[str]] = None, 
             star: bool = False, unstar: bool = False, mark_read: bool = False, 
             mark_unread: bool = False) -> str:
        """Organize email using Gmail API."""
        try:
            service = self._get_gmail_service()
            
            # Prepare modification request
            body = {
                'addLabelIds': [],
                'removeLabelIds': []
            }
            
            # Handle labels
            if labels_to_add:
                # Get or create labels
                for label_name in labels_to_add:
                    label_id = self._get_or_create_label(service, label_name)
                    if label_id:
                        body['addLabelIds'].append(label_id)
            
            if labels_to_remove:
                for label_name in labels_to_remove:
                    label_id = self._get_label_id(service, label_name)
                    if label_id:
                        body['removeLabelIds'].append(label_id)
            
            # Handle starring
            if star:
                body['addLabelIds'].append('STARRED')
            elif unstar:
                body['removeLabelIds'].append('STARRED')
            
            # Handle read status
            if mark_read:
                body['removeLabelIds'].append('UNREAD')
            elif mark_unread:
                body['addLabelIds'].append('UNREAD')
            
            # Apply modifications
            if body['addLabelIds'] or body['removeLabelIds']:
                result = service.users().messages().modify(
                    userId='me',
                    id=email_id,
                    body=body
                ).execute()
                
                return f"Successfully organized email {email_id}"
            else:
                return f"No changes requested for email {email_id}"
            
        except Exception as e:
            return f"Error organizing email {email_id}: {str(e)}"

    def _get_or_create_label(self, service, label_name: str) -> Optional[str]:
        """Get existing label ID or create new label."""
        try:
            # List existing labels
            results = service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            # Check if label exists
            for label in labels:
                if label['name'].upper() == label_name.upper():
                    return label['id']
            
            # Create new label
            label_object = {
                'name': label_name,
                'messageListVisibility': 'show',
                'labelListVisibility': 'labelShow'
            }
            
            created_label = service.users().labels().create(
                userId='me',
                body=label_object
            ).execute()
            
            return created_label['id']
            
        except Exception as e:
            print(f"Error creating label {label_name}: {e}")
            return None

    def _get_label_id(self, service, label_name: str) -> Optional[str]:
        """Get label ID by name."""
        try:
            results = service.users().labels().list(userId='me').execute()
            labels = results.get('labels', [])
            
            for label in labels:
                if label['name'].upper() == label_name.upper():
                    return label['id']
            
            return None
            
        except Exception as e:
            print(f"Error getting label {label_name}: {e}")
            return None


class OAuth2GmailDeleteToolSchema(BaseModel):
    """Schema for OAuth2GmailDeleteTool input."""
    email_id: str = Field(description="ID of the email to delete")

class OAuth2GmailDeleteTool(OAuth2GmailToolBase):
    """OAuth2 version of the Gmail delete tool."""
    
    name: str = "OAuth2GmailDeleteTool"
    description: str = "Delete emails from Gmail using OAuth2 authentication"
    args_schema: type[BaseModel] = OAuth2GmailDeleteToolSchema

    def _run(self, email_id: str) -> str:
        """Delete email using Gmail API."""
        try:
            service = self._get_gmail_service()
            
            # Move to trash (Gmail doesn't permanently delete immediately)
            service.users().messages().trash(userId='me', id=email_id).execute()
            
            return f"Successfully moved email {email_id} to trash"
            
        except Exception as e:
            return f"Error deleting email {email_id}: {str(e)}"


class OAuth2SaveDraftToolSchema(BaseModel):
    """Schema for OAuth2SaveDraftTool input."""
    recipient: str = Field(description="Email address of the recipient")
    subject: str = Field(description="Subject line of the email")
    body: str = Field(description="Body content of the email")
    in_reply_to: Optional[str] = Field(default=None, description="Message ID this is a reply to")

class OAuth2SaveDraftTool(OAuth2GmailToolBase):
    """OAuth2 version of the Gmail draft saver tool."""
    
    name: str = "OAuth2SaveDraftTool"
    description: str = "Save email drafts in Gmail using OAuth2 authentication"
    args_schema: type[BaseModel] = OAuth2SaveDraftToolSchema

    def _run(self, recipient: str, subject: str, body: str, in_reply_to: Optional[str] = None) -> str:
        """Save email draft using Gmail API."""
        try:
            service = self._get_gmail_service()
            
            # Create message
            message = MIMEMultipart()
            message['To'] = recipient
            message['Subject'] = subject
            
            if in_reply_to:
                message['In-Reply-To'] = in_reply_to
                message['References'] = in_reply_to
            
            message.attach(MIMEText(body, 'plain'))
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Create draft
            draft_body = {
                'message': {
                    'raw': raw_message
                }
            }
            
            draft = service.users().drafts().create(
                userId='me',
                body=draft_body
            ).execute()
            
            return f"Successfully saved draft (ID: {draft['id']}) to {recipient}"
            
        except Exception as e:
            return f"Error saving draft to {recipient}: {str(e)}"


class OAuth2EmptyTrashToolSchema(BaseModel):
    """Schema for OAuth2EmptyTrashTool input."""
    pass  # No parameters needed

class OAuth2EmptyTrashTool(OAuth2GmailToolBase):
    """OAuth2 version of the empty trash tool."""
    
    name: str = "OAuth2EmptyTrashTool"
    description: str = "Empty Gmail trash using OAuth2 authentication"
    args_schema: type[BaseModel] = OAuth2EmptyTrashToolSchema

    def _run(self) -> str:
        """Empty Gmail trash using Gmail API."""
        try:
            service = self._get_gmail_service()
            
            # Empty trash
            service.users().messages().emptyTrash(userId='me').execute()
            
            return "Successfully emptied Gmail trash"
            
        except Exception as e:
            return f"Error emptying trash: {str(e)}" 


class OAuth2GetSentEmailsToolSchema(BaseModel):
    """Schema for OAuth2GetSentEmailsTool input."""
    max_emails: int = Field(
        default=100,
        description="Maximum number of sent emails to retrieve for analysis",
        ge=1, le=200
    )

class OAuth2GetSentEmailsTool(OAuth2GmailToolBase):
    """OAuth2 tool to fetch sent emails for user persona analysis."""
    
    name: str = "OAuth2GetSentEmailsTool"
    description: str = "Fetch sent emails from Gmail using OAuth2 authentication for user persona analysis"
    args_schema: type[BaseModel] = OAuth2GetSentEmailsToolSchema

    def _run(self, max_emails: int = 100) -> List[Tuple[str, str, str, str, Dict]]:
        """Fetch sent emails using Gmail API."""
        try:
            service = self._get_gmail_service()
            
            # Get sent messages
            results = service.users().messages().list(
                userId='me',
                q='in:sent',
                maxResults=max_emails
            ).execute()
            
            messages = results.get('messages', [])
            emails = []
            
            for msg in messages:
                # Get full message
                message = service.users().messages().get(
                    userId='me',
                    id=msg['id'],
                    format='full'
                ).execute()
                
                # Convert to email format
                email_data = self._gmail_message_to_email_format(message)
                emails.append(email_data)
            
            print(f"Fetched {len(emails)} sent emails for user persona analysis")
            return emails
            
        except Exception as e:
            print(f"Error fetching sent emails with OAuth2: {e}")
            return []


class OAuth2UserPersonaAnalyzerToolSchema(BaseModel):
    """Schema for OAuth2UserPersonaAnalyzerTool input."""
    sent_emails: List[Tuple[str, str, str, str, Dict]] = Field(
        description="List of sent emails to analyze for user persona"
    )

class OAuth2UserPersonaAnalyzerTool(OAuth2GmailToolBase):
    """OAuth2 tool to analyze sent emails and create user persona."""
    
    name: str = "OAuth2UserPersonaAnalyzerTool"
    description: str = "Analyze sent emails to create comprehensive user persona and facts"
    args_schema: type[BaseModel] = OAuth2UserPersonaAnalyzerToolSchema

    def _run(self, sent_emails: List[Tuple[str, str, str, str, Dict]]) -> str:
        """Analyze sent emails to build user persona."""
        try:
            if not sent_emails:
                return "No sent emails provided for analysis"
            
            # Extract user email address from OAuth2 credentials
            user_email = self.oauth_manager.get_user_email(self.user_id) if self.oauth_manager else "Unknown"
            
            # Analyze emails to build persona
            analysis = self._analyze_emails_for_persona(sent_emails, user_email)
            
            # Save to user_facts.txt
            facts_file = "knowledge/user_facts.txt"
            with open(facts_file, 'w', encoding='utf-8') as f:
                f.write(analysis)
            
            print(f"User persona analysis saved to {facts_file}")
            return f"User persona created and saved to {facts_file}. Analysis includes professional information, communication style, relationships, and personal details based on {len(sent_emails)} sent emails."
            
        except Exception as e:
            print(f"Error analyzing user persona: {e}")
            return f"Error creating user persona: {str(e)}"
    
    def _analyze_emails_for_persona(self, sent_emails: List[Tuple[str, str, str, str, Dict]], user_email: str) -> str:
        """Analyze sent emails to build comprehensive user persona."""
        
        # Initialize analysis variables
        recipients = set()
        domains = set()
        subjects = []
        bodies = []
        communication_patterns = {
            'formal_count': 0,
            'casual_count': 0,
            'professional_count': 0,
            'personal_count': 0
        }
        
        # Extract data from emails
        for subject, to_header, body, email_id, thread_info in sent_emails:
            subjects.append(subject)
            bodies.append(body)
            
            # Extract recipients and domains
            if to_header:
                # Handle multiple recipients
                to_emails = [email.strip() for email in to_header.replace(',', ';').split(';')]
                for email_addr in to_emails:
                    # Clean email address (remove names)
                    clean_email = email_addr.split('<')[-1].replace('>', '').strip()
                    if '@' in clean_email:
                        recipients.add(clean_email)
                        domain = clean_email.split('@')[-1]
                        domains.add(domain)
            
            # Analyze communication style
            body_lower = body.lower()
            subject_lower = subject.lower()
            
            # Formal indicators
            if any(word in body_lower for word in ['dear', 'sincerely', 'regards', 'best regards', 'yours truly']):
                communication_patterns['formal_count'] += 1
            
            # Casual indicators
            if any(word in body_lower for word in ['hey', 'thanks!', 'cheers', 'talk soon', 'catch up']):
                communication_patterns['casual_count'] += 1
            
            # Professional indicators
            if any(word in body_lower + subject_lower for word in ['meeting', 'project', 'deadline', 'proposal', 'contract', 'business', 'schedule', 'agenda']):
                communication_patterns['professional_count'] += 1
            
            # Personal indicators
            if any(word in body_lower + subject_lower for word in ['family', 'weekend', 'vacation', 'birthday', 'dinner', 'lunch', 'personal']):
                communication_patterns['personal_count'] += 1
        
        # Identify top domains and recipients
        top_domains = sorted(domains, key=lambda d: sum(1 for r in recipients if d in r), reverse=True)[:10]
        frequent_contacts = sorted(recipients, key=lambda r: sum(1 for email in sent_emails if r in email[1]), reverse=True)[:15]
        
        # Build persona analysis
        persona = f"""USER PERSONA AND FACTS
Generated from analysis of {len(sent_emails)} sent emails

=== BASIC INFORMATION ===
Email Address: {user_email}
Primary Communication Style: {self._determine_primary_style(communication_patterns)}

=== PROFESSIONAL PROFILE ===
Top Business Domains: {', '.join(top_domains[:5])}
Professional Communication: {communication_patterns['professional_count']} professional emails
Formal Communication: {communication_patterns['formal_count']} formal emails

Key Professional Topics:
{self._extract_professional_topics(subjects + bodies)}

=== RELATIONSHIPS AND CONTACTS ===
Frequent Email Contacts:
{self._format_contact_list(frequent_contacts[:10])}

Communication Patterns:
- Professional: {communication_patterns['professional_count']} emails
- Personal: {communication_patterns['personal_count']} emails  
- Formal: {communication_patterns['formal_count']} emails
- Casual: {communication_patterns['casual_count']} emails

=== PERSONAL INSIGHTS ===
{self._extract_personal_insights(bodies)}

=== COMMUNICATION STYLE ANALYSIS ===
{self._analyze_communication_style(bodies)}

=== TOPICS OF INTEREST ===
{self._extract_topics_of_interest(subjects + bodies)}

=== WORK AND INDUSTRY ===
{self._analyze_work_industry(subjects + bodies, top_domains)}

=== FAMILY AND PERSONAL LIFE ===
{self._extract_family_personal(bodies)}

Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Emails Analyzed: {len(sent_emails)}
"""
        return persona
    
    def _determine_primary_style(self, patterns: Dict[str, int]) -> str:
        """Determine primary communication style."""
        max_count = max(patterns.values())
        for style, count in patterns.items():
            if count == max_count:
                return style.replace('_count', '').title()
        return "Professional"
    
    def _extract_professional_topics(self, text_list: List[str]) -> str:
        """Extract professional topics from email content."""
        professional_keywords = [
            'project', 'meeting', 'deadline', 'proposal', 'contract', 'budget', 'team', 'client',
            'strategy', 'planning', 'development', 'marketing', 'sales', 'revenue', 'growth',
            'management', 'leadership', 'innovation', 'technology', 'software', 'product'
        ]
        
        topic_counts = {}
        for text in text_list:
            text_lower = text.lower()
            for keyword in professional_keywords:
                if keyword in text_lower:
                    topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
        
        # Get top topics
        top_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        return '\n'.join([f"- {topic.title()}: mentioned {count} times" for topic, count in top_topics])
    
    def _format_contact_list(self, contacts: List[str]) -> str:
        """Format contact list for readability."""
        return '\n'.join([f"- {contact}" for contact in contacts])
    
    def _extract_personal_insights(self, bodies: List[str]) -> str:
        """Extract personal insights from email bodies."""
        insights = []
        personal_indicators = {
            'location': ['located in', 'based in', 'live in', 'from', 'california', 'new york', 'texas', 'florida'],
            'family': ['wife', 'husband', 'kids', 'children', 'son', 'daughter', 'family', 'parents'],
            'interests': ['hobby', 'enjoy', 'love', 'passion', 'interested in', 'fan of'],
            'lifestyle': ['weekend', 'vacation', 'travel', 'exercise', 'gym', 'fitness']
        }
        
        for body in bodies:
            body_lower = body.lower()
            for category, keywords in personal_indicators.items():
                for keyword in keywords:
                    if keyword in body_lower:
                        # Extract sentence containing the keyword
                        sentences = body.split('.')
                        for sentence in sentences:
                            if keyword in sentence.lower():
                                insights.append(f"- {sentence.strip()}")
                                break
        
        # Remove duplicates and limit
        unique_insights = list(set(insights))[:10]
        return '\n'.join(unique_insights) if unique_insights else "- Limited personal information detected in sent emails"
    
    def _analyze_communication_style(self, bodies: List[str]) -> str:
        """Analyze communication style patterns."""
        style_analysis = []
        
        # Analyze greeting patterns
        greetings = []
        closings = []
        
        for body in bodies:
            lines = body.split('\n')
            if lines:
                # First few lines might contain greetings
                first_lines = ' '.join(lines[:3]).lower()
                if any(word in first_lines for word in ['hi', 'hello', 'hey', 'dear']):
                    greetings.append(first_lines[:50])
                
                # Last few lines might contain closings
                last_lines = ' '.join(lines[-3:]).lower()
                if any(word in last_lines for word in ['thanks', 'regards', 'best', 'sincerely']):
                    closings.append(last_lines[:50])
        
        # Analyze length and tone
        avg_length = sum(len(body) for body in bodies) / len(bodies) if bodies else 0
        
        style_analysis.append(f"- Average email length: {int(avg_length)} characters")
        
        if greetings:
            style_analysis.append(f"- Common greetings: {', '.join(set(greetings[:3]))}")
        
        if closings:
            style_analysis.append(f"- Common closings: {', '.join(set(closings[:3]))}")
        
        return '\n'.join(style_analysis)
    
    def _extract_topics_of_interest(self, text_list: List[str]) -> str:
        """Extract topics of interest from email content."""
        interest_keywords = [
            'AI', 'artificial intelligence', 'machine learning', 'technology', 'innovation',
            'startup', 'entrepreneurship', 'business', 'investment', 'venture',
            'health', 'fitness', 'travel', 'education', 'learning', 'development'
        ]
        
        topic_counts = {}
        for text in text_list:
            text_lower = text.lower()
            for keyword in interest_keywords:
                if keyword.lower() in text_lower:
                    topic_counts[keyword] = topic_counts.get(keyword, 0) + 1
        
        # Get top interests
        top_interests = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        return '\n'.join([f"- {interest}: mentioned {count} times" for interest, count in top_interests])
    
    def _analyze_work_industry(self, text_list: List[str], domains: List[str]) -> str:
        """Analyze work and industry information."""
        work_analysis = []
        
        # Industry indicators from domains
        industry_domains = {
            'tech': ['.io', 'github.com', 'google.com', 'microsoft.com', 'apple.com'],
            'finance': ['.bank', 'financial', 'capital', 'investment'],
            'healthcare': ['health', 'medical', 'hospital', 'clinic'],
            'education': ['.edu', 'university', 'school', 'college']
        }
        
        detected_industries = []
        for domain in domains[:10]:
            for industry, indicators in industry_domains.items():
                if any(indicator in domain.lower() for indicator in indicators):
                    detected_industries.append(industry)
        
        if detected_industries:
            work_analysis.append(f"- Likely industries: {', '.join(set(detected_industries))}")
        
        # Job title indicators
        title_keywords = ['CEO', 'CTO', 'manager', 'director', 'lead', 'senior', 'developer', 'engineer', 'analyst']
        found_titles = []
        
        for text in text_list:
            for title in title_keywords:
                if title.lower() in text.lower():
                    found_titles.append(title)
        
        if found_titles:
            unique_titles = list(set(found_titles))[:5]
            work_analysis.append(f"- Potential roles/titles mentioned: {', '.join(unique_titles)}")
        
        return '\n'.join(work_analysis) if work_analysis else "- Work/industry information not clearly detected"
    
    def _extract_family_personal(self, bodies: List[str]) -> str:
        """Extract family and personal life information."""
        family_info = []
        family_keywords = ['wife', 'husband', 'spouse', 'kids', 'children', 'son', 'daughter', 'family', 'parents', 'mom', 'dad']
        
        for body in bodies:
            body_lower = body.lower()
            for keyword in family_keywords:
                if keyword in body_lower:
                    # Extract context around the keyword
                    sentences = body.split('.')
                    for sentence in sentences:
                        if keyword in sentence.lower() and len(sentence.strip()) > 10:
                            family_info.append(f"- {sentence.strip()}")
                            break
        
        # Remove duplicates and limit
        unique_family_info = list(set(family_info))[:8]
        return '\n'.join(unique_family_info) if unique_family_info else "- Limited family/personal information detected in sent emails" 


class OAuth2UserPersonaUpdaterToolSchema(BaseModel):
    """Schema for OAuth2UserPersonaUpdaterTool input."""
    days_back: int = Field(default=30, description="Number of days back to analyze for updates")

class OAuth2UserPersonaUpdaterTool(OAuth2GmailToolBase):
    """OAuth2 tool to update existing user persona with recent email data."""
    
    name: str = "OAuth2UserPersonaUpdaterTool"
    description: str = "Update existing user persona with analysis of recent sent emails"
    args_schema: type[BaseModel] = OAuth2UserPersonaUpdaterToolSchema

    def _run(self, days_back: int = 30) -> str:
        """Update existing user persona with recent email data."""
        try:
            facts_file = "knowledge/user_facts.txt"
            
            # Check if existing persona exists
            existing_persona = ""
            if os.path.exists(facts_file):
                with open(facts_file, 'r', encoding='utf-8') as f:
                    existing_persona = f.read()
            
            if not existing_persona or len(existing_persona) < 50:
                return "No existing user persona found. Use the rebuild function to create a new persona first."
            
            # Fetch recent sent emails
            sent_email_tool = OAuth2GetSentEmailsTool(user_id=self.user_id, oauth_manager=self.oauth_manager)
            recent_emails = sent_email_tool._run(max_emails=50)
            
            if not recent_emails:
                return f"No sent emails found in the last {days_back} days to analyze for updates."
            
            # Extract user email address
            user_email = self.oauth_manager.get_user_email(self.user_id) if self.oauth_manager else "Unknown"
            
            # Analyze recent emails for updates
            recent_analysis = self._analyze_recent_emails(recent_emails, user_email, days_back)
            
            # Merge with existing persona
            updated_persona = self._merge_persona_data(existing_persona, recent_analysis, len(recent_emails))
            
            # Save updated persona
            with open(facts_file, 'w', encoding='utf-8') as f:
                f.write(updated_persona)
            
            print(f"User persona updated with analysis of {len(recent_emails)} recent emails")
            return f"User persona successfully updated with analysis of {len(recent_emails)} emails from the last {days_back} days. New insights have been merged with existing information."
            
        except Exception as e:
            print(f"Error updating user persona: {e}")
            return f"Error updating user persona: {str(e)}"
    
    def _analyze_recent_emails(self, recent_emails: List[Tuple[str, str, str, str, Dict]], user_email: str, days_back: int) -> Dict[str, Any]:
        """Analyze recent emails for persona updates."""
        
        # Initialize analysis variables
        new_recipients = set()
        new_domains = set()
        subjects = []
        bodies = []
        new_topics = {}
        recent_communication_patterns = {
            'formal_count': 0,
            'casual_count': 0,
            'professional_count': 0,
            'personal_count': 0
        }
        
        # Extract data from recent emails
        for subject, to_header, body, email_id, thread_info in recent_emails:
            subjects.append(subject)
            bodies.append(body)
            
            # Extract recipients and domains
            if to_header:
                to_emails = [email.strip() for email in to_header.replace(',', ';').split(';')]
                for email_addr in to_emails:
                    clean_email = email_addr.split('<')[-1].replace('>', '').strip()
                    if '@' in clean_email:
                        new_recipients.add(clean_email)
                        domain = clean_email.split('@')[-1]
                        new_domains.add(domain)
            
            # Analyze communication style
            body_lower = body.lower()
            subject_lower = subject.lower()
            
            # Count communication patterns
            if any(word in body_lower for word in ['dear', 'sincerely', 'regards', 'best regards', 'yours truly']):
                recent_communication_patterns['formal_count'] += 1
            if any(word in body_lower for word in ['hey', 'thanks!', 'cheers', 'talk soon', 'catch up']):
                recent_communication_patterns['casual_count'] += 1
            if any(word in body_lower + subject_lower for word in ['meeting', 'project', 'deadline', 'proposal', 'contract', 'business']):
                recent_communication_patterns['professional_count'] += 1
            if any(word in body_lower + subject_lower for word in ['family', 'weekend', 'vacation', 'birthday', 'dinner', 'personal']):
                recent_communication_patterns['personal_count'] += 1
            
            # Extract topics
            all_text = (subject + " " + body).lower()
            topic_keywords = [
                'AI', 'artificial intelligence', 'machine learning', 'technology', 'innovation',
                'startup', 'entrepreneurship', 'business', 'investment', 'venture',
                'project', 'meeting', 'team', 'client', 'strategy', 'development'
            ]
            
            for keyword in topic_keywords:
                if keyword.lower() in all_text:
                    new_topics[keyword] = new_topics.get(keyword, 0) + 1
        
        return {
            'new_recipients': new_recipients,
            'new_domains': new_domains,
            'recent_topics': new_topics,
            'recent_communication': recent_communication_patterns,
            'new_personal_insights': self._extract_recent_personal_insights(bodies),
            'recent_style_analysis': self._analyze_recent_style(bodies),
            'recent_work_insights': self._analyze_recent_work(subjects + bodies, list(new_domains)),
            'analysis_period': days_back,
            'total_recent_emails': len(recent_emails)
        }
    
    def _merge_persona_data(self, existing_persona: str, recent_analysis: Dict[str, Any], recent_email_count: int) -> str:
        """Merge recent analysis with existing persona data."""
        
        # Parse existing persona sections
        sections = {}
        current_section = None
        current_content = []
        
        for line in existing_persona.split('\n'):
            if line.startswith('=== ') and line.endswith(' ==='):
                if current_section:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.strip('= ')
                current_content = []
            else:
                current_content.append(line)
        
        if current_section:
            sections[current_section] = '\n'.join(current_content)
        
        # Update sections with recent data
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Add recent update section
        recent_updates = f"""
=== RECENT UPDATES ({recent_analysis['analysis_period']} days) ===
Last Update Analysis: {now}
Recent Emails Analyzed: {recent_email_count}

New Contacts (Last {recent_analysis['analysis_period']} Days):
{self._format_new_contacts(recent_analysis['new_recipients'])}

Recent Topics of Activity:
{self._format_recent_topics(recent_analysis['recent_topics'])}

Recent Communication Pattern:
- Professional: {recent_analysis['recent_communication']['professional_count']} emails
- Personal: {recent_analysis['recent_communication']['personal_count']} emails
- Formal: {recent_analysis['recent_communication']['formal_count']} emails
- Casual: {recent_analysis['recent_communication']['casual_count']} emails

Recent Personal Insights:
{recent_analysis['new_personal_insights']}

Recent Work/Professional Activity:
{recent_analysis['recent_work_insights']}
"""
        
        # Reconstruct the persona with updates
        updated_persona_parts = []
        
        # Keep basic information
        if 'BASIC INFORMATION' in sections:
            updated_persona_parts.append(f"=== BASIC INFORMATION ===\n{sections['BASIC INFORMATION']}")
        
        # Keep professional profile but note recent activity
        if 'PROFESSIONAL PROFILE' in sections:
            professional = sections['PROFESSIONAL PROFILE']
            professional += f"\n\nRecent Professional Activity ({recent_analysis['analysis_period']} days): {recent_analysis['recent_communication']['professional_count']} professional emails"
            updated_persona_parts.append(f"=== PROFESSIONAL PROFILE ===\n{professional}")
        
        # Update relationships with new contacts
        if 'RELATIONSHIPS AND CONTACTS' in sections:
            relationships = sections['RELATIONSHIPS AND CONTACTS']
            if recent_analysis['new_recipients']:
                relationships += f"\n\nNew Contacts (Last {recent_analysis['analysis_period']} Days):\n"
                relationships += '\n'.join([f"- {contact}" for contact in list(recent_analysis['new_recipients'])[:5]])
            updated_persona_parts.append(f"=== RELATIONSHIPS AND CONTACTS ===\n{relationships}")
        
        # Keep other existing sections
        for section_name, content in sections.items():
            if section_name not in ['BASIC INFORMATION', 'PROFESSIONAL PROFILE', 'RELATIONSHIPS AND CONTACTS', 'RECENT UPDATES']:
                updated_persona_parts.append(f"=== {section_name} ===\n{content}")
        
        # Add recent updates section
        updated_persona_parts.append(recent_updates)
        
        # Update footer
        updated_persona_parts.append(f"\nLast Updated: {now}")
        total_emails = sections.get('Total Emails Analyzed', 'Unknown')
        if 'Total Emails Analyzed:' in existing_persona:
            try:
                existing_count = int(existing_persona.split('Total Emails Analyzed:')[-1].strip().split()[0])
                total_emails = existing_count + recent_email_count
            except:
                total_emails = f"Unknown + {recent_email_count} recent"
        
        updated_persona_parts.append(f"Total Emails Analyzed: {total_emails}")
        
        return '\n\n'.join(updated_persona_parts)
    
    def _format_new_contacts(self, new_recipients: set) -> str:
        """Format new contacts for display."""
        if not new_recipients:
            return "- No new contacts in recent emails"
        
        sorted_contacts = sorted(list(new_recipients))[:10]
        return '\n'.join([f"- {contact}" for contact in sorted_contacts])
    
    def _format_recent_topics(self, recent_topics: Dict[str, int]) -> str:
        """Format recent topics for display."""
        if not recent_topics:
            return "- No significant topics detected in recent emails"
        
        sorted_topics = sorted(recent_topics.items(), key=lambda x: x[1], reverse=True)[:8]
        return '\n'.join([f"- {topic}: mentioned {count} times" for topic, count in sorted_topics])
    
    def _extract_recent_personal_insights(self, bodies: List[str]) -> str:
        """Extract personal insights from recent email bodies."""
        insights = []
        personal_indicators = {
            'location': ['located in', 'based in', 'live in', 'moving to', 'relocated'],
            'family': ['wife', 'husband', 'kids', 'children', 'son', 'daughter', 'family'],
            'interests': ['hobby', 'enjoy', 'started', 'learning', 'trying'],
            'lifestyle': ['weekend', 'vacation', 'travel', 'exercise', 'new']
        }
        
        for body in bodies:
            body_lower = body.lower()
            for category, keywords in personal_indicators.items():
                for keyword in keywords:
                    if keyword in body_lower:
                        sentences = body.split('.')
                        for sentence in sentences:
                            if keyword in sentence.lower() and len(sentence.strip()) > 10:
                                insights.append(f"- {sentence.strip()}")
                                break
        
        unique_insights = list(set(insights))[:5]
        return '\n'.join(unique_insights) if unique_insights else "- No new personal insights detected"
    
    def _analyze_recent_style(self, bodies: List[str]) -> str:
        """Analyze recent communication style."""
        if not bodies:
            return "- No recent style changes detected"
        
        avg_length = sum(len(body) for body in bodies) / len(bodies)
        return f"- Recent average email length: {int(avg_length)} characters"
    
    def _analyze_recent_work(self, text_list: List[str], domains: List[str]) -> str:
        """Analyze recent work and professional activity."""
        work_keywords = ['project', 'meeting', 'deadline', 'proposal', 'contract', 'client', 'team', 'launch', 'development']
        
        work_activity = {}
        for text in text_list:
            text_lower = text.lower()
            for keyword in work_keywords:
                if keyword in text_lower:
                    work_activity[keyword] = work_activity.get(keyword, 0) + 1
        
        if not work_activity:
            return "- No significant professional activity detected"
        
        top_activities = sorted(work_activity.items(), key=lambda x: x[1], reverse=True)[:5]
        return '\n'.join([f"- {activity.title()}: {count} mentions" for activity, count in top_activities]) 