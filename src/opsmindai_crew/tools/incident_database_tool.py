from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional, ClassVar
import json
from datetime import datetime
import time
import os

class IncidentDatabaseRequest(BaseModel):
    """Input schema for Incident Database Tool."""
    operation: str = Field(
        ..., 
        description="Operation to perform: 'create', 'read', 'update', 'list', or 'delete'"
    )
    incident_id: Optional[str] = Field(
        None, 
        description="Unique incident ID (required for read, update, delete operations). Auto-generated if not provided for create."
    )
    service_name: Optional[str] = Field(
        None, 
        description="Name of the affected service"
    )
    severity: Optional[str] = Field(
        None, 
        description="Incident severity level (e.g., Critical, High, Medium, Low)"
    )
    status: Optional[str] = Field(
        None, 
        description="Current incident status (e.g., Open, In Progress, Resolved, Closed)"
    )
    timestamp: Optional[str] = Field(
        None, 
        description="Incident timestamp (if not provided, current timestamp will be used)"
    )
    commander: Optional[str] = Field(
        None, 
        description="Name of the incident commander"
    )
    communication_lead: Optional[str] = Field(
        None, 
        description="Name of the communication lead"
    )
    playbook_applied: Optional[str] = Field(
        None, 
        description="Name or reference of the playbook applied"
    )
    timeline: Optional[str] = Field(
        None, 
        description="Incident timeline or chronological events"
    )
    resolution_details: Optional[str] = Field(
        None, 
        description="Details about how the incident was resolved"
    )

class IncidentDatabaseTool(BaseTool):
    """Tool for managing incident data in a persistent file-based database with CRUD operations."""

    name: str = "incident_database_tool"
    description: str = (
        "Persistent file-based database tool for storing and retrieving incident data. "
        "Supports CREATE, READ, UPDATE, LIST, and DELETE operations for incident records. "
        "Data persists to 'incidents_database.json' file across automation runs. "
        "Use 'create' to add new incidents, 'read' to get specific incidents by ID, "
        "'update' to modify existing incidents, 'list' to get all incidents, "
        "and 'delete' to remove incidents."
    )
    args_schema: Type[BaseModel] = IncidentDatabaseRequest

    # CLASS-LEVEL STORAGE for persistent data across automation runs
    _incident_store: ClassVar[Dict[str, Dict[str, Any]]] = {}
    _db_file_path: ClassVar[str] = "incidents_database.json"

    def _run(
        self,
        operation: str,
        incident_id: Optional[str] = None,
        service_name: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        timestamp: Optional[str] = None,
        commander: Optional[str] = None,
        communication_lead: Optional[str] = None,
        playbook_applied: Optional[str] = None,
        timeline: Optional[str] = None,
        resolution_details: Optional[str] = None
    ) -> str:
        """Execute the requested database operation."""
        
        try:
            # Normalize operation to lowercase for case-insensitive matching
            operation = operation.lower().strip()
            
            if operation == "create":
                return self._create_incident(
                    incident_id, service_name, severity, status, timestamp,
                    commander, communication_lead, playbook_applied, timeline, resolution_details
                )
            elif operation == "read":
                return self._read_incident(incident_id)
            elif operation == "update":
                return self._update_incident(
                    incident_id, service_name, severity, status, timestamp,
                    commander, communication_lead, playbook_applied, timeline, resolution_details
                )
            elif operation == "list":
                return self._list_incidents()
            elif operation == "delete":
                return self._delete_incident(incident_id)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"Invalid operation '{operation}'. Supported operations: create, read, update, list, delete"
                }, indent=2)
                
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"Database operation failed: {str(e)}",
                "operation": operation
            }, indent=2)

    def _load_from_file(self) -> None:
        """Load incidents from JSON file into memory store."""
        try:
            if os.path.exists(self._db_file_path):
                with open(self._db_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Update class-level store with file data
                    self._incident_store.update(data)
                    print(f"[DB] Loaded {len(data)} incidents from {self._db_file_path}")
            else:
                print(f"[DB] Database file {self._db_file_path} not found, starting with empty database")
        except Exception as e:
            print(f"[DB] Error loading from file: {e}")

    def _save_to_file(self) -> None:
        """Save incidents from memory store to JSON file."""
        try:
            print(f"[DB DEBUG] Attempting to save {len(self._incident_store)} incidents to {self._db_file_path}")
            with open(self._db_file_path, 'w', encoding='utf-8') as f:
                json.dump(self._incident_store, f, indent=2, ensure_ascii=False)
            print(f"[DB] Saved {len(self._incident_store)} incidents to {self._db_file_path}")
            print(f"[DB DEBUG] File exists after save: {os.path.exists(self._db_file_path)}")
        except Exception as e:
            print(f"[DB] Error saving to file: {e}")
            import traceback
            traceback.print_exc()

    def _ensure_data_loaded(self) -> None:
        """Ensure data is loaded from file if store is empty."""
        if not self._incident_store:
            self._load_from_file()

    def _generate_incident_id(self) -> str:
        """
        Generate a unique incident ID using timestamp and milliseconds.
        Format: INC-{timestamp_ms}
        Example: INC-1758546061234
        """
        timestamp_ms = int(time.time() * 1000)  # Milliseconds since epoch
        return f"INC-{timestamp_ms}"

    def _create_incident(
        self,
        incident_id: Optional[str],
        service_name: Optional[str],
        severity: Optional[str],
        status: Optional[str],
        timestamp: Optional[str],
        commander: Optional[str],
        communication_lead: Optional[str],
        playbook_applied: Optional[str],
        timeline: Optional[str],
        resolution_details: Optional[str]
    ) -> str:
        """Create a new incident record."""
        
        # Ensure data is loaded from file
        self._ensure_data_loaded()
        
        # Auto-generate ID if not provided, or validate format if provided
        if not incident_id:
            incident_id = self._generate_incident_id()
        else:
            # Validate that provided incident_id follows INC-{timestamp_ms} format
            import re
            if not re.match(r'^INC-\d+$', incident_id):
                # If invalid format, generate a new compliant ID
                print(f"[DB] Warning: Invalid incident ID format '{incident_id}', generating compliant ID")
                incident_id = self._generate_incident_id()
        
        # Use current timestamp if not provided
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        # Validate required fields for meaningful incident
        if not service_name:
            return json.dumps({
                "success": False,
                "error": "service_name is required for creating an incident"
            }, indent=2)
        
        incident_record = {
            "incident_id": incident_id,
            "service_name": service_name,
            "severity": severity or "Medium",  # Default severity
            "status": status or "Open",  # Default status
            "timestamp": timestamp,
            "commander": commander,
            "communication_lead": communication_lead,
            "playbook_applied": playbook_applied,
            "timeline": timeline,
            "resolution_details": resolution_details,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat()
        }
        
        # Store the incident (overwrite if exists - no "already exists" error)
        IncidentDatabaseTool._incident_store[incident_id] = incident_record
        
        # Save to file for persistence
        self._save_to_file()
        
        return json.dumps({
            "success": True,
            "message": f"Incident '{incident_id}' created successfully",
            "data": incident_record
        }, indent=2)

    def _read_incident(self, incident_id: Optional[str]) -> str:
        """Read an incident record by ID."""
        
        # Ensure data is loaded from file
        self._ensure_data_loaded()
        
        if not incident_id:
            return json.dumps({
                "success": False,
                "error": "incident_id is required for read operation"
            }, indent=2)
        
        if incident_id not in IncidentDatabaseTool._incident_store:
            return json.dumps({
                "success": False,
                "error": f"Incident with ID '{incident_id}' not found",
                "available_incidents": list(IncidentDatabaseTool._incident_store.keys())
            }, indent=2)
        
        return json.dumps({
            "success": True,
            "data": IncidentDatabaseTool._incident_store[incident_id]
        }, indent=2)

    def _update_incident(
        self,
        incident_id: Optional[str],
        service_name: Optional[str],
        severity: Optional[str],
        status: Optional[str],
        timestamp: Optional[str],
        commander: Optional[str],
        communication_lead: Optional[str],
        playbook_applied: Optional[str],
        timeline: Optional[str],
        resolution_details: Optional[str]
    ) -> str:
        """Update an existing incident record."""
        
        # Ensure data is loaded from file
        self._ensure_data_loaded()
        
        if not incident_id:
            return json.dumps({
                "success": False,
                "error": "incident_id is required for update operation"
            }, indent=2)
        
        if incident_id not in IncidentDatabaseTool._incident_store:
            return json.dumps({
                "success": False,
                "error": f"Incident with ID '{incident_id}' not found",
                "available_incidents": list(IncidentDatabaseTool._incident_store.keys())
            }, indent=2)
        
        # Get existing record
        incident_record = IncidentDatabaseTool._incident_store[incident_id]
        
        # Track what was updated
        updates = {}
        
        # Update fields that are provided (non-None values)
        if service_name is not None:
            incident_record["service_name"] = service_name
            updates["service_name"] = service_name
        if severity is not None:
            incident_record["severity"] = severity
            updates["severity"] = severity
        if status is not None:
            incident_record["status"] = status
            updates["status"] = status
        if timestamp is not None:
            incident_record["timestamp"] = timestamp
            updates["timestamp"] = timestamp
        if commander is not None:
            incident_record["commander"] = commander
            updates["commander"] = commander
        if communication_lead is not None:
            incident_record["communication_lead"] = communication_lead
            updates["communication_lead"] = communication_lead
        if playbook_applied is not None:
            incident_record["playbook_applied"] = playbook_applied
            updates["playbook_applied"] = playbook_applied
        if timeline is not None:
            incident_record["timeline"] = timeline
            updates["timeline"] = timeline
        if resolution_details is not None:
            incident_record["resolution_details"] = resolution_details
            updates["resolution_details"] = resolution_details
        
        # Always update last_updated timestamp
        incident_record["last_updated"] = datetime.now().isoformat()
        
        if not updates:
            return json.dumps({
                "success": False,
                "error": "No fields provided for update. At least one field must be specified.",
                "current_data": incident_record
            }, indent=2)
        
        # Save to file for persistence
        self._save_to_file()
        
        return json.dumps({
            "success": True,
            "message": f"Incident '{incident_id}' updated successfully",
            "updated_fields": list(updates.keys()),
            "updates": updates,
            "data": incident_record
        }, indent=2)

    def _list_incidents(self) -> str:
        """List all incident records."""
        
        # Ensure data is loaded from file
        self._ensure_data_loaded()
        
        incident_count = len(IncidentDatabaseTool._incident_store)
        
        if incident_count == 0:
            return json.dumps({
                "success": True,
                "message": "No incidents found in database",
                "count": 0,
                "data": []
            }, indent=2)
        
        # Sort incidents by created_at timestamp for consistent ordering
        sorted_incidents = sorted(
            IncidentDatabaseTool._incident_store.values(),
            key=lambda x: x.get("created_at", ""),
            reverse=True  # Most recent first
        )
        
        return json.dumps({
            "success": True,
            "count": incident_count,
            "message": f"Retrieved {incident_count} incident(s)",
            "data": sorted_incidents
        }, indent=2)

    def _delete_incident(self, incident_id: Optional[str]) -> str:
        """Delete an incident record by ID."""
        
        # Ensure data is loaded from file
        self._ensure_data_loaded()
        
        if not incident_id:
            return json.dumps({
                "success": False,
                "error": "incident_id is required for delete operation"
            }, indent=2)
        
        if incident_id not in IncidentDatabaseTool._incident_store:
            return json.dumps({
                "success": False,
                "error": f"Incident with ID '{incident_id}' not found",
                "available_incidents": list(IncidentDatabaseTool._incident_store.keys())
            }, indent=2)
        
        deleted_record = IncidentDatabaseTool._incident_store.pop(incident_id)
        
        # Save to file for persistence
        self._save_to_file()
        
        return json.dumps({
            "success": True,
            "message": f"Incident '{incident_id}' deleted successfully",
            "deleted_data": deleted_record,
            "remaining_count": len(IncidentDatabaseTool._incident_store)
        }, indent=2)