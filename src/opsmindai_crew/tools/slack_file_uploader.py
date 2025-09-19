from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Dict, Any
import requests
import base64
import json

class SlackFileUploadInput(BaseModel):
    """Input schema for Slack File Uploader Tool."""
    channel: str = Field(default="", description="The Slack channel to upload to (e.g., 'all-opsmindai'). Leave empty for private upload.")
    file_content: str = Field(..., description="The file content as base64 encoded string")
    filename: str = Field(..., description="Name of the file (e.g., 'incident_retrospective_INC-1736962745123.pdf')")
    title: str = Field(..., description="Title for the file in Slack")
    initial_comment: str = Field(default="", description="Message to accompany the file upload")
    filetype: str = Field(default="pdf", description="File type (e.g., 'pdf', 'txt', 'png')")

class SlackFileUploader(BaseTool):
    """Tool for uploading files directly to Slack channels with custom messages."""

    name: str = "slack_file_uploader"
    description: str = (
        "Upload files (especially PDF files) directly to Slack channels. "
        "Supports custom messages, titles, and handles incident reports. "
        "Returns file URL, file ID, and upload status."
    )
    args_schema: Type[BaseModel] = SlackFileUploadInput

    def _run(self, channel: str = "", file_content: str = "", filename: str = "", title: str = "", initial_comment: str = "", filetype: str = "pdf") -> str:
        """
        Upload a file to Slack channel using Slack API.
        
        Args:
            channel: Slack channel name or ID
            file_content: Base64 encoded file content
            filename: Name for the uploaded file
            title: Title for the file in Slack
            initial_comment: Optional message to accompany the file
            filetype: File type extension
            
        Returns:
            JSON string with upload results
        """
        try:
            # Get Slack bot token from environment
            import os
            slack_token = os.getenv('SLACK_BOT_AUTH')
            
            if not slack_token:
                return json.dumps({
                    "upload_success": False,
                    "error": "SLACK_BOT_AUTH environment variable not found",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })

            # Decode base64 file content
            try:
                file_bytes = base64.b64decode(file_content)
            except Exception as decode_error:
                return json.dumps({
                    "upload_success": False,
                    "error": f"Failed to decode base64 file content: {str(decode_error)}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })

            # Resolve channel name to ID if needed
            resolved_channel = self._resolve_channel(channel, slack_token) if channel and channel.strip() else ""

            # Use the new Slack files API (v2) approach
            # Step 1: Get upload URL
            upload_url_endpoint = "https://slack.com/api/files.getUploadURLExternal"
            
            headers = {
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Get upload URL
            upload_params = {
                'filename': filename,
                'length': len(file_bytes)
            }
            
            response = requests.post(upload_url_endpoint, headers=headers, data=upload_params, timeout=30)
            
            if response.status_code != 200:
                return json.dumps({
                    "upload_success": False,
                    "error": f"Failed to get upload URL: {response.text}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })
            
            upload_response = response.json()
            if not upload_response.get('ok'):
                return json.dumps({
                    "upload_success": False,
                    "error": f"Upload URL error: {upload_response.get('error', 'Unknown error')}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })
            
            upload_url = upload_response.get('upload_url')
            file_id = upload_response.get('file_id')
            
            # Step 2: Upload file to the URL
            upload_headers = {}  # No auth needed for direct upload
            upload_files = {
                'file': (filename, file_bytes, f'application/{filetype}')
            }
            
            file_response = requests.post(upload_url, files=upload_files, timeout=60)
            
            if file_response.status_code != 200:
                return json.dumps({
                    "upload_success": False,
                    "error": f"File upload failed: {file_response.text}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })
            
            # Step 3: Complete the upload and optionally share to channel
            complete_url = "https://slack.com/api/files.completeUploadExternal"
            
            complete_data = {
                'files': json.dumps([{
                    'id': file_id,
                    'title': title
                }])
            }
            
            # Only specify channel if one is provided
            if resolved_channel and resolved_channel.strip():
                complete_data['channel_id'] = resolved_channel.strip()
                
            # Only add comment if provided
            if initial_comment and initial_comment.strip():
                complete_data['initial_comment'] = initial_comment.strip()
            
            response = requests.post(complete_url, headers=headers, data=complete_data, timeout=30)
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('ok'):
                    files_info = response_data.get('files', [])
                    if files_info:
                        file_info = files_info[0]
                        
                        upload_type = "private" if not channel or not channel.strip() else f"channel #{channel}"
                        
                        return json.dumps({
                            "upload_success": True,
                            "file_url": file_info.get('url_private', ''),
                            "file_id": file_info.get('id', ''),
                            "message_timestamp": file_info.get('timestamp', ''),
                            "channel": channel if channel else "private",
                            "permalink": file_info.get('permalink', ''),
                            "file_size": file_info.get('size', 0),
                            "mimetype": file_info.get('mimetype', ''),
                            "upload_type": upload_type,
                            "public_url": file_info.get('url_private_download', ''),
                            "title": file_info.get('title', title)
                        })
                    else:
                        return json.dumps({
                            "upload_success": False,
                            "error": "No file information returned from Slack API",
                            "file_url": None,
                            "file_id": None,
                            "message_timestamp": None,
                            "channel": channel
                        })
                else:
                    error_msg = response_data.get('error', 'Unknown Slack API error')
                    return json.dumps({
                        "upload_success": False,
                        "error": f"Slack API error: {error_msg}",
                        "file_url": None,
                        "file_id": None,
                        "message_timestamp": None,
                        "channel": channel
                    })
            else:
                return json.dumps({
                    "upload_success": False,
                    "error": f"HTTP error {response.status_code}: {response.text}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })
                
        except requests.exceptions.Timeout:
            return json.dumps({
                "upload_success": False,
                "error": "Request timeout - Slack API did not respond within 30 seconds",
                "file_url": None,
                "file_id": None,
                "message_timestamp": None,
                "channel": channel
            })
        except requests.exceptions.RequestException as req_error:
            return json.dumps({
                "upload_success": False,
                "error": f"Request error: {str(req_error)}",
                "file_url": None,
                "file_id": None,
                "message_timestamp": None,
                "channel": channel
            })
        except Exception as e:
            return json.dumps({
                "upload_success": False,
                "error": f"Unexpected error: {str(e)}",
                "file_url": None,
                "file_id": None,
                "message_timestamp": None,
                "channel": channel
            })
    
    def _resolve_channel(self, channel: str, slack_token: str) -> str:
        """
        Resolve channel name to channel ID if needed.
        Returns channel ID if input is already an ID, or resolves name to ID.
        """
        if not channel or not channel.strip():
            return ""
        
        channel = channel.strip()
        
        # If it looks like a channel ID (starts with C), return as-is
        if channel.startswith('C') and len(channel) >= 9:
            return channel
        
        # If it's a channel name, try to resolve it
        try:
            headers = {
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json'
            }
            
            # Remove # if present
            channel_name = channel.lstrip('#')
            
            # Known channel mapping for performance
            known_channels = {
                'all-opsmindai': 'C09DMPGG737'
            }
            
            if channel_name in known_channels:
                return known_channels[channel_name]
            
            # If not in known channels, try API lookup
            response = requests.get('https://slack.com/api/conversations.list?limit=200', headers=headers)
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    for ch in data.get('channels', []):
                        if ch.get('name') == channel_name:
                            return ch.get('id')
            
            # If still not found, return original (might be valid)
            return channel
            
        except Exception:
            # If resolution fails, return original channel
            return channel