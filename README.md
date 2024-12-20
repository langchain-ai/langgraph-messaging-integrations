# Messaging Event Servers



## Quick start

### Prereqs

- LangGraph platform deployment
- [Modal account](https://modal.com/apps/) (if you want to deploy to Modal)

### Setup

1. Install `uv` (optional) and install dependencies
```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --dev
```
2. Create a Slack app https://api.slack.com/apps/ . Ensure you give it permissions to receive events and to read/write messages.
3. Copy the SLACK_SIGNING_SECRET and SLACK_BOT_TOKEN to your .env file. These are found in the oauth section of your Slack App.
```shell
# .dotenv
SLACK_SIGNING_SECRET=
SLACK_BOT_TOKEN=xoxb-...
```
4. Copy your LangGraph deployment's URL and assistant ID (or graph name) to the `.env` file, along with a LangGraph/LangSmith API key (they're the same).

```shell
# .dotenv
LANGGRAPH_URL=
LANGGRAPH_ASSISTANT_ID=
LANGGRAPH_API_KEY=
```
5. Deploy. Replace "slack-handler" with your desired app name. 
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

6. Copy the deployment URL from the printout in your terminal. Add that to your `.env` file.
```
# Get the following when you run modal deploy
DEPLOYMENT_URL=
``` 
7. Redeploy with the updated deployment URL.

8. Install your app to your Slack workspace.

Chat with the bot. The bot responds if you `@mention` it within a channel of which it is a member. You can also DM the bot. You needn't use `@mention`'s in the bot's DMs. It's clear who you are speaking to.


