# Messaging Event Servers

## Quick start

### Prerequisites

- [LangGraph platform](https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/) deployment of an app that accepts `messages` (e.g., a chatbot).
- [Modal account](https://modal.com/apps/) for creating a server that receives Slack events and passes them to your LangGraph app.

### Flow

The overall concept is simple: we will deploy a server (with Modal, by default) that acts as a proxy between Slack and LangGraph. It has two main functions: first, it receives Slack events, packages them into a format that our LangGraph app can understand (chat `messages`), and passes them to our LangGraph app. Second, it receives the LangGraph app's responses, extracts the most recent `message` from the `messages` list, and sends it back to Slack. 

### Setup

1. Install `uv` (optional) and dependencies.
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --dev
```

2. Create a Slack app https://api.slack.com/apps/. 
* You can use the below manifest if you want to `From A Manifest`.
* Alternatively, you can follow these instructions to create an app `From Scratch`.

3. When creating an app `From Scratch`, go to `OAuth & Permissions` and add the following under `"Bot Token Scopes"`.
* This gives the app the necessary permissions to read and write messages.
* Add scopes for the app's functionality, as an example: 

```
# Reading Messages
"app_mentions:read",     # View when the bot is @mentioned
"channels:read",         # View basic channel info and membership
"channels:history",      # View messages in public channels
"groups:read",          # View private channel info and membership
"groups:history",       # View messages in private channels
"im:read",             # View direct message info
"im:history",          # View messages in direct messages
"mpim:history",        # View messages in group direct messages

# Writing Messages
"chat:write",          # Send messages in channels the bot is in
"chat:write.public",   # Send messages in any public channel
"im:write",           # Send direct messages to users

# Special Permissions
"assistant:write",     # Use Slack's built-in AI features
"channels:join",       # Join public channels automatically
```

4. Then, go to `OAuth & Permissions` and `Install App to Workspace`. This will expose the app's `SLACK_BOT_TOKEN`. 

5. Go to "Basic Information" and get `SLACK_SIGNING_SECRET`.

6. Copy both `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` to the `.env` file.
* `SLACK_BOT_TOKEN` is used to authenticate API calls FROM your bot TO Slack.
* `SLACK_SIGNING_SECRET` is used to verify that incoming requests TO your server are actually FROM Slack.

```shell
# .dotenv
SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=xoxb-...
```

7. Copy your LangGraph deployment's URL and assistant ID (or graph name) to the `.env` file, along with a LangGraph/LangSmith API key (they're the same).

```shell
# .dotenv
LANGGRAPH_URL=
LANGGRAPH_ASSISTANT_ID=
LANGGRAPH_API_KEY=
```

8. Deploy your Modal server and replace "<Your modal app name>" with your desired app name. 
```shell
DEPLOY_MODAL=true uv run modal deploy src/langgraph_slack/server.py::modal_app --name <Your modal app name>
```
If successful, you should see something like this in your terminal:

```shell
✓ Created objects.
├── 🔨 Created mount /Users/foo/path/to/slack-server/src/langgraph_slack/server.py
├── 🔨 Created mount PythonPackage:langgraph_slack
└── 🔨 Created web function fastapi_app => https://youraccount--yourdeploymentname-fastapi-app.modal.run
✓ App deployed in 1.101s! 🎉

View Deployment: https://modal.com/apps/youraccount/main/deployed/yourdeploymentname
```

9. Add the Modal deployment URL to your `.env` file.
```
# Get the following when you run modal deploy
DEPLOYMENT_URL=https://youraccount--yourdeploymentname-fastapi-app.modal.run
``` 

10. Finally, go to `Event Subscriptions` in Slack and add: `https://youraccount--yourdeploymentname-fastapi-app.modal.run/events/slack` as the request URL. 
* This is the URL that Slack will send events to.
* Make sure to add the `/events/slack` path to the end of the Modal deployment URL.
* Add events that you want to receive, as an example: 

```
"app_mention",        # Notify when bot is @mentioned
"message.im",         # Notify about direct messages
"message.mpim"        # Notify about group messages
"message.channels",   # Get notified of channel messages
```

11. Re-install your app to your Slack workspace, `Install App to Workspace` and test.
* Chat with the bot. 
* The bot responds if you `@mention` it within a channel of which it is a member. 
* You can also DM the bot. You needn't use `@mention`'s in the bot's DMs. It's clear who you are speaking to.

## Slack Manifest

Here is an example Slack app manifest, which you can use for quickstart.

Simply replace `<Your-App-Name>` with your app's name.

And replace `<Your-Modal-deployment-url>` with your Modal deployment URL.

```JSON
{
    "display_information": {
        "name": "Reply-gAI"
    },
    "features": {
        "bot_user": {
            "display_name": "Reply-gAI",
            "always_online": false
        }
    },
    "oauth_config": {
        "scopes": {
            "bot": [
                "app_mentions:read",
                "assistant:write",
                "channels:history",
                "channels:join",
                "channels:read",
                "chat:write",
                "groups:history",
                "groups:read",
                "im:history",
                "im:write",
                "mpim:history",
                "im:read",
                "chat:write.public"
            ]
        }
    },
    "settings": {
        "event_subscriptions": {
            "request_url": "https://lance--reply-gai-fastapi-app.modal.run/events/slack",
            "bot_events": [
                "app_mention",
                "message.channels",
                "message.im",
                "message.mpim"
            ]
        },
        "org_deploy_enabled": false,
        "socket_mode_enabled": false,
        "token_rotation_enabled": false
    }
}
```