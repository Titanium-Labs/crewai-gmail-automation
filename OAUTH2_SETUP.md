# 🔐 OAuth2 Setup Guide for Gmail CrewAI

This guide will help you set up OAuth2 authentication for Gmail CrewAI, enabling multiple users to securely access their Gmail accounts through the application.

## 📋 Prerequisites

1. **Google Cloud Project**: You need a Google Cloud project to create OAuth2 credentials
2. **Python Environment**: Python 3.8+ with the required dependencies
3. **OpenAI API Key**: For AI email processing

## 🚀 Step 1: Install Dependencies

First, install all required dependencies:

```bash
pip install -r requirements.txt
```

Required packages:
- `streamlit==1.39.0` - Web UI framework
- `google-auth-oauthlib==1.2.0` - OAuth2 authentication
- `google-auth-httplib2==0.2.0` - HTTP library for Google APIs
- `google-api-python-client==2.147.0` - Gmail API client
- `crewai[tools]==0.80.0` - AI agent framework
- Other supporting packages

## 🔧 Step 2: Google Cloud Console Setup

### 2.1 Create or Select a Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your project ID for reference

### 2.2 Enable Gmail API

1. In the Google Cloud Console, go to **"APIs & Services" > "Library"**
2. Search for **"Gmail API"**
3. Click on it and press **"Enable"**

### 2.3 Configure OAuth Consent Screen

1. Go to **"APIs & Services" > "OAuth consent screen"**
2. Choose **"External"** (unless you have Google Workspace)
3. Fill in the required information:
   - **App name**: "Gmail CrewAI" (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
4. **Add scopes** (very important):
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/gmail.modify`
   - `https://www.googleapis.com/auth/gmail.compose`
5. **Add test users**: Add email addresses that will use the application
6. Save the configuration

### 2.4 Create OAuth2 Credentials

1. Go to **"APIs & Services" > "Credentials"**
2. Click **"Create Credentials" > "OAuth 2.0 Client ID"**
3. Choose **"Desktop Application"** as the application type
4. Give it a name like "Gmail CrewAI Desktop"
5. Click **"Create"**

### 2.5 Download Credentials

1. After creating the credentials, click the **download button** (⬇️)
2. Save the downloaded JSON file as `credentials.json` in your project root directory
3. **IMPORTANT**: Add `credentials.json` to your `.gitignore` file for security!

## 🔑 Step 3: Environment Variables

Create a `.env` file in your project root with the following:

```env
# Required for AI processing
OPENAI_API_KEY=your_openai_api_key_here

# The app will automatically handle OAuth2 user management
```

## 🏃‍♂️ Step 4: Run the Application

### Streamlit Web UI (Recommended)

```bash
streamlit run streamlit_app.py --server.port ${PORT:-8505}
```

This will open a web interface where you can:
- Authenticate multiple Gmail accounts
- Manage user sessions
- Process emails with AI
- View processing results

### Command Line

For OAuth2 authentication:

```bash
# Set the user ID for the session
export CURRENT_USER_ID=your_user_id

# Run the crew
python -m src.gmail_crew_ai.main
```

## 👥 Step 5: Multi-User Authentication

### First Time Setup

1. Launch the Streamlit app: `streamlit run streamlit_app.py --server.port ${PORT:-8505}`
2. Follow the on-screen setup instructions
3. Upload your `credentials.json` file if not already present
4. Click **"Add New User"**
5. Enter a unique name for the account (e.g., "john_work", "mary_personal")
6. Click **"Authenticate"**
7. Follow the Google OAuth2 flow:
   - Click the authorization link
   - Grant permissions in your browser
   - Copy the authorization code
   - Paste it back in the app

### Subsequent Uses

1. Launch the app
2. Select an existing authenticated user from the dropdown
3. Click **"Use Selected Account"**
4. Start processing emails!

## 🔒 Security Features

- **Token Storage**: OAuth2 tokens are stored locally in encrypted format
- **Automatic Refresh**: Tokens are automatically refreshed when needed
- **Revocation**: Users can revoke access at any time
- **Local Processing**: All AI processing happens locally with your OpenAI key
- **No Data Storage**: Email content is not permanently stored

## 🛠️ Troubleshooting

### "OAuth2 credentials file not found"
- Ensure `credentials.json` is in your project root
- Make sure you downloaded the correct file from Google Cloud Console

### "Authentication failed"
- Check that you've added yourself as a test user in the OAuth consent screen
- Verify that all required scopes are added
- Try refreshing authentication in the Settings tab

### "Gmail API not enabled"
- Go back to Google Cloud Console and ensure Gmail API is enabled
- Wait a few minutes for changes to propagate

### "Invalid scope" errors
- Double-check that you've added all three required scopes:
  - `gmail.readonly`
  - `gmail.modify`
  - `gmail.compose`

### Import errors
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (3.8+ required)

### Performance issues
- Processing time depends on the number of emails
- Consider reducing the number of emails processed at once
- Check your OpenAI API rate limits

## 📁 File Structure

After setup, your project should look like:

```
gmail-crewai/
├── credentials.json          # OAuth2 credentials (keep secret!)
├── tokens/                   # User tokens directory (auto-created)
│   ├── user1_abc123_token.pickle
│   └── user2_def456_token.pickle
├── output/                   # Processing results (auto-created)
├── streamlit_app.py         # Main web interface
├── requirements.txt         # Dependencies
├── .env                     # Environment variables
├── .gitignore              # Include credentials.json here!
└── src/gmail_crew_ai/      # Main application code
```

## 🎯 What's Next?

Once set up, you can:

1. **Process Multiple Accounts**: Add and manage multiple Gmail accounts
2. **AI Email Management**: Let AI categorize, organize, and respond to emails
3. **Custom Rules**: Modify the AI agents' behavior in the config files
4. **Automation**: Set up scheduled processing (future enhancement)

## 🆘 Getting Help

If you encounter issues:

1. Check the troubleshooting section above
2. Verify your Google Cloud Console setup
3. Review the application logs in the Streamlit interface
4. Check that all environment variables are set correctly

## 🔐 Security Best Practices

1. **Never commit `credentials.json`** to version control
2. **Regularly review** OAuth2 permissions in your Google account
3. **Revoke access** for users who no longer need it
4. **Keep dependencies updated** for security patches
5. **Use strong API keys** and rotate them regularly

---

**🎉 You're all set!** Your Gmail CrewAI with OAuth2 authentication is ready to help you manage emails across multiple accounts securely. 