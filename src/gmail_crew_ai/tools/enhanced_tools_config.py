"""Enhanced tools configuration for CrewAI Gmail automation agents."""

import os
from typing import List, Any, Optional, Type

from . import (
    # Custom Gmail Tools
    GetUnreadEmailsTool, SaveDraftTool, GmailOrganizeTool, GmailDeleteTool, EmptyTrashTool,
    DateCalculationTool, FileReadTool, JsonFileReadTool, JsonFileSaveTool,
    
    # CrewAI Tools
    CrewAIFileReadTool, ScrapeWebsiteTool, SeleniumScrapingTool,
    PGSearchTool, MySQLSearchTool, QdrantVectorSearchTool, WeaviateVectorSearchTool,
    SerperDevTool, EXASearchTool, DallETool, VisionTool,
    CSVSearchTool, JSONSearchTool, MDXSearchTool, PDFSearchTool, TXTSearchTool, XMLSearchTool,
    YoutubeChannelSearchTool, YoutubeVideoSearchTool
)


class EnhancedToolsConfig:
    """Configuration class for enhanced CrewAI tools integration."""
    
    def __init__(self):
        """Initialize tools configuration with environment-based availability."""
        self.serper_api_key = os.getenv("SERPER_API_KEY")
        self.exa_api_key = os.getenv("EXA_API_KEY")
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
    
    def get_categorizer_tools(self) -> List[Any]:
        """Tools for the email categorizer agent."""
        tools = [
            FileReadTool(),  # Custom file reader with UTF-8 support
            JsonFileReadTool(),  # Custom JSON file reader
        ]
        
        # Add CrewAI file tools if available
        if CrewAIFileReadTool:
            tools.append(CrewAIFileReadTool())
        
        # Add JSON and CSV search tools for analysis (without parameters)
        if JSONSearchTool:
            tools.append(JSONSearchTool)
        if CSVSearchTool:
            tools.append(CSVSearchTool)
        
        return tools
    
    def get_organizer_tools(self) -> List[Any]:
        """Tools for the email organizer agent."""
        tools = [
            FileReadTool(),
            JsonFileReadTool(),
        ]
        
        # Add Gmail organization tool class for later instantiation
        tools.append(GmailOrganizeTool)
        
        # Add search tools as classes for agent to instantiate with proper config
        if SerperDevTool and self.serper_api_key:
            tools.append(SerperDevTool)
        
        if EXASearchTool and self.exa_api_key:
            tools.append(EXASearchTool)
        
        return tools
    
    def get_response_generator_tools(self) -> List[Any]:
        """Tools for the email response generator agent."""
        tools = [
            FileReadTool(),
            JsonFileReadTool(),
        ]
        
        # Add draft saving tool class for later instantiation
        tools.append(SaveDraftTool)
        
        # Add web scraping tools as classes
        if ScrapeWebsiteTool:
            tools.append(ScrapeWebsiteTool)
        
        # Add search tools as classes
        if SerperDevTool and self.serper_api_key:
            tools.append(SerperDevTool)
        
        if EXASearchTool and self.exa_api_key:
            tools.append(EXASearchTool)
        
        # Add AI-powered tools as classes
        if VisionTool and self.openai_api_key:
            tools.append(VisionTool)
        
        # Add YouTube tools as classes
        if YoutubeChannelSearchTool:
            tools.append(YoutubeChannelSearchTool)
        if YoutubeVideoSearchTool:
            tools.append(YoutubeVideoSearchTool)
        
        return tools
    
    def get_cleaner_tools(self) -> List[Any]:
        """Tools for the email cleanup agent."""
        tools = [
            DateCalculationTool(),  # Custom date calculations
            FileReadTool(),
            JsonFileReadTool(),
        ]
        
        # Add Gmail tool classes for later instantiation
        tools.extend([GmailDeleteTool, EmptyTrashTool])
        
        # Add document analysis tools as classes
        if PDFSearchTool:
            tools.append(PDFSearchTool)
        if TXTSearchTool:
            tools.append(TXTSearchTool)
        if XMLSearchTool:
            tools.append(XMLSearchTool)
        
        return tools
    
    def get_available_tool_classes(self) -> dict:
        """Return available tool classes organized by category."""
        return {
            "file_management": [
                FileReadTool, JsonFileReadTool, JsonFileSaveTool,
                CrewAIFileReadTool if CrewAIFileReadTool else None
            ],
            "web_scraping": [
                ScrapeWebsiteTool if ScrapeWebsiteTool else None,
                SeleniumScrapingTool if SeleniumScrapingTool else None
            ],
            "database": [
                PGSearchTool if PGSearchTool else None,
                MySQLSearchTool if MySQLSearchTool else None
            ],
            "vector_database": [
                QdrantVectorSearchTool if QdrantVectorSearchTool else None,
                WeaviateVectorSearchTool if WeaviateVectorSearchTool else None
            ],
            "search_api": [
                SerperDevTool if SerperDevTool and self.serper_api_key else None,
                EXASearchTool if EXASearchTool and self.exa_api_key else None
            ],
            "ai_powered": [
                DallETool if DallETool and self.openai_api_key else None,
                VisionTool if VisionTool and self.openai_api_key else None
            ],
            "document_analysis": [
                CSVSearchTool, JSONSearchTool, MDXSearchTool,
                PDFSearchTool, TXTSearchTool, XMLSearchTool
            ],
            "youtube": [
                YoutubeChannelSearchTool if YoutubeChannelSearchTool else None,
                YoutubeVideoSearchTool if YoutubeVideoSearchTool else None
            ],
            "gmail_custom": [
                GetUnreadEmailsTool, SaveDraftTool, GmailOrganizeTool,
                GmailDeleteTool, EmptyTrashTool, DateCalculationTool
            ]
        }
    
    def print_available_tools(self):
        """Print a summary of available tools."""
        print("\n🛠️  ENHANCED CREWAI TOOLS CONFIGURATION")
        print("=" * 50)
        
        tools = self.get_available_tool_classes()
        
        print(f"📁 File Management Tools: {len([t for t in tools['file_management'] if t])} available")
        print(f"🌐 Web Scraping Tools: {len([t for t in tools['web_scraping'] if t])} available")
        print(f"💾 Database Tools: {len([t for t in tools['database'] if t])} available")
        print(f"🔍 Search API Tools: {len([t for t in tools['search_api'] if t])} available")
        print(f"🤖 AI-Powered Tools: {len([t for t in tools['ai_powered'] if t])} available")
        print(f"📄 Document Analysis Tools: {len([t for t in tools['document_analysis'] if t])} available")
        print(f"📺 YouTube Tools: {len([t for t in tools['youtube'] if t])} available")
        print(f"📧 Custom Gmail Tools: {len([t for t in tools['gmail_custom'] if t])} available")
        
        print("\n📝 API Key Status:")
        print(f"  SERPER_API_KEY: {'✅ Set' if self.serper_api_key else '❌ Not set'}")
        print(f"  EXA_API_KEY: {'✅ Set' if self.exa_api_key else '❌ Not set'}")
        print(f"  OPENAI_API_KEY: {'✅ Set' if self.openai_api_key else '❌ Not set'}")
        
        if not self.serper_api_key:
            print("⚠️  Set SERPER_API_KEY for enhanced search capabilities")
        if not self.exa_api_key:
            print("⚠️  Set EXA_API_KEY for advanced search features")
        
        print("=" * 50)


# Global instance
enhanced_tools_config = EnhancedToolsConfig() 