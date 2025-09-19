from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import base64
import os

class GitHubRepositoryAnalyzerInput(BaseModel):
    """Input schema for GitHub Repository Analyzer Tool."""
    repository: str = Field(
        default="mkurabalakota-equinix/OpsMindJava",
        description="GitHub repository in format 'owner/repo'"
    )
    operation: str = Field(
        ...,
        description="Operation to perform: 'analyze_structure', 'read_file', 'find_class', 'get_method_context', 'check_branch', 'create_branch'"
    )
    file_path: Optional[str] = Field(
        None,
        description="File path for specific file operations (e.g., src/main/java/com/ai/mind/ops/DemoController.java)"
    )
    class_name: Optional[str] = Field(
        None,
        description="Class name to search for"
    )
    method_name: Optional[str] = Field(
        None,
        description="Method name to search for within a class"
    )
    line_number: Optional[int] = Field(
        None,
        description="Line number to get context around"
    )
    branch_name: Optional[str] = Field(
        None,
        description="Branch name for branch operations"
    )

class GitHubRepositoryAnalyzer(BaseTool):
    """Tool for comprehensive GitHub repository analysis including structure mapping, file reading, and code search."""

    name: str = "github_repository_analyzer"
    description: str = (
        "Analyzes GitHub repositories with comprehensive features including repository structure analysis, "
        "Java source file reading, method signature extraction, branch operations, and code search capabilities. "
        "Supports operations like analyze_structure, read_file, find_class, get_method_context, check_branch, and create_branch."
    )
    args_schema: Type[BaseModel] = GitHubRepositoryAnalyzerInput

    def _get_headers(self) -> Dict[str, str]:
        """Get authentication headers for GitHub API."""
        token = os.getenv("GITHUB_API_KEY")
        if not token:
            raise ValueError("GITHUB_API_KEY environment variable is required")
        
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CrewAI-GitHub-Analyzer"
        }

    def _make_github_request(self, url: str) -> Dict[str, Any]:
        """Make authenticated request to GitHub API."""
        try:
            response = requests.get(url, headers=self._get_headers(), timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"GitHub API request failed: {str(e)}")

    def _get_default_branch(self, repository: str) -> str:
        """Get the default branch of the repository."""
        url = f"https://api.github.com/repos/{repository}"
        repo_data = self._make_github_request(url)
        return repo_data.get("default_branch", "main")

    def _analyze_structure(self, repository: str) -> Dict[str, Any]:
        """Analyze repository structure starting from default branch."""
        try:
            # Get default branch
            default_branch = self._get_default_branch(repository)
            
            # Get repository contents
            url = f"https://api.github.com/repos/{repository}/contents?ref={default_branch}"
            contents = self._make_github_request(url)
            
            structure = {
                "repository": repository,
                "default_branch": default_branch,
                "root_contents": [],
                "java_files": [],
                "directory_structure": {}
            }
            
            # Process root contents
            for item in contents:
                structure["root_contents"].append({
                    "name": item["name"],
                    "type": item["type"],
                    "path": item["path"]
                })
            
            # Look for Java source files in src/main/java/
            java_dir_path = "src/main/java"
            try:
                java_url = f"https://api.github.com/repos/{repository}/contents/{java_dir_path}?ref={default_branch}"
                java_contents = self._make_github_request(java_url)
                structure["java_files"] = self._extract_java_files(repository, java_contents, java_dir_path, default_branch)
            except Exception as e:
                structure["java_files"] = f"Could not access Java directory: {str(e)}"
            
            return structure
            
        except Exception as e:
            return {"error": f"Failed to analyze structure: {str(e)}"}

    def _extract_java_files(self, repository: str, contents: List[Dict], base_path: str, branch: str) -> List[Dict]:
        """Recursively extract Java files from directory structure."""
        java_files = []
        
        for item in contents:
            if item["type"] == "file" and item["name"].endswith(".java"):
                java_files.append({
                    "name": item["name"],
                    "path": item["path"],
                    "size": item["size"]
                })
            elif item["type"] == "dir":
                try:
                    subdir_url = f"https://api.github.com/repos/{repository}/contents/{item['path']}?ref={branch}"
                    subdir_contents = self._make_github_request(subdir_url)
                    java_files.extend(self._extract_java_files(repository, subdir_contents, item["path"], branch))
                except Exception:
                    continue
        
        return java_files

    def _read_file(self, repository: str, file_path: str) -> Dict[str, Any]:
        """Read a specific file from the repository."""
        try:
            default_branch = self._get_default_branch(repository)
            url = f"https://api.github.com/repos/{repository}/contents/{file_path}?ref={default_branch}"
            file_data = self._make_github_request(url)
            
            if file_data.get("encoding") == "base64":
                content = base64.b64decode(file_data["content"]).decode("utf-8")
                
                result = {
                    "repository": repository,
                    "file_path": file_path,
                    "branch": default_branch,
                    "size": file_data["size"],
                    "content": content,
                    "lines": content.split("\n"),
                    "line_count": len(content.split("\n"))
                }
                
                # Extract method signatures if it's a Java file
                if file_path.endswith(".java"):
                    result["methods"] = self._extract_java_methods(content)
                
                return result
            else:
                return {"error": "File encoding not supported or file is binary"}
                
        except Exception as e:
            return {"error": f"Failed to read file: {str(e)}"}

    def _extract_java_methods(self, content: str) -> List[Dict[str, Any]]:
        """Extract Java method signatures and line numbers."""
        methods = []
        lines = content.split("\n")
        
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            # Simple method detection (can be enhanced)
            if (("public " in line_stripped or "private " in line_stripped or "protected " in line_stripped) 
                and "(" in line_stripped and ")" in line_stripped and "{" in line_stripped):
                methods.append({
                    "line_number": i,
                    "signature": line_stripped,
                    "method_name": self._extract_method_name(line_stripped)
                })
        
        return methods

    def _extract_method_name(self, signature: str) -> str:
        """Extract method name from signature."""
        try:
            # Find the part between space and opening parenthesis
            parts = signature.split("(")[0].split()
            return parts[-1] if parts else "unknown"
        except Exception:
            return "unknown"

    def _find_class(self, repository: str, class_name: str) -> Dict[str, Any]:
        """Find a specific class in the repository."""
        try:
            # Search for the class file
            search_url = f"https://api.github.com/search/code?q={class_name}+extension:java+repo:{repository}"
            search_results = self._make_github_request(search_url)
            
            results = []
            for item in search_results.get("items", []):
                if class_name in item["name"]:
                    results.append({
                        "file_name": item["name"],
                        "path": item["path"],
                        "url": item["html_url"]
                    })
            
            return {
                "repository": repository,
                "class_name": class_name,
                "found_files": results,
                "total_matches": len(results)
            }
            
        except Exception as e:
            return {"error": f"Failed to find class: {str(e)}"}

    def _get_method_context(self, repository: str, file_path: str, line_number: int, context_lines: int = 5) -> Dict[str, Any]:
        """Get context around a specific line number."""
        try:
            file_data = self._read_file(repository, file_path)
            if "error" in file_data:
                return file_data
            
            lines = file_data["lines"]
            total_lines = len(lines)
            
            start_line = max(0, line_number - context_lines - 1)
            end_line = min(total_lines, line_number + context_lines)
            
            context = []
            for i in range(start_line, end_line):
                context.append({
                    "line_number": i + 1,
                    "content": lines[i],
                    "is_target": i + 1 == line_number
                })
            
            return {
                "repository": repository,
                "file_path": file_path,
                "target_line": line_number,
                "context_lines": context_lines,
                "context": context,
                "analysis": self._analyze_line_for_npe(lines[line_number - 1] if line_number <= total_lines else "")
            }
            
        except Exception as e:
            return {"error": f"Failed to get method context: {str(e)}"}

    def _analyze_line_for_npe(self, line: str) -> Dict[str, Any]:
        """Analyze a line for potential NullPointerException issues."""
        analysis = {
            "potential_npe_risks": [],
            "suggestions": []
        }
        
        line_stripped = line.strip()
        
        # Check for common NPE patterns
        if "." in line_stripped and not line_stripped.startswith("//"):
            analysis["potential_npe_risks"].append("Method/field access without null check")
            analysis["suggestions"].append("Consider adding null checks before method/field access")
        
        if ".get(" in line_stripped:
            analysis["potential_npe_risks"].append("Collection access without null/bounds checking")
            analysis["suggestions"].append("Consider checking if collection is null and has elements")
        
        return analysis

    def _check_branch(self, repository: str, branch_name: str) -> Dict[str, Any]:
        """Check if a branch exists."""
        try:
            url = f"https://api.github.com/repos/{repository}/branches/{branch_name}"
            branch_data = self._make_github_request(url)
            
            return {
                "repository": repository,
                "branch_name": branch_name,
                "exists": True,
                "commit_sha": branch_data["commit"]["sha"],
                "last_commit_message": branch_data["commit"]["commit"]["message"]
            }
            
        except Exception as e:
            if "404" in str(e):
                return {
                    "repository": repository,
                    "branch_name": branch_name,
                    "exists": False,
                    "error": "Branch not found"
                }
            return {"error": f"Failed to check branch: {str(e)}"}

    def _run(self, repository: str, operation: str, file_path: Optional[str] = None, 
            class_name: Optional[str] = None, method_name: Optional[str] = None, 
            line_number: Optional[int] = None, branch_name: Optional[str] = None) -> str:
        """Execute the GitHub repository analysis operation."""
        
        try:
            if operation == "analyze_structure":
                result = self._analyze_structure(repository)
            elif operation == "read_file":
                if not file_path:
                    return "Error: file_path is required for read_file operation"
                result = self._read_file(repository, file_path)
            elif operation == "find_class":
                if not class_name:
                    return "Error: class_name is required for find_class operation"
                result = self._find_class(repository, class_name)
            elif operation == "get_method_context":
                if not file_path or not line_number:
                    return "Error: file_path and line_number are required for get_method_context operation"
                result = self._get_method_context(repository, file_path, line_number)
            elif operation == "check_branch":
                if not branch_name:
                    return "Error: branch_name is required for check_branch operation"
                result = self._check_branch(repository, branch_name)
            else:
                return f"Error: Unsupported operation '{operation}'. Supported operations: analyze_structure, read_file, find_class, get_method_context, check_branch"
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            return f"Tool execution failed: {str(e)}"