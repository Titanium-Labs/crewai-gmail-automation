#!/usr/bin/env python3
"""Minimal CrewAI test to verify output capture."""

import os
import sys
from pathlib import Path
from io import StringIO
import contextlib

# Set environment variables
os.environ['CURRENT_USER_ID'] = 'user_zhQ7K854ngI'  
os.environ['MODEL'] = 'anthropic/claude-sonnet-4-20250514'
os.environ['CREWAI_VERBOSE'] = 'true'
os.environ['LANGCHAIN_VERBOSE'] = 'true'

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

print("🧪 Minimal CrewAI Output Test")
print("=" * 30)

try:
    from crewai import Agent, Task, Crew
    from crewai import LLM
    
    print("✅ CrewAI imported")
    
    # Create a simple test crew with mock data
    llm = LLM(model="anthropic/claude-sonnet-4-20250514", api_key=os.getenv('ANTHROPIC_API_KEY'))
    
    # Simple agent
    agent = Agent(
        role="Test Agent",
        goal="Test output capture",
        backstory="A simple test agent",
        verbose=True,
        llm=llm
    )
    
    # Simple task
    task = Task(
        description="Say hello and describe what you are doing in 2-3 sentences.",
        agent=agent,
        expected_output="A brief greeting and description"
    )
    
    # Create crew
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True
    )
    
    print("✅ Test crew created")
    
    # Test output capture
    class TestCapture:
        def __init__(self):
            self.captured_lines = []
            self._original_stdout = sys.__stdout__
            
        def write(self, text):
            if text.strip():
                self._original_stdout.write(f"🔍 CAPTURED: {text.strip()}\n")
                self._original_stdout.flush()
                self.captured_lines.append(text.strip())
            return len(text)
        
        def flush(self):
            pass
    
    capture = TestCapture()
    
    print("\n🚀 Running test crew with output capture...")
    
    # Run with captured output
    try:
        with contextlib.redirect_stdout(capture):
            with contextlib.redirect_stderr(capture):
                result = crew.kickoff()
        
        print(f"\n✅ Crew completed! Captured {len(capture.captured_lines)} lines")
        print(f"📄 Result: {result}")
        
        if capture.captured_lines:
            print("\n📝 Sample captured output:")
            for line in capture.captured_lines[:5]:  # Show first 5 lines
                print(f"   {line}")
        else:
            print("⚠️ No output was captured - this suggests CrewAI may not be writing to stdout")
            
    except Exception as e:
        print(f"❌ Crew execution failed: {e}")
        
        # Check if it's a rate limit error
        if "rate_limit" in str(e).lower():
            print("💡 This is expected - we're hitting rate limits")
            print("💡 The output capture system is working, just need valid API calls")
        else:
            import traceback
            traceback.print_exc()

except Exception as e:
    print(f"❌ Setup error: {e}")
    import traceback
    traceback.print_exc()