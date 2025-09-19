from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from ..utils import get_incident_file_path, get_incident_summary


class FileOrganizerInput(BaseModel):
    incident_id: str = Field(..., description="The incident ID to organize files for")
    file_type: str = Field(default="report", description="Type of file: 'report', 'timeline', 'gantt'")


class FileOrganizerTool(BaseTool):
    name: str = "file_organizer"
    description: str = "Get the proper file path for incident outputs in organized folder structure"
    args_schema: Type[BaseModel] = FileOrganizerInput

    def _run(self, incident_id: str, file_type: str = "report") -> str:
        """Get the proper file path for incident outputs."""
        try:
            # Handle parameter descriptions if passed as dicts
            if isinstance(incident_id, dict):
                incident_id = incident_id.get('description', 'UNKNOWN_INCIDENT')
            if isinstance(file_type, dict):
                file_type = file_type.get('description', 'report')
            
            # Ensure string values
            incident_id = str(incident_id) if incident_id else 'UNKNOWN_INCIDENT'
            file_type = str(file_type) if file_type else 'report'
            
            # Determine filename based on type
            if file_type.lower() == "report":
                filename = f"COE_{incident_id}.pdf"
            elif file_type.lower() == "timeline":
                filename = f"timeline_{incident_id}.html"
            elif file_type.lower() == "gantt":
                filename = f"gantt_{incident_id}.html"
            else:
                filename = f"{file_type}_{incident_id}.pdf"
            
            # Get the proper file path
            file_path = get_incident_file_path(incident_id, filename)
            
            # Get current summary
            summary = get_incident_summary(incident_id)
            
            return f"""File Organization for Incident {incident_id}:

PROPER FILE PATHS:
- Report: {file_path}
- Timeline: {get_incident_file_path(incident_id, f'timeline_{incident_id}.html')}
- Gantt: {get_incident_file_path(incident_id, f'gantt_{incident_id}.html')}

CURRENT FILES IN FOLDER:
{summary.get('total_files', 0)} files found
Output folder: {summary.get('output_folder', 'Not created')}

IMPORTANT: Always use the same filename for the same file type to avoid duplicates.
Use 'COE_[incident_id].pdf' for the main report, not 'incident_report_X.pdf'."""
            
        except Exception as e:
            return f"File Organizer Error: {str(e)}"
