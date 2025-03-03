# Gmail CrewAI

Gmail CrewAI is an intelligent email management system that uses AI agents to categorize, organize, respond to, and clean up your Gmail inbox automatically.

![Gmail Automation](./assets/gmail-automation.jpg)
## Features

- **Email Categorization**: Automatically categorizes emails into specific types (newsletters, promotions, personal, etc.)
- **Priority Assignment**: Assigns priority levels (HIGH, MEDIUM, LOW) based on content and sender
- **Smart Organization**: Applies Gmail labels and stars based on categories and priorities
- **Automated Responses**: Generates draft responses for important emails that need replies
- **Slack Notifications**: Sends creative notifications for high-priority emails
- **Intelligent Cleanup**: Safely deletes low-priority emails based on age and category
- **YouTube Content Protection**: Special handling for YouTube-related emails

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/gmail_crew_ai.git
cd gmail_crew_ai

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
crewai install
```

## Configuration

1. Create a `.env` file in the root directory with the following variables:

```
# Choose your LLM provider
# Gemini
MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your_gemini_api_key

# Or Ollama
MODEL=ollama/llama3-groq-tool-use # use ones that have tool calling capabilities

# Gmail credentials
EMAIL_ADDRESS=your_email@gmail.com
APP_PASSWORD=your_app_password

# Optional: Slack notifications
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

2. To get an App Password for Gmail:
   - Go to your `Google Account > Security`
   - Enable `2-Step Verification` if not already enabled
   - Go to `App passwords`
   - Select `Mail` and `Other (Custom name)`
   - Enter `Gmail CrewAI` and click `Generate`
   - Copy the 16-character password

## Usage

Run the application with:

```bash
crewai run
```

You'll be prompted to enter the number of emails to process (default is 5).

The application will:
1. Fetch your unread emails
2. Categorize them by type and priority
3. Apply appropriate labels and stars
4. Generate draft responses for important emails
5. Send Slack notifications for high-priority items
6. Clean up low-priority emails based on age

## Output

The application generates detailed reports in the `output` directory:
- `categorization_report.txt`: Details about each email's category and priority
- `organization_report.txt`: Actions taken to organize emails
- `response_report.txt`: Draft responses created
- `notification_report.txt`: Slack notifications sent
- `cleanup_report.txt`: Emails deleted and preserved

## Special Features

- **Date-Based Cleanup**: Emails are only deleted if they meet age thresholds based on category
- **YouTube Protection**: All YouTube-related emails are preserved regardless of age
- **Smart Response Generation**: Responses are tailored to the email context and include proper formatting
- **Creative Slack Notifications**: Fun, attention-grabbing notifications for important emails

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
