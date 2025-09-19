from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import requests
import json

class SlackMessageTestInput(BaseModel):
    """Input schema for Slack Message Test Tool."""
    channel_name: str = Field(
        default="all-opsmindai",
        description="The Slack channel name (without #) to send the test message to"
    )
    test_message: str = Field(
        default="🤖 Test message from CrewAI Bot - Configuration verified!",
        description="The test message to send to the channel"
    )

class SlackMessageTestTool(BaseTool):
    """Tool for sending test messages to Slack channels to verify bot configuration."""

    name: str = "slack_message_test_tool"
    description: str = (
        "Send a test message to a Slack channel to verify that the Slack bot token "
        "is properly configured and can successfully communicate with Slack. "
        "Useful for testing Slack integration before deploying automated workflows."
    )
    args_schema: Type[BaseModel] = SlackMessageTestInput

    def _run(self, channel_name: str = "all-opsmindai", test_message: str = "🤖 Test message from CrewAI Bot - Configuration verified!") -> str:
        """
        Send a test message to Slack to verify bot configuration.
        
        Args:
            channel_name: The Slack channel name (without #)
            test_message: The test message to send
            
        Returns:
            String containing success/failure status and details
        """
        try:
            # Get the Slack bot token from environment
            import os
            slack_token = os.getenv('SLACK_BOT_TKN')
            
            if not slack_token:
                return "❌ ERROR: SLACK_BOT_TKN environment variable not found. Please set your Slack bot token."
            
            # Prepare the API endpoint
            url = "https://slack.com/api/chat.postMessage"
            
            # Prepare headers
            headers = {
                'Authorization': f'Bearer {slack_token}',
                'Content-Type': 'application/json'
            }
            
            # Prepare the payload
            payload = {
                'channel': f'#{channel_name}' if not channel_name.startswith('#') else channel_name,
                'text': test_message
            }
            
            # Make the API request
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            # Parse the response
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('ok'):
                return (
                    f"✅ SUCCESS: Test message sent successfully!\n"
                    f"Channel: {channel_name}\n"
                    f"Message: {test_message}\n"
                    f"Message ID: {response_data.get('ts', 'Unknown')}\n"
                    f"Response: {json.dumps(response_data, indent=2)}"
                )
            else:
                error = response_data.get('error', 'Unknown error')
                error_messages = {
                    'invalid_auth': 'Invalid or missing Slack bot token',
                    'channel_not_found': f'Channel #{channel_name} not found or bot not invited',
                    'not_in_channel': f'Bot is not a member of #{channel_name}',
                    'account_inactive': 'Slack account is inactive',
                    'token_revoked': 'Slack bot token has been revoked',
                    'missing_scope': 'Bot token missing required scopes (chat:write)',
                    'rate_limited': 'Rate limited by Slack API',
                    'channel_archived': f'Channel #{channel_name} is archived'
                }
                
                detailed_error = error_messages.get(error, f'API error: {error}')
                
                return (
                    f"❌ FAILED: Could not send test message\n"
                    f"Error: {detailed_error}\n"
                    f"Channel: {channel_name}\n"
                    f"HTTP Status: {response.status_code}\n"
                    f"Full Response: {json.dumps(response_data, indent=2)}"
                )
                
        except requests.exceptions.Timeout:
            return "❌ ERROR: Request timed out. Check your internet connection."
        except requests.exceptions.ConnectionError:
            return "❌ ERROR: Could not connect to Slack API. Check your internet connection."
        except requests.exceptions.RequestException as e:
            return f"❌ ERROR: Request failed - {str(e)}"
        except json.JSONDecodeError:
            return f"❌ ERROR: Invalid JSON response from Slack API. Status: {response.status_code}"
        except Exception as e:
            return f"❌ ERROR: Unexpected error occurred - {str(e)}"