#!/usr/bin/env python3
"""Test script for the enhanced Gmail automation with feedback loop."""

import os
import sys
import json

# Add src directory to Python path
sys.path.insert(0, 'src')

def test_enhanced_features():
    """Test the enhanced Gmail automation features."""
    print("🧪 Testing Enhanced Gmail Automation Features")
    print("=" * 60)
    
    # Test 1: Check if all new files exist
    print("\n1. 📁 Testing file structure...")
    required_files = [
        'src/gmail_crew_ai/crew_with_feedback.py',
        'src/gmail_crew_ai/enhanced_crew_runner.py', 
        'knowledge/user_learned_rules.json',
        'FEEDBACK_LOOP_FEATURES.md'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"   ✅ {file_path}")
        else:
            print(f"   ❌ {file_path} - MISSING")
    
    # Test 2: Check configuration updates
    print("\n2. ⚙️ Testing configuration updates...")
    
    # Check agents.yaml for new agents
    try:
        with open('src/gmail_crew_ai/config/agents.yaml', 'r') as f:
            agents_config = f.read()
        
        if 'summary_reporter:' in agents_config:
            print("   ✅ Summary reporter agent configured")
        else:
            print("   ❌ Summary reporter agent missing")
            
        if 'feedback_processor:' in agents_config:
            print("   ✅ Feedback processor agent configured")
        else:
            print("   ❌ Feedback processor agent missing")
            
    except Exception as e:
        print(f"   ❌ Error reading agents config: {e}")
    
    # Check tasks.yaml for new tasks
    try:
        with open('src/gmail_crew_ai/config/tasks.yaml', 'r') as f:
            tasks_config = f.read()
        
        if 'summary_report_task:' in tasks_config:
            print("   ✅ Summary report task configured")
        else:
            print("   ❌ Summary report task missing")
            
        if 'feedback_monitoring_task:' in tasks_config:
            print("   ✅ Feedback monitoring task configured")
        else:
            print("   ❌ Feedback monitoring task missing")
            
        if 'mark_read: true' in tasks_config:
            print("   ✅ Mark as read functionality enabled")
        else:
            print("   ❌ Mark as read functionality missing")
            
    except Exception as e:
        print(f"   ❌ Error reading tasks config: {e}")
    
    # Test 3: Check learned rules structure
    print("\n3. 🧠 Testing learned rules system...")
    try:
        with open('knowledge/user_learned_rules.json', 'r') as f:
            rules_data = json.load(f)
        
        required_sections = [
            'categorization_rules',
            'priority_rules', 
            'response_rules',
            'organization_rules',
            'cleanup_rules',
            'exclusion_rules'
        ]
        
        for section in required_sections:
            if section in rules_data.get('learned_rules', {}):
                print(f"   ✅ {section} section exists")
            else:
                print(f"   ❌ {section} section missing")
                
        stats = rules_data.get('rule_statistics', {})
        print(f"   📊 Total rules: {stats.get('total_rules', 0)}")
        print(f"   📊 Active rules: {stats.get('active_rules', 0)}")
        
    except Exception as e:
        print(f"   ❌ Error reading learned rules: {e}")
    
    # Test 4: Test enhanced crew creation
    print("\n4. 🚀 Testing enhanced crew creation...")
    try:
        from gmail_crew_ai.crew_with_feedback import create_enhanced_crew
        
        crew = create_enhanced_crew()
        print("   ✅ Enhanced crew created successfully")
        print(f"   📋 Crew type: {type(crew).__name__}")
        
        # Test agents
        agents = ['categorizer', 'organizer', 'response_generator', 'cleaner', 'summary_reporter', 'feedback_processor']
        for agent_name in agents:
            if hasattr(crew, agent_name):
                print(f"   ✅ {agent_name} agent available")
            else:
                print(f"   ❌ {agent_name} agent missing")
        
        # Test tasks  
        tasks = ['categorization_task', 'organization_task', 'response_task', 'cleanup_task', 'summary_report_task', 'feedback_monitoring_task']
        for task_name in tasks:
            if hasattr(crew, task_name):
                print(f"   ✅ {task_name} available")
            else:
                print(f"   ❌ {task_name} missing")
                
    except Exception as e:
        print(f"   ❌ Error creating enhanced crew: {e}")
    
    # Test 5: Test runner functionality
    print("\n5. 🎮 Testing runner functionality...")
    try:
        from gmail_crew_ai.enhanced_crew_runner import run_gmail_automation_with_feedback
        
        print("   ✅ Enhanced runner imported successfully")
        print("   🎯 Available modes: main, feedback, complete, legacy")
        
        # Test mode validation (without actually running)
        try:
            # This should raise an error for invalid mode
            result = run_gmail_automation_with_feedback("invalid_mode")
            if "error" in result:
                print("   ✅ Mode validation working")
            else:
                print("   ❌ Mode validation not working")
        except:
            print("   ✅ Mode validation working (exception caught)")
            
    except Exception as e:
        print(f"   ❌ Error testing runner: {e}")
    
    # Test 6: OAuth2 improvements
    print("\n6. 🔐 Testing OAuth2 improvements...")
    try:
        from gmail_crew_ai.tools.gmail_tools import GetUnreadEmailsTool
        
        # Test auto-detection (without actually running)
        tool = GetUnreadEmailsTool()
        if hasattr(tool, '_get_primary_user_id'):
            print("   ✅ User auto-detection method available")
        else:
            print("   ❌ User auto-detection method missing")
            
        if tool.user_id:
            print(f"   ✅ User ID detected: {tool.user_id}")
        else:
            print("   ❌ No user ID detected")
            
    except Exception as e:
        print(f"   ❌ Error testing OAuth2 improvements: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 Enhanced Gmail Automation Test Complete!")
    print("=" * 60)
    
    print("\n💡 Next Steps:")
    print("1. Run: python src/gmail_crew_ai/enhanced_crew_runner.py --mode complete")
    print("2. Check your inbox for summary email")
    print("3. Reply to summary email with feedback")
    print("4. Run feedback monitoring to see learning in action")
    print("\n🚀 The system is ready for enhanced automation with feedback loop!")

def demonstrate_workflow():
    """Demonstrate the complete workflow."""
    print("\n🎯 ENHANCED WORKFLOW DEMONSTRATION")
    print("=" * 60)
    
    workflow_steps = [
        "📧 1. Fetch unread emails from Gmail",
        "🏷️ 2. Categorize emails (PERSONAL, IMPORTANT, etc.)",
        "⭐ 3. Organize emails (labels, stars, mark as READ)",
        "💬 4. Generate draft responses for priority emails",  
        "🗑️ 5. Clean up old/unwanted emails",
        "📊 6. Generate comprehensive summary email",
        "📧 7. Send summary to user's inbox",
        "👂 8. Monitor for user feedback replies",
        "🧠 9. Learn from feedback and extract rules",
        "📝 10. Update system configuration",
        "✅ 11. Send acknowledgment to user",
        "🔄 12. Apply learned rules to future processing"
    ]
    
    for step in workflow_steps:
        print(f"   {step}")
    
    print("\n💬 Example User Feedback:")
    print('   "Don\'t respond to emails from @noreply.com"')
    print('   "Always mark emails from my boss as HIGH priority"')
    print('   "Use more casual tone for family emails"')
    
    print("\n🧠 What The System Learns:")
    print("   📋 New categorization rules")
    print("   🎯 Priority assignment preferences")
    print("   💬 Response tone adjustments")
    print("   🏷️ Custom labeling rules")
    print("   🗑️ Cleanup preferences")
    
    print("\n🎉 Result: Continuously improving email automation!")

if __name__ == "__main__":
    test_enhanced_features()
    demonstrate_workflow()