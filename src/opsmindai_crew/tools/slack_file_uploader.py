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
    filename: str = Field(default="report.pdf", description="Name of the file (e.g., 'incident_retrospective_INC-1736962745123.pdf')")
    title: str = Field(default="Incident Report", description="Title for the file in Slack")
    initial_comment: str = Field(default="", description="Message to accompany the file upload")
    filetype: str = Field(default="pdf", description="File type (e.g., 'pdf', 'txt', 'png')")
    send_announcement: bool = Field(default=True, description="Send a separate announcement message after file upload for better visibility")

class SlackFileUploader(BaseTool):
    """Tool for uploading files directly to Slack channels with custom messages."""

    name: str = "slack_file_uploader"
    description: str = (
        "Upload files (especially PDF files) directly to Slack channels. "
        "Supports custom messages, titles, and handles incident reports. "
        "Returns file URL, file ID, and upload status."
    )
    args_schema: Type[BaseModel] = SlackFileUploadInput

    def _run(self, channel: str = "", file_content: str = "", filename: str = "", title: str = "", initial_comment: str = "", filetype: str = "pdf", send_announcement: bool = True) -> str:
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
        import time
        start_time = time.time()
        print(f"[SlackUploader DEBUG] Starting upload process at {time.strftime('%H:%M:%S')}")
        
        try:
            # Validate required inputs
            validation_start = time.time()
            print(f"[SlackUploader DEBUG] Starting validation at {time.strftime('%H:%M:%S')}")
            
            if not file_content or file_content.strip() == "":
                print(f"[SlackUploader DEBUG] Validation failed: empty file_content")
                return json.dumps({
                    "upload_success": False,
                    "error": "file_content is required and cannot be empty. Please provide base64 encoded file content.",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel,
                    "hint": "Use file_to_base64_converter tool first to get the base64 content, then provide it to this tool."
                })
            
            # Check if the content looks like base64
            import re
            base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
            clean_test_content = ''.join(file_content.strip().split())
            
            if not base64_pattern.match(clean_test_content):
                print(f"[SlackUploader DEBUG] Validation failed: invalid base64 format")
                return json.dumps({
                    "upload_success": False,
                    "error": "file_content does not appear to be valid base64. Please ensure you're providing base64 encoded content.",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel,
                    "hint": "Use file_to_base64_converter tool first to get the base64 content, then extract the 'base64_content' field from its response.",
                    "debug_info": f"Content length: {len(file_content)}, First 50 chars: {file_content[:50]}"
                })

            validation_time = time.time() - validation_start
            print(f"[SlackUploader DEBUG] Validation completed in {validation_time:.2f}s")

            # Get Slack bot token from environment
            token_start = time.time()
            print(f"[SlackUploader DEBUG] Getting Slack token at {time.strftime('%H:%M:%S')}")
            import os
            slack_token = os.getenv('SLACK_BOT_AUTH')
            
            if not slack_token:
                print(f"[SlackUploader DEBUG] Token not found")
                return json.dumps({
                    "upload_success": False,
                    "error": "SLACK_BOT_AUTH environment variable not found",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })
            
            token_time = time.time() - token_start
            print(f"[SlackUploader DEBUG] Token retrieved in {token_time:.3f}s")

            # Decode base64 file content with padding fix
            decode_start = time.time()
            print(f"[SlackUploader DEBUG] Starting base64 decode at {time.strftime('%H:%M:%S')}")
            print(f"[SlackUploader DEBUG] Base64 content length: {len(file_content)} chars")
            
            try:
                # Clean and fix base64 padding
                clean_content = file_content.strip()
                
                # Remove any whitespace, newlines, or invalid characters  
                clean_content = ''.join(clean_content.split())
                
                # Remove any existing padding first
                clean_content = clean_content.rstrip('=')
                
                # Calculate and add correct padding
                missing_padding = len(clean_content) % 4
                if missing_padding:
                    clean_content += '=' * (4 - missing_padding)
                
                print(f"[SlackUploader DEBUG] Cleaned content length: {len(clean_content)} (should be multiple of 4)")
                print(f"[SlackUploader DEBUG] Padding added: {4 - missing_padding if missing_padding else 0} characters")
                
                file_bytes = base64.b64decode(clean_content)
                
                # Validate that we got actual file data
                if len(file_bytes) == 0:
                    print(f"[SlackUploader DEBUG] Base64 decoded to empty file")
                    return json.dumps({
                        "upload_success": False,
                        "error": "Base64 content decoded to empty file. Please check the file_content parameter.",
                        "file_url": None,
                        "file_id": None,
                        "message_timestamp": None,
                        "channel": channel,
                        "debug_info": f"Original length: {len(file_content)}, Cleaned length: {len(clean_content)}"
                    })
                
                decode_time = time.time() - decode_start
                print(f"[SlackUploader DEBUG] Base64 decode completed in {decode_time:.3f}s, got {len(file_bytes)} bytes")
                    
            except Exception as decode_error:
                decode_time = time.time() - decode_start
                print(f"[SlackUploader DEBUG] Base64 decode failed in {decode_time:.3f}s: {decode_error}")
                return json.dumps({
                    "upload_success": False,
                    "error": f"Failed to decode base64 file content: {str(decode_error)}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel,
                    "debug_info": f"Content length: {len(file_content) if file_content else 0}, First 100 chars: {file_content[:100] if file_content else 'None'}"
                })

            # Resolve channel name to ID if needed
            channel_start = time.time()
            print(f"[SlackUploader DEBUG] Resolving channel '{channel}' at {time.strftime('%H:%M:%S')}")
            
            resolved_channel = self._resolve_channel(channel, slack_token) if channel and channel.strip() else ""
            
            channel_time = time.time() - channel_start
            print(f"[SlackUploader DEBUG] Channel resolution completed in {channel_time:.3f}s: '{channel}' -> '{resolved_channel}'")

            # Use the new Slack files API (v2) approach
            # Step 1: Get upload URL
            step1_start = time.time()
            print(f"[SlackUploader DEBUG] Step 1: Getting upload URL at {time.strftime('%H:%M:%S')}")
            
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
            
            print(f"[SlackUploader DEBUG] Making request to {upload_url_endpoint}")
            response = requests.post(upload_url_endpoint, headers=headers, data=upload_params, timeout=30)
            
            step1_time = time.time() - step1_start
            print(f"[SlackUploader DEBUG] Step 1 completed in {step1_time:.3f}s with status {response.status_code}")
            
            if response.status_code != 200:
                print(f"[SlackUploader DEBUG] Step 1 failed with {response.status_code}: {response.text}")
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
                print(f"[SlackUploader DEBUG] Step 1 API error: {upload_response.get('error')}")
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
            print(f"[SlackUploader DEBUG] Got upload URL and file_id: {file_id}")
            
            # Step 2: Upload file to the URL
            step2_start = time.time()
            print(f"[SlackUploader DEBUG] Step 2: Uploading {len(file_bytes)} bytes to presigned URL at {time.strftime('%H:%M:%S')}")
            
            upload_headers = {}  # No auth needed for direct upload
            upload_files = {
                'file': (filename, file_bytes, f'application/{filetype}')
            }
            
            print(f"[SlackUploader DEBUG] Making file upload request to presigned URL")
            file_response = requests.post(upload_url, files=upload_files, timeout=60)
            
            step2_time = time.time() - step2_start
            print(f"[SlackUploader DEBUG] Step 2 completed in {step2_time:.3f}s with status {file_response.status_code}")
            
            if file_response.status_code != 200:
                print(f"[SlackUploader DEBUG] Step 2 failed with {file_response.status_code}: {file_response.text}")
                return json.dumps({
                    "upload_success": False,
                    "error": f"File upload failed: {file_response.text}",
                    "file_url": None,
                    "file_id": None,
                    "message_timestamp": None,
                    "channel": channel
                })
            
            # Step 3: Complete the upload and optionally share to channel
            step3_start = time.time()
            print(f"[SlackUploader DEBUG] Step 3: Completing upload and sharing to channel at {time.strftime('%H:%M:%S')}")
            
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
                print(f"[SlackUploader DEBUG] Adding channel_id to completion: {resolved_channel}")
                
            # Only add comment if provided
            if initial_comment and initial_comment.strip():
                complete_data['initial_comment'] = initial_comment.strip()
                print(f"[SlackUploader DEBUG] Adding initial_comment to completion")
            
            print(f"[SlackUploader DEBUG] Making completion request to {complete_url}")
            response = requests.post(complete_url, headers=headers, data=complete_data, timeout=30)
            
            step3_time = time.time() - step3_start
            print(f"[SlackUploader DEBUG] Step 3 completed in {step3_time:.3f}s with status {response.status_code}")
            
            total_time = time.time() - start_time
            print(f"[SlackUploader DEBUG] Total upload process completed in {total_time:.3f}s")
            
            if response.status_code == 200:
                response_data = response.json()
                
                if response_data.get('ok'):
                    files_info = response_data.get('files', [])
                    if files_info:
                        file_info = files_info[0]
                        
                        upload_type = "private" if not channel or not channel.strip() else f"channel #{channel}"
                        
                        # Send follow-up announcement message if requested and we have both channel and message
                        announcement_success = False
                        announcement_ts = None
                        
                        if send_announcement and resolved_channel and initial_comment:
                            try:
                                print(f"[SlackUploader DEBUG] Sending follow-up announcement message")
                                announcement_url = "https://slack.com/api/chat.postMessage"
                                
                                # Format the announcement message with file reference
                                announcement_text = f"{initial_comment}\n\n📎 *Attached Report:* {filename}"
                                
                                # Use form data headers for announcement
                                announcement_headers = {
                                    'Authorization': f'Bearer {slack_token}',
                                    'Content-Type': 'application/x-www-form-urlencoded'
                                }
                                
                                announcement_data = {
                                    'channel': resolved_channel,
                                    'text': announcement_text
                                }
                                
                                announcement_response = requests.post(
                                    announcement_url, 
                                    headers=announcement_headers, 
                                    data=announcement_data,
                                    timeout=30
                                )
                                
                                if announcement_response.status_code == 200:
                                    announcement_resp_data = announcement_response.json()
                                    if announcement_resp_data.get('ok'):
                                        announcement_success = True
                                        announcement_ts = announcement_resp_data.get('ts')
                                        print(f"[SlackUploader DEBUG] Follow-up announcement sent successfully")
                                    else:
                                        print(f"[SlackUploader DEBUG] Announcement failed: {announcement_resp_data.get('error')}")
                                else:
                                    print(f"[SlackUploader DEBUG] Announcement HTTP error: {announcement_response.status_code}")
                                    
                            except Exception as e:
                                print(f"[SlackUploader DEBUG] Announcement exception: {e}")
                        
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
                            "title": file_info.get('title', title),
                            "announcement_sent": announcement_success,
                            "announcement_timestamp": announcement_ts
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
        import time
        resolve_start = time.time()
        print(f"[SlackUploader DEBUG] Channel resolution: input='{channel}'")
        
        if not channel or not channel.strip():
            print(f"[SlackUploader DEBUG] Channel resolution: empty channel, returning empty")
            return ""
        
        channel = channel.strip()
        
        # If it looks like a channel ID (starts with C), return as-is
        if channel.startswith('C') and len(channel) >= 9:
            print(f"[SlackUploader DEBUG] Channel resolution: looks like ID, returning as-is")
            return channel
        
        # If it's a channel name, try to resolve it
        try:
            headers = {
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json'
            }
            
            # Remove # if present
            channel_name = channel.lstrip('#')
            print(f"[SlackUploader DEBUG] Channel resolution: resolving name '{channel_name}'")
            
            # Known channel mapping for performance
            known_channels = {
                'all-opsmindai': 'C09DMPGG737'
            }
            
            if channel_name in known_channels:
                resolve_time = time.time() - resolve_start
                result = known_channels[channel_name]
                print(f"[SlackUploader DEBUG] Channel resolution: found in cache in {resolve_time:.3f}s: '{channel_name}' -> '{result}'")
                return result
            
            # If not in known channels, try API lookup
            api_start = time.time()
            print(f"[SlackUploader DEBUG] Channel resolution: not in cache, making API call")
            response = requests.get('https://slack.com/api/conversations.list?limit=200', headers=headers)
            api_time = time.time() - api_start
            print(f"[SlackUploader DEBUG] Channel resolution: API call completed in {api_time:.3f}s")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    for ch in data.get('channels', []):
                        if ch.get('name') == channel_name:
                            result = ch.get('id')
                            resolve_time = time.time() - resolve_start
                            print(f"[SlackUploader DEBUG] Channel resolution: found via API in {resolve_time:.3f}s: '{channel_name}' -> '{result}'")
                            return result
            
            # If still not found, return original (might be valid)
            resolve_time = time.time() - resolve_start
            print(f"[SlackUploader DEBUG] Channel resolution: not found, returning original in {resolve_time:.3f}s")
            return channel
            
        except Exception as e:
            resolve_time = time.time() - resolve_start
            print(f"[SlackUploader DEBUG] Channel resolution: exception in {resolve_time:.3f}s: {e}")
            # If resolution fails, return original channel
            return channel