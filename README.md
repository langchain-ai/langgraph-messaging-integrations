# LangGraph Application Integration with Slack

Modern AI applications like chatbots and agents communicate through natural language, making messaging platforms like Slack an ideal interface for interacting with them. As these AI assistants take on more complex tasks, users need to engage with them in their native work environments rather than separate web interfaces.

This repository demonstrates how to connect any LangGraph-powered application (chatbot, agent, or other AI system) to Slack, allowing teams to interact with their AI assistants directly in their everyday communication channels. Currently focused on Slack integration, with a straightforward approach that can be adapted for other messaging platforms.

## Quickstart

### Prerequisites

- [LangGraph platform](https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/) deployment with a `messages` state key (e.g., a chatbot).
- [Modal account](https://modal.com/apps/) for creating a server that receives Slack events and passes them to your LangGraph app.

### Flow

The overall concept is simple: we will deploy a server (with Modal, by default) that acts as a proxy between Slack and LangGraph. It has two main functions: first, it receives Slack events, packages them into a format that our LangGraph app can understsand (chat `messages`), and passes them to our LangGraph app. Second, it receives the LangGraph app's responses, extracts the most recent `message` from the `messages` list, and sends it back to Slack. 

![slack_integration](https://github.com/user-attachments/assets/e73f5121-fed1-4cde-9297-3250ea273e1e)

### Quickstart setup

1. Install `uv` (optional) and dependencies.
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --dev
```

2. Create a Slack app https://api.slack.com/apps/ and select `From A Manifest`.

3. Copy the below manifest and paste it into the `Manifest` field.

* Replace `your-app-name` with your app's name and `your-app-description` with your app's description.
* You will update `your-app-name` in the Modal deployment URL later.
* The scopes gives the app the necessary permissions to read and write messages.
* The events are what we want to receive from Slack.

```JSON
{
    "display_information": {
        "name": "your-app-name"
    },
    "features": {
        "bot_user": {
            "display_name": "your-app-name",
            "always_online": false
        },
        "assistant_view": {
            "assistant_description": "your-app-description"
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
            "request_url": "https://your-app-name-fastapi-app.modal.run/events/slack",
            "bot_events": [
                "app_mention",
                "message.channels",
                "message.im",
                "message.mpim",
                "assistant_thread_started"
            ]
        },
        "org_deploy_enabled": false,
        "socket_mode_enabled": false,
        "token_rotation_enabled": false
    }
}
```

4. Got to `OAuth & Permissions` and `Install App to Workspace`.

5. Copy `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` to the `.env` file: 
* `OAuth & Permissions` page will expose the app's `SLACK_BOT_TOKEN` after installation.
* Go to "Basic Information" and get `SLACK_SIGNING_SECRET`.
* `SLACK_BOT_TOKEN` is used to authenticate API calls FROM your bot TO Slack.
* `SLACK_SIGNING_SECRET` is used to verify that incoming requests TO your server are actually FROM Slack.

6. Copy your LangGraph deployment's URL and assistant ID (or graph name) to the `.env` file.
* For example, for a ChatLangChain blog post you can use the following public deployment URL.
* Simply provide your LangSmith/LangGraph API key.
```shell
LANGGRAPH_URL="https://langr.ph/marketplace/6d5d0ba3-f1a3-4769-97d8-dc2a4f6dba16"
LANGGRAPH_ASSISTANT_ID="chat"
LANGGRAPH_API_KEY="xxx"
CONFIG={"configurable": {"response_model": "anthropic/claude-3-5-sonnet-latest"}}
```

7. Install the package and deploy your Modal app.

If you are using Modal for the first time: 
```
modal token new
```

Install the package and deploy your Modal server to get your modal app URL.
```shell
uv pip install -e .
DEPLOY_MODAL=true uv run modal deploy src/langgraph_slack/server.py::modal_app --name <Your modal app name>
```

For example, you should see the following for `--name chat-langchain-bot`:
```
2025-01-08 13:54:08 WARNING DEPLOYMENT_URL not set
✓ Created objects.
├── 🔨 Created mount /Users/rlm/Desktop/Code/langgraph-messaging-integrations/src/langgraph_slack/server.py
├── 🔨 Created mount PythonPackage:langgraph_slack
└── 🔨 Created web function fastapi_app => https://lance--chat-langchain-bot-fastapi-app.modal.run
✓ App deployed in 1.037s! 🎉

View Deployment: https://modal.com/apps/lance/main/deployed/chat-langchain-bot
```

8. Add the Modal deployment URL to `Event Subscriptions` in Slack with `/events/slack` appended.
* E.g., `https://youraccount--yourdeploymentname-fastapi-app.modal.run/events/slack` as the request URL. 
* This is the URL that Slack will send events to.

## `From Scratch` Slack App Setup

You can use this setup to customize your Slack app permissions and event subscriptions.

1. Create a Slack app https://api.slack.com/apps/ amd select `From Scratch`.

2. Go to `OAuth & Permissions` and add your desired `Bot Token Scopes`.
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

3. Then, go to `OAuth & Permissions` and `Install App to Workspace`. This will expose the app's `SLACK_BOT_TOKEN`. 

4. Go to "Basic Information" and get `SLACK_SIGNING_SECRET`.

5. Copy both `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` to the `.env` file.
* `SLACK_BOT_TOKEN` is used to authenticate API calls FROM your bot TO Slack.
* `SLACK_SIGNING_SECRET` is used to verify that incoming requests TO your server are actually FROM Slack.

```shell
# .dotenv
SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=xoxb-...
```

6. Copy your LangGraph deployment's URL and assistant ID (or graph name) to the `.env` file, along with a LangGraph/LangSmith API key (they're the same).

```shell
# .dotenv
LANGGRAPH_URL=
LANGGRAPH_ASSISTANT_ID=
LANGGRAPH_API_KEY=
```

7. Deploy your Modal server and replace "<Your modal app name>" with your desired app name. 
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

8. Add the Modal deployment URL to your `.env` file.
```
# Get the following when you run modal deploy
DEPLOYMENT_URL=https://youraccount--yourdeploymentname-fastapi-app.modal.run
``` 

9. Also add the Modal deployment URL to `Event Subscriptions` in Slack with `/events/slack` appended.
* E.g., `https://youraccount--yourdeploymentname-fastapi-app.modal.run/events/slack` as the request URL. 
* This is the URL that Slack will send events to.

10. In `Event Subscriptions`, add events that you want to receive. As an example: 

```
"app_mention",        # Notify when bot is @mentioned
"message.im",         # Notify about direct messages
"message.mpim"        # Notify about group messages
"message.channels",   # Get notified of channel messages
```

11. Re-deploy your modal app now that the DEPLOYMENT_URL has been added to the .env file.

12. Chat with the bot in Slack. 
* The bot responds if you `@mention` it within a channel of which it is a member. 
* You can also DM the bot. You needn't use `@mention`'s in the bot's DMs. It's clear who you are speaking to.

## Customizing the input and output

By default, the bot assums that the LangGraph deployment uses the `messages` state key.

The request to the LangGraph deployment using the LangGraph SDK is made here in `src/langgraph_slack/server.py`:

```
result = await LANGGRAPH_CLIENT.runs.create(
            thread_id=thread_id,
            assistant_id=config.ASSISTANT_ID,
            input={
                "messages": [
                    {
                        "role": "user",
                        "content": _replace_mention(event),
                    }
                ]
            },
```

And you can see that the output, which we send back to Slack, is extracted from the `messages` list here:

```
response_message = state_values["messages"][-1]
```

You can customize either for the specific LangGraph deployment you are using! 
