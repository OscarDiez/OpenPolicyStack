from data_utils import send_teams_message
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Get webhook URL from environment
webhook_url = os.getenv("hook_teams")

# Test message
test_message = "🔍 Test message from Connect Monitor Bot\nThis is a test of the Teams webhook integration."

# Send the message
success = send_teams_message(webhook_url, test_message)
print(f"Message sent successfully: {success}")
