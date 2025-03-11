from langgraph_sdk import Auth


auth = Auth()


@auth.authenticate
async def authenticate(request, path, headers, method):
    user_agent = headers.get(b"user-agent")
    if user_agent and user_agent.startswith(b"Slackbot"):
        return {"identity": "default-user", "permissions": ["read", "write"]}
    return None
