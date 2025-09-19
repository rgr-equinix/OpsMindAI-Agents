from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional
import json
from .single_incident_reader import SingleIncidentReader

class TimelineExtractorInput(BaseModel):
    """Input schema for Timeline Extractor Tool."""
    incident_id: str = Field(..., description="The incident ID to extract timeline data for")

class TimelineExtractor(BaseTool):
    """Tool that extracts and formats timeline data from incident database."""
    
    name: str = "timeline_extractor"
    description: str = (
        "Extracts and formats timeline information from incident data. "
        "Returns structured timeline data if present, or indicates when timeline data is missing. "
        "Use this to ensure timeline data is properly included in reports."
    )
    args_schema: Type[BaseModel] = TimelineExtractorInput
    
    def _run(self, incident_id: str) -> str:
        """Extract timeline data for the specified incident."""
        
        # Clean the incident ID
        incident_id = str(incident_id).strip()
        
        # Get incident data using single incident reader
        reader = SingleIncidentReader()
        incident_json = reader._run(incident_id)
        
        try:
            incident_result = json.loads(incident_json)
            
            if not incident_result.get("success"):
                return json.dumps({
                    "success": False,
                    "error": "Could not retrieve incident data",
                    "incident_id": incident_id,
                    "details": incident_result.get("error", "Unknown error")
                }, indent=2)
            
            incident_data = incident_result.get("data", {})
            timeline_raw = incident_data.get("timeline", "")
            
            # Process timeline data
            timeline_analysis = self._analyze_timeline(timeline_raw, incident_data)
            
            return json.dumps({
                "success": True,
                "incident_id": incident_id,
                "timeline_present": bool(timeline_raw and timeline_raw.strip()),
                "timeline_raw": timeline_raw,
                "timeline_analysis": timeline_analysis,
                "other_incident_fields": {
                    "service_name": incident_data.get("service_name"),
                    "severity": incident_data.get("severity"),
                    "status": incident_data.get("status"),
                    "commander": incident_data.get("commander"),
                    "communication_lead": incident_data.get("communication_lead"),
                    "playbook_applied": incident_data.get("playbook_applied"),
                    "resolution_details": incident_data.get("resolution_details"),
                    "timestamp": incident_data.get("timestamp")
                }
            }, indent=2)
            
        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Failed to parse incident data: {str(e)}",
                "incident_id": incident_id
            }, indent=2)
    
    def _analyze_timeline(self, timeline_raw: str, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze timeline data and extract key events."""
        
        if not timeline_raw or not timeline_raw.strip():
            return {
                "has_timeline": False,
                "message": "No timeline data found in incident record",
                "events": [],
                "duration_analysis": "Cannot calculate duration - no timeline data"
            }
        
        # Parse timeline events (assuming newline-separated format)
        events = []
        lines = timeline_raw.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Try to extract time and event description
            if ' - ' in line:
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    time_str, event_desc = parts
                    events.append({
                        "time": time_str.strip(),
                        "event": event_desc.strip(),
                        "raw_line": line
                    })
                else:
                    events.append({
                        "time": "Unknown",
                        "event": line,
                        "raw_line": line
                    })
            else:
                # Line without time separator
                events.append({
                    "time": "Unknown",
                    "event": line,
                    "raw_line": line
                })
        
        # Calculate duration if possible
        duration_analysis = self._calculate_duration(events)
        
        return {
            "has_timeline": True,
            "event_count": len(events),
            "events": events,
            "duration_analysis": duration_analysis,
            "timeline_quality": "Good" if len(events) >= 3 else "Limited"
        }
    
    def _calculate_duration(self, events: list) -> str:
        """Try to calculate incident duration from timeline events."""
        
        if len(events) < 2:
            return "Cannot calculate duration - insufficient timeline events"
        
        first_event = events[0]
        last_event = events[-1]
        
        # Simple heuristic - look for time patterns
        first_time = first_event.get("time", "")
        last_time = last_event.get("time", "")
        
        if first_time and last_time and first_time != "Unknown" and last_time != "Unknown":
            return f"Incident duration from {first_time} to {last_time} (based on timeline events)"
        else:
            return f"Duration calculated from {len(events)} timeline events"
