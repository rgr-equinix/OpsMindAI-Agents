from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import json
from datetime import datetime

class IncidentData(BaseModel):
    """Input schema for JSON Report Formatter Tool."""
    incident_id: str = Field(..., description="Unique incident identifier")
    title: str = Field(..., description="Brief incident title")
    description: str = Field(..., description="Detailed incident description")
    severity: str = Field(..., description="Incident severity level (Critical, High, Medium, Low)")
    start_time: str = Field(..., description="Incident start time (ISO format)")
    end_time: Optional[str] = Field(None, description="Incident end time (ISO format)")
    affected_services: List[str] = Field(..., description="List of affected services/systems")
    timeline_events: List[Dict[str, Any]] = Field(..., description="Timeline events with timestamps and descriptions")
    metrics: Dict[str, Any] = Field(..., description="Impact metrics (downtime, users affected, etc.)")
    root_causes: List[str] = Field(..., description="Identified root causes")
    lessons_learned: List[str] = Field(..., description="Lessons learned from the incident")
    action_items: List[Dict[str, Any]] = Field(..., description="Action items with priority, owner, and due date")
    responders: List[str] = Field(..., description="List of incident responders")
    raw_logs: Optional[List[str]] = Field([], description="Raw log entries for appendix")
    additional_notes: Optional[str] = Field("", description="Additional notes or context")

class JsonReportFormatter(BaseTool):
    """Tool for formatting raw incident data into professional JSON reports."""

    name: str = "JSON Report Formatter"
    description: str = (
        "Formats raw incident data into a professional, well-structured JSON report "
        "suitable for display and PDF conversion. Creates compliance-ready reports "
        "with proper sections, formatting metadata, and structured content."
    )
    args_schema: Type[BaseModel] = IncidentData

    def _run(
        self,
        incident_id: str,
        title: str,
        description: str,
        severity: str,
        start_time: str,
        affected_services: List[str],
        timeline_events: List[Dict[str, Any]],
        metrics: Dict[str, Any],
        root_causes: List[str],
        lessons_learned: List[str],
        action_items: List[Dict[str, Any]],
        responders: List[str],
        end_time: Optional[str] = None,
        raw_logs: Optional[List[str]] = None,
        additional_notes: Optional[str] = ""
    ) -> str:
        """Format incident data into a professional JSON report."""
        
        try:
            # Set defaults for optional parameters
            if raw_logs is None:
                raw_logs = []
            
            # Calculate duration if end time is provided
            duration = "Ongoing"
            if end_time:
                try:
                    start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                    end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                    duration_seconds = (end_dt - start_dt).total_seconds()
                    hours = int(duration_seconds // 3600)
                    minutes = int((duration_seconds % 3600) // 60)
                    duration = f"{hours}h {minutes}m"
                except:
                    duration = "Duration calculation error"

            # Generate executive summary
            affected_services_text = ", ".join(affected_services[:3])
            if len(affected_services) > 3:
                affected_services_text += f" and {len(affected_services) - 3} others"
            
            executive_summary = {
                "overview": f"Incident {incident_id} occurred affecting {affected_services_text}.",
                "severity": severity,
                "duration": duration,
                "impact": self._generate_impact_summary(metrics),
                "status": "Resolved" if end_time else "Ongoing"
            }

            # Sort timeline events by timestamp
            sorted_timeline = sorted(timeline_events, key=lambda x: x.get('timestamp', ''))

            # Categorize lessons learned
            categorized_lessons = self._categorize_lessons_learned(lessons_learned)

            # Prioritize and structure action items
            structured_action_items = self._structure_action_items(action_items)

            # Format the complete report
            formatted_report = {
                "metadata": {
                    "report_type": "incident_report",
                    "incident_id": incident_id,
                    "generated_at": datetime.now().isoformat(),
                    "format_version": "1.0",
                    "pdf_formatting": {
                        "page_orientation": "portrait",
                        "font_family": "Arial",
                        "title_font_size": 16,
                        "header_font_size": 14,
                        "body_font_size": 11,
                        "margin_top": 20,
                        "margin_bottom": 20,
                        "margin_left": 15,
                        "margin_right": 15,
                        "line_spacing": 1.2,
                        "color_scheme": {
                            "primary": "#2E3440",
                            "secondary": "#4C566A",
                            "accent": "#5E81AC",
                            "danger": "#BF616A",
                            "warning": "#EBCB8B",
                            "success": "#A3BE8C"
                        }
                    }
                },
                "report": {
                    "header": {
                        "title": f"Incident Report: {title}",
                        "incident_id": incident_id,
                        "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"),
                        "severity_badge": {
                            "text": severity,
                            "color": self._get_severity_color(severity)
                        }
                    },
                    "executive_summary": {
                        "section_title": "Executive Summary",
                        "content": executive_summary,
                        "formatting": {
                            "background_color": "#F8F9FA",
                            "border_left": "4px solid #5E81AC",
                            "padding": 15
                        }
                    },
                    "incident_details": {
                        "section_title": "Incident Details",
                        "basic_information": {
                            "incident_id": incident_id,
                            "title": title,
                            "description": description,
                            "severity": severity,
                            "start_time": start_time,
                            "end_time": end_time or "Ongoing",
                            "duration": duration,
                            "affected_services": affected_services,
                            "responders": responders
                        },
                        "timeline": {
                            "title": "Incident Timeline",
                            "events": sorted_timeline,
                            "formatting": {
                                "style": "timeline",
                                "show_timestamps": True,
                                "highlight_critical": True
                            }
                        }
                    },
                    "impact_analysis": {
                        "section_title": "Impact Analysis",
                        "metrics": metrics,
                        "visual_elements": {
                            "charts_recommended": [
                                "downtime_chart",
                                "users_affected_graph",
                                "service_availability_timeline"
                            ]
                        },
                        "summary": self._generate_detailed_impact_analysis(metrics, affected_services)
                    },
                    "root_cause_analysis": {
                        "section_title": "Root Cause Analysis",
                        "primary_causes": root_causes,
                        "analysis_method": "5 Whys / Fishbone Analysis",
                        "contributing_factors": self._extract_contributing_factors(root_causes),
                        "formatting": {
                            "use_numbered_list": True,
                            "highlight_primary": True
                        }
                    },
                    "lessons_learned": {
                        "section_title": "Lessons Learned",
                        "categorized": categorized_lessons,
                        "formatting": {
                            "group_by_category": True,
                            "use_icons": True
                        }
                    },
                    "action_items": {
                        "section_title": "Action Items & Recommendations",
                        "items": structured_action_items,
                        "summary": {
                            "total_items": len(action_items),
                            "high_priority": len([item for item in action_items if item.get('priority', '').lower() == 'high']),
                            "assigned_owners": list(set([item.get('owner', 'Unassigned') for item in action_items]))
                        },
                        "formatting": {
                            "show_priority_badges": True,
                            "group_by_priority": True,
                            "show_due_dates": True
                        }
                    },
                    "appendices": {
                        "section_title": "Appendices",
                        "raw_data": {
                            "title": "Appendix A: Raw Incident Data",
                            "timeline_raw": timeline_events,
                            "metrics_raw": metrics,
                            "additional_context": additional_notes
                        },
                        "logs": {
                            "title": "Appendix B: Log Entries",
                            "entries": raw_logs[:50],  # Limit to first 50 entries
                            "note": f"Showing first 50 of {len(raw_logs)} log entries" if len(raw_logs) > 50 else f"All {len(raw_logs)} log entries included"
                        },
                        "formatting": {
                            "font_family": "monospace",
                            "font_size": 9,
                            "preserve_formatting": True
                        }
                    }
                }
            }

            return json.dumps(formatted_report, indent=2, ensure_ascii=False)

        except Exception as e:
            return f"Error formatting incident report: {str(e)}"

    def _generate_impact_summary(self, metrics: Dict[str, Any]) -> str:
        """Generate a concise impact summary from metrics."""
        impact_parts = []
        
        if "users_affected" in metrics:
            impact_parts.append(f"{metrics['users_affected']} users affected")
        
        if "downtime_minutes" in metrics:
            hours = int(metrics["downtime_minutes"]) // 60
            minutes = int(metrics["downtime_minutes"]) % 60
            if hours > 0:
                impact_parts.append(f"{hours}h {minutes}m downtime")
            else:
                impact_parts.append(f"{minutes}m downtime")
        
        if "revenue_impact" in metrics:
            impact_parts.append(f"${metrics['revenue_impact']} revenue impact")
        
        return "; ".join(impact_parts) if impact_parts else "Impact being assessed"

    def _generate_detailed_impact_analysis(self, metrics: Dict[str, Any], affected_services: List[str]) -> Dict[str, Any]:
        """Generate detailed impact analysis."""
        return {
            "service_impact": {
                "total_services_affected": len(affected_services),
                "services_list": affected_services,
                "criticality": "High" if len(affected_services) > 3 else "Medium"
            },
            "user_impact": {
                "users_affected": metrics.get("users_affected", "Unknown"),
                "percentage_of_user_base": metrics.get("percentage_affected", "Unknown")
            },
            "business_impact": {
                "revenue_impact": metrics.get("revenue_impact", "Unknown"),
                "sla_breach": metrics.get("sla_breach", False),
                "customer_complaints": metrics.get("customer_complaints", 0)
            }
        }

    def _categorize_lessons_learned(self, lessons_learned: List[str]) -> Dict[str, List[str]]:
        """Categorize lessons learned by type."""
        categories = {
            "process_improvements": [],
            "technical_enhancements": [],
            "monitoring_alerts": [],
            "communication": [],
            "training": [],
            "general": []
        }
        
        for lesson in lessons_learned:
            lesson_lower = lesson.lower()
            if any(word in lesson_lower for word in ["process", "procedure", "workflow"]):
                categories["process_improvements"].append(lesson)
            elif any(word in lesson_lower for word in ["technical", "code", "system", "infrastructure"]):
                categories["technical_enhancements"].append(lesson)
            elif any(word in lesson_lower for word in ["monitoring", "alert", "notification", "dashboard"]):
                categories["monitoring_alerts"].append(lesson)
            elif any(word in lesson_lower for word in ["communication", "notify", "inform", "escalation"]):
                categories["communication"].append(lesson)
            elif any(word in lesson_lower for word in ["training", "knowledge", "documentation", "runbook"]):
                categories["training"].append(lesson)
            else:
                categories["general"].append(lesson)
        
        # Remove empty categories
        return {k: v for k, v in categories.items() if v}

    def _structure_action_items(self, action_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Structure and prioritize action items."""
        priority_order = {"high": 1, "medium": 2, "low": 3}
        
        structured_items = []
        for item in action_items:
            structured_item = {
                "title": item.get("title", "Untitled Action Item"),
                "description": item.get("description", ""),
                "priority": item.get("priority", "medium").lower(),
                "owner": item.get("owner", "Unassigned"),
                "due_date": item.get("due_date", ""),
                "status": item.get("status", "open"),
                "priority_score": priority_order.get(item.get("priority", "medium").lower(), 2),
                "formatting": {
                    "priority_color": self._get_priority_color(item.get("priority", "medium").lower()),
                    "status_badge": item.get("status", "open").upper()
                }
            }
            structured_items.append(structured_item)
        
        # Sort by priority then by due date
        return sorted(structured_items, key=lambda x: (x["priority_score"], x.get("due_date", "9999-12-31")))

    def _extract_contributing_factors(self, root_causes: List[str]) -> List[str]:
        """Extract contributing factors from root causes."""
        contributing_factors = []
        for cause in root_causes:
            if "due to" in cause.lower() or "caused by" in cause.lower():
                # Extract the part after "due to" or "caused by"
                parts = cause.lower().split("due to")
                if len(parts) == 1:
                    parts = cause.lower().split("caused by")
                if len(parts) > 1:
                    contributing_factors.append(parts[1].strip().capitalize())
        
        return contributing_factors if contributing_factors else ["Analysis in progress"]

    def _get_severity_color(self, severity: str) -> str:
        """Get color code for severity level."""
        severity_colors = {
            "critical": "#BF616A",
            "high": "#D08770", 
            "medium": "#EBCB8B",
            "low": "#A3BE8C"
        }
        return severity_colors.get(severity.lower(), "#4C566A")

    def _get_priority_color(self, priority: str) -> str:
        """Get color code for priority level."""
        priority_colors = {
            "high": "#BF616A",
            "medium": "#EBCB8B",
            "low": "#A3BE8C"
        }
        return priority_colors.get(priority.lower(), "#4C566A")