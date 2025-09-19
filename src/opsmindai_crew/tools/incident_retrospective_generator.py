from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

class IncidentRetrospectiveRequest(BaseModel):
    """Input schema for Incident Retrospective Generator Tool."""
    incident_data: Dict[str, Any] = Field(
        ...,
        description="Dictionary containing incident details from database including timestamps, priority, type, etc."
    )
    pr_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dictionary containing GitHub PR information if applicable (URL, merge time, etc.)"
    )
    confluence_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dictionary containing Confluence page information if applicable (URL, creation time, etc.)"
    )
    slack_details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Dictionary containing Slack message information (channel, timestamps, participants, etc.)"
    )

class IncidentRetrospectiveGenerator(BaseTool):
    """Tool for generating comprehensive incident retrospective reports with metrics and structured analysis."""

    name: str = "incident_retrospective_generator"
    description: str = (
        "Generates comprehensive structured incident retrospective reports including executive summary, "
        "timeline analysis, root cause analysis, impact assessment, and actionable recommendations. "
        "Calculates key metrics like response time, resolution time, and impact duration from incident data."
    )
    args_schema: Type[BaseModel] = IncidentRetrospectiveRequest

    def _run(self, incident_data: Dict[str, Any], pr_details: Optional[Dict[str, Any]] = None, 
             confluence_details: Optional[Dict[str, Any]] = None, slack_details: Optional[Dict[str, Any]] = None) -> str:
        try:
            # Generate unique report ID
            report_id = f"INC-RETRO-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            generation_timestamp = datetime.now().isoformat()
            
            # Calculate key metrics
            metrics = self._calculate_metrics(incident_data, pr_details, confluence_details, slack_details)
            
            # Generate report sections
            report = {
                "report_metadata": {
                    "report_id": report_id,
                    "generation_timestamp": generation_timestamp,
                    "incident_id": incident_data.get("incident_id", "N/A"),
                    "report_version": "1.0"
                },
                
                "executive_summary": self._generate_executive_summary(incident_data, metrics),
                
                "incident_details": self._extract_incident_details(incident_data),
                
                "timeline_events": self._generate_timeline(incident_data, pr_details, confluence_details, slack_details),
                
                "root_cause_analysis": self._generate_root_cause_analysis(incident_data),
                
                "resolution_actions": self._generate_resolution_actions(pr_details, confluence_details, incident_data),
                
                "impact_assessment": self._generate_impact_assessment(incident_data, metrics),
                
                "response_team": self._extract_response_team(incident_data, slack_details),
                
                "lessons_learned": self._generate_lessons_learned(incident_data, metrics),
                
                "technical_appendix": self._generate_technical_appendix(incident_data, pr_details, confluence_details, slack_details),
                
                "key_metrics": metrics
            }
            
            return json.dumps(report, indent=2, default=str)
            
        except Exception as e:
            return f"Error generating incident retrospective report: {str(e)}"

    def _calculate_metrics(self, incident_data: Dict[str, Any], pr_details: Optional[Dict[str, Any]], 
                          confluence_details: Optional[Dict[str, Any]], slack_details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate key incident metrics."""
        metrics = {}
        
        try:
            # Parse timestamps
            created_time = self._parse_timestamp(incident_data.get("created_at"))
            resolved_time = self._parse_timestamp(incident_data.get("resolved_at"))
            first_response_time = self._parse_timestamp(incident_data.get("first_response_at"))
            
            if created_time and resolved_time:
                total_duration = resolved_time - created_time
                metrics["total_incident_duration_minutes"] = int(total_duration.total_seconds() / 60)
                metrics["total_incident_duration_hours"] = round(total_duration.total_seconds() / 3600, 2)
                
            if created_time and first_response_time:
                response_time = first_response_time - created_time
                metrics["first_response_time_minutes"] = int(response_time.total_seconds() / 60)
                
            # Resolution method effectiveness
            metrics["resolution_method"] = self._determine_resolution_method(pr_details, confluence_details, incident_data)
            
            # Impact metrics
            metrics["affected_systems"] = len(incident_data.get("affected_systems", []))
            metrics["affected_users"] = incident_data.get("affected_users_count", 0)
            
            # Team metrics
            if slack_details:
                metrics["team_members_involved"] = len(set(slack_details.get("participants", [])))
                
        except Exception as e:
            metrics["calculation_error"] = str(e)
            
        return metrics

    def _parse_timestamp(self, timestamp_str: Optional[str]) -> Optional[datetime]:
        """Parse timestamp string to datetime object."""
        if not timestamp_str:
            return None
            
        try:
            # Try different timestamp formats
            formats = [
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ", 
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S"
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(timestamp_str, fmt)
                except ValueError:
                    continue
                    
            # If none work, try to parse as ISO format
            return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
        except Exception:
            return None

    def _generate_executive_summary(self, incident_data: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate executive summary section."""
        return {
            "incident_id": incident_data.get("incident_id", "N/A"),
            "severity": incident_data.get("severity", "Unknown"),
            "priority": incident_data.get("priority", "Unknown"),
            "status": incident_data.get("status", "Unknown"),
            "total_duration_hours": metrics.get("total_incident_duration_hours", "N/A"),
            "first_response_time_minutes": metrics.get("first_response_time_minutes", "N/A"),
            "affected_systems_count": metrics.get("affected_systems", 0),
            "affected_users_count": metrics.get("affected_users", 0),
            "resolution_method": metrics.get("resolution_method", "Unknown"),
            "brief_description": incident_data.get("description", "No description provided")[:200] + "..."
        }

    def _extract_incident_details(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and format incident details."""
        return {
            "incident_id": incident_data.get("incident_id"),
            "title": incident_data.get("title"),
            "description": incident_data.get("description"),
            "severity": incident_data.get("severity"),
            "priority": incident_data.get("priority"),
            "status": incident_data.get("status"),
            "created_at": incident_data.get("created_at"),
            "resolved_at": incident_data.get("resolved_at"),
            "reporter": incident_data.get("reporter"),
            "assigned_to": incident_data.get("assigned_to"),
            "tags": incident_data.get("tags", []),
            "incident_type": incident_data.get("incident_type")
        }

    def _generate_timeline(self, incident_data: Dict[str, Any], pr_details: Optional[Dict[str, Any]], 
                          confluence_details: Optional[Dict[str, Any]], slack_details: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate chronological timeline of events."""
        timeline = []
        
        # Add incident creation
        if incident_data.get("created_at"):
            timeline.append({
                "timestamp": incident_data.get("created_at"),
                "event": "Incident Created",
                "description": f"Incident {incident_data.get('incident_id')} was created",
                "source": "incident_system"
            })
        
        # Add first response
        if incident_data.get("first_response_at"):
            timeline.append({
                "timestamp": incident_data.get("first_response_at"),
                "event": "First Response",
                "description": "Initial response to incident",
                "source": "incident_system"
            })
            
        # Add PR events
        if pr_details:
            if pr_details.get("created_at"):
                timeline.append({
                    "timestamp": pr_details.get("created_at"),
                    "event": "Fix PR Created",
                    "description": f"PR {pr_details.get('number', 'N/A')} created: {pr_details.get('title', 'N/A')}",
                    "source": "github",
                    "url": pr_details.get("html_url")
                })
            if pr_details.get("merged_at"):
                timeline.append({
                    "timestamp": pr_details.get("merged_at"),
                    "event": "Fix PR Merged",
                    "description": f"PR {pr_details.get('number', 'N/A')} merged",
                    "source": "github",
                    "url": pr_details.get("html_url")
                })
        
        # Add Confluence documentation
        if confluence_details and confluence_details.get("created_at"):
            timeline.append({
                "timestamp": confluence_details.get("created_at"),
                "event": "Documentation Created",
                "description": f"Confluence page created: {confluence_details.get('title', 'N/A')}",
                "source": "confluence",
                "url": confluence_details.get("url")
            })
        
        # Add incident resolution
        if incident_data.get("resolved_at"):
            timeline.append({
                "timestamp": incident_data.get("resolved_at"),
                "event": "Incident Resolved",
                "description": "Incident marked as resolved",
                "source": "incident_system"
            })
        
        # Sort timeline by timestamp
        timeline.sort(key=lambda x: x.get("timestamp", ""))
        
        return timeline

    def _generate_root_cause_analysis(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate root cause analysis section."""
        return {
            "primary_cause": incident_data.get("root_cause", "Investigation ongoing"),
            "contributing_factors": incident_data.get("contributing_factors", []),
            "failure_point": incident_data.get("failure_point", "Unknown"),
            "logs_analysis": incident_data.get("logs_analysis", "No logs analysis available"),
            "technical_details": incident_data.get("technical_details", "No technical details provided"),
            "why_analysis": incident_data.get("five_whys", [])
        }

    def _generate_resolution_actions(self, pr_details: Optional[Dict[str, Any]], 
                                   confluence_details: Optional[Dict[str, Any]], 
                                   incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate resolution actions section."""
        actions = {
            "immediate_actions": incident_data.get("immediate_actions", []),
            "manual_steps": incident_data.get("manual_steps", []),
            "code_changes": [],
            "documentation": [],
            "preventive_measures": incident_data.get("preventive_measures", [])
        }
        
        if pr_details:
            actions["code_changes"].append({
                "type": "Pull Request",
                "title": pr_details.get("title", "N/A"),
                "url": pr_details.get("html_url"),
                "status": "Merged" if pr_details.get("merged_at") else "Open",
                "files_changed": pr_details.get("changed_files", 0),
                "additions": pr_details.get("additions", 0),
                "deletions": pr_details.get("deletions", 0)
            })
        
        if confluence_details:
            actions["documentation"].append({
                "type": "Confluence Page",
                "title": confluence_details.get("title", "N/A"),
                "url": confluence_details.get("url"),
                "created_at": confluence_details.get("created_at")
            })
        
        return actions

    def _generate_impact_assessment(self, incident_data: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate impact assessment section."""
        return {
            "duration_minutes": metrics.get("total_incident_duration_minutes", 0),
            "duration_hours": metrics.get("total_incident_duration_hours", 0),
            "affected_systems": incident_data.get("affected_systems", []),
            "affected_users_count": incident_data.get("affected_users_count", 0),
            "business_impact": incident_data.get("business_impact", "Unknown"),
            "financial_impact": incident_data.get("financial_impact", "Not calculated"),
            "customer_complaints": incident_data.get("customer_complaints", 0),
            "sla_breach": incident_data.get("sla_breach", False),
            "impact_level": incident_data.get("impact_level", "Unknown")
        }

    def _extract_response_team(self, incident_data: Dict[str, Any], slack_details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract response team information."""
        team = {
            "incident_commander": incident_data.get("incident_commander"),
            "assigned_engineers": incident_data.get("assigned_engineers", []),
            "escalated_to": incident_data.get("escalated_to", []),
            "external_contacts": incident_data.get("external_contacts", [])
        }
        
        if slack_details:
            team["slack_participants"] = list(set(slack_details.get("participants", [])))
            team["slack_channel"] = slack_details.get("channel")
        
        return team

    def _generate_lessons_learned(self, incident_data: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Generate lessons learned and recommendations."""
        return {
            "what_went_well": incident_data.get("what_went_well", []),
            "what_could_be_improved": incident_data.get("what_could_be_improved", []),
            "action_items": incident_data.get("action_items", []),
            "prevention_recommendations": incident_data.get("prevention_recommendations", []),
            "process_improvements": incident_data.get("process_improvements", []),
            "monitoring_enhancements": incident_data.get("monitoring_enhancements", []),
            "training_needs": incident_data.get("training_needs", [])
        }

    def _generate_technical_appendix(self, incident_data: Dict[str, Any], pr_details: Optional[Dict[str, Any]], 
                                   confluence_details: Optional[Dict[str, Any]], slack_details: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate technical appendix with raw data and references."""
        appendix = {
            "error_logs": incident_data.get("error_logs", []),
            "system_metrics": incident_data.get("system_metrics", {}),
            "configuration_changes": incident_data.get("configuration_changes", []),
            "monitoring_alerts": incident_data.get("monitoring_alerts", []),
            "external_references": []
        }
        
        # Add external references
        if pr_details and pr_details.get("html_url"):
            appendix["external_references"].append({
                "type": "GitHub PR",
                "url": pr_details.get("html_url"),
                "title": pr_details.get("title", "Fix PR")
            })
        
        if confluence_details and confluence_details.get("url"):
            appendix["external_references"].append({
                "type": "Confluence Documentation",
                "url": confluence_details.get("url"),
                "title": confluence_details.get("title", "Incident Documentation")
            })
        
        if slack_details and slack_details.get("channel"):
            appendix["external_references"].append({
                "type": "Slack Channel",
                "channel": slack_details.get("channel"),
                "message_count": len(slack_details.get("messages", []))
            })
        
        return appendix

    def _determine_resolution_method(self, pr_details: Optional[Dict[str, Any]], 
                                   confluence_details: Optional[Dict[str, Any]], 
                                   incident_data: Dict[str, Any]) -> str:
        """Determine the primary resolution method used."""
        methods = []
        
        if pr_details and pr_details.get("merged_at"):
            methods.append("Code Fix")
        if incident_data.get("manual_steps"):
            methods.append("Manual Intervention")
        if incident_data.get("configuration_changes"):
            methods.append("Configuration Change")
        if confluence_details:
            methods.append("Documentation Update")
        
        if not methods:
            return "Unknown"
        
        return ", ".join(methods)