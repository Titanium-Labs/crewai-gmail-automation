#!/usr/bin/env python
"""Enhanced crew runner that provides backward compatibility while adding feedback features."""

import os
import sys
from typing import Dict, Any, Optional

# Add src directory to Python path  
sys.path.insert(0, 'src')

def run_gmail_automation_with_feedback(mode: str = "complete") -> Dict[str, Any]:
    """
    Run Gmail automation with enhanced feedback capabilities.
    
    Args:
        mode: "main" (just email processing), "feedback" (just feedback monitoring), 
              or "complete" (both)
    
    Returns:
        Results dictionary with processing outcomes
    """
    print("🔄 Initializing Enhanced Gmail Automation...")
    
    try:
        from gmail_crew_ai.crew_with_feedback import create_enhanced_crew
        
        # Create enhanced crew
        crew = create_enhanced_crew()
        
        if mode == "main":
            print("📧 Running main email processing only...")
            return crew.run_main_processing()
        
        elif mode == "feedback":
            print("👂 Running feedback monitoring only...")
            return crew.run_feedback_monitoring()
        
        elif mode == "complete":
            print("🚀 Running complete automation cycle...")
            return crew.run_complete_cycle()
        
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'main', 'feedback', or 'complete'")
            
    except Exception as e:
        print(f"❌ Error running enhanced automation: {e}")
        return {"error": str(e), "success": False}


def run_legacy_automation() -> Dict[str, Any]:
    """
    Run the legacy automation (for backward compatibility).
    """
    print("🔄 Running legacy Gmail automation...")
    
    try:
        from gmail_crew_ai.crew import GmailCrewAi
        
        crew = GmailCrewAi()
        result = crew.crew().kickoff()
        
        return {"result": result, "success": True, "mode": "legacy"}
        
    except Exception as e:
        print(f"❌ Error running legacy automation: {e}")
        return {"error": str(e), "success": False}


def main():
    """Main entry point with command line argument support."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Gmail Automation with Feedback")
    parser.add_argument(
        "--mode", 
        choices=["main", "feedback", "complete", "legacy"],
        default="complete",
        help="Automation mode to run"
    )
    parser.add_argument(
        "--user-id",
        help="Override CURRENT_USER_ID environment variable"
    )
    
    args = parser.parse_args()
    
    # Set user ID if provided
    if args.user_id:
        os.environ['CURRENT_USER_ID'] = args.user_id
        print(f"🔧 Set CURRENT_USER_ID to: {args.user_id}")
    
    # Run automation based on mode
    if args.mode == "legacy":
        result = run_legacy_automation()
    else:
        result = run_gmail_automation_with_feedback(args.mode)
    
    # Print results
    print("\n" + "="*60)
    print("📊 AUTOMATION RESULTS")
    print("="*60)
    
    if result.get("success", True):
        print("✅ Automation completed successfully")
        if "cycle_completed" in result:
            print("🔄 Complete cycle finished")
        print(f"📋 Mode: {args.mode}")
    else:
        print("❌ Automation failed")
        print(f"💥 Error: {result.get('error', 'Unknown error')}")
    
    return result


if __name__ == "__main__":
    main()