from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any
import requests
import json

class GitHubPRTestRequest(BaseModel):
    """Input schema for GitHub PR Test Tool."""
    github_api_key: str = Field(..., description="GitHub API key token for authentication (from GITHUB_API_KEY environment variable)")
    repository_url: str = Field(
        default="https://github.com/mkurabalakota-equinix/OpsMindJava",
        description="GitHub repository URL to test access"
    )

class GitHubPRTestTool(BaseTool):
    """Tool for testing GitHub token and repository access before PR creation."""

    name: str = "GitHub PR Test Tool"
    description: str = (
        "Tests GitHub token validity and repository access permissions. "
        "Validates authentication, checks repository access, lists branches, "
        "and tests basic permissions required for PR creation."
    )
    args_schema: Type[BaseModel] = GitHubPRTestRequest

    def _mask_token(self, token: str) -> str:
        """Safely mask token showing only first 4 and last 4 characters."""
        if len(token) <= 8:
            return "****"
        return f"{token[:4]}{'*' * (len(token) - 8)}{token[-4:]}"

    def _extract_repo_info(self, repository_url: str) -> tuple:
        """Extract owner and repo name from GitHub URL."""
        try:
            # Remove .git suffix if present
            url = repository_url.rstrip('.git')
            # Handle different GitHub URL formats
            if 'github.com/' in url:
                parts = url.split('github.com/')[-1].split('/')
                if len(parts) >= 2:
                    owner = parts[0]
                    repo = parts[1]
                    return owner, repo
            return None, None
        except Exception:
            return None, None

    def _make_github_request(self, url: str, token: str) -> tuple:
        """Make authenticated request to GitHub API."""
        headers = {
            'Authorization': f'Bearer {token}',  # Using Bearer authentication
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'CrewAI-GitHub-PR-Test-Tool'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            return response.status_code, response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            return 0, {'error': str(e)}

    def _run(self, github_api_key: str, repository_url: str) -> str:
        """Execute GitHub PR readiness test."""
        results = {
            'status': 'TESTING',
            'token_masked': self._mask_token(github_api_key),
            'repository_url': repository_url,
            'tests': {}
        }

        try:
            # Test 1: Validate token with GET /user
            print(f"Testing token: {results['token_masked']}")
            status_code, user_data = self._make_github_request('https://api.github.com/user', github_api_key)
            
            if status_code == 200:
                results['tests']['token_validation'] = {
                    'status': 'SUCCESS',
                    'user_login': user_data.get('login', 'Unknown'),
                    'user_id': user_data.get('id', 'Unknown'),
                    'user_type': user_data.get('type', 'Unknown')
                }
                print(f"✓ Token valid for user: {user_data.get('login', 'Unknown')}")
            else:
                results['tests']['token_validation'] = {
                    'status': 'FAILURE',
                    'error': f"HTTP {status_code}: {user_data.get('message', 'Invalid token')}"
                }
                results['status'] = 'FAILURE'
                print(f"✗ Token validation failed: HTTP {status_code}")

            # Test 2: Extract repository information
            owner, repo = self._extract_repo_info(repository_url)
            if not owner or not repo:
                results['tests']['repository_parsing'] = {
                    'status': 'FAILURE',
                    'error': 'Could not parse repository URL format'
                }
                results['status'] = 'FAILURE'
                return json.dumps(results, indent=2)

            results['repository_owner'] = owner
            results['repository_name'] = repo

            # Test 3: Check repository access
            repo_url = f'https://api.github.com/repos/{owner}/{repo}'
            status_code, repo_data = self._make_github_request(repo_url, github_api_key)
            
            if status_code == 200:
                results['tests']['repository_access'] = {
                    'status': 'SUCCESS',
                    'repository_name': repo_data.get('full_name', f'{owner}/{repo}'),
                    'private': repo_data.get('private', False),
                    'permissions': repo_data.get('permissions', {})
                }
                print(f"✓ Repository access confirmed: {repo_data.get('full_name')}")
            else:
                results['tests']['repository_access'] = {
                    'status': 'FAILURE',
                    'error': f"HTTP {status_code}: {repo_data.get('message', 'Repository not accessible')}"
                }
                results['status'] = 'FAILURE'
                print(f"✗ Repository access failed: HTTP {status_code}")

            # Test 4: List branches to confirm main branch exists
            branches_url = f'https://api.github.com/repos/{owner}/{repo}/branches'
            status_code, branches_data = self._make_github_request(branches_url, github_api_key)
            
            if status_code == 200 and isinstance(branches_data, list):
                branch_names = [branch['name'] for branch in branches_data]
                main_branches = [name for name in branch_names if name in ['main', 'master']]
                
                results['tests']['branches_access'] = {
                    'status': 'SUCCESS',
                    'total_branches': len(branch_names),
                    'branch_names': branch_names[:10],  # Show first 10 branches
                    'main_branch_found': main_branches,
                    'truncated': len(branch_names) > 10
                }
                print(f"✓ Found {len(branch_names)} branches, main branches: {main_branches}")
            else:
                results['tests']['branches_access'] = {
                    'status': 'FAILURE',
                    'error': f"HTTP {status_code}: {branches_data.get('message', 'Could not list branches') if isinstance(branches_data, dict) else 'Invalid response format'}"
                }
                results['status'] = 'FAILURE'
                print(f"✗ Branch listing failed: HTTP {status_code}")

            # Test 5: Check token scopes and permissions
            # GitHub returns scopes in the X-OAuth-Scopes header, but we can infer from successful operations
            headers = {
                'Authorization': f'Bearer {github_api_key}',  # Using Bearer authentication
                'Accept': 'application/vnd.github.v3+json'
            }
            
            try:
                response = requests.get('https://api.github.com/user', headers=headers, timeout=30)
                scopes = response.headers.get('X-OAuth-Scopes', 'Unknown')
                results['tests']['token_permissions'] = {
                    'status': 'SUCCESS',
                    'scopes': scopes,
                    'rate_limit_remaining': response.headers.get('X-RateLimit-Remaining', 'Unknown')
                }
            except Exception as e:
                results['tests']['token_permissions'] = {
                    'status': 'FAILURE',
                    'error': f"Could not retrieve token permissions: {str(e)}"
                }

            # Determine overall status
            failed_tests = [test for test, data in results['tests'].items() if data['status'] == 'FAILURE']
            
            if not failed_tests:
                results['status'] = 'SUCCESS'
                results['summary'] = "✅ All tests passed! Token and repository are ready for PR creation."
            else:
                results['status'] = 'FAILURE'
                results['summary'] = f"❌ {len(failed_tests)} test(s) failed: {', '.join(failed_tests)}"

            return json.dumps(results, indent=2)

        except Exception as e:
            results['status'] = 'ERROR'
            results['error'] = f"Unexpected error during testing: {str(e)}"
            return json.dumps(results, indent=2)