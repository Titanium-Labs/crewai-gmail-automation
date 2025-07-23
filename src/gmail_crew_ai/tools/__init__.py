# Custom Gmail Tools
from .gmail_tools import GetUnreadEmailsTool, SaveDraftTool, GmailOrganizeTool, GmailDeleteTool, EmptyTrashTool
from .date_tools import DateCalculationTool
from .file_tools import FileReadTool, JsonFileReadTool, JsonFileSaveTool

# Official CrewAI Tools - File Management
try:
    from crewai_tools import FileReadTool as CrewAIFileReadTool
except ImportError:
    CrewAIFileReadTool = None

# Official CrewAI Tools - Web Scraping
try:
    from crewai_tools import ScrapeWebsiteTool, SeleniumScrapingTool
except ImportError:
    ScrapeWebsiteTool = None
    SeleniumScrapingTool = None

# Official CrewAI Tools - Database Integrations
try:
    from crewai_tools import PGSearchTool, MySQLSearchTool
except ImportError:
    PGSearchTool = None
    MySQLSearchTool = None

# Official CrewAI Tools - Vector Database Integrations
try:
    from crewai_tools import (
        QdrantVectorSearchTool,
        WeaviateVectorSearchTool
    )
except ImportError:
    QdrantVectorSearchTool = None
    WeaviateVectorSearchTool = None

# Official CrewAI Tools - API Integrations
try:
    from crewai_tools import SerperDevTool, EXASearchTool
except ImportError:
    SerperDevTool = None
    EXASearchTool = None

# Official CrewAI Tools - AI-powered Tools
try:
    from crewai_tools import (
        DallETool,
        VisionTool
    )
except ImportError:
    DallETool = None
    VisionTool = None

# Additional useful CrewAI Tools
try:
    from crewai_tools import (
        CSVSearchTool,
        JSONSearchTool,
        MDXSearchTool,
        PDFSearchTool,
        TXTSearchTool,
        XMLSearchTool,
        YoutubeChannelSearchTool,
        YoutubeVideoSearchTool
    )
except ImportError:
    CSVSearchTool = None
    JSONSearchTool = None
    MDXSearchTool = None
    PDFSearchTool = None
    TXTSearchTool = None
    XMLSearchTool = None
    YoutubeChannelSearchTool = None
    YoutubeVideoSearchTool = None

__all__ = [
    # Custom Gmail Tools
    'GetUnreadEmailsTool',
    'SaveDraftTool', 
    'GmailOrganizeTool',
    'GmailDeleteTool',
    'EmptyTrashTool',
    'DateCalculationTool',
    'FileReadTool',
    'JsonFileReadTool',
    'JsonFileSaveTool',
    
    # Official CrewAI Tools - File Management
    'CrewAIFileReadTool',
    
    # Web Scraping
    'ScrapeWebsiteTool',
    'SeleniumScrapingTool',
    
    # Database Integrations
    'PGSearchTool',
    'MySQLSearchTool',
    
    # Vector Database Integrations
    'QdrantVectorSearchTool',
    'WeaviateVectorSearchTool',
    
    # API Integrations
    'SerperDevTool',
    'EXASearchTool',
    
    # AI-powered Tools
    'DallETool',
    'VisionTool',
    
    # Additional Tools
    'CSVSearchTool',
    'JSONSearchTool',
    'MDXSearchTool',
    'PDFSearchTool',
    'TXTSearchTool',
    'XMLSearchTool',
    'YoutubeChannelSearchTool',
    'YoutubeVideoSearchTool'
]
