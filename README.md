# LangGraph Application Integration with Slack

Modern AI applications like chatbots and agents communicate through natural language, making messaging platforms like Slack an ideal interface for interacting with them. As these AI assistants take on more complex tasks, users need to engage with them in their native work environments rather than separate web interfaces.

This repository demonstrates how to connect any LangGraph-powered application (chatbot, agent, or other AI system) to Slack, allowing teams to interact with their AI assistants directly in their everyday communication channels. Currently focused on Slack integration, with a straightforward approach that can be adapted for other messaging platforms.

## Quickstart

### Prerequisites

- [LangGraph platform](https://langchain-ai.github.io/langgraph/concepts/langgraph_platform/) deployment with a `messages` state key (e.g., a chatbot).

### Flow

The overall concept is simple: Slack routes are added directly to the API server deployed on the LangGraph platform using the custom routes support. The server has two main functions: first, it receives Slack events, packages them into a format that our LangGraph app can understand (chat `messages`), and passes them to our LangGraph app. Second, it receives the LangGraph app's responses, extracts the most recent `message` from the `messages` list, and sends it back to Slack.

<!-- this is outdated; Modal no longer used. Should replace. -->
<!-- ![slack_integration](https://github.com/user-attachments/assets/e73f5121-fed1-4cde-9297-3250ea273e1e) -->

### Quickstart setup

**Note:** This messaging integration should be added to your existing LangGraph application directory. Copy or move these files into your LangGraph app's root directory alongside your existing `langgraph.json` file.

1. Install `uv` (optional) and dependencies.
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --dev
```

2. Create a Slack app https://api.slack.com/apps/ and select `From A Manifest`.

3. Copy the below manifest and paste it into the `Manifest` field.

* Replace `your-app-name` with your app's name and `your-app-description` with your app's description.
* Replace `your-langgraph-platform-url` with your LangGraph platform URL (if you're testing locally, you can use something like ngrok for tunneling)
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
            "request_url": "your-langgraph-platform-url/events/slack",
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
* The `.env.example` file shows the required environment variables.
* Example environment variables:
```shell
# Slack credentials
SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=xoxb-...
# SLACK_BOT_USER_ID= (optional)

# LangGraph platform instance you're connecting to
LANGGRAPH_ASSISTANT_ID=
CONFIG= # Optional
```

7. Deploy your application to the LangGraph platform with custom routes.

The Slack routes are added directly to the API server deployed on the LangGraph platform, using the custom routes support as documented at https://langchain-ai.github.io/langgraph/how-tos/http/custom_routes/.

The integration uses the langgraph_sdk and connects to the current platform routes by setting URL to None, which connects to the loopback server. The Slack Bolt SDK is used to register a slack webhook to handle slack events (new messages, @mentions, etc). When an event is received, it creates a run on the current server and passes in a webhook "/webhooks/<thread_id>" that is triggered when the chatbot completes. Since a relative path is provided, the LangGraph platform knows to call the route on this server itself.

8. Add your LangGraph platform URL to `Event Subscriptions` in Slack with `/events/slack` appended.
* E.g., `https://your-langgraph-platform-url/events/slack` as the request URL. 
* This is the URL that Slack will send events to.

## `From Scratch` Slack App Setup

You can use this setup to customize your Slack app permissions and event subscriptions.

1. Create a Slack app https://api.slack.com/apps/ and select `From Scratch`.

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
# .env
SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=xoxb-...
```

6. Set up your LangGraph deployment with custom routes support.

```shell
# .env
LANGGRAPH_ASSISTANT_ID=your_assistant_id
CONFIG={"your_config": "here"}
```

7. Deploy your application to the LangGraph platform with custom routes.

The application uses the LangGraph platform's custom routes feature to add Slack integration directly to your deployed application. When deployed, the Slack routes will be available at your LangGraph platform URL.

After deployment, update your Slack app's Event Subscriptions URL to point to your LangGraph platform URL with `/events/slack` appended.

8. In `Event Subscriptions`, add events that you want to receive. As an example: 

```
"app_mention",        # Notify when bot is @mentioned
"message.im",         # Notify about direct messages
"message.mpim"        # Notify about group messages
"message.channels",   # Get notified of channel messages
```

9. Chat with the bot in Slack. 
* The bot responds if you `@mention` it within a channel of which it is a member. 
* You can also DM the bot. You needn't use `@mention`'s in the bot's DMs. It's clear who you are speaking to.

## Customizing the input and output

By default, the bot assumes that the LangGraph deployment uses the `messages` state key.

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
