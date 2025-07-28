# Common Errors and Solutions

## Startup Errors

### 1. Widget Key Conflicts
**Error**: `The widget with key "filter_max_emails" was created with a default value but also had its value set via the Session State API`
**Solution**: Already fixed - removed duplicate value setting

### 2. Missing Environment Variables
**Error**: `EMAIL_ADDRESS and APP_PASSWORD must be set in the environment`
**Solution**: Add to `.env` file or use OAuth2 authentication instead

### 3. OAuth2 Redirect URI Mismatch
**Error**: `redirect_uri_mismatch`
**Solution**: Ensure OAUTH_REDIRECT_URI matches Google Console settings (http://localhost:8505)

### 4. Missing Credentials File
**Error**: `OAuth2 credentials file not found: credentials.json`
**Solution**: Download from Google Cloud Console and place in project root

## Runtime Errors

### 5. Token Expiration
**Error**: `Token has been expired or revoked`
**Solution**: Re-authenticate the user through OAuth2 flow

### 6. Gmail API Quota Exceeded
**Error**: `Quota exceeded for quota metric`
**Solution**: Wait for quota reset or upgrade Gmail API limits

### 7. Stripe Webhook Signature Verification
**Error**: `Webhook signature verification failed`
**Solution**: Update STRIPE_WEBHOOK_SECRET in environment

### 8. File Permission Errors
**Error**: `Permission denied` when accessing logs or tokens
**Solution**: Check file permissions, especially in Docker

## Data Errors

### 9. JSON Decode Errors
**Error**: `JSONDecodeError` in user_sessions.json or users.json
**Solution**: Validate JSON files or reset corrupted files

### 10. Missing User Session
**Error**: `KeyError: 'user_id'`
**Solution**: Clear browser cookies and re-login

## Monitoring Commands

```bash
# Run with monitoring
./monitor_app.sh

# Check specific log files
tail -f logs/app.log
tail -f logs/system.log
tail -f logs/auth.log

# Watch for errors in real-time
tail -f logs/*.log | grep -i error

# Check recent errors
grep -i "error\|exception" logs/*.log | tail -20
```