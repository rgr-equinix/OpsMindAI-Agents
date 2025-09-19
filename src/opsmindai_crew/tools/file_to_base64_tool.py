from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import base64
import os

class FileToBase64Input(BaseModel):
    """Input schema for File to Base64 converter."""
    file_path: str = Field(..., description="Path to the file to convert to base64")

class FileToBase64Tool(BaseTool):
    """Tool for converting files to base64 encoded strings for Slack upload."""

    name: str = "file_to_base64_converter"
    description: str = (
        "Convert any file (especially PDF files) to base64 encoded string. "
        "Useful for preparing files for Slack upload or other APIs that require base64 encoding."
    )
    args_schema: Type[BaseModel] = FileToBase64Input

    def _run(self, file_path: str) -> str:
        """
        Convert a file to base64 encoded string.
        
        Args:
            file_path: Path to the file to convert
            
        Returns:
            JSON string with base64 content and file info
        """
        import json
        
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return json.dumps({
                    "success": False,
                    "error": f"File not found: {file_path}",
                    "base64_content": None,
                    "file_size": 0,
                    "filename": None
                })
            
            # Get file info
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # Read and encode file
            with open(file_path, 'rb') as file:
                file_content = file.read()
                base64_content = base64.b64encode(file_content).decode('utf-8')
            
            return json.dumps({
                "success": True,
                "base64_content": base64_content,
                "file_size": file_size,
                "filename": filename,
                "file_path": file_path
            })
            
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Error converting file to base64: {str(e)}",
                "base64_content": None,
                "file_size": 0,
                "filename": None
            })
