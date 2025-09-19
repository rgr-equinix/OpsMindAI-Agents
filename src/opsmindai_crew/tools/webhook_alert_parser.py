from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, Optional
import json
from datetime import datetime

class WebhookAlertParserInput(BaseModel):
    """Input schema for Webhook Alert Parser Tool."""
    webhook_payload: str = Field(
        ..., 
        description="JSON string of the incoming webhook payload from monitoring system"
    )
    source_system: str = Field(
        ..., 
        description="The monitoring system source (grafana, pagerduty, prometheus, datadog, newrelic, etc.)"
    )
    severity_thresholds: Optional[str] = Field(
        None, 
        description="Optional JSON string with custom severity thresholds (e.g., {'critical': 90, 'high': 70, 'medium': 50})"
    )

class WebhookAlertParserTool(BaseTool):
    """Tool for parsing webhook alert payloads from monitoring systems and normalizing them into a standard incident format."""

    name: str = "webhook_alert_parser"
    description: str = (
        "Parses webhook payloads from monitoring systems (Grafana, PagerDuty, Prometheus, etc.) "
        "and normalizes them into a standard incident format. Extracts service name, alert type, "
        "severity, metric values, timestamps, and determines if an incident should be created."
    )
    args_schema: Type[BaseModel] = WebhookAlertParserInput

    def _run(
        self, 
        webhook_payload: str, 
        source_system: str, 
        severity_thresholds: Optional[str] = None
    ) -> str:
        try:
            # Parse the webhook payload
            try:
                payload = json.loads(webhook_payload)
            except json.JSONDecodeError as e:
                return json.dumps({
                    "error": f"Invalid JSON payload: {str(e)}",
                    "success": False
                })

            # Parse optional severity thresholds
            thresholds = {
                "critical": 90,
                "high": 70,
                "medium": 50,
                "low": 30
            }
            
            if severity_thresholds:
                try:
                    custom_thresholds = json.loads(severity_thresholds)
                    thresholds.update(custom_thresholds)
                except json.JSONDecodeError:
                    pass  # Use default thresholds if parsing fails

            # Normalize based on source system
            source_system = source_system.lower()
            
            if source_system == "grafana":
                normalized_data = self._parse_grafana(payload)
            elif source_system == "pagerduty":
                normalized_data = self._parse_pagerduty(payload)
            elif source_system == "prometheus":
                normalized_data = self._parse_prometheus(payload)
            elif source_system == "datadog":
                normalized_data = self._parse_datadog(payload)
            elif source_system == "newrelic":
                normalized_data = self._parse_newrelic(payload)
            else:
                normalized_data = self._parse_generic(payload)

            # Calculate severity based on thresholds
            severity = self._calculate_severity(normalized_data.get("metric_value", 0), thresholds)
            normalized_data["severity"] = severity

            # Determine if incident should be created
            normalized_data["should_create_incident"] = severity in ["P1", "P2"]

            # Ensure all required fields are present
            result = {
                "service_name": normalized_data.get("service_name", "unknown"),
                "alert_type": normalized_data.get("alert_type", "unknown"),
                "severity": normalized_data.get("severity", "P3"),
                "metric_value": normalized_data.get("metric_value", 0),
                "threshold_breached": normalized_data.get("threshold_breached", False),
                "timestamp": normalized_data.get("timestamp", datetime.utcnow().isoformat()),
                "raw_message": normalized_data.get("raw_message", str(payload)[:500]),
                "should_create_incident": normalized_data.get("should_create_incident", False),
                "success": True,
                "debug_info": normalized_data.get("debug_info", {})  # Added debug info
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to parse webhook payload: {str(e)}",
                "success": False
            })

    def _parse_grafana(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Grafana webhook payload."""
        result = {}
        
        # Extract service name
        result["service_name"] = (
            payload.get("ruleName", "") or 
            payload.get("title", "") or
            "grafana-alert"
        )
        
        # Extract alert type
        result["alert_type"] = payload.get("state", "unknown")
        
        # Extract metric value
        eval_matches = payload.get("evalMatches", [])
        if eval_matches:
            result["metric_value"] = eval_matches[0].get("value", 0)
        else:
            result["metric_value"] = 0
            
        # Extract timestamp
        result["timestamp"] = payload.get("date", datetime.utcnow().isoformat())
        
        # Raw message
        result["raw_message"] = payload.get("message", str(payload)[:500])
        
        # Check threshold breach
        result["threshold_breached"] = payload.get("state") == "alerting"
        
        return result

    def _parse_pagerduty(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse PagerDuty webhook payload."""
        result = {}
        
        messages = payload.get("messages", [])
        if messages:
            incident = messages[0].get("incident", {})
            result["service_name"] = incident.get("service", {}).get("name", "pagerduty-alert")
            result["alert_type"] = incident.get("incident_key", "incident")
            result["timestamp"] = incident.get("created_at", datetime.utcnow().isoformat())
            result["raw_message"] = incident.get("summary", str(payload)[:500])
            result["threshold_breached"] = incident.get("status") in ["triggered", "acknowledged"]
        else:
            result["service_name"] = "pagerduty-alert"
            result["alert_type"] = "unknown"
            result["timestamp"] = datetime.utcnow().isoformat()
            result["raw_message"] = str(payload)[:500]
            result["threshold_breached"] = False
            
        result["metric_value"] = 0  # PagerDuty doesn't typically include metric values
        
        return result

    def _parse_prometheus(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Prometheus webhook payload."""
        result = {}
        
        alerts = payload.get("alerts", [])
        if alerts:
            alert = alerts[0]
            labels = alert.get("labels", {})
            
            result["service_name"] = (
                labels.get("service") or 
                labels.get("job") or 
                labels.get("instance", "prometheus-alert")
            )
            result["alert_type"] = labels.get("alertname", "unknown")
            result["timestamp"] = alert.get("startsAt", datetime.utcnow().isoformat())
            result["raw_message"] = alert.get("annotations", {}).get("summary", str(payload)[:500])
            result["threshold_breached"] = alert.get("status") == "firing"
            
            # Try to extract metric value from annotations
            annotations = alert.get("annotations", {})
            value_str = annotations.get("value", "0")
            try:
                result["metric_value"] = float(value_str)
            except (ValueError, TypeError):
                result["metric_value"] = 0
        else:
            result["service_name"] = "prometheus-alert"
            result["alert_type"] = "unknown"
            result["timestamp"] = datetime.utcnow().isoformat()
            result["raw_message"] = str(payload)[:500]
            result["threshold_breached"] = False
            result["metric_value"] = 0
            
        return result

    def _parse_datadog(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse DataDog webhook payload."""
        result = {}
        
        result["service_name"] = (
            payload.get("host") or 
            payload.get("tags", {}).get("service") or
            "datadog-alert"
        )
        result["alert_type"] = payload.get("alert_type", "unknown")
        result["timestamp"] = payload.get("date", datetime.utcnow().isoformat())
        result["raw_message"] = payload.get("body", str(payload)[:500])
        result["threshold_breached"] = payload.get("alert_transition") in ["Triggered", "No Data"]
        
        # Try to extract metric value
        try:
            result["metric_value"] = float(payload.get("snapshot", "0"))
        except (ValueError, TypeError):
            result["metric_value"] = 0
            
        return result

    def _parse_newrelic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse New Relic webhook payload."""
        result = {}
        
        result["service_name"] = (
            payload.get("application_name") or 
            payload.get("account_name") or
            "newrelic-alert"
        )
        result["alert_type"] = payload.get("condition_name", "unknown")
        result["timestamp"] = payload.get("timestamp", datetime.utcnow().isoformat())
        result["raw_message"] = payload.get("details", str(payload)[:500])
        result["threshold_breached"] = payload.get("current_state") in ["open", "acknowledged"]
        
        # Try to extract metric value
        try:
            result["metric_value"] = float(payload.get("metric_value_function", "0"))
        except (ValueError, TypeError):
            result["metric_value"] = 0
            
        return result

    def _parse_generic(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Parse generic webhook payload with improved debugging and field extraction."""
        result = {}
        debug_info = {
            "payload_keys": list(payload.keys()),
            "parsing_steps": []
        }
        
        # Ensure we're working with the top-level payload
        if isinstance(payload, dict):
            working_payload = payload
        else:
            debug_info["parsing_steps"].append("Payload is not a dict, converting to string")
            working_payload = {"raw_data": str(payload)}
        
        debug_info["parsing_steps"].append(f"Working with payload keys: {list(working_payload.keys())}")
        
        # Try common field names for service - improved with case-insensitive matching
        service_candidates = ["service", "service_name", "serviceName", "host", "application", "app", "name"]
        result["service_name"] = "generic-alert"
        for candidate in service_candidates:
            # Check exact match first
            if candidate in working_payload and working_payload[candidate]:
                result["service_name"] = str(working_payload[candidate]).strip()
                debug_info["parsing_steps"].append(f"Found service_name with key '{candidate}': {result['service_name']}")
                break
            # Check case-insensitive match
            for key in working_payload.keys():
                if key.lower() == candidate.lower() and working_payload[key]:
                    result["service_name"] = str(working_payload[key]).strip()
                    debug_info["parsing_steps"].append(f"Found service_name with case-insensitive key '{key}': {result['service_name']}")
                    break
            else:
                continue
            break
                
        # Try common field names for alert type - improved with case-insensitive matching and better candidates
        type_candidates = ["alert_type", "alertType", "type", "kind", "category", "event_type", "eventType", "alert_name", "alertName"]
        result["alert_type"] = "unknown"
        found_alert_type = False
        
        for candidate in type_candidates:
            # Check exact match first
            if candidate in working_payload and working_payload[candidate]:
                value = working_payload[candidate]
                if value and str(value).strip():
                    result["alert_type"] = str(value).strip()
                    debug_info["parsing_steps"].append(f"Found alert_type with exact key '{candidate}': {result['alert_type']}")
                    found_alert_type = True
                    break
            
            # Check case-insensitive match
            for key in working_payload.keys():
                if key.lower() == candidate.lower() and working_payload[key]:
                    value = working_payload[key]
                    if value and str(value).strip():
                        result["alert_type"] = str(value).strip()
                        debug_info["parsing_steps"].append(f"Found alert_type with case-insensitive key '{key}' (looking for '{candidate}'): {result['alert_type']}")
                        found_alert_type = True
                        break
            
            if found_alert_type:
                break
        
        if not found_alert_type:
            debug_info["parsing_steps"].append(f"No alert_type found. Checked candidates: {type_candidates}")
            debug_info["parsing_steps"].append(f"Available keys were: {list(working_payload.keys())}")
                
        # Try common field names for timestamp - improved
        timestamp_candidates = ["timestamp", "time", "date", "created_at", "createdAt", "occurred_at", "occurredAt"]
        result["timestamp"] = datetime.utcnow().isoformat()
        for candidate in timestamp_candidates:
            if candidate in working_payload and working_payload[candidate]:
                result["timestamp"] = str(working_payload[candidate]).strip()
                debug_info["parsing_steps"].append(f"Found timestamp with key '{candidate}': {result['timestamp']}")
                break
            # Check case-insensitive match
            for key in working_payload.keys():
                if key.lower() == candidate.lower() and working_payload[key]:
                    result["timestamp"] = str(working_payload[key]).strip()
                    debug_info["parsing_steps"].append(f"Found timestamp with case-insensitive key '{key}': {result['timestamp']}")
                    break
            else:
                continue
            break
                
        # Try to find metric value - improved with more candidates
        value_candidates = ["metric_value", "metricValue", "value", "current_value", "currentValue", "threshold", "score", "count"]
        result["metric_value"] = 0
        for candidate in value_candidates:
            if candidate in working_payload and working_payload[candidate] is not None:
                try:
                    result["metric_value"] = float(working_payload[candidate])
                    debug_info["parsing_steps"].append(f"Found metric_value with key '{candidate}': {result['metric_value']}")
                    break
                except (ValueError, TypeError):
                    continue
            # Check case-insensitive match
            for key in working_payload.keys():
                if key.lower() == candidate.lower() and working_payload[key] is not None:
                    try:
                        result["metric_value"] = float(working_payload[key])
                        debug_info["parsing_steps"].append(f"Found metric_value with case-insensitive key '{key}': {result['metric_value']}")
                        break
                    except (ValueError, TypeError):
                        continue
            else:
                continue
            break
                    
        # Raw message - improved
        message_candidates = ["message", "description", "summary", "body", "details", "text"]
        result["raw_message"] = str(working_payload)[:500]
        for candidate in message_candidates:
            if candidate in working_payload and working_payload[candidate]:
                result["raw_message"] = str(working_payload[candidate])[:500]
                debug_info["parsing_steps"].append(f"Found raw_message with key '{candidate}'")
                break
                
        # Threshold breach detection - improved
        breach_candidates = ["alert", "critical", "warning", "breach", "triggered", "threshold_breached", "thresholdBreached"]
        result["threshold_breached"] = False
        for candidate in breach_candidates:
            if candidate in working_payload and working_payload[candidate] is not None:
                value = str(working_payload[candidate]).lower().strip()
                if value in ["true", "1", "yes", "critical", "alert", "triggered", "breach", "high", "error"]:
                    result["threshold_breached"] = True
                    debug_info["parsing_steps"].append(f"Found threshold_breached=True with key '{candidate}': {value}")
                    break
        
        result["debug_info"] = debug_info
        return result

    def _calculate_severity(self, metric_value: float, thresholds: Dict[str, float]) -> str:
        """Calculate severity based on metric value and thresholds."""
        if metric_value >= thresholds.get("critical", 90):
            return "P1"
        elif metric_value >= thresholds.get("high", 70):
            return "P2"
        elif metric_value >= thresholds.get("medium", 50):
            return "P3"
        else:
            return "P4"