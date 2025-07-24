#!/usr/bin/env python3
"""
Test script to verify logging configuration and rotation.

This script tests the enhanced logging system with multiple log files
and TimedRotatingFileHandler configuration.
"""

import sys
import os
import time
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    from common.logger import get_logger, exception_info
    
    # Test different logger instances
    app_logger = get_logger('gmail_crew_ai.app')
    system_logger = get_logger('gmail_crew_ai.system')
    auth_logger = get_logger('gmail_crew_ai.auth')
    billing_logger = get_logger('gmail_crew_ai.billing')
    crew_logger = get_logger('gmail_crew_ai.crew')
    
    print("🔍 Testing logging configuration...")
    print(f"📅 Test started at: {datetime.now().isoformat()}")
    
    # Test general application logging
    app_logger.info("✅ Application logger test - INFO level")
    app_logger.debug("🔍 Application logger test - DEBUG level (should not appear in logs)")
    
    # Test system logging (warnings and errors)
    system_logger.warning("⚠️ System logger test - WARNING level")
    system_logger.error("❌ System logger test - ERROR level")
    
    # Test authentication logging
    auth_logger.info("🔐 Authentication logger test - OAuth2 simulation")
    auth_logger.info("✅ User authentication successful - user_123")
    
    # Test billing logging
    billing_logger.info("💳 Billing logger test - subscription event")
    billing_logger.info("📊 Usage tracking - user processed 5 emails")
    
    # Test crew logging
    crew_logger.info("🤖 CrewAI logger test - agent processing")
    crew_logger.info("📧 Email classification started")
    crew_logger.info("🏷️ Applied labels to 3 emails")
    
    # Test exception logging
    try:
        # Intentionally cause an exception
        result = 1 / 0
    except Exception:
        exception_info(system_logger, "Testing exception logging with traceback")
    
    print("\n📁 Checking log files created...")
    
    logs_dir = "logs"
    if os.path.exists(logs_dir):
        for log_file in os.listdir(logs_dir):
            file_path = os.path.join(logs_dir, log_file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                print(f"📄 {log_file}: {size} bytes")
    else:
        print("❌ Logs directory not found!")
    
    print("\n✅ Logging test completed successfully!")
    print("📋 Check the following log files:")
    print("   - logs/app.log (general application logs)")
    print("   - logs/system.log (warnings and errors)")
    print("   - logs/auth.log (authentication events)")
    print("   - logs/billing.log (billing activities)")
    print("   - logs/crew.log (CrewAI processing)")
    
    print("\n🔄 Log rotation info:")
    print("   - Files rotate daily at midnight")
    print("   - 14 days of rotated logs are kept")
    print("   - Rotated files use YYYY-MM-DD suffix")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running this from the project root directory")
    sys.exit(1)
except Exception as e:
    print(f"❌ Test failed: {e}")
    sys.exit(1)
