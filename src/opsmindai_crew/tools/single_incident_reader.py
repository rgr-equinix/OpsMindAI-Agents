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
        import time
        start_time = time.time()
        
        try:
            print(f"\n🔍 [REPORTING AGENT - DATABASE LOGGING] Starting incident read for: {incident_id}")
            
            if not incident_id or incident_id.strip() == "" or incident_id.strip().upper() == "ALL" or incident_id.strip().startswith("["):
                return json.dumps({
                    "success": False,
                    "error": "Invalid incident_id. Provide a concrete INC-... value.",
                    "incident_id": incident_id
                })

            db = IncidentDatabaseTool()
            
            # First, list ALL database rows to show current state
            print("📋 [DATABASE STATE] Listing all incidents before report generation:")
            all_incidents = db._run(operation="list")
            
            try:
                incidents_data = json.loads(all_incidents)
                if incidents_data.get("success") and incidents_data.get("count", 0) > 0:
                    print(f"📊 [DATABASE STATE] Found {incidents_data['count']} incidents in database:")
                    for i, incident in enumerate(incidents_data.get("data", []), 1):
                        incident_id_db = incident.get("incident_id", "Unknown")
                        title = incident.get("title", "No title")
                        status = incident.get("status", "unknown")
                        severity = incident.get("severity", "unknown")
                        created_at = incident.get("created_at", "unknown")
                        print(f"   {i}. 🆔 {incident_id_db} | 📋 {title} | 🚨 {severity} | 📊 {status} | 📅 {created_at}")
                else:
                    print("❌ [DATABASE STATE] No incidents found in database")
            except json.JSONDecodeError:
                print("⚠️ [DATABASE STATE] Could not parse incident list response")
            
            print(f"🎯 [TARGET INCIDENT] Now reading specific incident: {incident_id}")
            
            # Now read the specific incident
            result = db._run(operation="read", incident_id=incident_id)
            
            # Log the specific incident data
            try:
                result_data = json.loads(result)
                if result_data.get("success") and "data" in result_data:
                    incident_data = result_data["data"]
                    print(f"✅ [TARGET INCIDENT] Successfully retrieved incident data:")
                    print(f"   🆔 ID: {incident_data.get('incident_id', 'Unknown')}")
                    print(f"   📋 Title: {incident_data.get('title', 'No title')}")
                    print(f"   🚨 Severity: {incident_data.get('severity', 'unknown')}")
                    print(f"   📊 Status: {incident_data.get('status', 'unknown')}")
                    print(f"   🏢 Service: {incident_data.get('service_name', 'unknown')}")
                    print(f"   👤 Commander: {incident_data.get('commander', 'unknown')}")
                    print(f"   📞 Comm Lead: {incident_data.get('communication_lead', 'unknown')}")
                    print(f"   📅 Created: {incident_data.get('created_at', 'unknown')}")
                    print(f"   ✅ Resolved: {incident_data.get('resolved_at', 'not resolved')}")
                    
                    # Show timeline info if available
                    timeline = incident_data.get('timeline', [])
                    if timeline:
                        print(f"   ⏰ Timeline Events: {len(timeline)} events")
                    else:
                        print(f"   ⏰ Timeline Events: No timeline data available")
                    
                    # ENHANCED: Check if incident is resolved and show resolution details
                    status = incident_data.get('status', '').lower()
                    resolution_details = incident_data.get('resolution_details')
                    if status == 'resolved' and resolution_details:
                        print(f"   🎯 [RESOLUTION STATUS] This incident is RESOLVED with detailed resolution information!")
                        print(f"   📝 Resolution Details: {resolution_details}")
                        print(f"   💡 [REPORTING GUIDANCE] Report should focus on:")
                        print(f"      • Root cause analysis from resolution")
                        print(f"      • Implementation details of the fix")
                        print(f"      • Prevention strategies to avoid recurrence")
                        print(f"      • Lessons learned from the resolution process")
                    elif status == 'resolved':
                        print(f"   🎯 [RESOLUTION STATUS] Incident is resolved but no resolution details available")
                        print(f"   ⚠️ [REPORTING GUIDANCE] Limited resolution information for comprehensive analysis")
                    else:
                        print(f"   🔄 [INCIDENT STATUS] Incident is {status.upper()} - ongoing situation")
                        print(f"   📊 [REPORTING GUIDANCE] Report should focus on current status and next steps")
                        
                    print("🚀 [REPORTING AGENT] Ready to proceed with report generation")
                else:
                    print(f"❌ [TARGET INCIDENT] Failed to read incident: {result_data.get('error', 'unknown error')}")
            except json.JSONDecodeError:
                print("⚠️ [TARGET INCIDENT] Could not parse incident read response")
            
            elapsed = time.time() - start_time
            print(f"⏱️ [SingleIncidentReader] Database logging and read completed in {elapsed:.2f}s\n")
            
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[SingleIncidentReader ERROR] Failed in {elapsed:.2f}s: {e}")
            return json.dumps({
                "success": False,
                "error": f"SingleIncidentReader failed: {str(e)}",
                "incident_id": incident_id
            })
