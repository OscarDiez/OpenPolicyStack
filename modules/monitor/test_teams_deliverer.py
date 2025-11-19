from data_delivering import TeamsDeliverer
from dotenv import load_dotenv
import os

def test_teams_message():
    """Test sending a message via Teams webhook."""
    load_dotenv()
    
    # Initialize deliverer
    deliverer = TeamsDeliverer(
        from_name="Connect Monitor Bot",
        webhook_url=os.getenv("hook_teams"),
        message_subject="Test Message",
        message_text="This is a test message from the Connect Monitor Bot.\nIt supports **markdown** formatting."
    )
    
    # Send message
    success = deliverer.send_message()
    print(f"Message sent: {'✅' if success else '❌'}")

if __name__ == "__main__":
    test_teams_message()
