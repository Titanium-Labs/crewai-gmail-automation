# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gmail Automation with CrewAI is an intelligent email management system that uses AI agents to categorize, organize, respond to, and clean up Gmail inboxes automatically using OAuth2 authentication. The project includes a Stripe-powered subscription system with usage-based limits.

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
# Web interface (recommended)
streamlit run streamlit_app.py

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
- **CrewAI Framework**: Uses agents and tasks for email processing
- **OAuth2 Authentication**: Multi-user support via Google OAuth2
- **Stripe Integration**: Subscription management with webhooks
- **Logging System**: Multi-file logging with automatic rotation

### Key Components

1. **Email Processing Crew** (`src/gmail_crew_ai/crew.py`)
   - Categorizer Agent: Classifies emails by type and priority
   - Organizer Agent: Applies Gmail labels and stars
   - Response Generator: Creates draft responses
   - Cleaner Agent: Manages email deletion and trash

2. **OAuth2 Manager** (`src/gmail_crew_ai/auth/oauth2_manager.py`)
   - Handles Google authentication flow
   - Token storage and refresh
   - Multi-user session management

3. **Billing System** (`src/gmail_crew_ai/billing/`)
   - Stripe subscription management
   - Usage tracking with daily limits
   - Webhook processing for payment events

4. **Logging Infrastructure** (`src/common/logger.py`)
   - 5 separate log files with daily rotation
   - 14-day retention policy
   - Automatic cleanup via GitHub Actions

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

## Key Considerations

### Security
- Never commit `credentials.json` or `.env` files
- OAuth2 tokens are stored locally with encryption
- Stripe webhooks use signature verification

### Email Processing Rules
- YouTube emails are marked READ_ONLY
- Promotions older than 2 days are deleted
- Newsletters older than 7 days are deleted (unless HIGH priority)
- Receipts and important documents are archived, not deleted

### Subscription Tiers
- Free: 10 emails/day
- Basic ($9.99/mo): 100 emails/day
- Premium ($29.99/mo): Unlimited

### PowerShell PSReadLine Fix
The project includes fixes for PSReadLine compatibility issues with Warp terminal. Use `install-profile.ps1` to apply the fix.

## Common Tasks

### Adding New Email Categories
1. Update categorizer agent in `config/agents.yaml`
2. Add handling logic in `src/gmail_crew_ai/models.py`
3. Update organization rules in organizer agent

### Modifying Subscription Limits
1. Edit limits in `src/gmail_crew_ai/billing/subscription_manager.py`
2. Update Stripe products in dashboard
3. Test webhook handling with `test_stripe_webhooks.py`

### Debugging OAuth Issues
1. Check `logs/auth.log` for authentication errors
2. Verify Google Cloud Console settings
3. Ensure correct scopes in OAuth consent screen
4. Check token expiration in `tokens/` directory

### Logging Configuration
The project includes logging fixes to reduce verbose output:
- `configure_logging.py`: Suppresses verbose third-party library logging
- `.streamlit/config.toml`: Optimized for threading and reduced warnings
- Streamlit ScriptRunContext warnings automatically filtered during CrewAI execution
- Test logging fixes with: `python3 test_logging_fixes.py`