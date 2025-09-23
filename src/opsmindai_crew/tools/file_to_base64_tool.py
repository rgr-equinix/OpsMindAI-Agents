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
        import time
        
        start_time = time.time()
        print(f"[Base64Converter DEBUG] Starting conversion of {file_path}")
        
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
            print(f"[Base64Converter DEBUG] File size: {file_size} bytes")
            
            # Check if file is too large (>10MB for performance)
            if file_size > 10 * 1024 * 1024:
                return json.dumps({
                    "success": False,
                    "error": f"File too large: {file_size} bytes. Maximum supported size is 10MB.",
                    "base64_content": None,
                    "file_size": file_size,
                    "filename": filename
                })
            
            # Read and encode file in chunks for better memory efficiency
            read_start = time.time()
            with open(file_path, 'rb') as file:
                file_content = file.read()
            
            read_time = time.time() - read_start
            print(f"[Base64Converter DEBUG] File read in {read_time:.3f}s")
            
            # Encode to base64
            encode_start = time.time()
            base64_content = base64.b64encode(file_content).decode('utf-8')
            encode_time = time.time() - encode_start
            
            total_time = time.time() - start_time
            print(f"[Base64Converter DEBUG] Base64 encoding completed in {encode_time:.3f}s")
            print(f"[Base64Converter DEBUG] Total conversion time: {total_time:.3f}s")
            print(f"[Base64Converter DEBUG] Base64 content length: {len(base64_content)} chars")
            
            # Validate base64 content length (should be multiple of 4)
            if len(base64_content) % 4 != 0:
                print(f"[Base64Converter DEBUG] WARNING: Base64 length {len(base64_content)} is not multiple of 4")
            
            return json.dumps({
                "success": True,
                "base64_content": base64_content,
                "file_size": file_size,
                "filename": filename,
                "file_path": file_path,
                "conversion_time": total_time,
                "base64_length": len(base64_content)
            })
            
        except Exception as e:
            total_time = time.time() - start_time
            print(f"[Base64Converter DEBUG] Conversion failed in {total_time:.3f}s: {e}")
            return json.dumps({
                "success": False,
                "error": f"Error converting file to base64: {str(e)}",
                "base64_content": None,
                "file_size": 0,
                "filename": None,
                "conversion_time": total_time
            })
