#!/usr/bin/env python3
"""Test CrewAI output visibility."""

import os
import sys
from pathlib import Path

# Set environment variables BEFORE any imports
os.environ['CURRENT_USER_ID'] = 'user_zhQ7K854ngI'  
os.environ['MODEL'] = 'anthropic/claude-sonnet-4-20250514'

# Load .env file to get API key
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("🧪 Testing CrewAI Output Capture")
print("=" * 40)

# Test basic CrewAI import and agent creation
try:
    from gmail_crew_ai.crew_oauth import create_crew_for_user
    from gmail_crew_ai.auth.oauth2_manager import OAuth2Manager
    
    print("✅ Imports successful")
    
    # Create OAuth manager and crew
    oauth_manager = OAuth2Manager()
    user_api_keys = {
        'anthropic': os.getenv('ANTHROPIC_API_KEY'),
        'openai': os.getenv('OPENAI_API_KEY')
    }
    
    print("🤖 Creating CrewAI instance...")
    crew_instance = create_crew_for_user('user_zhQ7K854ngI', oauth_manager, user_api_keys)
    
    print("✅ CrewAI instance created")
    
    # Test agent creation
    categorizer = crew_instance.categorizer()
    print(f"✅ Categorizer agent: {categorizer.role}")
    
    organizer = crew_instance.organizer()
    print(f"✅ Organizer agent: {organizer.role}")
    
    # Test crew assembly
    crew = crew_instance.crew()
    print("✅ Crew assembled successfully")
    
    print("\n📝 Testing output capture...")
    
    # Create custom output capturer
    from io import StringIO
    import contextlib
    
    class TestCapture(StringIO):
        def __init__(self):
            super().__init__()
            self.captured = []
            self._original_stdout = sys.__stdout__
            
        def write(self, text):
            if text.strip():
                self._original_stdout.write(f"CAPTURED: {text.strip()}\n")
                self._original_stdout.flush()
                self.captured.append(text.strip())
            return len(text)
    
    capture = TestCapture()
    
    # Test if we can capture any output
    with contextlib.redirect_stdout(capture):
        print("This should be captured")
        
    print(f"✅ Capture test: {len(capture.captured)} items captured")
    
    print("\n🎯 Output capture system is ready")
    print("Note: Actual CrewAI execution requires valid emails and may hit rate limits")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()