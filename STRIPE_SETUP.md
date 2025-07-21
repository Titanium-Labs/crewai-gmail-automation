# Stripe Subscription Setup Guide

This guide will help you set up Stripe subscriptions for your Gmail CrewAI application.

## 1. Create Stripe Account

1. Go to [stripe.com](https://stripe.com) and create an account
2. Complete the account verification process
3. Access your Stripe Dashboard

## 2. Set up Products and Prices

### Create Products

1. Go to **Products** in your Stripe Dashboard
2. Click **Add Product**
3. Create these products:

#### Basic Plan
- **Name**: Gmail CrewAI Basic
- **Description**: 100 emails processed per day with advanced features
- **Statement descriptor**: GMAIL_CREW_BASIC

#### Premium Plan
- **Name**: Gmail CrewAI Premium  
- **Description**: 1000 emails processed per day with all features
- **Statement descriptor**: GMAIL_CREW_PREMIUM

### Create Prices

For each product, create a recurring price:

#### Basic Plan Price
- **Price**: $9.99 USD
- **Billing period**: Monthly
- **Payment type**: Recurring
- **Copy the Price ID** (starts with `price_`)

#### Premium Plan Price
- **Price**: $29.99 USD
- **Billing period**: Monthly
- **Payment type**: Recurring
- **Copy the Price ID** (starts with `price_`)

## 3. Configure Webhooks

1. Go to **Developers** → **Webhooks** in your Stripe Dashboard
2. Click **Add endpoint**
3. **Endpoint URL**: `https://your-domain.com/webhook/stripe` (update with your actual domain)
4. **Listen to**: Select these events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
5. Click **Add endpoint**
6. **Copy the webhook secret** (starts with `whsec_`)

## 4. Get API Keys

1. Go to **Developers** → **API Keys** in your Stripe Dashboard
2. Copy your **Publishable key** (starts with `pk_test_` or `pk_live_`)
3. Copy your **Secret key** (starts with `sk_test_` or `sk_live_`)

## 5. Configure Environment Variables

Add these variables to your `.env` file:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Stripe Price IDs (from step 2)
STRIPE_BASIC_PRICE_ID=price_1234567890abcdef
STRIPE_PREMIUM_PRICE_ID=price_0987654321fedcba
```

## 6. Test the Integration

### Test Mode
- Use test credit cards: `4242 4242 4242 4242`
- Use any future expiration date
- Use any 3-digit CVC
- Use any 5-digit ZIP code

### Production Mode
- Switch to live keys when ready for production
- Update webhook endpoint to production URL
- Test with real payment methods

## 7. Subscription Plans

The application includes these subscription tiers:

### Free Plan
- **Price**: $0/month
- **Email Limit**: 10 emails/day
- **Features**: Basic email categorization, Gmail integration

### Basic Plan
- **Price**: $9.99/month
- **Email Limit**: 100 emails/day
- **Features**: All Free features + automated responses, Slack notifications, email cleanup

### Premium Plan
- **Price**: $29.99/month
- **Email Limit**: 1000 emails/day
- **Features**: All Basic features + priority support, custom email rules, analytics dashboard

## 8. Webhook Handler

The application includes a webhook handler that processes these events:

- **Subscription Created**: Activates user subscription
- **Subscription Updated**: Updates subscription status and billing period
- **Subscription Deleted**: Cancels user subscription and reverts to free plan
- **Payment Succeeded**: Confirms successful payment and activates subscription
- **Payment Failed**: Marks subscription as past due

## 9. Security Considerations

- **Webhook Verification**: All webhooks are verified using Stripe's signature verification
- **Environment Variables**: All sensitive data is stored in environment variables
- **Test Mode**: Use test keys during development
- **HTTPS**: Ensure your webhook endpoint uses HTTPS in production

## 10. Troubleshooting

### Common Issues

1. **Webhook Not Receiving Events**
   - Check webhook endpoint URL is correct
   - Verify webhook secret is correct
   - Check firewall/security settings

2. **Payment Processing Fails**
   - Verify Stripe keys are correct
   - Check test card numbers are valid
   - Ensure webhook endpoint is accessible

3. **Subscription Not Activating**
   - Check webhook handler is processing events
   - Verify user exists in the system
   - Check subscription status in Stripe Dashboard

### Debug Mode

To debug webhook events:

1. Enable webhook event logging in Stripe Dashboard
2. Check the webhook endpoint logs
3. Test webhook events using Stripe CLI:

```bash
stripe listen --forward-to localhost:8501/webhook/stripe
```

## 11. Going Live

When ready for production:

1. **Switch to Live Keys**
   - Update `STRIPE_SECRET_KEY` to live key
   - Update `STRIPE_PUBLISHABLE_KEY` to live key
   - Update `STRIPE_WEBHOOK_SECRET` to live webhook secret

2. **Update Webhook Endpoint**
   - Change webhook URL to production domain
   - Test webhook delivery

3. **Test Payment Flow**
   - Test with real payment methods
   - Verify subscription activation
   - Test cancellation flow

4. **Monitor Payments**
   - Set up payment monitoring
   - Configure failed payment alerts
   - Monitor subscription metrics

## Support

For Stripe-related issues:
- Check the [Stripe Documentation](https://stripe.com/docs)
- Use the [Stripe CLI](https://stripe.com/docs/stripe-cli) for testing
- Contact [Stripe Support](https://support.stripe.com) for payment issues

For application-specific issues:
- Check the application logs
- Verify environment variables are set correctly
- Ensure webhook endpoint is accessible
