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

USER_NAME_CACHE: dict[str, str] = {}
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
            task = await TASK_QUEUE.get()
            if not task:
                LOGGER.info("Worker received sentinel, exiting.")
                break

            LOGGER.info(f"Worker got a new task: {task}")
            await _process_task(task)
        except Exception as exc:
            LOGGER.exception(f"Error in worker: {exc}")
        finally:
            TASK_QUEUE.task_done()


async def _process_task(task: dict):
    event = task["event"]
    event_type = task["type"]
    if event_type == "slack_message":
        thread_id = _get_thread_id(
            event.get("thread_ts") or event["ts"], event["channel"]
        )
        channel_id = event["channel"]
        # This will connect to the loopback endpoint if not provided.
        webhook = f"{config.DEPLOYMENT_URL}/callbacks/{thread_id}"

        if (await _is_mention(event)) or _is_dm(event):
            text_with_names = await _build_contextual_message(event)
        else:
            LOGGER.info("Skipping non-mention message")
            return

        LOGGER.info(
            f"[{channel_id}].[{thread_id}] sending message to LangGraph: "
            f"with webhook {webhook}: {text_with_names}"
        )

        result = await LANGGRAPH_CLIENT.runs.create(
            thread_id=thread_id,
            assistant_id=config.ASSISTANT_ID,
            input={
                "messages": [
                    {
                        "role": "user",
                        "content": text_with_names,
                    }
                ]
            },
            config=GRAPH_CONFIG,
            metadata={
                "event": "slack",
                "slack_event_type": "message",
                "bot_user_id": config.BOT_USER_ID,
                "slack_user_id": event["user"],
                "channel_id": channel_id,
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
    LOGGER.info("Enqueuing handle_message task...")
    nouser = not event.get("user")
    ismention = await _is_mention(event)
    userisbot = event.get("bot_id") == config.BOT_USER_ID
    isdm = _is_dm(event)
    if nouser or userisbot or not (ismention or isdm):
        LOGGER.info(f"Ignoring message not directed at the bot: {event}")
        return

    TASK_QUEUE.put_nowait({"type": "slack_message", "event": event})
    await ack()


async def just_ack(ack: Callable[..., Awaitable], event):
    LOGGER.info(f"Acknowledging {event.get('type')} event")
    await ack()


APP_HANDLER = AsyncSlackRequestHandler(AsyncApp(logger=LOGGER))
MENTION_REGEX = re.compile(r"<@([A-Z0-9]+)>")
USER_ID_PATTERN = re.compile(rf"<@{config.BOT_USER_ID}>")
APP_HANDLER.app.event("message")(ack=just_ack, lazy=[handle_message])
APP_HANDLER.app.event("app_mention")(
    ack=just_ack,
    lazy=[],
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


async def _is_mention(event: SlackMessageData):
    global USER_ID_PATTERN
    if not config.BOT_USER_ID or config.BOT_USER_ID == "fake-user-id":
        config.BOT_USER_ID = (await APP_HANDLER.app.client.auth_test())["user_id"]
        USER_ID_PATTERN = re.compile(rf"<@{config.BOT_USER_ID}>")
    matches = re.search(USER_ID_PATTERN, event["text"])
    return bool(matches)


def _get_thread_id(thread_ts: str, channel: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"SLACK:{thread_ts}-{channel}"))


def _is_dm(event: SlackMessageData):
    if channel_type := event.get("channel_type"):
        return channel_type == "im"
    return False


async def _fetch_thread_history(
    channel_id: str, thread_ts: str
) -> list[SlackMessageData]:
    """
    Fetch all messages in a Slack thread, following pagination if needed.
    """
    LOGGER.info(
        f"Fetching thread history for channel={channel_id}, thread_ts={thread_ts}"
    )
    all_messages = []
    cursor = None

    while True:
        try:
            if cursor:
                response = await APP_HANDLER.app.client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    inclusive=True,
                    limit=150,
                    cursor=cursor,
                )
            else:
                response = await APP_HANDLER.app.client.conversations_replies(
                    channel=channel_id,
                    ts=thread_ts,
                    inclusive=True,
                    limit=150,
                )
            all_messages.extend(response["messages"])
            if not response.get("has_more"):
                break
            cursor = response["response_metadata"]["next_cursor"]
        except Exception as exc:
            LOGGER.exception(f"Error fetching thread messages: {exc}")
            break

    return all_messages


async def _fetch_user_names(user_ids: set[str]) -> dict[str, str]:
    """Fetch and cache Slack display names for user IDs."""
    uncached_ids = [uid for uid in user_ids if uid not in USER_NAME_CACHE]
    if uncached_ids:
        tasks = [APP_HANDLER.app.client.users_info(user=uid) for uid in uncached_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for uid, result in zip(uncached_ids, results):
            if isinstance(result, Exception):
                LOGGER.warning(f"Failed to fetch user info for {uid}: {result}")
                continue
            user_obj = result.get("user", {})
            profile = user_obj.get("profile", {})
            display_name = (
                profile.get("display_name") or profile.get("real_name") or uid
            )
            USER_NAME_CACHE[uid] = display_name
    return {uid: USER_NAME_CACHE[uid] for uid in user_ids if uid in USER_NAME_CACHE}


async def _build_contextual_message(event: SlackMessageData) -> str:
    """Build a message with thread context, using display names for all users."""
    thread_ts = event.get("thread_ts") or event["ts"]
    channel_id = event["channel"]

    history = await _fetch_thread_history(channel_id, thread_ts)
    included = []
    for msg in reversed(history):
        if msg.get("bot_id") == config.BOT_USER_ID:
            break
        included.append(msg)

    all_user_ids = set()
    for msg in included:
        all_user_ids.add(msg.get("user", "unknown"))
        all_user_ids.update(MENTION_REGEX.findall(msg["text"]))

    all_user_ids.add(event["user"])
    all_user_ids.update(MENTION_REGEX.findall(event["text"]))

    user_names = await _fetch_user_names(all_user_ids)

    def format_message(msg: SlackMessageData) -> str:
        text = msg["text"]
        user_id = msg.get("user", "unknown")

        def repl(match: re.Match) -> str:
            uid = match.group(1)
            return user_names.get(uid, uid)

        replaced_text = MENTION_REGEX.sub(repl, text)
        speaker_name = user_names.get(user_id, user_id)

        return (
            f'<slackMessage user="{speaker_name}">' f"{replaced_text}" "</slackMessage>"
        )

    context_parts = [format_message(msg) for msg in reversed(included)]
    new_message = context_parts[-1]
    preceding_context = "\n".join(context_parts[:-1])

    contextual_message = (
        (("Preceding context:\n" + preceding_context) if preceding_context else "")
        + "\n\nNew message:\n"
        + new_message
    )
    return contextual_message


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("langgraph_slack.server:APP", host="0.0.0.0", port=8080)
