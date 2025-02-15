# Gmail Automation with CrewAI

![Gmail Automation](./assets/gmail-automation.jpg)

This project uses [CrewAI](https://crewai.com) to automate Gmail inbox management through a multi-agent system. The agents work together to categorize, organize, and respond to emails intelligently.

## Features

- **Smart Email Categorization:**
  - SOCIALS (LinkedIn, Community updates)
  - GITHUB (Repository notifications, Security alerts)
  - RECEIPTS_INVOICES (Purchases, Billing)
  - PROMOTIONS (Marketing, Sales)
  - NEWSLETTERS (Updates, Digests)
  - RECRUITMENT (Job opportunities)
  - SPONSORSHIPS (Partnership offers)
  - PERSONAL (Direct communications)
  - EVENT_INVITATIONS (Webinars, Conferences)
  - COLD_EMAIL (Unsolicited pitches)

- **Priority-based Organization:**
  - HIGH: Response within 24 hours
  - MEDIUM: Handle within 48-72 hours
  - LOW: Handle when convenient

- **Automated Responses:**
  - Context-aware reply drafts
  - Thread-aware responses
  - Category-specific templates
  - Professional formatting

## Installation

1. **Prerequisites:**
   - Python >=3.10 <3.13
   - Gmail account with IMAP enabled; create an app password here: (https://myaccount.google.com/u/3/apppasswords)
   - App password for Gmail

2. **Setup:**

    - Clone this repository
        ```bash
        git clone https://github.com/tonykipkemboi/crewai-gmail-automation.git
        ```
    - Install dependencies by running:
        ```bash
        crewai install
        ```

3. **Configuration:**
   Create a `.env` file with:
   ```text
   GEMINI_API_KEY=your_key_here (YOU CAN USE OPENAI_API_KEY AS WELL)
   EMAIL_ADDRESS=your.email@gmail.com
   APP_PASSWORD=your_gmail_app_password
   ```

## Usage

Run the automation:
```bash
crewai run
```

The system will:
1. Fetch unread emails
2. Categorize them by type and priority
3. Apply appropriate labels
4. Create response drafts for important emails

## Output

The system generates three reports:
- `output/categorization_report.txt`: Email categorization details
- `output/organization_report.txt`: Applied labels and organization
- `output/response_report.txt`: Generated email responses

## Customization

- `src/gmail_crew_ai/config/tasks.yaml`: Modify categorization rules and response templates
- `src/gmail_crew_ai/config/agents.yaml`: Adjust agent behaviors
- `src/gmail_crew_ai/tools/gmail_tools.py`: Customize Gmail interactions

## Support

For questions or issues:
- [Project Issues](https://github.com/tonykipkemboi/crewai-gmail-automation/issues)
- [CrewAI Documentation](https://docs.crewai.com)
- [Join CrewAI Community](https://community.crewai.com)

## License

[MIT License](LICENSE)
