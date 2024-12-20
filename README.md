# Messaging Event Servers

## Quick start

### Prereqs

- LangGraph platform deployment
- [Modal account](https://modal.com/apps/) (if you want to deploy to Modal)

### Setup

**1. Install `uv` (optional) and install dependencies**
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --dev
```

**2. Create a Slack app**

a. Go to https://api.slack.com/apps/.

b. Navigate to "OAuth & Permissions". 

c. Add these `essential scopes` under "Bot Token Scopes":

```
   app_mentions:read      # To receive mention events
   chat:write            # To send messages
   channels:history      # To read messages in channels
   groups:history        # To read messages in private channels
   im:history           # To read direct messages
   im:write             # To send direct messages
```

d. Under OAuth Tokens, install the app with `Install to Slack Workspace` and then get `SLACK_BOT_TOKEN`.

e. Under "Basic Information", get `SLACK_SIGNING_SECRET`.

**3. Copy the SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN to your .env file.** 

```shell
# .dotenv
SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=xoxb-...
```

**4. Copy your LangGraph deployment's URL and assistant ID (or graph name) to the `.env` file.**

Also add your LangGraph/LangSmith API key (they're the same).

```shell
# .dotenv
LANGGRAPH_URL=
LANGGRAPH_ASSISTANT_ID=
LANGGRAPH_API_KEY=
```

**5. Install the package in development mode**
```shell
uv pip install -e .
```

**6. Deploy with Modal**

a. If using Modal, run `modal token new`. 

b. This create an API token in `/Users/rlm/.modal.toml`. 

c. Replace "slack-handler" with your desired app name. 
```shell
DEPLOY_MODAL=true uv run modal deploy src/langgraph_slack/server.py::modal_app --name slack-handler
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

**7. Copy the deployment URL from the printout in your terminal. Add that to your `.env` file.**
```
# Get the following when you run modal deploy
DEPLOYMENT_URL=
``` 

**8. Go to "Event Subscriptions", and toggle "Enable Events" to "On".**

**9. Then, in `Event Subscriptions`, update the Request URL with the Modal deployment URL.**

Be sure to add `/events/slack` to the end of the URL.

```
https://<app-name>-fastapi-app.modal.run/events/slack
```

**10. In `Event Subscriptions`, "Subscribe to bot events"** 

```
     message.channels    # Messages in public channels
     message.groups     # Messages in private channels
     message.im        # Direct messages
     app_mention      # When your app is mentioned
```

**11. Install your app to your Slack workspace.**

Chat with the bot. The bot responds if you `@mention` it within a channel of which it is a member. You can also DM the bot. You needn't use `@mention`'s in the bot's DMs. It's clear who you are speaking to.

### Debugging 

To test the app, run the `test.py` script:

```shell
python test.py 
```

Check your Modal deployment logs to see the response.

Also check your LangGraph deployment logs to see the response.

