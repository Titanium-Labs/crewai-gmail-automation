"""Email utility functions for parsing and formatting email content from Gmail API."""

import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup
import base64


def extract_header_value(headers: List[Dict[str, str]], header_name: str) -> str:
    """
    Extract header value from Gmail API headers list.
    
    Args:
        headers: List of header dictionaries from Gmail API
        header_name: Name of the header to extract (case-insensitive)
        
    Returns:
        Header value or empty string if not found
    """
    header_name_lower = header_name.lower()
    for header in headers:
        if header.get('name', '').lower() == header_name_lower:
            return header.get('value', '')
    return ''


def clean_email_body(email_body: str, max_length: int = 300) -> str:
    """
    Clean the email body by removing HTML tags, excessive whitespace, and limit length.
    
    Args:
        email_body: The raw email body content
        max_length: Maximum length of the cleaned body (default: 300)
        
    Returns:
        Cleaned and truncated email body text
    """
    if not email_body:
        return ""
    
    try:
        # Handle encoding issues by replacing problematic characters
        email_body = email_body.encode('utf-8', errors='replace').decode('utf-8')
        
        soup = BeautifulSoup(email_body, "html.parser")
        text = soup.get_text(separator=" ")  # Get text with spaces instead of <br/>
    except Exception:
        text = email_body  # Fallback to raw body if parsing fails

    # Remove excessive whitespace and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove common problematic unicode characters
    text = re.sub(r'[\u200c\u200d\u00ad]+', '', text)  # Remove zero-width and soft hyphen chars
    text = re.sub(r'[^\x00-\x7F\u00A0-\u024F\u1E00-\u1EFF]+', ' ', text)  # Keep basic Latin chars
    
    # Truncate if too long, keeping first part which usually has most important content
    if len(text) > max_length:
        text = text[:max_length] + "... [Content truncated for processing]"
    
    return text


def decode_base64_content(encoded_data: str) -> str:
    """
    Decode base64 encoded content from Gmail API.
    
    Args:
        encoded_data: Base64 URL-safe encoded string
        
    Returns:
        Decoded string content
    """
    try:
        return base64.urlsafe_b64decode(encoded_data).decode('utf-8', errors='replace')
    except Exception:
        return ''


def extract_body_from_payload(payload: Dict[str, Any], max_length: int = 250) -> str:
    """
    Extract email body from Gmail API payload structure.
    
    Args:
        payload: Gmail API message payload
        max_length: Maximum length for the extracted body
        
    Returns:
        Extracted email body text
    """
    body = ""
    
    if 'parts' in payload:
        for part in payload['parts']:
            mime_type = part.get('mimeType', '')
            body_data = part.get('body', {}).get('data', '')
            
            if not body_data:
                continue
                
            if mime_type == 'text/plain':
                decoded_body = decode_base64_content(body_data)
                if len(decoded_body) > 200:
                    decoded_body = decoded_body[:200] + "... [Part truncated]"
                body += decoded_body
            elif mime_type == 'text/html':
                html_body = decode_base64_content(body_data)
                cleaned_body = clean_email_body(html_body, max_length=200)
                body += cleaned_body
    else:
        # Single part message
        mime_type = payload.get('mimeType', '')
        body_data = payload.get('body', {}).get('data', '')
        
        if body_data:
            if mime_type == 'text/plain':
                body = decode_base64_content(body_data)
            elif mime_type == 'text/html':
                html_body = decode_base64_content(body_data)
                body = clean_email_body(html_body, max_length=200)
    
    # Final safety check
    if len(body) > max_length:
        body = body[:max_length] + "... [Email truncated]"
    
    return body.strip()


def format_thread_body(current_body: str, thread_messages: List[str], 
                      current_max_length: int = 1500, 
                      thread_max_length: int = 500,
                      total_max_length: int = 2500) -> str:
    """
    Format email body with thread history, applying length limits.
    
    Args:
        current_body: The current email's body
        thread_messages: List of previous messages in the thread
        current_max_length: Max length for current message
        thread_max_length: Max length for each thread message
        total_max_length: Max total length for entire output
        
    Returns:
        Formatted body with thread history
    """
    # Truncate current body if needed
    if len(current_body) > current_max_length:
        current_body = current_body[:current_max_length] + "... [Message truncated]"
    
    # Process thread messages
    if thread_messages:
        # Limit to 2 most recent thread messages
        thread_messages = thread_messages[:2]
        
        # Truncate each thread message
        truncated_threads = []
        for msg in thread_messages:
            if len(msg) > thread_max_length:
                truncated_threads.append(msg[:thread_max_length] + "... [Truncated]")
            else:
                truncated_threads.append(msg)
        
        # Combine current message with thread history
        full_body = current_body + "\n\n--- Previous Messages (Limited) ---\n" + "\n".join(truncated_threads)
    else:
        full_body = current_body
    
    # Final length check
    if len(full_body) > total_max_length:
        full_body = full_body[:total_max_length] + "... [Content truncated for processing]"
    
    return full_body


def get_gmail_label_ids() -> Dict[str, str]:
    """
    Get common Gmail system label IDs used by the Gmail API.
    
    Returns:
        Dictionary of label names to their system IDs
    """
    return {
        'INBOX': 'INBOX',
        'SENT': 'SENT',
        'DRAFT': 'DRAFT',
        'TRASH': 'TRASH',
        'SPAM': 'SPAM',
        'STARRED': 'STARRED',
        'IMPORTANT': 'IMPORTANT',
        'UNREAD': 'UNREAD',
        'CATEGORY_PERSONAL': 'CATEGORY_PERSONAL',
        'CATEGORY_SOCIAL': 'CATEGORY_SOCIAL',
        'CATEGORY_PROMOTIONS': 'CATEGORY_PROMOTIONS',
        'CATEGORY_UPDATES': 'CATEGORY_UPDATES',
        'CATEGORY_FORUMS': 'CATEGORY_FORUMS'
    }