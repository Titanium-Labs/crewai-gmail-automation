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
    def get_categorizer_tools() -> List[Any]:
        """Get basic tools for the email categorizer agent."""
        tools = []
        
        # Add basic file reading tools
        tools.extend([FileReadTool, JsonFileReadTool, JsonFileSaveTool])
        
        print("🔧 Categorizer tools: File operations for email analysis")
        return tools
    
    @staticmethod
    def get_organizer_tools() -> List[Any]:
        """Get tools for the email organizer agent."""
        tools = []
        
        # Add file tools
        tools.extend([FileReadTool, JsonFileReadTool, JsonFileSaveTool])
        
        # Add Gmail organization tool class for later instantiation
        tools.append(GmailOrganizeTool)
        
        print("🔧 Organizer tools: Gmail organization + File operations")
        return tools
    
    @staticmethod
    def get_response_generator_tools() -> List[Any]:
        """Get tools for the response generator agent."""
        tools = []
        
        # Add file tools
        tools.extend([FileReadTool, JsonFileReadTool, JsonFileSaveTool])
        
        # Add draft saving tool class for later instantiation
        tools.append(SaveDraftTool)
        
        print("🔧 Response Generator tools: Email drafting + File operations")
        return tools
    
    @staticmethod
    def get_cleaner_tools() -> List[Any]:
        """Get tools for the email cleaner agent."""
        tools = []
        
        # Add file tools
        tools.extend([FileReadTool, JsonFileReadTool, JsonFileSaveTool])
        
        # Add Gmail tool classes for later instantiation
        tools.extend([GmailDeleteTool, EmptyTrashTool])
        
        # Add date calculation tool
        tools.append(DateCalculationTool)
        
        print("🔧 Cleaner tools: Gmail cleanup + Date calculations + File operations")
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