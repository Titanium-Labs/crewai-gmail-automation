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
        tools.extend([FileReadTool, JsonFileReadTool])
        
        print(f"✅ Categorizer equipped with {len(tools)} basic tools")
        return tools
    
    @staticmethod
    def get_organizer_tools() -> List[Any]:
        """Get basic tools for the email organizer agent.""" 
        tools = []
        
        # Add Gmail organization tools
        tools.extend([GmailOrganizeTool, FileReadTool, JsonFileReadTool])
        
        print(f"✅ Organizer equipped with {len(tools)} basic tools")
        return tools
    
    @staticmethod
    def get_response_generator_tools() -> List[Any]:
        """Get basic tools for the response generator agent."""
        tools = []
        
        # Add draft saving and file tools
        tools.extend([SaveDraftTool, FileReadTool, JsonFileReadTool])
        
        print(f"✅ Response Generator equipped with {len(tools)} basic tools")
        return tools
    
    @staticmethod
    def get_cleaner_tools() -> List[Any]:
        """Get basic tools for the cleanup agent."""
        tools = []
        
        # Add Gmail tools and date calculation
        tools.extend([GmailDeleteTool, EmptyTrashTool, DateCalculationTool, FileReadTool])
        
        print(f"✅ Cleaner equipped with {len(tools)} basic tools")
        return tools
    
    @staticmethod
    def get_all_available_tools() -> List[Any]:
        """Get all available basic tools."""
        all_tools = []
        all_tools.extend(BasicToolsConfig.get_categorizer_tools())
        all_tools.extend(BasicToolsConfig.get_organizer_tools()) 
        all_tools.extend(BasicToolsConfig.get_response_generator_tools())
        all_tools.extend(BasicToolsConfig.get_cleaner_tools())
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tools = []
        for tool in all_tools:
            tool_name = getattr(tool, '__name__', str(tool))
            if tool_name not in seen:
                seen.add(tool_name)
                unique_tools.append(tool)
        
        return unique_tools


# Create instance for easy import
basic_tools_config = BasicToolsConfig() 