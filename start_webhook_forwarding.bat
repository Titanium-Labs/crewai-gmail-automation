@echo off
echo 🚀 Starting Stripe webhook forwarding...
echo 📡 Forwarding to: localhost:5000/webhook/stripe
echo 🔐 Make sure to copy the webhook secret that appears below!
echo ===============================================
.\stripe.exe listen --forward-to localhost:5000/webhook/stripe
pause
