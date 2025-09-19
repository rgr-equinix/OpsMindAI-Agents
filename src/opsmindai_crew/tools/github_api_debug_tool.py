from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any
import requests
import json
import re

class GitHubApiDebugRequest(BaseModel):
    """Input schema for GitHub API Debug Tool."""
    github_token: str = Field(description="The GitHub token to test and debug")
    test_url: str = Field(
        default="https://api.github.com/repos/mkurabalakota-equinix/OpsMindJava",
        description="The GitHub API URL to test authentication against"
    )
    max_attempts: int = Field(
        default=1,
        description="Number of attempts (default 1 for clean debugging, no retries)"
    )

class GitHubApiDebugTool(BaseTool):
    """A comprehensive GitHub API debugging tool for authentication troubleshooting."""

    name: str = "github_api_debug_tool"
    description: str = (
        "Debug GitHub API authentication issues by testing tokens with different "
        "authentication methods, validating token format, and providing detailed "
        "request/response analysis for troubleshooting."
    )
    args_schema: Type[BaseModel] = GitHubApiDebugRequest

    def _mask_token(self, token: str) -> str:
        """Safely mask token for logging purposes."""
        if len(token) <= 8:
            return "****"
        return f"{token[:4]}****{token[-4:]}"

    def _validate_token_format(self, token: str) -> Dict[str, Any]:
        """Validate GitHub token format and characteristics."""
        results = {
            "is_valid_format": False,
            "token_type": "unknown",
            "length": len(token),
            "has_whitespace": bool(re.search(r'\s', token)),
            "issues": []
        }

        # Remove whitespace for analysis
        clean_token = token.strip()
        
        if token != clean_token:
            results["issues"].append("Token contains leading/trailing whitespace")
            
        if '\n' in token or '\r' in token:
            results["issues"].append("Token contains newline characters")

        # Check token patterns
        if clean_token.startswith('ghp_'):
            results["token_type"] = "Personal Access Token (classic)"
            results["is_valid_format"] = len(clean_token) >= 36
        elif clean_token.startswith('github_pat_'):
            results["token_type"] = "Fine-grained Personal Access Token"
            results["is_valid_format"] = len(clean_token) >= 80
        elif clean_token.startswith('gho_'):
            results["token_type"] = "OAuth Token"
            results["is_valid_format"] = len(clean_token) >= 36
        elif clean_token.startswith('ghu_'):
            results["token_type"] = "User Token"
            results["is_valid_format"] = len(clean_token) >= 36
        elif clean_token.startswith('ghs_'):
            results["token_type"] = "Server Token"
            results["is_valid_format"] = len(clean_token) >= 36
        elif clean_token.startswith('ghr_'):
            results["token_type"] = "Refresh Token"
            results["is_valid_format"] = len(clean_token) >= 36
        else:
            results["issues"].append("Token doesn't match known GitHub token patterns")

        if results["length"] < 20:
            results["issues"].append("Token appears too short for a valid GitHub token")

        return results

    def _test_auth_method(self, token: str, test_url: str, auth_method: str) -> Dict[str, Any]:
        """Test a specific authentication method."""
        headers = {
            "User-Agent": "GitHub-API-Debug-Tool/1.0",
            "Accept": "application/vnd.github.v3+json"
        }

        if auth_method == "Bearer":
            headers["Authorization"] = f"Bearer {token.strip()}"
        elif auth_method == "token":
            headers["Authorization"] = f"token {token.strip()}"

        try:
            response = requests.get(test_url, headers=headers, timeout=30)
            
            # Extract rate limit information
            rate_limit_info = {
                "limit": response.headers.get("X-RateLimit-Limit"),
                "remaining": response.headers.get("X-RateLimit-Remaining"),
                "reset": response.headers.get("X-RateLimit-Reset"),
                "used": response.headers.get("X-RateLimit-Used"),
                "resource": response.headers.get("X-RateLimit-Resource")
            }

            return {
                "method": auth_method,
                "status_code": response.status_code,
                "success": response.status_code == 200,
                "headers": dict(response.headers),
                "rate_limit": rate_limit_info,
                "response_size": len(response.content),
                "error": None,
                "response_preview": response.text[:500] if response.text else "No response body"
            }

        except requests.exceptions.RequestException as e:
            return {
                "method": auth_method,
                "status_code": None,
                "success": False,
                "headers": {},
                "rate_limit": {},
                "response_size": 0,
                "error": str(e),
                "response_preview": None
            }

    def _analyze_response(self, response_data: Dict[str, Any]) -> list:
        """Analyze response and provide troubleshooting recommendations."""
        recommendations = []

        if not response_data["success"]:
            if response_data["status_code"] == 401:
                recommendations.append("Authentication failed - check if token is valid and has required permissions")
            elif response_data["status_code"] == 403:
                recommendations.append("Forbidden - token may lack required scopes or repository access")
            elif response_data["status_code"] == 404:
                recommendations.append("Repository not found - check URL or token permissions")
            elif response_data["status_code"] == 429:
                recommendations.append("Rate limit exceeded - wait before making more requests")
            elif response_data.get("error"):
                recommendations.append(f"Network error: {response_data['error']}")
            else:
                recommendations.append(f"Unexpected status code: {response_data.get('status_code')}")

        # Check rate limits
        rate_limit = response_data.get("rate_limit", {})
        if rate_limit.get("remaining"):
            remaining = int(rate_limit["remaining"])
            if remaining < 10:
                recommendations.append(f"Low API rate limit remaining: {remaining} requests")

        return recommendations

    def _run(self, github_token: str, test_url: str, max_attempts: int) -> str:
        """Execute GitHub API debugging analysis."""
        try:
            debug_report = {
                "tool_version": "1.0",
                "test_timestamp": None,
                "input_parameters": {
                    "test_url": test_url,
                    "max_attempts": max_attempts,
                    "token_masked": self._mask_token(github_token)
                },
                "token_analysis": {},
                "authentication_tests": [],
                "recommendations": [],
                "summary": {}
            }

            # Token validation
            debug_report["token_analysis"] = self._validate_token_format(github_token)

            # Test different authentication methods
            auth_methods = ["Bearer", "token"]
            
            for method in auth_methods:
                result = self._test_auth_method(github_token, test_url, method)
                debug_report["authentication_tests"].append(result)
                
                # Add method-specific recommendations
                recommendations = self._analyze_response(result)
                debug_report["recommendations"].extend([
                    f"[{method}] {rec}" for rec in recommendations
                ])

            # Generate summary
            successful_methods = [
                test["method"] for test in debug_report["authentication_tests"] 
                if test["success"]
            ]
            
            debug_report["summary"] = {
                "token_format_valid": debug_report["token_analysis"]["is_valid_format"],
                "token_issues_found": len(debug_report["token_analysis"]["issues"]),
                "successful_auth_methods": successful_methods,
                "total_methods_tested": len(auth_methods),
                "overall_success": len(successful_methods) > 0
            }

            # Add general recommendations
            if not successful_methods:
                debug_report["recommendations"].append("CRITICAL: No authentication methods worked - verify token validity")
            elif len(successful_methods) == 1:
                debug_report["recommendations"].append(f"SUCCESS: Use '{successful_methods[0]}' authentication method")
            else:
                debug_report["recommendations"].append(f"SUCCESS: Multiple auth methods work: {', '.join(successful_methods)}")

            if debug_report["token_analysis"]["issues"]:
                debug_report["recommendations"].append("Fix token format issues: " + ", ".join(debug_report["token_analysis"]["issues"]))

            return json.dumps(debug_report, indent=2)

        except Exception as e:
            error_report = {
                "error": "Debug tool execution failed",
                "message": str(e),
                "token_masked": self._mask_token(github_token) if github_token else "No token provided"
            }
            return json.dumps(error_report, indent=2)