from crewai.tools import BaseTool
from pydantic import BaseModel
from typing import Type
import datetime
import json

class CurrentDateToolInput(BaseModel):
    """Input schema for Current Date Tool. Takes no parameters."""
    pass

class CurrentDateTool(BaseTool):
    """Tool for automatically generating current date and time in multiple formats."""

    name: str = "current_date_tool"
    description: str = (
        "Automatically generates the current date and time in multiple formats. "
        "Returns YYYYMMDD format, HHMMSS format, ISO timestamp, and Unix timestamp. "
        "Perfect for creating unique identifiers, channel names, or timestamps in automation workflows. "
        "Takes no input parameters - uses current system date/time automatically."
    )
    args_schema: Type[BaseModel] = CurrentDateToolInput

    def _run(self) -> str:
        """
        Generate current date and time in multiple formats.
        
        Returns:
            str: JSON string containing formatted date/time information
        """
        try:
            # Get current date and time
            now = datetime.datetime.now()
            
            # Format date as YYYYMMDD
            yyyymmdd = now.strftime("%Y%m%d")
            
            # Format time as HHMMSS (24-hour format)
            hhmmss = now.strftime("%H%M%S")
            
            # ISO timestamp
            iso_timestamp = now.isoformat()
            
            # Unix timestamp as integer
            unix_timestamp = int(now.timestamp())
            
            # Create response dictionary
            response = {
                "yyyymmdd": yyyymmdd,
                "hhmmss": hhmmss,
                "timestamp": iso_timestamp,
                "unix_timestamp": unix_timestamp,
                "formatted_display": now.strftime("%Y-%m-%d %H:%M:%S"),
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second
            }
            
            # Return JSON string
            return json.dumps(response, indent=2)
            
        except Exception as e:
            error_response = {
                "error": f"Failed to generate current date/time: {str(e)}",
                "yyyymmdd": None,
                "hhmmss": None,
                "timestamp": None,
                "unix_timestamp": None
            }
            return json.dumps(error_response, indent=2)