from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any, List
import requests
import json
from datetime import datetime, timedelta
import re
import base64
import time

class GitHubPRCreatorRequest(BaseModel):
    """Input schema for GitHub PR Creator Tool."""
    repository_url: str = Field(..., description="GitHub repository URL (e.g., https://github.com/owner/repo)")
    pr_title: str = Field(..., description="Title for the pull request")
    pr_description: str = Field(..., description="Description including RCA and fix details")
    file_changes: Dict[str, str] = Field(..., description="Dictionary where keys are file paths and values are the new file content")
    base_branch: str = Field(default="main", description="Base branch to create PR against (default: 'main')")

class GitHubPRCreatorTool(BaseTool):
    """Tool for creating GitHub pull requests with code changes using GitHub REST API with circuit breaker logic."""

    name: str = "GitHub PR Creator"
    description: str = (
        "Creates a GitHub pull request with code changes, including RCA analysis in the PR description. "
        "Uses GitHub REST API to create a new branch, commit file changes, and create a pull request. "
        "Requires GITHUB_API_KEY environment variable for authentication. "
        "Includes enhanced error handling, retry logic with strict limits, circuit breaker patterns, "
        "and critical repository access validation for better reliability."
    )
    args_schema: Type[BaseModel] = GitHubPRCreatorRequest

    def _get_github_token(self) -> tuple[str, str]:
        """
        Get GitHub token from GITHUB_API_KEY environment variable only.
        
        Returns (token, error_message) tuple.
        """
        import os
        
        # Check for GITHUB_API_KEY only
        github_token = os.getenv('GITHUB_API_KEY')
        if github_token:
            return github_token, ""
        
        error_msg = (
            "Error: GitHub authentication token not found. "
            "Please set GITHUB_API_KEY environment variable. "
            "You can create a token at https://github.com/settings/tokens"
        )
        return "", error_msg

    def _make_api_request(self, method: str, url: str, headers: Dict[str, str], 
                         json_data: Dict = None, max_retries: int = 3) -> tuple[requests.Response, str]:
        """
        Make API request with retry logic and enhanced error handling.
        MAXIMUM 3 retries to prevent excessive API calls.
        """
        for attempt in range(max_retries):
            try:
                # Add circuit breaker: fail fast after 3 consecutive failures
                if method.upper() == 'GET':
                    response = requests.get(url, headers=headers, timeout=15)  # Reduced timeout
                elif method.upper() == 'POST':
                    response = requests.post(url, headers=headers, json=json_data, timeout=15)
                elif method.upper() == 'PUT':
                    response = requests.put(url, headers=headers, json=json_data, timeout=15)
                else:
                    return None, f"Unsupported HTTP method: {method}"
                
                return response, ""
                
            except requests.exceptions.Timeout:
                error_msg = f"Request timeout on attempt {attempt + 1}/{max_retries}"
                if attempt < max_retries - 1:
                    time.sleep(1)  # Fixed 1 second delay instead of exponential backoff
                    continue
                return None, f"Error: {error_msg}. Request timed out after {max_retries} attempts."
                
            except requests.exceptions.ConnectionError:
                error_msg = f"Connection error on attempt {attempt + 1}/{max_retries}"
                if attempt < max_retries - 1:
                    time.sleep(1)  # Fixed 1 second delay
                    continue
                return None, f"Error: {error_msg}. Could not connect to GitHub API."
                
            except requests.exceptions.RequestException as e:
                return None, f"Error: Network request failed: {str(e)}"
        
        return None, "Error: Max retry attempts exceeded"

    def _generate_branch_name(self, pr_title: str) -> str:
        """
        Generate branch name from PR title using format: {issue_name}-{timestamp}
        
        Process:
        1. Convert to lowercase
        2. Replace spaces with hyphens
        3. Remove special characters except hyphens
        4. Take first 20 characters if longer
        5. Add timestamp in format YYYYMMDD-HHMMSS
        """
        # Convert to lowercase and replace spaces with hyphens
        issue_name = pr_title.lower().replace(' ', '-')
        
        # Remove special characters except hyphens and alphanumeric
        issue_name = re.sub(r'[^a-z0-9\\-]', '', issue_name)
        
        # Remove multiple consecutive hyphens
        issue_name = re.sub(r'-+', '-', issue_name)
        
        # Remove leading/trailing hyphens
        issue_name = issue_name.strip('-')
        
        # Take first 20 characters if longer
        if len(issue_name) > 20:
            issue_name = issue_name[:20].rstrip('-')
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Combine issue name and timestamp
        branch_name = f"{issue_name}-{timestamp}"
        
        return branch_name

    def _run(self, repository_url: str, pr_title: str, pr_description: str, 
             file_changes: Dict[str, str], base_branch: str = "main") -> str:
        # Add overall execution time limit
        start_time = datetime.now()
        max_execution_time = timedelta(minutes=3)  # 3 minute max execution time
        
        try:
            # CIRCUIT BREAKER: Fail fast if token is invalid
            github_token, token_error = self._get_github_token()
            if token_error:
                return f"AUTHENTICATION_FAILURE: {token_error}"
            
            # Extract owner and repo from repository URL
            repo_match = re.match(r'https://github\.com/([^/]+)/([^/]+)', repository_url.rstrip('/'))
            if not repo_match:
                return f"Error: Invalid GitHub repository URL format: {repository_url}. Expected format: https://github.com/owner/repo"
            
            owner, repo = repo_match.groups()
            
            # Set up headers with proper authentication and User-Agent
            # REVERTED: Use 'Bearer' prefix instead of 'token' for Personal Access Tokens (as confirmed by user's curl testing)
            headers = {
                'Authorization': f'Bearer {github_token}',
                'Accept': 'application/vnd.github.v3+json',
                'Content-Type': 'application/json',
                'User-Agent': 'CrewAI-GitHub-PR-Creator/1.0'
            }
            
            base_api_url = f"https://api.github.com/repos/{owner}/{repo}"
            
            # STEP 1: Validate repository access and token permissions
            print(f"DEBUG: Validating repository access to {owner}/{repo}")

            # CIRCUIT BREAKER: Validate token immediately
            user_response, error_msg = self._make_api_request('GET', 'https://api.github.com/user', headers, max_retries=2)
            if error_msg or user_response.status_code != 200:
                return f"AUTHENTICATION_FAILURE: GitHub token is invalid. Status: {user_response.status_code if user_response else 'None'}"

            user_info = user_response.json()
            print(f"DEBUG: Authenticated as GitHub user: {user_info.get('login', 'Unknown')}")

            # Check execution time before major operation
            if datetime.now() - start_time > max_execution_time:
                return "TIMEOUT_ERROR: Operation exceeded maximum execution time of 3 minutes"

            # Second, validate repository access
            repo_response, error_msg = self._make_api_request('GET', base_api_url, headers, max_retries=2)
            if error_msg:
                return f"Error: Failed to access repository: {error_msg}"

            if repo_response.status_code == 404:
                return (f"Error: Repository '{owner}/{repo}' not found or not accessible. "
                       f"Please check: 1) Repository URL is correct, 2) Repository exists, "
                       f"3) GITHUB_API_KEY has access to this repository. "
                       f"If it's a private repository, ensure token has 'repo' scope.")
            elif repo_response.status_code == 401:
                return f"AUTHENTICATION_FAILURE: Authentication failed for repository '{owner}/{repo}'. GITHUB_API_KEY may not have sufficient permissions. Required scopes: 'repo' (for private repos) or 'public_repo' (for public repos)"
            elif repo_response.status_code != 200:
                return f"Error: Failed to access repository '{owner}/{repo}'. Status: {repo_response.status_code}, Response: {repo_response.text}"

            repo_info = repo_response.json()
            print(f"DEBUG: Repository access validated. Full name: {repo_info.get('full_name')}, Private: {repo_info.get('private', False)}")
            
            # Check execution time before major operation
            if datetime.now() - start_time > max_execution_time:
                return "TIMEOUT_ERROR: Operation exceeded maximum execution time of 3 minutes"
            
            # Generate branch name using improved naming convention
            branch_name = self._generate_branch_name(pr_title)
            
            # Get the latest commit SHA from base branch with enhanced error handling
            print(f"DEBUG: Getting reference for base branch '{base_branch}' from {owner}/{repo}")
            
            base_ref_response, error_msg = self._make_api_request(
                'GET', 
                f"{base_api_url}/git/ref/heads/{base_branch}", 
                headers,
                max_retries=2
            )
            
            if error_msg:
                return error_msg
            
            if base_ref_response.status_code != 200:
                error_details = {
                    "status_code": base_ref_response.status_code,
                    "response_text": base_ref_response.text,
                    "repository": f"{owner}/{repo}",
                    "base_branch": base_branch
                }
                
                if base_ref_response.status_code == 404:
                    return (f"Error: Base branch '{base_branch}' not found in repository {owner}/{repo}. "
                           f"Please check if the branch exists. Available branches can be checked at: "
                           f"https://github.com/{owner}/{repo}/branches")
                elif base_ref_response.status_code == 401:
                    return f"AUTHENTICATION_FAILURE: Authentication failed. Please check your GITHUB_API_KEY permissions. Token should have 'repo' scope for private repositories or 'public_repo' for public ones."
                else:
                    return f"Error: Failed to get base branch reference. Details: {json.dumps(error_details, indent=2)}"
            
            base_sha = base_ref_response.json()['object']['sha']
            print(f"DEBUG: Base SHA for branch '{base_branch}': {base_sha}")
            
            # Check execution time before major operation
            if datetime.now() - start_time > max_execution_time:
                return "TIMEOUT_ERROR: Operation exceeded maximum execution time of 3 minutes"
            
            # Create new branch
            create_branch_data = {
                "ref": f"refs/heads/{branch_name}",
                "sha": base_sha
            }
            
            print(f"DEBUG: Creating new branch '{branch_name}'")
            create_branch_response, error_msg = self._make_api_request(
                'POST',
                f"{base_api_url}/git/refs",
                headers,
                create_branch_data,
                max_retries=2
            )
            
            if error_msg:
                return error_msg
            
            if create_branch_response.status_code != 201:
                error_details = {
                    "status_code": create_branch_response.status_code,
                    "response_text": create_branch_response.text,
                    "branch_name": branch_name,
                    "base_sha": base_sha
                }
                
                if create_branch_response.status_code == 422:
                    return (f"Error: Branch '{branch_name}' already exists or there's a validation error. "
                           f"Details: {json.dumps(error_details, indent=2)}")
                else:
                    return f"Error: Failed to create branch. Details: {json.dumps(error_details, indent=2)}"
            
            print(f"DEBUG: Successfully created branch '{branch_name}'")
            
            # Check execution time before file operations
            if datetime.now() - start_time > max_execution_time:
                return "TIMEOUT_ERROR: Operation exceeded maximum execution time of 3 minutes"
            
            # Commit file changes
            committed_files = []
            for file_path, file_content in file_changes.items():
                try:
                    # Check execution time for each file
                    if datetime.now() - start_time > max_execution_time:
                        return "TIMEOUT_ERROR: Operation exceeded maximum execution time of 3 minutes"
                    
                    print(f"DEBUG: Processing file '{file_path}'")
                    
                    # Get current file info (if exists) to get SHA for update
                    file_info_response, error_msg = self._make_api_request(
                        'GET',
                        f"{base_api_url}/contents/{file_path}?ref={branch_name}",
                        headers,
                        max_retries=2
                    )
                    
                    if error_msg:
                        return f"Error checking file '{file_path}': {error_msg}"
                    
                    # Encode content to base64
                    encoded_content = base64.b64encode(file_content.encode('utf-8')).decode('utf-8')
                    
                    commit_data = {
                        "message": f"Update {file_path}",
                        "content": encoded_content,
                        "branch": branch_name
                    }
                    
                    # If file exists, add SHA for update
                    if file_info_response.status_code == 200:
                        commit_data["sha"] = file_info_response.json()['sha']
                        print(f"DEBUG: File '{file_path}' exists, updating with SHA")
                    else:
                        print(f"DEBUG: File '{file_path}' is new, creating")
                    
                    # Create or update file
                    commit_response, error_msg = self._make_api_request(
                        'PUT',
                        f"{base_api_url}/contents/{file_path}",
                        headers,
                        commit_data,
                        max_retries=2
                    )
                    
                    if error_msg:
                        return f"Error committing file '{file_path}': {error_msg}"
                    
                    if commit_response.status_code in [200, 201]:
                        committed_files.append(file_path)
                        print(f"DEBUG: Successfully committed file '{file_path}'")
                    else:
                        error_details = {
                            "status_code": commit_response.status_code,
                            "response_text": commit_response.text,
                            "file_path": file_path
                        }
                        return f"Error: Failed to commit file '{file_path}'. Details: {json.dumps(error_details, indent=2)}"
                        
                except Exception as e:
                    return f"Error: Failed to process file '{file_path}': {str(e)}"
            
            if not committed_files:
                return "Error: No files were successfully committed"
            
            print(f"DEBUG: Successfully committed {len(committed_files)} files")
            
            # Check execution time before final operation
            if datetime.now() - start_time > max_execution_time:
                return "TIMEOUT_ERROR: Operation exceeded maximum execution time of 3 minutes"
            
            # Create pull request
            pr_data = {
                "title": pr_title,
                "head": branch_name,
                "base": base_branch,
                "body": f"{pr_description}\\n\\n**Files Modified:**\\n" + "\\n".join([f"- {file}" for file in committed_files]),
                "maintainer_can_modify": True
            }
            
            print(f"DEBUG: Creating pull request from '{branch_name}' to '{base_branch}'")
            pr_response, error_msg = self._make_api_request(
                'POST',
                f"{base_api_url}/pulls",
                headers,
                pr_data,
                max_retries=2
            )
            
            if error_msg:
                return f"Error creating pull request: {error_msg}"
            
            if pr_response.status_code != 201:
                error_details = {
                    "status_code": pr_response.status_code,
                    "response_text": pr_response.text,
                    "pr_data": pr_data
                }
                
                if pr_response.status_code == 422:
                    return (f"Error: Pull request validation failed. This might be due to no changes between branches "
                           f"or a PR already exists. Details: {json.dumps(error_details, indent=2)}")
                else:
                    return f"Error: Failed to create pull request. Details: {json.dumps(error_details, indent=2)}"
            
            pr_info = pr_response.json()
            pr_url = pr_info['html_url']
            pr_number = pr_info['number']
            
            print(f"DEBUG: Successfully created PR #{pr_number}: {pr_url}")
            
            # Check final execution time
            total_execution_time = datetime.now() - start_time
            
            result = {
                "status": "success",
                "pr_url": pr_url,
                "pr_number": pr_number,
                "branch_name": branch_name,
                "base_branch": base_branch,
                "repository": f"{owner}/{repo}",
                "committed_files": committed_files,
                "message": f"Successfully created PR #{pr_number}: {pr_title}",
                "execution_time_seconds": total_execution_time.total_seconds(),
                "debug_info": {
                    "repository_url": repository_url,
                    "files_processed": len(file_changes),
                    "files_committed": len(committed_files)
                }
            }
            
            return json.dumps(result, indent=2)
            
        except json.JSONDecodeError as e:
            return f"CRITICAL_ERROR: Failed to parse JSON response: {str(e)}"
        except Exception as e:
            return f"CRITICAL_ERROR: {str(e)}"