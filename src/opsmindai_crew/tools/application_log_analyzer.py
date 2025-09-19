from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import re
import json
from datetime import datetime

class LogAnalysisInput(BaseModel):
    """Input schema for Application Log Analyzer Tool."""
    log_content: str = Field(
        ...,
        description="The raw log content to be analyzed for incident details"
    )

class ApplicationLogAnalyzer(BaseTool):
    """Tool for analyzing application logs to extract key incident details."""

    name: str = "application_log_analyzer"
    description: str = (
        "Analyzes application logs to extract incident details with priority on structured log formats "
        "(key=value pairs). Extracts service names, class names, method names, line numbers, error types, "
        "endpoints, timestamps, and file paths from structured logs and traditional stack traces. "
        "Never hallucinates data - only returns information that exists in the log content."
    )
    args_schema: Type[BaseModel] = LogAnalysisInput

    def _run(self, log_content: str) -> str:
        """
        Analyze log content and extract structured incident information.
        
        Args:
            log_content: Raw log content to analyze
            
        Returns:
            JSON string with extracted incident details
        """
        try:
            result = {
                "service_name": None,
                "extracted_classname": None,
                "method_name": None,
                "line_number": None,
                "error_type": None,
                "endpoint": None,
                "timestamp": None,
                "file_path": None,
                "root_cause_summary": None,
                "suggested_fix_type": None,
                "log_format": None,
                "additional_details": {}
            }

            # First priority: Parse structured logs (key=value format)
            structured_analysis = self._analyze_structured_logs(log_content)
            
            # If structured analysis found substantial data, prioritize it
            if self._has_substantial_data(structured_analysis):
                result.update(structured_analysis)
                result["log_format"] = "structured"
            else:
                # Fallback to traditional stack trace analysis
                java_analysis = self._analyze_java_logs(log_content)
                python_analysis = self._analyze_python_logs(log_content)
                nodejs_analysis = self._analyze_nodejs_logs(log_content)
                generic_analysis = self._analyze_generic_logs(log_content)
                
                # Combine results, prioritizing the most complete analysis
                analyses = [java_analysis, python_analysis, nodejs_analysis, generic_analysis]
                best_analysis = max(analyses, key=lambda x: sum(1 for v in x.values() if v is not None))
                
                # Update result with best analysis
                for key, value in best_analysis.items():
                    if value is not None and result.get(key) is None:
                        result[key] = value
                        
                result["log_format"] = "traditional"

            # Extract timestamp patterns if not already found
            if not result["timestamp"]:
                result["timestamp"] = self._extract_timestamp_patterns(log_content)
            
            # Determine suggested fix type
            result["suggested_fix_type"] = self._determine_fix_type(result)

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Failed to analyze log content: {str(e)}",
                "service_name": None,
                "extracted_classname": None,
                "method_name": None,
                "line_number": None,
                "error_type": "analysis_error",
                "endpoint": None,
                "timestamp": None,
                "file_path": None,
                "root_cause_summary": f"Log analysis tool encountered an error: {str(e)}",
                "suggested_fix_type": "code",
                "log_format": "error"
            }, indent=2)

    def _analyze_structured_logs(self, log_content: str) -> Dict[str, Any]:
        """Analyze structured log formats with key=value pairs."""
        result = {
            "service_name": None,
            "extracted_classname": None,
            "method_name": None,
            "line_number": None,
            "error_type": None,
            "endpoint": None,
            "timestamp": None,
            "file_path": None,
            "root_cause_summary": None
        }

        try:
            # Pattern to match key=value pairs, handling quoted values
            kv_pattern = r'(\w+)=(?:"([^"]+)"|\'([^\']+)\'|([^\s]+))'
            matches = re.findall(kv_pattern, log_content)
            
            # Convert matches to dictionary
            structured_data = {}
            for match in matches:
                key = match[0]
                # Get the non-empty value from the groups
                value = match[1] or match[2] or match[3]
                structured_data[key] = value

            # Extract specific fields based on exact key names
            if "service" in structured_data:
                result["service_name"] = structured_data["service"]
            
            if "className" in structured_data:
                result["extracted_classname"] = structured_data["className"]
                
            if "methodName" in structured_data:
                result["method_name"] = structured_data["methodName"]
                
            if "file" in structured_data:
                result["file_path"] = structured_data["file"]
                
            if "line" in structured_data:
                try:
                    result["line_number"] = int(structured_data["line"])
                except (ValueError, TypeError):
                    pass
                    
            if "errorType" in structured_data:
                result["error_type"] = structured_data["errorType"]
                
            if "endpoint" in structured_data:
                result["endpoint"] = structured_data["endpoint"]
                
            if "timestamp" in structured_data:
                result["timestamp"] = structured_data["timestamp"]
                
            # Extract message as root cause if available
            if "message" in structured_data:
                result["root_cause_summary"] = structured_data["message"]
            elif "msg" in structured_data:
                result["root_cause_summary"] = structured_data["msg"]
            elif "error" in structured_data:
                result["root_cause_summary"] = structured_data["error"]
                
            # Look for error level indicators at the beginning of the log line
            error_level_pattern = r'^(ERROR|FATAL|WARN|WARNING|RUNTIME_ERROR|EXCEPTION)\b'
            error_level_match = re.search(error_level_pattern, log_content, re.IGNORECASE)
            if error_level_match and not result["error_type"]:
                result["error_type"] = error_level_match.group(1).lower()

        except Exception:
            pass

        return result

    def _has_substantial_data(self, analysis: Dict[str, Any]) -> bool:
        """Check if the structured analysis found substantial data."""
        key_fields = ["service_name", "extracted_classname", "method_name", "error_type"]
        found_fields = sum(1 for field in key_fields if analysis.get(field) is not None)
        return found_fields >= 2  # Consider substantial if at least 2 key fields are found

    def _analyze_java_logs(self, log_content: str) -> Dict[str, Any]:
        """Analyze Java stack traces and exceptions."""
        result = {
            "service_name": None,
            "extracted_classname": None,
            "method_name": None,
            "line_number": None,
            "error_type": None,
            "endpoint": None,
            "timestamp": None,
            "file_path": None,
            "root_cause_summary": None
        }

        try:
            # Java exception pattern
            java_exception_pattern = r'(?:Exception in thread \".*?\" )?([a-zA-Z0-9.$_]+(?:Exception|Error)): (.+)'
            exception_match = re.search(java_exception_pattern, log_content)
            
            if exception_match:
                result["extracted_classname"] = exception_match.group(1)
                result["error_type"] = "java_exception"
                result["root_cause_summary"] = exception_match.group(2).strip()

            # Java stack trace method and line pattern
            stack_pattern = r'at ([a-zA-Z0-9.$_]+)\.([a-zA-Z0-9_$<>]+)\(([^)]*):(\d+)\)'
            stack_matches = re.findall(stack_pattern, log_content)
            
            if stack_matches:
                # Take the first (topmost) stack frame
                class_name, method_name, file_name, line_num = stack_matches[0]
                if not result["extracted_classname"]:
                    result["extracted_classname"] = class_name
                result["method_name"] = method_name
                result["line_number"] = int(line_num)
                result["file_path"] = file_name

            # Java specific error patterns
            if "OutOfMemoryError" in log_content:
                result["error_type"] = "java_memory_error"
                result["root_cause_summary"] = "Java heap space exhausted"
            elif "NullPointerException" in log_content:
                result["error_type"] = "java_null_pointer"
                if not result["root_cause_summary"]:
                    result["root_cause_summary"] = "Null reference access"

        except Exception:
            pass

        return result

    def _analyze_python_logs(self, log_content: str) -> Dict[str, Any]:
        """Analyze Python tracebacks and exceptions."""
        result = {
            "service_name": None,
            "extracted_classname": None,
            "method_name": None,
            "line_number": None,
            "error_type": None,
            "endpoint": None,
            "timestamp": None,
            "file_path": None,
            "root_cause_summary": None
        }

        try:
            # Python traceback pattern
            traceback_pattern = r'File \"([^\"]+)\", line (\d+), in ([^\n]+)'
            traceback_matches = re.findall(traceback_pattern, log_content)
            
            if traceback_matches:
                # Take the last (most recent) frame
                file_name, line_num, method_name = traceback_matches[-1]
                result["method_name"] = method_name.strip()
                result["line_number"] = int(line_num)
                result["file_path"] = file_name

            # Python exception pattern
            python_exception_pattern = r'([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Exception): (.+)'
            exception_match = re.search(python_exception_pattern, log_content)
            
            if exception_match:
                result["extracted_classname"] = exception_match.group(1)
                result["error_type"] = "python_exception"
                result["root_cause_summary"] = exception_match.group(2).strip()

            # Python specific patterns
            if "ImportError" in log_content or "ModuleNotFoundError" in log_content:
                result["error_type"] = "python_import_error"
                if not result["root_cause_summary"]:
                    result["root_cause_summary"] = "Missing module or import issue"

        except Exception:
            pass

        return result

    def _analyze_nodejs_logs(self, log_content: str) -> Dict[str, Any]:
        """Analyze Node.js errors and stack traces."""
        result = {
            "service_name": None,
            "extracted_classname": None,
            "method_name": None,
            "line_number": None,
            "error_type": None,
            "endpoint": None,
            "timestamp": None,
            "file_path": None,
            "root_cause_summary": None
        }

        try:
            # Node.js error pattern
            nodejs_error_pattern = r'([A-Za-z0-9_]+Error): (.+)'
            error_match = re.search(nodejs_error_pattern, log_content)
            
            if error_match:
                result["extracted_classname"] = error_match.group(1)
                result["error_type"] = "nodejs_error"
                result["root_cause_summary"] = error_match.group(2).strip()

            # Node.js stack trace pattern
            nodejs_stack_pattern = r'at (?:([A-Za-z0-9_.$]+)\s+)?\(([^:]+):(\d+):\d+\)'
            stack_matches = re.findall(nodejs_stack_pattern, log_content)
            
            if stack_matches:
                # Take the first meaningful stack frame
                for method_name, file_path, line_num in stack_matches:
                    if method_name and method_name != "Object.<anonymous>":
                        result["method_name"] = method_name
                        result["line_number"] = int(line_num)
                        result["file_path"] = file_path
                        break

            # Node.js specific patterns
            if "ENOENT" in log_content:
                result["error_type"] = "nodejs_file_not_found"
                if not result["root_cause_summary"]:
                    result["root_cause_summary"] = "File or directory not found"
            elif "TypeError" in log_content and "undefined" in log_content:
                result["error_type"] = "nodejs_undefined_reference"
                if not result["root_cause_summary"]:
                    result["root_cause_summary"] = "Undefined variable or property access"

        except Exception:
            pass

        return result

    def _analyze_generic_logs(self, log_content: str) -> Dict[str, Any]:
        """Analyze generic application logs."""
        result = {
            "service_name": None,
            "extracted_classname": None,
            "method_name": None,
            "line_number": None,
            "error_type": None,
            "endpoint": None,
            "timestamp": None,
            "file_path": None,
            "root_cause_summary": None
        }

        try:
            # Generic error level patterns
            error_patterns = [
                r'ERROR[:\s]+(.+)',
                r'FATAL[:\s]+(.+)',
                r'SEVERE[:\s]+(.+)',
                r'error[:\s]+(.+)',
                r'fail(?:ed|ure)[:\s]+(.+)'
            ]

            for pattern in error_patterns:
                match = re.search(pattern, log_content, re.IGNORECASE)
                if match:
                    result["error_type"] = "generic_error"
                    result["root_cause_summary"] = match.group(1).strip()[:200]  # Limit length
                    break

            # Look for class or method references
            class_method_pattern = r'([A-Z][a-zA-Z0-9]*(?:\.[A-Z][a-zA-Z0-9]*)*)\\.([a-zA-Z0-9_]+)\\('
            class_method_match = re.search(class_method_pattern, log_content)
            
            if class_method_match:
                result["extracted_classname"] = class_method_match.group(1)
                result["method_name"] = class_method_match.group(2)

            # Look for line number references
            line_pattern = r'line\s+(\d+)'
            line_match = re.search(line_pattern, log_content, re.IGNORECASE)
            if line_match:
                result["line_number"] = int(line_match.group(1))

        except Exception:
            pass

        return result

    def _extract_timestamp_patterns(self, log_content: str) -> Optional[str]:
        """Extract timestamp patterns from log content."""
        try:
            timestamp_patterns = [
                r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{3})?Z?',  # ISO format
                r'\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}',             # ISO without milliseconds
                r'\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}:\d{2}',               # US format
                r'\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}',               # EU format
                r'\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}'                  # Syslog format
            ]

            for pattern in timestamp_patterns:
                match = re.search(pattern, log_content)
                if match:
                    return match.group(0)
            
            return None

        except Exception:
            return None

    def _determine_fix_type(self, analysis_result: Dict[str, Any]) -> str:
        """Determine if the suggested fix is code or configuration based."""
        try:
            error_type = analysis_result.get("error_type", "")
            root_cause = analysis_result.get("root_cause_summary", "").lower()
            
            # Configuration-related keywords
            config_keywords = [
                "config", "property", "setting", "parameter", "env",
                "connection", "timeout", "port", "host", "url",
                "permission", "access", "auth", "credential",
                "file not found", "enoent", "path", "directory"
            ]
            
            # Code-related error types
            code_error_types = [
                "null_pointer", "undefined_reference", "import_error",
                "java_exception", "python_exception", "nodejs_error",
                "nullpointerexception"
            ]

            # Check for configuration indicators
            if any(keyword in root_cause for keyword in config_keywords):
                return "configuration"
            
            # Check for code error types
            if any(error_type.lower() in error_type.lower() for error_type in code_error_types):
                return "code"
            
            # Default to code if uncertain
            return "code"

        except Exception:
            return "code"