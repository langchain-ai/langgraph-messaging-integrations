import hashlib
import hmac
import time
import requests
import json
from dotenv import load_dotenv
import os

def generate_slack_signature(signing_secret, timestamp, body):
    # Create the signature base string
    sig_basestring = f"v0:{timestamp}:{body}"
    
    # Create the signature
    signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature

# Your Slack signing secret from .env
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')

# Slack bot token from .env
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

# Create the request
timestamp = str(int(time.time()))
current_time = int(timestamp)

# Create the body as a dictionary first
body_dict = {
    "type": "event_callback",
    "event": {
        "type": "app_mention",
        "channel": "C082C8M8BFE",
        "user": "U05A4L15MM5",
        "text": "<@U05PQCG2YS1> what's interesting these days?",
        "blocks": [
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_section",
                        "elements": [
                            {
                                "type": "user",
                                "user_id": "U05PQCG2YS1"
                            },
                            {
                                "type": "text",
                                "text": " what's interesting these days?"
                            }
                        ]
                    }
                ]
            }
        ],
        "ts": f"{current_time}.929449",
        "thread_ts": f"{current_time}.929449",
        "event_ts": f"{current_time}.929449"
    },
    "team_id": "T04F8K3FZB5",
    "api_app_id": "A085S2BTMV4",
    "event_id": f"Ev{current_time}",
    "event_time": current_time,
    "authorizations": [
        {
            "enterprise_id": None,
            "team_id": "T04F8K3FZB5",
            "user_id": "U05PQCG2YS1",
            "is_bot": True,
            "is_enterprise_install": False
        }
    ],
    "is_ext_shared_channel": False,
    "context_team_id": "T04F8K3FZB5",
    "context_enterprise_id": None
}

# Convert to JSON string with consistent formatting
body = json.dumps(body_dict)

# Generate signature using the exact same string
signature = generate_slack_signature(SLACK_SIGNING_SECRET, timestamp, body)

print(f"Timestamp: {timestamp}")
print(f"Signature: {signature}")
print(f"Body: {body}")
print("\nSending request...")

response = requests.post(
    "https://lance--slack-handler-fastapi-app.modal.run/events/slack",
    headers={
        "Content-Type": "application/json",
        "X-Slack-Request-Timestamp": timestamp,
        "X-Slack-Signature": signature,
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}"  # Add bot token
    },
    data=body
)

print(f"\nStatus Code: {response.status_code}")
print(f"Response: {response.text}")