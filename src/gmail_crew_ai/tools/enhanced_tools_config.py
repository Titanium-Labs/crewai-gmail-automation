"""Basic tools configuration for Gmail automation agents without crewai-tools dependency."""

import os
from typing import List, Any, Optional, Type

from . import (
    # Custom Gmail Tools
    GetUnreadEmailsTool, SaveDraftTool, GmailOrganizeTool, GmailDeleteTool, EmptyTrashTool,
    DateCalculationTool, FileReadTool, JsonFileReadTool, JsonFileSaveTool
)

# Note: CrewAI tools removed due to embedchain dependency conflicts


class BasicToolsConfig:
    """Basic configuration class for Gmail automation without crewai-tools dependency."""
    
    @staticmethod
    def get_categorizer_tools(user_id: Optional[str] = None) -> List[Any]:
        """Get basic tools for the email categorizer agent."""
        tools = []
        
        # Add basic file reading tools (instantiate them)
        tools.extend([FileReadTool(), JsonFileReadTool(), JsonFileSaveTool()])
        
        print("🔧 Categorizer tools: File operations for email analysis")
        return tools
    
    @staticmethod
    def get_organizer_tools(user_id: Optional[str] = None) -> List[Any]:
        """Get tools for the email organizer agent."""
        tools = []
        
        # Add file tools (instantiate them)
        tools.extend([FileReadTool(), JsonFileReadTool(), JsonFileSaveTool()])
        
        # Add Gmail organization tool - using OAuth2 version directly
        from .gmail_oauth_tools import OAuth2GmailOrganizeTool
        tools.append(OAuth2GmailOrganizeTool())
        
        print("🔧 Organizer tools: Gmail organization + File operations")
        return tools
    
    @staticmethod
    def get_response_generator_tools() -> List[Any]:
        """Get tools for the response generator agent."""
        tools = []
        
        # Add file tools (instantiate them)
        tools.extend([FileReadTool(), JsonFileReadTool(), JsonFileSaveTool()])
        
        # Add Gmail tools - using OAuth2 versions directly  
        from .gmail_oauth_tools import OAuth2SaveDraftTool, OAuth2GetUnreadEmailsTool
        tools.extend([OAuth2SaveDraftTool(), OAuth2GetUnreadEmailsTool()])
        
        print("🔧 Response Generator tools: Email drafting + Email search + File operations")
        return tools
    
    @staticmethod
    def get_cleaner_tools() -> List[Any]:
        """Get tools for the email cleaner agent."""
        tools = []
        
        # Add file tools (instantiate them)
        tools.extend([FileReadTool(), JsonFileReadTool(), JsonFileSaveTool()])
        
        # Add Gmail tool instances - using OAuth2 versions directly
        from .gmail_oauth_tools import OAuth2GmailDeleteTool, OAuth2EmptyTrashTool, OAuth2GmailOrganizeTool, OAuth2GmailTool
        tools.extend([OAuth2GmailDeleteTool(), OAuth2EmptyTrashTool(), OAuth2GmailOrganizeTool(), OAuth2GmailTool()])
        
        # Add date calculation tool instance
        tools.append(DateCalculationTool())
        
        print("🔧 Cleaner tools: Gmail cleanup + Organization + Date calculations + File operations")
        return tools
    
    @staticmethod
    def get_summary_reporter_tools() -> List[Any]:
        """Get tools for the summary reporter agent."""
        tools = []
        
        # Add file tools for reading reports (instantiate them)
        tools.extend([FileReadTool(), JsonFileReadTool(), JsonFileSaveTool()])
        
        # Add draft saving tool instance for sending summary emails - using OAuth2 version
        from .gmail_oauth_tools import OAuth2SaveDraftTool
        tools.append(OAuth2SaveDraftTool())
        
        print("🔧 Summary Reporter tools: Report generation + Email drafting + File operations")
        return tools
    
    @staticmethod
    def get_feedback_processor_tools() -> List[Any]:
        """Get tools for the feedback processor agent."""
        tools = []
        
        # Add file tools for reading/writing configuration (instantiate them)
        tools.extend([FileReadTool(), JsonFileReadTool(), JsonFileSaveTool()])
        
        # Add Gmail tool instances for reading feedback emails and sending responses - using OAuth2 versions
        from .gmail_oauth_tools import OAuth2GetUnreadEmailsTool, OAuth2SaveDraftTool
        tools.extend([OAuth2GetUnreadEmailsTool(), OAuth2SaveDraftTool()])
        
        print("🔧 Feedback Processor tools: Gmail monitoring + Configuration updates + File operations")
        return tools
    
    @staticmethod
    def display_available_tools():
        """Display information about available tools."""
        print("\n🛠️ AVAILABLE TOOLS (Basic Configuration)")
        print("=" * 50)
        print("📁 File Management:")
        print("   ✅ FileReadTool - Local file reading")
        print("   ✅ JsonFileReadTool - JSON file operations")
        print("   ✅ JsonFileSaveTool - JSON file saving")
        print("\n📧 Gmail Operations:")
        print("   ✅ GmailOrganizeTool - Email organization")
        print("   ✅ SaveDraftTool - Draft creation")
        print("   ✅ GmailDeleteTool - Email deletion") 
        print("   ✅ EmptyTrashTool - Trash management")
        print("\n📅 Utilities:")
        print("   ✅ DateCalculationTool - Date operations")
        print("\n⚠️ Note: CrewAI tools unavailable due to dependency conflicts")
        print("=" * 50)


# Create global instance
basic_tools_config = BasicToolsConfig() 