# Gmail Automation with CrewAI 📧✨

[![YouTube Channel Subscribers](https://img.shields.io/youtube/channel/subscribers/UCApiD66gf36M9hZanbjgNaw?style=social)](https://www.youtube.com/@tonykipkemboi)
[![GitHub followers](https://img.shields.io/github/followers/tonykipkemboi?style=social)](https://github.com/tonykipkemboi)
[![Twitter Follow](https://img.shields.io/twitter/follow/tonykipkemboi?style=social)](https://twitter.com/tonykipkemboi)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat&logo=linkedin)](https://www.linkedin.com/in/tonykipkemboi/)

Gmail Automation with CrewAI is an intelligent email management system that uses AI agents to categorize, organize, respond to, and clean up your Gmail inbox automatically.

![Gmail Automation](./assets/gmail-automation.jpg)

## ✨ Features

![Stars](https://img.shields.io/github/stars/tonykipkemboi/crewai-gmail-automation?style=social)
![Last Commit](https://img.shields.io/github/last-commit/tonykipkemboi/crewai-gmail-automation) 
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

- **📋 Email Categorization**: Automatically categorizes emails into specific types (newsletters, promotions, personal, etc.)
- **🔔 Priority Assignment**: Assigns priority levels (HIGH, MEDIUM, LOW) based on content and sender
- **🏷️ Smart Organization**: Applies Gmail labels and stars based on categories and priorities
- **💬 Automated Responses**: Generates draft responses for important emails that need replies
- **📱 Slack Notifications**: Sends creative notifications for high-priority emails
- **🧹 Intelligent Cleanup**: Safely deletes low-priority emails based on age and category
- **🎬 YouTube Content Protection**: Special handling for YouTube-related emails

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/tonykipkemboi/crewai-gmail-automation.git
cd crewai-gmail-automation

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
crewai install
```

## ⚙️ Configuration

1. Create a `.env` file in the root directory with the following variables:

```
# Choose your LLM provider
# Gemini
MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY=your_gemini_api_key

# Or Ollama
# Download the model from https://ollama.com/library
MODEL=ollama/llama3-groq-tool-use # use ones that have tool calling capabilities

# Gmail credentials
EMAIL_ADDRESS=your_email@gmail.com
APP_PASSWORD=your_app_password

# Optional: Slack notifications
SLACK_WEBHOOK_URL=your_slack_webhook_url
```

<details>
<summary><b>🔑 How to create a Gmail App Password</b></summary>

1. Go to your Google Account settings at [myaccount.google.com](https://myaccount.google.com/)
2. Select **Security** from the left navigation panel
3. Under "Signing in to Google," find and select **2-Step Verification** (enable it if not already enabled)
4. Scroll to the bottom and find **App passwords**
5. Select **Mail** from the "Select app" dropdown
6. Select **Other (Custom name)** from the "Select device" dropdown
7. Enter `Gmail CrewAI` as the name
8. Click **Generate**
9. Copy the 16-character password that appears (spaces will be removed automatically)
10. Paste this password in your `.env` file as the `APP_PASSWORD` value
11. Click **Done**

**Note**: App passwords can only be created if you have 2-Step Verification enabled on your Google account.
</details>

<details>
<summary><b>🔗 How to create a Slack Webhook URL</b></summary>

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click **Create New App**
3. Select **From scratch**
4. Enter `Gmail Notifications` as the app name
5. Select your workspace and click **Create App**
6. In the left sidebar, find and click on **Incoming Webhooks**
7. Toggle the switch to **Activate Incoming Webhooks**
8. Click **Add New Webhook to Workspace**
9. Select the channel where you want to receive notifications
10. Click **Allow**
11. Find the **Webhook URL** section and copy the URL that begins with `https://hooks.slack.com/services/`
12. Paste this URL in your `.env` file as the `SLACK_WEBHOOK_URL` value

**Customizing your Slack app (optional):**
1. Go to **Basic Information** in the left sidebar
2. Scroll down to **Display Information**
3. Add an app icon and description
4. Click **Save Changes**

**Note**: You need admin permissions or the ability to install apps in your Slack workspace.
</details>

## 📧 How It Works

This application uses the IMAP (Internet Message Access Protocol) to securely connect to your Gmail account and manage your emails. Here's how it works:

<details>
<summary><b>🔄 IMAP Connection Process</b></summary>

1. **Secure Connection**: The application establishes a secure SSL connection to Gmail's IMAP server (`imap.gmail.com`).

2. **Authentication**: It authenticates using your email address and app password (not your regular Google password).

3. **Mailbox Access**: Once authenticated, it can access your inbox and other mailboxes to:
   - Read unread emails
   - Apply labels
   - Move emails to trash
   - Save draft responses

4. **Safe Disconnection**: After each operation, the connection is properly closed to maintain security.

IMAP allows the application to work with your emails while they remain on Google's servers, unlike POP3 which would download them to your device. This means you can still access all emails through the regular Gmail interface.

**Security Note**: Your credentials are only stored locally in your `.env` file and are never shared with any external services.
</details>

## 🔍 Usage

Run the application with:

```bash
crewai run
```

You'll be prompted to enter the number of emails to process (default is 5).

The application will:
1. 📥 Fetch your unread emails
2. 🔎 Categorize them by type and priority
3. ⭐ Apply appropriate labels and stars
4. ✏️ Generate draft responses for important emails
5. 🔔 Send Slack notifications for high-priority items
6. 🗑️ Clean up low-priority emails based on age

## 📊 Output

The application generates detailed reports in the `output` directory:
- `categorization_report.txt`: Details about each email's category and priority
- `organization_report.txt`: Actions taken to organize emails
- `response_report.txt`: Draft responses created
- `notification_report.txt`: Slack notifications sent
- `cleanup_report.txt`: Emails deleted and preserved

## 🌟 Special Features

- **📅 Date-Based Cleanup**: Emails are only deleted if they meet age thresholds based on category
- **🎬 YouTube Protection**: All YouTube-related emails are preserved regardless of age (am a YouTube partner, so this is important to me)
- **✍️ Smart Response Generation**: Responses are tailored to the email context and include proper formatting
- **💡 Creative Slack Notifications**: Fun, attention-grabbing notifications for important emails

## 👥 Contributing

Contributions are welcome! Please feel free to submit a [Pull Request](https://github.com/tonykipkemboi/crewai-gmail-automation/pulls).

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📚 References

- [CrewAI](https://github.com/crewAIInc/crewAI/)
- [IMAP Protocol for Gmail](https://support.google.com/mail/answer/7126229)
- [Slack API](https://api.slack.com/messaging/webhooks)
- [Ollama](https://ollama.com/library)
- [Gemini](https://ai.google.com/gemini-api)

