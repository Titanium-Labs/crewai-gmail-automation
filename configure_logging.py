#!/usr/bin/env python3
"""Configure logging levels to reduce verbose output during CrewAI execution."""

import logging
import warnings
import os

def configure_logging():
    """Configure logging levels to reduce verbose output."""
    
    # Suppress verbose third-party logging
    loggers_to_suppress = [
        'LiteLLM',
        'litellm', 
        'litellm.utils',
        'litellm.cost_calculator',
        'openai',
        'httpx',
        'httpcore',
        'crewai',
        'chromadb',
        'sentence_transformers'
    ]
    
    for logger_name in loggers_to_suppress:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    # Suppress Streamlit threading warnings
    warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
    warnings.filterwarnings("ignore", message=".*Thread.*missing ScriptRunContext.*")
    
    # Set root logger to INFO to keep important messages
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # Only configure if not already configured
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
    
    print("🔇 Logging configured - reduced verbose output from third-party libraries")

if __name__ == "__main__":
    configure_logging()