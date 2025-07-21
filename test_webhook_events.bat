@echo off
echo 🧪 Stripe Webhook Event Testing
echo ================================
echo.
echo Choose an event to trigger:
echo 1. Customer Subscription Created
echo 2. Invoice Payment Succeeded  
echo 3. Invoice Payment Failed
echo 4. Customer Subscription Deleted
echo 5. Trigger All Events
echo.
set /p choice=Enter your choice (1-5): 

if "%choice%"=="1" (
    echo Triggering: customer.subscription.created
    .\stripe.exe trigger customer.subscription.created
)
if "%choice%"=="2" (
    echo Triggering: invoice.payment_succeeded
    .\stripe.exe trigger invoice.payment_succeeded
)
if "%choice%"=="3" (
    echo Triggering: invoice.payment_failed
    .\stripe.exe trigger invoice.payment_failed
)
if "%choice%"=="4" (
    echo Triggering: customer.subscription.deleted
    .\stripe.exe trigger customer.subscription.deleted
)
if "%choice%"=="5" (
    echo Triggering all events...
    .\stripe.exe trigger customer.subscription.created
    timeout /t 2 >nul
    .\stripe.exe trigger invoice.payment_succeeded
    timeout /t 2 >nul
    .\stripe.exe trigger invoice.payment_failed
    timeout /t 2 >nul
    .\stripe.exe trigger customer.subscription.deleted
)

echo.
echo ✅ Event(s) triggered! Check your webhook test server for output.
pause
