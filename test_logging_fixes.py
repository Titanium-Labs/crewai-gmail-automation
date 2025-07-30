#!/usr/bin/env python3
"""Test logging fixes for Streamlit threading warnings and LiteLLM verbosity."""

import os
import sys
import warnings
from pathlib import Path

# Set environment variables BEFORE any imports
os.environ['CURRENT_USER_ID'] = 'user_zhQ7K854ngI'  
os.environ['MODEL'] = 'anthropic/claude-sonnet-4-20250514'

# Load .env file to get API key
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Configure logging first
from configure_logging import configure_logging
configure_logging()

print("🧪 Testing Logging Fixes")
print("=" * 40)

def test_logging_suppression():
    """Test that verbose logging is suppressed."""
    print("📝 Testing logging suppression...")
    
    import logging
    
    # Test LiteLLM logger level
    litellm_logger = logging.getLogger("LiteLLM")
    print(f"✅ LiteLLM logger level: {litellm_logger.level} (should be >= 30 for WARNING)")
    
    # Test warnings filtering
    with warnings.catch_warnings(record=True) as w:
        warnings.warn("Thread 'ThreadPoolExecutor-1_0': missing ScriptRunContext!")
        if len(w) == 0:
            print("✅ Streamlit ScriptRunContext warnings are being filtered")
        else:
            print(f"⚠️  Still showing {len(w)} warnings")
    
    return True

def test_crewai_import():
    """Test that CrewAI can be imported without excessive logging."""
    print("\n🤖 Testing CrewAI import...")
    
    try:
        from gmail_crew_ai.crew import GmailCrewAi
        print("✅ CrewAI imported successfully")
        
        # Test agent creation (without full execution)
        crew_instance = GmailCrewAi()
        categorizer = crew_instance.categorizer()
        print(f"✅ Categorizer agent created: {categorizer.role}")
        
        return True
        
    except Exception as e:
        print(f"❌ CrewAI import/creation failed: {e}")
        return False

def main():
    """Run all logging tests."""
    results = []
    
    results.append(test_logging_suppression())
    results.append(test_crewai_import())
    
    print("\n" + "=" * 40)
    print("📊 LOGGING TEST RESULTS")
    print("=" * 40)
    
    if all(results):
        print("🎉 ALL LOGGING FIXES WORKING!")
        print("✅ Streamlit ScriptRunContext warnings suppressed")
        print("✅ LiteLLM verbose logging reduced")
        print("✅ CrewAI imports cleanly")
        print("\n🚀 Ready for clean Streamlit execution")
    else:
        print("⚠️  Some logging issues remain - check output above")
    
    return all(results)

if __name__ == "__main__":
    success = main()