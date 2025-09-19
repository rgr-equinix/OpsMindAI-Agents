from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import json
from .incident_database_tool import IncidentDatabaseTool


class SingleIncidentReaderInput(BaseModel):
    """Input schema for Single Incident Reader Tool."""
    incident_id: str = Field(..., description="Concrete incident ID, e.g., INC-1758194295321")


class SingleIncidentReader(BaseTool):
    """Read exactly one incident from the incident database in a single call."""

    name: str = "single_incident_reader"
    description: str = (
        "Fetch one incident by ID using a single database read. Rejects placeholders or 'ALL'."
    )
    args_schema: Type[BaseModel] = SingleIncidentReaderInput

    def _run(self, incident_id: str) -> str:
        try:
            if not incident_id or incident_id.strip() == "" or incident_id.strip().upper() == "ALL" or incident_id.strip().startswith("["):
                return json.dumps({
                    "success": False,
                    "error": "Invalid incident_id. Provide a concrete INC-... value.",
                    "incident_id": incident_id
                })

            db = IncidentDatabaseTool()
            result = db._run(operation="read", incident_id=incident_id)
            return result
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"SingleIncidentReader failed: {str(e)}",
                "incident_id": incident_id
            })

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional
import json
from .incident_database_tool import IncidentDatabaseTool

class SingleIncidentReaderInput(BaseModel):
    """Input schema for Single Incident Reader Tool."""
    incident_id: str = Field(..., description="The specific incident ID to read from database")

class SingleIncidentReader(BaseTool):
    """Tool that reads exactly one incident from the database and prevents multiple calls."""
    
    name: str = "single_incident_reader"
    description: str = (
        "Reads exactly ONE incident from the database for the specified incident_id. "
        "This tool enforces single database access and returns complete incident data "
        "for report generation. Use this instead of incident_database_tool for report generation."
    )
    args_schema: Type[BaseModel] = SingleIncidentReaderInput
    
    # Class-level cache to prevent multiple calls for same incident
    _cache: Dict[str, Dict[str, Any]] = {}
    _call_count: Dict[str, int] = {}  # Track number of calls per incident
    
    def _run(self, incident_id: str) -> str:
        """Read a single incident from database with caching to prevent multiple calls."""
        
        # Clean the incident ID
        incident_id = str(incident_id).strip()
        
        # Track call count for debugging
        if incident_id not in self._call_count:
            self._call_count[incident_id] = 0
        self._call_count[incident_id] += 1
        
        print(f"[SingleIncidentReader DEBUG] Call #{self._call_count[incident_id]} for incident: {incident_id}")
        
        # Check cache first to prevent multiple database calls
        if incident_id in self._cache:
            cached_data = self._cache[incident_id]
            print(f"[SingleIncidentReader DEBUG] Returning cached data for {incident_id}")
            return json.dumps({
                "success": True,
                "message": f"Retrieved cached incident data for {incident_id}",
                "data": cached_data,
                "cached": True,
                "call_count": self._call_count[incident_id]
            }, indent=2)
        
        # If not cached, make single database call
        print(f"[SingleIncidentReader DEBUG] Making database call for {incident_id}")
        db_tool = IncidentDatabaseTool()
        result_json = db_tool._run(operation="read", incident_id=incident_id)
        
        try:
            result = json.loads(result_json)
            
            if result.get("success"):
                # Cache the successful result
                self._cache[incident_id] = result["data"]
                
                return json.dumps({
                    "success": True,
                    "message": f"Retrieved incident data for {incident_id}",
                    "data": result["data"],
                    "database_call_made": True,
                    "cached": False,
                    "call_count": self._call_count[incident_id]
                }, indent=2)
            else:
                # If incident not found, return error with available incidents
                return json.dumps({
                    "success": False,
                    "error": f"Incident '{incident_id}' not found",
                    "message": "Use the available_incidents list to see what incidents exist",
                    "available_incidents": result.get("available_incidents", []),
                    "instruction": "Select one incident ID from the available_incidents list to generate a report"
                }, indent=2)
                
        except json.JSONDecodeError:
            return json.dumps({
                "success": False,
                "error": "Failed to parse database response",
                "raw_response": result_json
            }, indent=2)
    
    @classmethod
    def clear_cache(cls):
        """Clear the cache (useful for testing)."""
        cls._cache.clear()
        cls._call_count.clear()
        
    @classmethod 
    def get_call_stats(cls):
        """Get debugging statistics about tool calls."""
        return {
            "cached_incidents": list(cls._cache.keys()),
            "call_counts": dict(cls._call_count)
        }
