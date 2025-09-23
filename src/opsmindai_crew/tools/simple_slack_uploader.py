from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import requests
import json
import os
from pathlib import Path

class SimpleSlackUploadInput(BaseModel):
    """Input schema for Simple Slack File Uploader Tool."""
    file_path: str = Field(..., description="The absolute path to the file to upload (e.g., '/Users/pmishra/AI/OpsMindAI-Agents/report.pdf')")
    channel: str = Field(default="all-opsmindai", description="The Slack channel to upload to (e.g., 'all-opsmindai')")
    title: str = Field(default="Report", description="Title for the file in Slack")
    initial_comment: str = Field(default="", description="Message to accompany the file upload")

class SimpleSlackUploader(BaseTool):
    """Simple tool for uploading files directly to Slack channels from file paths."""

    name: str = "simple_slack_uploader"
    description: str = (
        "Upload files directly to Slack channels using file paths. "
        "Takes a file path as input and uploads it to the specified Slack channel. "
        "No base64 encoding required - works with file paths directly."
    )
    args_schema: Type[BaseModel] = SimpleSlackUploadInput

    def _run(self, file_path: str, channel: str = "all-opsmindai", title: str = "Report", initial_comment: str = "") -> str:
        """
        Upload a file to Slack channel directly from file path.
        
        Args:
            file_path: Absolute path to the file to upload
            channel: Slack channel name 
            title: Title for the file in Slack
            initial_comment: Optional message to accompany the file
            
        Returns:
            JSON string with upload results
        """
        try:
            # Validate file path
            if not file_path or not file_path.strip():
                return json.dumps({
                    "upload_success": False,
                    "error": "file_path is required and cannot be empty",
                    "file_url": None,
                    "file_id": None
                })

            file_path = file_path.strip()
            path_obj = Path(file_path)
            
            if not path_obj.exists():
                return json.dumps({
                    "upload_success": False,
                    "error": f"File does not exist: {file_path}",
                    "file_url": None,
                    "file_id": None
                })

            if not path_obj.is_file():
                return json.dumps({
                    "upload_success": False,
                    "error": f"Path is not a file: {file_path}",
                    "file_url": None,
                    "file_id": None
                })

            # Get Slack bot token from environment
            slack_token = os.getenv('SLACK_BOT_AUTH')
            if not slack_token:
                return json.dumps({
                    "upload_success": False,
                    "error": "SLACK_BOT_AUTH environment variable not found",
                    "file_url": None,
                    "file_id": None
                })

            # Resolve channel name to ID if needed
            channel_id = self._resolve_channel(channel, slack_token)
            
            # Read file content
            file_size = path_obj.stat().st_size
            filename = path_obj.name
            
            print(f"[SimpleSlackUploader] Uploading {filename} ({file_size} bytes) to #{channel}")

            # Step 1: Get upload URL using Slack Files API v2
            upload_url_endpoint = "https://slack.com/api/files.getUploadURLExternal"
            
            headers = {
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            upload_params = {
                'filename': filename,
                'length': file_size
            }
            
            response = requests.post(upload_url_endpoint, headers=headers, data=upload_params, timeout=30)
            
            if response.status_code != 200:
                return json.dumps({
                    "upload_success": False,
                    "error": f"Failed to get upload URL: {response.text}",
                    "file_url": None,
                    "file_id": None
                })
            
            upload_response = response.json()
            if not upload_response.get('ok'):
                return json.dumps({
                    "upload_success": False,
                    "error": f"Upload URL error: {upload_response.get('error', 'Unknown error')}",
                    "file_url": None,
                    "file_id": None
                })
            
            upload_url = upload_response.get('upload_url')
            file_id = upload_response.get('file_id')

            # Step 2: Upload file directly from disk
            with open(file_path, 'rb') as file_data:
                # Detect file type from extension
                file_extension = path_obj.suffix.lower().lstrip('.')
                mime_type = self._get_mime_type(file_extension)
                
                upload_files = {
                    'file': (filename, file_data, mime_type)
                }
                
                file_response = requests.post(upload_url, files=upload_files, timeout=60)
                
                if file_response.status_code != 200:
                    return json.dumps({
                        "upload_success": False,
                        "error": f"File upload failed: {file_response.text}",
                        "file_url": None,
                        "file_id": None
                    })

            # Step 3: Complete upload and share to channel
            complete_url = "https://slack.com/api/files.completeUploadExternal"
            
            complete_data = {
                'files': json.dumps([{
                    'id': file_id,
                    'title': title
                }])
            }
            
            # Add channel if specified
            if channel_id and channel_id.strip():
                complete_data['channel_id'] = channel_id.strip()
                
            # Add initial comment if provided
            if initial_comment and initial_comment.strip():
                complete_data['initial_comment'] = initial_comment.strip()
            
            response = requests.post(complete_url, headers=headers, data=complete_data, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('ok'):
                    files_info = response_data.get('files', [])
                    if files_info:
                        file_info = files_info[0]
                        
                        return json.dumps({
                            "upload_success": True,
                            "file_url": file_info.get('url_private', ''),
                            "file_id": file_info.get('id', ''),
                            "permalink": file_info.get('permalink', ''),
                            "channel": channel,
                            "filename": filename,
                            "file_size": file_size,
                            "title": title,
                            "message": f"Successfully uploaded {filename} to #{channel}"
                        })
                    else:
                        return json.dumps({
                            "upload_success": False,
                            "error": "No file information returned from Slack API",
                            "file_url": None,
                            "file_id": None
                        })
                else:
                    error_msg = response_data.get('error', 'Unknown Slack API error')
                    return json.dumps({
                        "upload_success": False,
                        "error": f"Slack API error: {error_msg}",
                        "file_url": None,
                        "file_id": None
                    })
            else:
                return json.dumps({
                    "upload_success": False,
                    "error": f"HTTP error {response.status_code}: {response.text}",
                    "file_url": None,
                    "file_id": None
                })
                
        except FileNotFoundError:
            return json.dumps({
                "upload_success": False,
                "error": f"File not found: {file_path}",
                "file_url": None,
                "file_id": None
            })
        except PermissionError:
            return json.dumps({
                "upload_success": False,
                "error": f"Permission denied reading file: {file_path}",
                "file_url": None,
                "file_id": None
            })
        except requests.exceptions.Timeout:
            return json.dumps({
                "upload_success": False,
                "error": "Request timeout - Slack API did not respond in time",
                "file_url": None,
                "file_id": None
            })
        except Exception as e:
            return json.dumps({
                "upload_success": False,
                "error": f"Unexpected error: {str(e)}",
                "file_url": None,
                "file_id": None
            })

    def _resolve_channel(self, channel: str, slack_token: str) -> str:
        """Resolve channel name to channel ID."""
        if not channel or not channel.strip():
            return ""
        
        channel = channel.strip()
        
        # If it looks like a channel ID (starts with C), return as-is
        if channel.startswith('C') and len(channel) >= 9:
            return channel
        
        # Known channel mapping for performance
        known_channels = {
            'all-opsmindai': 'C09DMPGG737',
            'general': 'C09DMPGG737'  # fallback
        }
        
        channel_name = channel.lstrip('#')
        
        if channel_name in known_channels:
            return known_channels[channel_name]
        
        # If not in known channels, try API lookup
        try:
            headers = {
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get('https://slack.com/api/conversations.list?limit=200', headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    for ch in data.get('channels', []):
                        if ch.get('name') == channel_name:
                            return ch.get('id')
            
            # If not found, return original
            return channel
            
        except Exception:
            # If resolution fails, return original channel
            return channel

    def _get_mime_type(self, file_extension: str) -> str:
        """Get MIME type based on file extension."""
        mime_types = {
            'pdf': 'application/pdf',
            'txt': 'text/plain',
            'json': 'application/json',
            'csv': 'text/csv',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'xls': 'application/vnd.ms-excel',
            'doc': 'application/msword',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'gif': 'image/gif',
            'zip': 'application/zip',
            'tar': 'application/x-tar',
            'gz': 'application/gzip'
        }
        
        return mime_types.get(file_extension, 'application/octet-stream')
