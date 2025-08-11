# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gmail Automation with CrewAI is a sophisticated, production-ready email management system that uses AI agents to categorize, organize, respond to, and clean up Gmail inboxes automatically using OAuth2 authentication. The project features a comprehensive Stripe-powered subscription system, multi-user support, intelligent rate limiting, and robust error handling.

**Key Features:**
- Multi-agent CrewAI email processing workflow
- OAuth2 Gmail integration with token management
- Stripe subscription billing with webhook support
- Multi-user session management with admin controls
- Comprehensive logging and error tracking
- User persona analysis and learning capabilities
- Real-time email processing with usage limits

## Development Commands

### Setup and Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
crewai install
pip install -r requirements.txt
```

### Running the Application
```bash
# Web interface (recommended) - uses PORT from env (default: 8505)
streamlit run streamlit_app.py --server.port ${PORT:-8505}

# Or use the start script which handles port configuration
./start.sh

# Command line (requires CURRENT_USER_ID env var)
export CURRENT_USER_ID=your_user_id
crewai run
```

### Testing
```bash
# Run Python tests
pytest tests/test_logging.py -v

# Test logging system
python run_regression_tests.py

# PowerShell PSReadLine tests
Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose
```

### Log Management
```bash
# Manual log cleanup (removes files older than 30 days)
python scripts/cleanup_logs.py

# Windows batch script
cleanup_logs.bat
```

## Architecture

### Core Structure
The system follows a modular, event-driven architecture with the following layers:

- **CrewAI Framework**: Sequential agent workflow for email processing
- **OAuth2 Authentication Layer**: Multi-user Google OAuth2 with token persistence
- **Stripe Integration Layer**: Subscription management with webhook processing
- **Logging & Monitoring Layer**: Multi-file logging with rotation and Streamlit integration
- **Rate Limiting Layer**: Intelligent API quota management
- **Multi-User Session Management**: User registration, approval, and admin controls

### Key Components

1. **Email Processing Crew** (`src/gmail_crew_ai/crew.py`)
   - **Smart LLM Fallback**: Auto-switches between OpenAI, Anthropic, and DO-AI models
   - **Categorizer Agent**: Uses 11 predefined categories (PERSONAL, NEWSLETTER, PROMOTION, RECEIPT, IMPORTANT, YOUTUBE, GITHUB, SPONSORSHIPS, RECRUITMENT, COLD_EMAIL, EVENT_INVITATIONS, SOCIALS)
   - **Organizer Agent**: Applies Gmail labels, stars, and keeps emails in INBOX (never removes INBOX label)
   - **Response Generator**: Creates contextual draft responses with thread support and user persona matching
   - **Cleaner Agent**: Conservative deletion rules (only deletes promotions >2 days, newsletters >7 days)
   - **Summary Reporter**: Sends processing summary emails to user's inbox
   - **Feedback Processor**: Learns from user feedback and updates system rules

2. **OAuth2 Manager** (`src/gmail_crew_ai/auth/oauth2_manager.py`)
   - **Comprehensive Scopes**: Gmail read/modify/compose, userinfo, drive readonly, calendar
   - **Token Management**: Pickle-based storage in `tokens/` directory with auto-refresh
   - **Multi-User Support**: User ID mapping with primary user detection
   - **Credential Validation**: Automatic cleanup of corrupted tokens
   - **Error Recovery**: Graceful handling of expired/invalid credentials
   - **Docker Support**: Handles `/app/data` directory structure

3. **Gmail API Integration** (`src/gmail_crew_ai/tools/gmail_oauth_tools.py`)
   - **Rate Limiting**: Conservative 20,000 tokens/minute with sliding window tracking
   - **Email Body Cleaning**: HTML parsing, encoding handling, length limits (250 chars)
   - **Thread Support**: Proper In-Reply-To and References headers for email threading
   - **Enhanced Email Attributes** (lines 163-199): Captures all Gmail attributes:
     - `is_starred`: Email star status
     - `is_important`: Gmail importance marker
     - `is_unread`: Read/unread status
     - `has_attachment`: Attachment detection
     - `custom_labels`: User-created labels
   - **Attachment Detection** (lines 203-214): Recursive checking for attachments in email parts
   - **Label Management**: Create/apply labels while preserving INBOX visibility
   - **Search Flexibility**: Custom Gmail search queries with chronological sorting
   - **User Persona Analysis**: Analyzes sent emails to build comprehensive user profiles

4. **Billing System** (`src/gmail_crew_ai/billing/`)
   - **Subscription Manager**: Handles FREE (10 emails/day), BASIC ($9.99/mo, 100 emails/day), PREMIUM ($29.99/mo, unlimited)
   - **Usage Tracker**: Daily limits with admin override (unlimited for admins)
   - **Stripe Service**: Customer creation, subscription management, webhook processing
   - **Webhook Handler**: Secure signature verification for payment events
   - **Streamlit Integration**: User-friendly billing interface

5. **Logging Infrastructure** (`src/common/logger.py`)
   - **Multi-File Strategy**: `system.log`, `auth.log`, `billing.log`, `crew.log`, `app.log`
   - **Windows Compatibility**: Special handler for Windows file locking issues
   - **Streamlit Integration**: Custom handler routes logs to Streamlit UI
   - **Daily Rotation**: 14-day retention with automated cleanup
   - **Error Integration**: Links with ErrorLogger for comprehensive error tracking

### Configuration Files
- **`.env`**: API keys and Stripe configuration
- **`credentials.json`**: Google OAuth2 credentials (not in repo)
- **`config/agents.yaml`**: Agent definitions and prompts
- **`config/tasks.yaml`**: Task workflows and outputs

### Data Storage
- **`tokens/`**: OAuth2 tokens for authenticated users
- **`output/`**: Email processing results (JSON)
- **`logs/`**: Application logs with rotation
- **`users.json`**: User registration data
- **`usage.json`**: Daily usage tracking

## Implementation Deep Dive

### OAuth2 Security Best Practices
- **Comprehensive Scopes**: Includes Gmail, userinfo, drive readonly, calendar for future extensibility
- **Token Security**: Pickle-based storage with automatic corruption detection and cleanup
- **Multi-User Isolation**: Each user's tokens stored separately in `tokens/{user_id}_token.pickle`
- **Refresh Strategy**: Automatic token refresh with fallback to re-authentication flow
- **Docker Compatibility**: Handles both local and containerized deployment paths
- **Error Handling**: Graceful degradation when credentials are invalid/expired

**Critical Security Notes:**
- Never commit `credentials.json` or `.env` files
- OAuth2 tokens are stored with pickle serialization (consider encryption for production)
- Stripe webhooks use signature verification (webhook endpoints: `/stripe-webhook`)
- User authentication requires manual approval in production mode

### Email Processing Logic
The system uses a sophisticated, conservative approach to email management:

**Categorization Rules:**
- **PERSONAL**: From known contacts, personal email addresses
- **IMPORTANT**: Business emails, urgent communications, official documents
- **YOUTUBE**: Any emails from YouTube/Google (marked READ_ONLY)
- **PROMOTION**: Marketing emails, promotions, newsletters from businesses
- **RECEIPT**: Purchases, invoices, financial documents
- **GITHUB**: All GitHub-related notifications and updates
- **NEWSLETTER**: Subscribed content, weekly digests
- **RECRUITMENT**: Job-related emails, LinkedIn messages
- **SPONSORSHIPS**: Partnership and sponsorship inquiries
- **COLD_EMAIL**: Unsolicited business outreach
- **EVENT_INVITATIONS**: Meeting invites, calendar events

**Priority Enhancement Based on Email Attributes** (`tasks.yaml` lines 14-23):
- Starred emails → Priority increased by one level
- Gmail Important emails → Minimum MEDIUM priority
- Unread PERSONAL emails → Minimum MEDIUM priority
- Emails with attachments (business-related) → Minimum MEDIUM priority

**Organization Strategy:**
- **INBOX Preservation**: Never removes INBOX label - emails remain visible
- **Additive Labeling**: Applies category-specific labels (Personal, Important, etc.)
- **Enhanced Smart Starring** (`tasks.yaml` lines 33-41):
  - HIGH priority → Always star
  - MEDIUM priority → Star if PERSONAL or IMPORTANT
  - Already starred → Keep star (respects user's manual starring)
  - Gmail Important → Always star
  - Has attachments → Star if needs action
- **Read Management**: Marks all processed emails as read

**Deletion Rules (Conservative):**
- **PROMOTION**: Only if >2 days old AND LOW priority
- **NEWSLETTER**: Only if >7 days old AND LOW priority  
- **Never Delete**: PERSONAL, IMPORTANT, RECEIPT, YOUTUBE emails
- **Special Case**: Shutterfly emails always deleted (user preference)

### CrewAI Agent Optimization
**Task Sequencing:**
1. `@before_kickoff`: Email fetching with age calculation
2. `categorization_task`: File-based input/output for reliability
3. `organization_task`: Context-aware label/star application
4. `response_task`: Contextual research + draft generation
5. `cleanup_task`: Conservative deletion with safety checks
6. `summary_report_task`: User notification and feedback request
7. `feedback_monitoring_task`: Continuous learning from user input

**Performance Optimizations:**
- **File-Based Context**: Uses JSON files in `output/` for inter-agent communication
- **Error Recovery**: Each task can handle missing input files gracefully
- **LLM Fallback**: Auto-switches between OpenAI, Anthropic, and DO-AI models
- **Rate Limiting**: 20,000 tokens/minute with sliding window tracking

### Gmail API Usage Patterns
**Quota Management:**
- Conservative 250 quota units per user per second limit
- Intelligent batching for bulk operations
- Exponential backoff for rate limiting
- Request caching where appropriate

**Search Optimization:**
- Uses Gmail search syntax for efficient filtering
- Chronological sorting (newest first) for relevance
- Limits email body to 250 characters to prevent token overflow
- HTML content cleaning with BeautifulSoup

**Response Generation Triggers** (`tasks.yaml` lines 103-111):
- Starred emails (any category except YOUTUBE)
- Gmail Important emails (any category except YOUTUBE)
- Unread PERSONAL emails with HIGH/MEDIUM priority
- PERSONAL emails with HIGH/MEDIUM priority
- IMPORTANT category with HIGH/MEDIUM priority
- Emails with attachments needing acknowledgment
- Any HIGH priority email requiring response

**Thread Handling:**
- Proper In-Reply-To and References headers for email threading
- Thread ID preservation for draft responses
- Message ID tracking for conversation continuity

### Multi-User Session Management
**User Lifecycle:**
1. **Registration**: Users register with email (stored in `users.json`)
2. **Approval**: Admin approval required for new users
3. **OAuth**: Users authenticate via Google OAuth2 flow
4. **Processing**: Usage tracking with daily limits based on subscription
5. **Administration**: Admins have unlimited processing and user management

**Session Architecture:**
- Streamlit session state for UI persistence
- OAuth user ID mapping to internal user system
- Primary user auto-detection from `users.json`
- Admin controls for user management and system monitoring

### Subscription Tiers & Billing
- **FREE**: 10 emails/day, basic features
- **BASIC**: $9.99/mo, 100 emails/day, advanced features  
- **PREMIUM**: $29.99/mo, unlimited emails, priority support
- **ADMIN**: Unlimited emails, system management capabilities

**Stripe Integration:**
- Webhook-driven subscription updates
- Secure signature verification
- Customer portal integration
- Usage-based billing tracking

## Development Best Practices

### Adding New Email Categories
1. **Update Models** (`src/gmail_crew_ai/models.py:56`):
   ```python
   EmailCategoryType = Literal["NEWSLETTERS", "PROMOTIONS", "PERSONAL", "GITHUB", 
                              "SPONSORSHIPS", "RECRUITMENT", "COLD_EMAIL", 
                              "EVENT_INVITATIONS", "RECEIPTS_INVOICES", "YOUTUBE", "SOCIALS", "NEW_CATEGORY"]
   ```

2. **Update Categorizer Agent** (`config/agents.yaml`):
   - Add category description and examples to agent backstory
   - Include categorization rules in agent instructions

3. **Update Organization Rules** (`config/tasks.yaml:40-57`):
   - Add label mapping for new category
   - Define star/priority rules
   - Specify cleanup behavior

### Modifying Subscription Limits
1. **Update Plan Models** (`src/gmail_crew_ai/billing/models.py`):
   ```python
   SUBSCRIPTION_PLANS = {
       PlanType.NEW_TIER: SubscriptionPlan(
           name="New Tier",
           daily_email_limit=500,
           stripe_price_id="price_xxxxx"
       )
   }
   ```

2. **Update Subscription Manager** (`src/gmail_crew_ai/billing/subscription_manager.py:186`):
   - Add checkout session handling for new tier
   - Update upgrade/downgrade logic

3. **Test Integration**:
   ```bash
   python test_stripe_webhooks.py
   # Test webhook handling with: test_webhook_events.bat
   ```

### User Persona System Integration
The system includes sophisticated user persona analysis:

**Automatic Persona Building** (`gmail_oauth_tools.py:600-897`):
- Analyzes sent emails to build comprehensive user profiles
- Extracts communication style, professional context, relationships
- Updates persona with recent email analysis (30-day rolling window)
- Stores in `knowledge/user_facts.txt` for agent context

**Using Persona in Agents**:
- Response generator reads persona from `knowledge/user_facts.txt`
- Matches user's communication style and context
- References professional background and relationships
- Adapts tone based on recipient relationship

## Troubleshooting Guide

### OAuth2 Authentication Issues
**Problem**: "No valid credentials found for user"
1. Check `logs/auth.log` for detailed error messages
2. Verify `credentials.json` exists and has correct client configuration
3. Ensure OAuth consent screen includes all required scopes
4. Clear corrupted tokens: `rm tokens/{user_id}*_token.pickle`
5. Re-authenticate through web interface

**Problem**: "Refresh token missing"
1. Revoke app access in Google Account settings
2. Re-authenticate with `prompt=consent` to force refresh token
3. Check OAuth2 client type is "Desktop Application"

**Problem**: Token file corruption
```bash
python -c "
from src.gmail_crew_ai.auth.oauth2_manager import OAuth2Manager
oauth = OAuth2Manager()
removed = oauth.cleanup_corrupted_tokens()
print(f'Removed {removed} corrupted token files')
"
```

### Gmail API Rate Limiting
**Symptoms**: "Quota exceeded" or "Rate limit exceeded"
1. **Check Current Usage**:
   ```python
   from src.gmail_crew_ai.utils.rate_limiter import rate_limiter
   stats = rate_limiter.get_usage_stats()
   print(stats)
   ```

2. **Adjust Rate Limits** (`utils/rate_limiter.py:90`):
   ```python
   rate_limiter = RateLimiter(max_tokens_per_minute=15000)  # Reduce from 20000
   ```

3. **Enable Request Batching**: Use Gmail batch API for bulk operations
4. **Implement Exponential Backoff**: Built into OAuth2GmailToolBase

### CrewAI Processing Failures
**Problem**: Agent tasks failing or producing empty results

1. **Check Agent LLM Configuration** (`crew.py:31-66`):
   - Verify API keys are set: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DO_AI_API_KEY`
   - Check LLM fallback chain is working
   - Monitor token usage with rate limiter

2. **Debug File-Based Context**:
   ```bash
   # Check if fetched emails exist
   cat output/fetched_emails.json
   
   # Verify task outputs
   ls -la output/
   cat output/categorization_report.json
   ```

3. **Test Individual Agents**:
   ```python
   from src.gmail_crew_ai.crew import GmailCrewAi
   crew = GmailCrewAi()
   categorizer = crew.categorizer()
   # Test agent directly
   ```

### Streamlit UI Issues
**Problem**: Session state corruption or user authentication failures

1. **Clear Session State**:
   - Use "Clear Cache" in Streamlit menu
   - Or restart Streamlit server
   - Check `user_sessions.json` for session persistence

2. **Debug User Management**:
   ```python
   # Check user registration status
   import json
   with open('users.json', 'r') as f:
       users = json.load(f)
   print(users)
   ```

3. **OAuth Session Mapping Issues**:
   - Verify `st.session_state.current_user` matches OAuth user ID
   - Check primary user detection in `oauth2_manager.py:112-134`

### Stripe Billing Integration
**Problem**: Webhook events not processing correctly

1. **Verify Webhook Endpoint**:
   ```bash
   # Test webhook forwarding
   start_webhook_forwarding.bat
   # Use ngrok or similar for local development
   ```

2. **Check Webhook Signatures**:
   - Verify `STRIPE_WEBHOOK_SECRET` in `.env`
   - Check signature verification in webhook handler

3. **Debug Subscription Status**:
   ```python
   from src.gmail_crew_ai.billing.subscription_manager import SubscriptionManager
   from src.gmail_crew_ai.billing.stripe_service import StripeService
   
   stripe_service = StripeService()
   sub_manager = SubscriptionManager(stripe_service)
   subscription = sub_manager.get_user_subscription(user_id)
   print(subscription.to_dict())
   ```

### Logging and Error Tracking
**Problem**: Verbose logging or missing error details

1. **Configure Logging Level**:
   ```python
   # Use configure_logging.py to suppress verbose libraries
   from configure_logging import configure_logging
   configure_logging()
   ```

2. **Check Specific Log Files**:
   ```bash
   tail -f logs/auth.log      # OAuth issues
   tail -f logs/billing.log   # Stripe/subscription issues  
   tail -f logs/crew.log      # CrewAI processing issues
   tail -f logs/system.log    # System-level warnings/errors
   ```

3. **Windows File Locking Issues**:
   - Uses `WindowsSafeTimedRotatingFileHandler` for Windows compatibility
   - Enable delayed file opening with `delay=True`

## Environment Variables Reference

### Required API Keys
```bash
# LLM Provider Keys (at least one required)
OPENAI_API_KEY=sk-xxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxx  
DO_AI_API_KEY=xxxxx

# Stripe Integration
STRIPE_PUBLISHABLE_KEY=pk_xxxxx
STRIPE_SECRET_KEY=sk_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Application Configuration
CURRENT_USER_ID=user_123        # For CLI usage
MODEL=openai/gpt-4.1            # Default LLM model
GMAIL_SEARCH_QUERY=is:unread    # Default Gmail search
PORT=8505                       # Streamlit port
DEBUG=false                     # Debug mode flag
```

### File Structure Reference
```
/mnt/c/GitHub/crewai-gmail-automation/
├── src/
│   ├── gmail_crew_ai/
│   │   ├── auth/oauth2_manager.py          # OAuth2 implementation
│   │   ├── billing/                        # Stripe integration
│   │   ├── config/{agents,tasks}.yaml      # CrewAI configuration
│   │   ├── tools/gmail_oauth_tools.py      # Gmail API tools
│   │   ├── utils/rate_limiter.py           # API quota management
│   │   ├── crew.py                         # Main CrewAI workflow
│   │   └── models.py                       # Pydantic data models
│   └── common/logger.py                    # Centralized logging
├── streamlit_app.py                        # Web interface
├── tokens/                                 # OAuth2 token storage
├── output/                                 # Processing results
├── logs/                                   # Application logs
├── knowledge/                              # User persona data
├── users.json                              # User registration
├── usage.json                              # Daily usage tracking
└── credentials.json                        # Google OAuth2 credentials (not in repo)
```

## PowerShell PSReadLine Fix
The project includes fixes for PSReadLine compatibility issues with Warp terminal:
```powershell
# Install the fix
.\install-profile.ps1

# Test the fix  
Invoke-Pester tests/Test-PSReadLineFix.Tests.ps1 -Verbose
```

## Critical Implementation Notes

### Gmail API Gotchas
- **INBOX Label**: Never remove INBOX label - emails become invisible in main view
- **Thread IDs**: Use `thread_id` from Gmail API, not email `id` for proper threading
- **Search Syntax**: Use Gmail search operators (`is:unread`, `from:user@domain.com`, `subject:keyword`)
- **Body Truncation**: Email bodies limited to 250 chars to prevent LLM token overflow
- **Rate Limiting**: Conservative approach with 20K tokens/minute sliding window

### CrewAI Best Practices
- **File-Based Context**: Inter-agent communication via JSON files in `output/`
- **Error Recovery**: Each task checks for missing input files gracefully
- **LLM Fallback**: Smart model switching (DO-AI → OpenAI → Anthropic)
- **Memory Management**: Agents have `memory: false` to prevent context bloat
- **Sequential Processing**: Uses `Process.sequential` for predictable execution order

### Security Considerations
- **Token Storage**: OAuth tokens stored as pickle files (consider encryption for production)
- **Admin Privileges**: Admin users have unlimited email processing (999999 limit)
- **User Approval**: Manual approval required for new user registrations
- **Webhook Security**: Stripe webhooks use signature verification
- **Credential Management**: Never commit `credentials.json` or `.env` files

### Performance Optimization
- **Batch Processing**: Use Gmail batch API for multiple operations
- **Context Caching**: User personas cached in `knowledge/user_facts.txt`
- **Rate Limiting**: Intelligent token usage tracking with wait mechanisms
- **Email Filtering**: Process only relevant emails based on search criteria
- **Log Rotation**: Daily log rotation with 14-day retention to prevent disk bloat