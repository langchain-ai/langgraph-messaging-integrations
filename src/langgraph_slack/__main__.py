import uvicorn

uvicorn.run("langgraph_slack.server:app", host="0.0.0.0", port=8080)
