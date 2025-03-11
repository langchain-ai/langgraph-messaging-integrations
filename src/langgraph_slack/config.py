from os import environ
import logging

LOGGER = logging.getLogger(__name__)

if DEPLOY_MODAL := environ.get("DEPLOY_MODAL"):
    DEPLOY_MODAL = DEPLOY_MODAL.lower() == "true"
BOT_USER_ID = environ.get("SLACK_BOT_USER_ID")
BOT_TOKEN = environ.get("SLACK_BOT_TOKEN")
if DEPLOY_MODAL:
    if not environ.get("SLACK_BOT_TOKEN"):
        environ["SLACK_BOT_TOKEN"] = "fake-token"
    BOT_USER_ID = BOT_USER_ID or "fake-user-id"
else:
    assert isinstance(BOT_TOKEN, str)
    # APP_TOKEN = environ["SLACK_APP_TOKEN"]


LANGGRAPH_URL = environ.get("LANGGRAPH_URL")
ASSISTANT_ID = environ.get("LANGGRAPH_ASSISTANT_ID", "chat")
CONFIG = environ.get("CONFIG") or "{}"
DEPLOYMENT_URL = environ.get("DEPLOYMENT_URL", "")
SLACK_CHANNEL_ID = environ.get("SLACK_CHANNEL_ID")
