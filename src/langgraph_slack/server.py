import asyncio
import logging
import re
import json
import uuid
from typing import Awaitable, Callable, TypedDict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from langgraph_sdk import get_client
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

from langgraph_slack import config

LOGGER = logging.getLogger(__name__)
LANGGRAPH_CLIENT = get_client(url=config.LANGGRAPH_URL)
GRAPH_CONFIG = (
    json.loads(config.CONFIG) if isinstance(config.CONFIG, str) else config.CONFIG
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    LOGGER.info("App is starting up. Creating background worker...")
    loop = asyncio.get_running_loop()
    loop.create_task(worker())
    yield
    LOGGER.info("App is shutting down. Stopping background worker...")
    TASK_QUEUE.put_nowait(None)


APP = FastAPI(lifespan=lifespan)

APP_HANDLER = AsyncSlackRequestHandler(AsyncApp(logger=LOGGER))
if not config.BOT_USER_ID or config.BOT_USER_ID == "fake-user-id":
    config.BOT_USER_ID = asyncio.run(APP_HANDLER.app.client.auth_test())["user_id"]
USER_ID_PATTERN = re.compile(rf"<@{config.BOT_USER_ID}>")
TASK_QUEUE: asyncio.Queue = asyncio.Queue()


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


async def worker():
    LOGGER.info("Background worker started.")
    while True:
        try:
            # Wait until a task is available
            task = await TASK_QUEUE.get()
            if not task:
                # This pattern can let you send a sentinel to stop the worker gracefully
                LOGGER.info("Worker received sentinel, exiting.")
                break

            LOGGER.info(f"Worker got a new task: {task}")
            await _process_task(task)

        except Exception as exc:
            LOGGER.exception(f"Error in worker: {exc}")
        finally:
            TASK_QUEUE.task_done()


async def _process_task(task: dict):
    """
    The actual logic for handling a single queued task.
    We separate this so we can keep 'worker()' logic simple.
    """
    event = task["event"]
    event_type = task["type"]
    if event_type == "slack_message":
        thread_id = _get_thread_id(
            event.get("thread_ts") or event["ts"], event["channel"]
        )
        channel_id = event["channel"]
        webhook = f"{config.DEPLOYMENT_URL}/callbacks/{thread_id}"
        LOGGER.info(
            f"[{channel_id}].[{thread_id}] sending message to LangGraph: "
            f"with webhook {webhook}: {event['text']}"
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
            config=GRAPH_CONFIG,
            metadata={
                "event": "slack",
                "slack_event_type": "message",
                "bot_user_id": config.BOT_USER_ID,
                "channel": channel_id,
                "thread_ts": event.get("thread_ts"),
                "event_ts": event["ts"],
                "channel_type": event.get("channel_type"),
            },
            multitask_strategy="interrupt",
            if_not_exists="create",
            webhook=webhook,
        )
        LOGGER.info(f"LangGraph run: {result}")
    elif event_type == "callback":
        LOGGER.info(f"Processing LangGraph callback: {event['thread_id']}")
        state_values = event["values"]
        response_message = state_values["messages"][-1]
        thread_ts = event["metadata"].get("thread_ts") or event["metadata"].get(
            "event_ts"
        )
        channel_id = event["metadata"].get("channel") or config.SLACK_CHANNEL_ID
        if not channel_id:
            raise ValueError(
                "Channel ID not found in event metadata and not set in environment"
            )
        await APP_HANDLER.app.client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=_clean_markdown(_get_text(response_message["content"])),
            metadata={
                "event_type": "webhook",
                "event_payload": {"thread_id": event["thread_id"]},
            },
        )
        LOGGER.info(
            f"[{channel_id}].[{thread_ts}] sent message to Slack for callback {event['thread_id']}"
        )
    else:
        raise ValueError(f"Unknown event type: {event_type}")


async def handle_message(event: SlackMessageData, say: Callable, ack: Callable):
    """Instead of awaiting the LangGraph call immediately,
    we just enqueue a task for the background worker.
    """
    LOGGER.info("Enqueuing handle_message task...")
    nouser = not event.get("user")
    userisbot = event.get("bot_id") == config.BOT_USER_ID
    ismention = _is_mention(event)
    isdm = _is_dm(event)
    if nouser or userisbot or not (ismention or isdm):
        LOGGER.info("Message not from bot or not a mention, ignoring")
        return

    TASK_QUEUE.put_nowait({"type": "slack_message", "event": event})
    await ack()


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


def _get_text(content: str | list[dict]):
    if isinstance(content, str):
        return content
    else:
        return "".join([block["text"] for block in content if block["type"] == "text"])


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
    LOGGER.info(
        f"Received webhook callback for {req.path_params['thread_id']}/{body['thread_id']}"
    )
    TASK_QUEUE.put_nowait({"type": "callback", "event": body})
    return {"status": "success"}


# Helper functions
def _is_mention(event: SlackMessageData):
    matches = re.search(USER_ID_PATTERN, event["text"])
    return bool(matches)


def _replace_mention(event: SlackMessageData):
    return re.sub(USER_ID_PATTERN, "assistant", event["text"])


def _get_thread_id(thread_ts: str, channel: str) -> str:
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
        keep_warm=1,
        allow_concurrent_inputs=30,
        secrets=[
            modal.Secret.from_dotenv(),
            modal.Secret.from_local_environ(["DEPLOY_MODAL"]),
        ],
    )
    @modal.asgi_app()
    def fastapi_app():
        if not config.DEPLOYMENT_URL:
            config.DEPLOYMENT_URL = fastapi_app.web_url
        return APP


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("langgraph_slack.server:APP", host="0.0.0.0", port=8080)
