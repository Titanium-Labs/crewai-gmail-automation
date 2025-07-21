"""Custom file tools with proper UTF-8 encoding support."""

import json
import os
from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Union


class FileSaveTool(BaseTool):
    """Tool for saving data to files with proper UTF-8 encoding."""
    
    name: str = "FileSaveTool"
    description: str = "Save data to a file with UTF-8 encoding support"

    def _run(self, data: Union[Dict, List, str], file_path: str) -> str:
        """Save data to a file with UTF-8 encoding."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                if isinstance(data, (dict, list)):
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    f.write(str(data))
            
            return f"Successfully saved data to {file_path}"
        except Exception as e:
            return f"Error saving file {file_path}: {str(e)}"


class FileReadTool(BaseTool):
    """Tool for reading files with proper UTF-8 encoding."""
    
    name: str = "FileReadTool"
    description: str = "Read files with UTF-8 encoding support"

    def _run(self, file_path: str) -> str:
        """Read a file with UTF-8 encoding."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            return f"Error reading file {file_path}: {str(e)}"


class JsonFileReadTool(BaseTool):
    """Tool for reading JSON files with proper UTF-8 encoding."""
    
    name: str = "JsonFileReadTool"
    description: str = "Read JSON files with UTF-8 encoding support"

    def _run(self, file_path: str) -> Union[Dict, List, str]:
        """Read a JSON file with UTF-8 encoding."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            return f"Error reading JSON file {file_path}: {str(e)}"


class JsonFileSaveTool(BaseTool):
    """Tool for saving JSON data to files with proper UTF-8 encoding."""
    
    name: str = "JsonFileSaveTool"
    description: str = "Save JSON data to files with UTF-8 encoding support"

    def _run(self, data: Union[Dict, List], file_path: str) -> str:
        """Save JSON data to a file with UTF-8 encoding."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return f"Successfully saved JSON data to {file_path}"
        except Exception as e:
            return f"Error saving JSON file {file_path}: {str(e)}" 