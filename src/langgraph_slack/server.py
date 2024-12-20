import asyncio
import logging
import re
import uuid
from typing import Awaitable, Callable, TypedDict

from fastapi import FastAPI, Request
from langgraph_sdk import get_client
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from langgraph_slack import config

LOGGER = logging.getLogger(__name__)
LANGGRAPH_CLIENT = get_client(url=config.LANGGRAPH_URL)
APP = FastAPI()
APP_HANDLER = AsyncSlackRequestHandler(AsyncApp(logger=LOGGER))
if not config.BOT_USER_ID or config.BOT_USER_ID == "fake-user-id":
    config.BOT_USER_ID = asyncio.run(APP_HANDLER.app.client.auth_test())["user_id"]
USER_ID_PATTERN = re.compile(rf"<@{config.BOT_USER_ID}>")


class SlackMessageData(TypedDict):
    user: str
    type: str
    subtype: str | None
    ts: str
    thread_ts: str | None
    client_msg_id: str
    text: str
    team: str
    parent_user_id: str
    blocks: list[dict]
    channel: str
    event_ts: str
    channel_type: str


async def handle_message(event: SlackMessageData, say: Callable, ack: Callable):
    nouser = not event.get("user")
    userisbot = event.get("bot_id") == config.BOT_USER_ID
    ismention = _is_mention(event)
    isdm = _is_dm(event)
    if (
        # Forget why we had this. Think for app events
        nouser
        # Suppress feedback
        or userisbot
        or not (ismention or isdm)
    ):
        LOGGER.info("Message not from bot or not a mention, ignoring")
        return
    thread_id = await _get_thread_id(
        event.get("thread_ts") or event["ts"], event["channel"]
    )
    channel_id = event["channel"]
    webhook = f"{config.DEPLOYMENT_URL}/callbacks/{thread_id}"
    LOGGER.info(
        f"[{channel_id}].[{thread_id}] sending message to LangGraph: with webhook {webhook}: {event['text']}"
    )
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
        metadata={
            "event": "slack",
            "slack_event_type": "message",
            "bot_user_id": config.BOT_USER_ID,
            "channel": channel_id,
            "thread_ts": event.get("thread_ts"),
            "event_ts": event["ts"],
            "channel_type": event.get("channel_type"),
        },
        if_not_exists="create",
        webhook=webhook,
    )
    LOGGER.info(f"LangGraph run: {result}")


async def just_ack(ack: Callable[..., Awaitable], event):
    LOGGER.info(f"Acknowledging {event.get('type')} event")
    await ack()


APP_HANDLER.app.event("message")(ack=just_ack, lazy=[handle_message])
APP_HANDLER.app.event("app_mention")(
    ack=just_ack,
    lazy=[],  # We handle mentions above
)


@APP.post("/events/slack")
async def slack_endpoint(req: Request):
    return await APP_HANDLER.handle(req)

async def _get_state(thread_id: str):
    for i in range(20):
        state = await LANGGRAPH_CLIENT.threads.get_state(thread_id)
        if not state["values"]:
            LOGGER.info(f"Attempt {i}: Got empty state for {thread_id}")
            await asyncio.sleep(1)
        else:  
            return state

def _get_text(content: str | list[dict]):
    if isinstance(content, str):
        return content
    else:
        return "".join(
            [
                block["text"]
                for block in content
                if block["type"] == "text"
            ]
        )

def _clean_markdown(text: str) -> str:
    text = re.sub(r"^```[^\n]*\n", "```\n", text, flags=re.MULTILINE)
    
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"*\1*", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"_\1_", text)
    text = re.sub(r"_([^_]+)_", r"_\1_", text)
    text = re.sub(r"^\s*[-*]\s", "• ", text, flags=re.MULTILINE)
    
    return text


@APP.post("/callbacks/{thread_id}")
async def webhook_callback(req: Request):
    body = await req.json()
    LOGGER.info(f"Received webhook callback for {req.path_params['thread_id']}/{body['thread_id']}")

    state = await _get_state(body["thread_id"])
    if not state:
        raise ValueError(f"Failed to get state for {body['thread_id']}")
    state_values = state["values"]
    response_message = state_values["messages"][-1]
    thread_ts = body["metadata"]["thread_ts"] or body["metadata"]["event_ts"]
    channel_id = body["metadata"]["channel"]
    thread_id = req.path_params["thread_id"]
    await APP_HANDLER.app.client.chat_postMessage(
        channel=channel_id,
        thread_ts=thread_ts,
        text=_clean_markdown(_get_text(response_message["content"])),
        metadata={"event_type": "webhook", "event_payload": {"thread_id": thread_id}},
    )
    return {"status": "success"}


# Helper functions


def _is_mention(event: SlackMessageData):
    matches = re.search(USER_ID_PATTERN, event["text"])
    return bool(matches)

def _replace_mention(event: SlackMessageData):
    return re.sub(USER_ID_PATTERN, "assistant", event["text"])


async def _get_thread_id(thread_ts: str, channel: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"SLACK:{thread_ts}-{channel}"))


def _is_dm(event: SlackMessageData):
    if channel_type := event.get("channel_type"):
        return channel_type == "im"
    return False


if config.DEPLOY_MODAL:
    import modal

    modal_app = modal.App()

    image = modal.Image.debian_slim().pip_install_from_pyproject(
        pyproject_toml="pyproject.toml"
    )

    @modal_app.function(
        image=image,
        keep_warm=True,
        secrets=[
            modal.Secret.from_dotenv(),
            modal.Secret.from_local_environ(["DEPLOY_MODAL"]),
        ],
    )
    @modal.asgi_app()
    def fastapi_app():
        return APP


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("langgraph_slack.server:APP", host="0.0.0.0", port=8080)
