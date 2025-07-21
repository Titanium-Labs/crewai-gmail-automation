# 📧 Email Setup Guide for Gmail CrewAI

This guide explains how to configure email sending for approval notifications.

## 🔧 Quick Setup (Recommended)

### Option 1: Use Existing Gmail Credentials
If you already have Gmail app password setup for email processing, the system will automatically use those credentials:

1. **Your existing credentials** (`EMAIL_ADDRESS` and `APP_PASSWORD`) will be used
2. **No additional setup needed** - emails will be sent automatically

### Option 2: Separate Email Credentials  
For dedicated email sending (recommended for production):

1. **Create a `.env` file** in the project root:
```env
# Email sending configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password

# Or use existing Gmail credentials
EMAIL_ADDRESS=your-email@gmail.com
APP_PASSWORD=your-app-password
```

2. **Get Gmail App Password**:
   - Go to [Google Account Settings](https://myaccount.google.com/)
   - Security → 2-Step Verification → App passwords
   - Create app password for "Mail"
   - Use that password in your `.env` file

## 🎯 How It Works

1. **When user registers** → Approval email sent to `articulatedesigns@gmail.com`
2. **When "Resend Approval Email" is clicked** → New email sent
3. **If email sending fails** → Request stored in admin panel for manual review

## ⚙️ Current Status

- ✅ **Email templates**: Professional HTML emails with approve/reject buttons
- ✅ **Fallback system**: If sending fails, shows in admin panel
- ✅ **User feedback**: Clear messages about email status
- ✅ **Security**: One-time approval tokens with expiration

## 🔍 Troubleshooting

### No emails received?
1. **Check spam folder** - automated emails sometimes go to spam
2. **Verify environment variables** - check `.env` file exists and has correct values
3. **Check terminal output** - look for email sending success/error messages
4. **Use admin panel** - view pending approvals even if emails fail

### Email sending errors?
- **"SMTP credentials not found"** → Add `SMTP_USERNAME` and `SMTP_PASSWORD` to `.env`
- **"Authentication failed"** → Check app password is correct
- **"Connection failed"** → Check internet connection and SMTP server settings

## 🚀 Testing

1. Register a new user
2. Check terminal for: `✅ Approval email sent successfully to articulatedesigns@gmail.com`
3. Check email in `articulatedesigns@gmail.com` inbox
4. Click approval buttons to test the workflow

## 📱 Admin Panel

Even without email setup, admins can:
- View all pending approval requests
- Manually approve/reject users
- See generated approval emails
- Copy approval links for manual sending 