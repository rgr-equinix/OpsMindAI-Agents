from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List, Optional
import requests
import json
import re


class EnhancedGitHubScannerInput(BaseModel):
    """Input schema for Enhanced GitHub Repository Scanner Tool."""
    repository_url: str = Field(..., description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    file_path: Optional[str] = Field(None, description="Specific file path to extract content (optional)")
    find_java_files: bool = Field(False, description="Whether to find all Java files in the repository")
    get_file_content: bool = Field(False, description="Whether to fetch actual file contents")


class EnhancedGitHubRepositoryScanner(BaseTool):
    """Enhanced tool for scanning GitHub repository structure and extracting file contents using GitHub's Tree API."""

    name: str = "Enhanced GitHub Repository Scanner"
    description: str = (
        "Enhanced GitHub repository scanner that uses GitHub's Tree API to get complete repository structure, "
        "find ALL Java files, extract specific file contents, and handle both 'main' and 'master' branches. "
        "Perfect for finding files like 'src/main/java/com/ai/mind/ops/DemoController.java' and getting their actual content."
    )
    args_schema: Type[BaseModel] = EnhancedGitHubScannerInput

    def _run(self, repository_url: str, file_path: Optional[str] = None, find_java_files: bool = False, get_file_content: bool = False) -> str:
        try:
            # Extract owner and repo from URL
            owner, repo = self._extract_repo_info(repository_url)
            if not owner or not repo:
                return "Error: Invalid GitHub repository URL format"

            result = {
                "repository": f"{owner}/{repo}",
                "repository_url": repository_url,
                "scan_timestamp": "scan_completed",
                "default_branch": None,
                "total_files": 0,
                "java_files": [],
                "file_content": {},
                "complete_tree_structure": {},
                "requested_file": None,
                "scan_summary": {}
            }

            # Get repository default branch
            default_branch = self._get_default_branch(owner, repo)
            result["default_branch"] = default_branch
            
            if not default_branch:
                return json.dumps({"error": "Could not determine repository default branch"}, indent=2)

            # Get complete repository tree structure using GitHub Tree API
            tree_data = self._get_complete_tree(owner, repo, default_branch)
            if not tree_data:
                return json.dumps({"error": "Could not fetch repository tree structure"}, indent=2)

            result["complete_tree_structure"] = tree_data
            result["total_files"] = len([item for item in tree_data if item.get("type") == "blob"])

            # Find all Java files if requested
            if find_java_files:
                java_files = self._find_all_java_files(tree_data)
                result["java_files"] = java_files
                result["scan_summary"]["java_files_found"] = len(java_files)

            # Handle specific file path request
            if file_path:
                # Try to find the exact file or similar files
                found_files = self._find_file_in_tree(tree_data, file_path)
                result["requested_file"] = {
                    "requested_path": file_path,
                    "found_files": found_files
                }
                
                # Get content for the requested file
                if get_file_content and found_files:
                    for found_file in found_files[:3]:  # Limit to first 3 matches
                        content = self._fetch_file_content(owner, repo, found_file["path"], default_branch)
                        if content:
                            result["file_content"][found_file["path"]] = {
                                "size": found_file.get("size", 0),
                                "content": content
                            }

            # Get content for Java files if requested and found
            elif get_file_content and find_java_files and result["java_files"]:
                # Get content for up to 5 Java files to avoid overwhelming response
                for java_file in result["java_files"][:5]:
                    content = self._fetch_file_content(owner, repo, java_file["path"], default_branch)
                    if content:
                        result["file_content"][java_file["path"]] = {
                            "size": java_file.get("size", 0),
                            "content": content
                        }

            # Add scan summary
            result["scan_summary"].update({
                "total_files_scanned": result["total_files"],
                "branch_used": default_branch,
                "content_extracted": len(result["file_content"]),
                "tree_api_success": True
            })

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": f"Error scanning repository: {str(e)}",
                "repository": repository_url,
                "scan_summary": {"tree_api_success": False, "error_details": str(e)}
            }, indent=2)

    def _extract_repo_info(self, url: str) -> tuple:
        """Extract owner and repository name from GitHub URL."""
        try:
            # Handle various GitHub URL formats
            if "github.com" not in url:
                return None, None
            
            # Remove .git suffix if present
            url = url.replace(".git", "")
            
            # Extract from URL patterns
            patterns = [
                r"github\.com/([^/]+)/([^/]+)",
                r"github\.com/([^/]+)/([^/]+)/?"
            ]
            
            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    return match.group(1), match.group(2)
            
            return None, None
        except Exception:
            return None, None

    def _get_default_branch(self, owner: str, repo: str) -> Optional[str]:
        """Get the default branch of the repository."""
        try:
            # Try to get repository info to find default branch
            url = f"https://api.github.com/repos/{owner}/{repo}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                repo_data = response.json()
                return repo_data.get("default_branch", "main")
            else:
                # Fallback: try common branch names
                for branch in ["main", "master"]:
                    test_url = f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}"
                    test_response = requests.get(test_url, timeout=5)
                    if test_response.status_code == 200:
                        return branch
                
            return None
        except Exception:
            # Fallback to common branch names
            return "main"

    def _get_complete_tree(self, owner: str, repo: str, branch: str) -> Optional[List[Dict[str, Any]]]:
        """Get complete repository tree structure using GitHub's Tree API."""
        try:
            # Use GitHub Tree API with recursive=1 to get complete tree
            url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                tree_data = response.json()
                return tree_data.get("tree", [])
            elif response.status_code == 404:
                # Try with HEAD if branch name fails
                url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/HEAD?recursive=1"
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    tree_data = response.json()
                    return tree_data.get("tree", [])
            
            return None
        except Exception:
            return None

    def _find_all_java_files(self, tree_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find all Java files in the repository tree."""
        java_files = []
        
        for item in tree_data:
            if item.get("type") == "blob" and item.get("path", "").endswith(".java"):
                java_files.append({
                    "path": item.get("path"),
                    "size": item.get("size", 0),
                    "sha": item.get("sha"),
                    "type": item.get("type"),
                    "url": item.get("url")
                })
        
        # Sort by path for better organization
        java_files.sort(key=lambda x: x["path"])
        
        return java_files

    def _find_file_in_tree(self, tree_data: List[Dict[str, Any]], target_file: str) -> List[Dict[str, Any]]:
        """Find specific file or similar files in the repository tree."""
        found_files = []
        
        # Normalize the target file path
        target_normalized = target_file.replace("\\", "/").lower()
        
        for item in tree_data:
            if item.get("type") == "blob":
                item_path = item.get("path", "")
                item_path_normalized = item_path.lower()
                
                # Exact match
                if item_path_normalized == target_normalized:
                    found_files.append({
                        "path": item_path,
                        "size": item.get("size", 0),
                        "sha": item.get("sha"),
                        "match_type": "exact",
                        "url": item.get("url")
                    })
                # Partial match (contains the filename)
                elif target_normalized in item_path_normalized:
                    found_files.append({
                        "path": item_path,
                        "size": item.get("size", 0),
                        "sha": item.get("sha"),
                        "match_type": "partial",
                        "url": item.get("url")
                    })
                # File name match (same filename, different path)
                elif target_file.split("/")[-1].lower() in item_path_normalized:
                    found_files.append({
                        "path": item_path,
                        "size": item.get("size", 0),
                        "sha": item.get("sha"),
                        "match_type": "filename",
                        "url": item.get("url")
                    })
        
        # Sort by match type (exact first, then partial, then filename)
        match_priority = {"exact": 0, "partial": 1, "filename": 2}
        found_files.sort(key=lambda x: (match_priority.get(x["match_type"], 3), x["path"]))
        
        return found_files

    def _fetch_file_content(self, owner: str, repo: str, file_path: str, branch: str) -> Optional[str]:
        """Fetch file content from GitHub raw URL."""
        try:
            # Use raw.githubusercontent.com to get file content
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{file_path}"
            response = requests.get(url, timeout=15)
            
            if response.status_code == 200:
                # Handle potential encoding issues
                try:
                    return response.text
                except UnicodeDecodeError:
                    return response.content.decode('utf-8', errors='ignore')
            
            return None
        except Exception:
            return None