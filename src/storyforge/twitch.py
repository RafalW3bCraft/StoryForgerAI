"""Authenticated Twitch OAuth and EventSub WebSocket adapter (no fixture masquerading)."""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx
import websockets
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .models import TokenVault
from .service import StoryService

HELIX = "https://api.twitch.tv/helix"
OAUTH = "https://id.twitch.tv/oauth2"
EVENTSUB_WS = "wss://eventsub.wss.twitch.tv/ws"
LOGGER = logging.getLogger(__name__)
CHAT_WRITE_SCOPE = "user:write:chat"
CHAT_REPLY_INTERVAL_SECONDS = 1.0
CHAT_REPLY_QUEUE_SIZE = 32


def reply_for_chat_outcome(result: str) -> str | None:
    """Return a fixed, non-echoing acknowledgement for useful chat outcomes."""
    replies = {
        "JOINED": "You joined StoryForge. Check the overlay for your character.",
        "UPDATED": "Persona updated. Check the overlay.",
        "VOTED": "Vote recorded. Check the overlay for the tally.",
        "QUEUED": "Contribution sent to the host for review.",
        "LEFT": "Your persona was removed.",
        "NOT_JOINED": "Join first with !join.",
        "NO_STORY": "There is no active story round. Check the overlay.",
        "PROFILE": "Try !persona <archetype>, !trait <trait>, or !avatar random.",
        "INVALID": "That command or choice is invalid. Try !help.",
        "HELP": (
            "Commands: !join, !persona <archetype>, !trait <trait>, !avatar random, "
            "!vote A/B, !line <idea>, !twist <idea>, !act <idea>."
        ),
        "INFO": "Check the StoryForge overlay for your persona and the current story.",
    }
    return replies.get(result)


class EventSubRevoked(RuntimeError):
    """The server revoked the subscription; reconnecting would be misleading."""


def login_url(settings: Settings, *, role: str, state: str) -> str:
    if role not in {"host", "viewer"}:
        raise ValueError("Invalid OAuth role")
    if not settings.twitch_client_id:
        raise ValueError("Twitch client ID not configured")
    params = {
        "client_id": settings.twitch_client_id,
        "redirect_uri": settings.base_url + "/auth/callback",
        "response_type": "code",
        "state": state,
        "scope": "user:read:chat user:write:chat" if role == "host" else "",
    }
    return OAUTH + "/authorize?" + urlencode(params)


async def exchange_code(settings: Settings, code: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as client:
        r = await client.post(
            OAUTH + "/token",
            data={
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.base_url + "/auth/callback",
            },
        )
        r.raise_for_status()
        return r.json()


async def user_for_token(settings: Settings, access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(
            HELIX + "/users",
            headers={
                "Authorization": "Bearer " + access_token,
                "Client-Id": settings.twitch_client_id,
            },
        )
        response.raise_for_status()
        users = response.json().get("data", [])
        if not users:
            raise ValueError("Twitch returned no user")
        return users[0]


def save_host_token(settings: Settings, sessions: sessionmaker, token: dict) -> None:
    if not settings.token_key:
        raise ValueError("TOKEN_ENCRYPTION_KEY is required")
    packed = {
        "access_token": token["access_token"],
        "refresh_token": token["refresh_token"],
        "scope": _token_scopes(token),
        "expires_at": (
            datetime.now(UTC) + timedelta(seconds=token.get("expires_in", 0))
        ).isoformat(),
    }
    encrypted = Fernet(settings.token_key.encode()).encrypt(json.dumps(packed).encode()).decode()
    with sessions.begin() as db:
        current = db.get(TokenVault, "host")
        if current:
            current.encrypted_json = encrypted
        else:
            db.add(TokenVault(key="host", encrypted_json=encrypted))


def _token_scopes(token: dict) -> list[str]:
    if not isinstance(token, dict):
        return []
    raw_scopes = token.get("scope", [])
    if isinstance(raw_scopes, str):
        raw_scopes = raw_scopes.split()
    if not isinstance(raw_scopes, list):
        return []
    return [scope for scope in raw_scopes if isinstance(scope, str)]


def token_has_chat_write_scope(token: dict) -> bool:
    return CHAT_WRITE_SCOPE in _token_scopes(token)


def host_has_chat_write_scope(settings: Settings, sessions: sessionmaker) -> bool:
    """Read granted scopes from the encrypted vault; old scope-less tokens need login."""
    if not settings.token_key:
        return False
    try:
        with sessions() as db:
            found = db.get(TokenVault, "host")
            if not found:
                return False
            packed = json.loads(
                Fernet(settings.token_key.encode()).decrypt(found.encrypted_json.encode())
            )
    except (InvalidToken, ValueError, TypeError, KeyError):
        return False
    return token_has_chat_write_scope(packed)


async def get_host_token(settings: Settings, sessions: sessionmaker) -> str | None:
    if not settings.token_key:
        return None
    with sessions() as db:
        found = db.get(TokenVault, "host")
        if not found:
            return None
        packed = json.loads(
            Fernet(settings.token_key.encode()).decrypt(found.encrypted_json.encode())
        )
    expires = datetime.fromisoformat(packed["expires_at"])
    if expires > datetime.now(UTC) + timedelta(minutes=3):
        return packed["access_token"]
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.post(
            OAUTH + "/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": packed["refresh_token"],
                "client_id": settings.twitch_client_id,
                "client_secret": settings.twitch_client_secret,
            },
        )
        response.raise_for_status()
        fresh = response.json()
    save_host_token(settings, sessions, fresh)
    return fresh["access_token"]


class TwitchConnector:
    def __init__(self, settings: Settings, sessions: sessionmaker, service: StoryService):
        self.settings, self.sessions, self.service = settings, sessions, service
        self.status = "NOT_CONFIGURED" if settings.mode == "demo" else "NEEDS_AUTH"
        self.last_event: str | None = None
        self.last_error: str | None = None
        self.chat_notifications_received = 0
        self.chat_outcomes: Counter[str] = Counter()
        self.last_chat_outcome = "NOT_SEEN"
        self.chat_reply_status = "DISABLED" if settings.mode != "live" else "NEEDS_AUTH"
        self.chat_replies_queued = 0
        self.chat_replies_sent = 0
        self.chat_replies_failed = 0
        self.chat_replies_dropped = 0
        self.chat_replies_skipped = 0
        self._reply_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(
            maxsize=CHAT_REPLY_QUEUE_SIZE
        )
        self._stop = asyncio.Event()

    def _record_chat_outcome(self, result: str) -> None:
        if result in {"JOINED", "UPDATED", "VOTED", "QUEUED", "LEFT"}:
            outcome = "ACCEPTED"
        elif result == "DUPLICATE":
            outcome = "DUPLICATE"
        elif result == "COOLDOWN":
            outcome = "COOLDOWN"
        elif result in {"INVALID", "NOT_JOINED", "NO_STORY", "PROFILE"}:
            outcome = "INVALID"
        elif result in {"IGNORED", "UNKNOWN", "HELP", "INFO"}:
            outcome = "IGNORED"
        else:
            outcome = "REJECTED"
        self.last_chat_outcome = outcome
        self.chat_outcomes[outcome] += 1

    def chat_health(self) -> dict[str, int | str]:
        """Return aggregate outcomes only; never expose chat text or Twitch identities."""
        return {
            "chat_notifications_received": self.chat_notifications_received,
            "last_chat_command_outcome": self.last_chat_outcome,
            "chat_commands_accepted": self.chat_outcomes["ACCEPTED"],
            "chat_commands_ignored": self.chat_outcomes["IGNORED"],
            "chat_commands_cooldown": self.chat_outcomes["COOLDOWN"],
            "chat_commands_invalid": self.chat_outcomes["INVALID"],
            "chat_commands_duplicate": self.chat_outcomes["DUPLICATE"],
            "chat_processing_errors": self.chat_outcomes["PROCESSING_ERROR"],
            "chat_reply_status": self.chat_reply_status,
            "chat_replies_queued": self.chat_replies_queued,
            "chat_replies_sent": self.chat_replies_sent,
            "chat_replies_failed": self.chat_replies_failed,
            "chat_replies_dropped": self.chat_replies_dropped,
            "chat_replies_skipped": self.chat_replies_skipped,
        }

    def _queue_chat_reply(self, message_id: str, result: str) -> None:
        reply = reply_for_chat_outcome(result)
        if not reply or self.settings.mode != "live":
            return
        if self.chat_reply_status != "READY":
            self.chat_replies_skipped += 1
            return
        try:
            self._reply_queue.put_nowait((message_id, reply))
        except asyncio.QueueFull:
            self.chat_replies_dropped += 1
            LOGGER.warning("Twitch chat reply queue full; one acknowledgement was dropped")
        else:
            self.chat_replies_queued += 1

    async def send_chat_message(self, token: str, parent_id: str, message: str) -> bool:
        """Send one bounded acknowledgement as a threaded reply through Twitch Helix."""
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.post(
                HELIX + "/chat/messages",
                json={
                    "broadcaster_id": self.settings.twitch_broadcaster_id,
                    "sender_id": self.settings.twitch_reader_id,
                    "message": message,
                    "reply_parent_message_id": parent_id,
                },
                headers={
                    "Client-Id": self.settings.twitch_client_id,
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                },
            )
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 401:
                    self.chat_reply_status = "REAUTH_REQUIRED"
                elif exc.response.status_code == 403:
                    self.chat_reply_status = "SEND_FORBIDDEN"
                else:
                    self.chat_reply_status = "SEND_ERROR"
                raise
            try:
                data = response.json().get("data", [])
                sent = bool(data and isinstance(data[0], dict) and data[0].get("is_sent") is True)
            except (AttributeError, IndexError, KeyError, TypeError, ValueError):
                sent = False
        self.chat_reply_status = "READY" if sent else "SEND_REJECTED"
        return sent

    async def _reply_worker(self) -> None:
        last_attempt = 0.0
        while not self._stop.is_set():
            try:
                parent_id, message = await asyncio.wait_for(self._reply_queue.get(), timeout=0.5)
            except TimeoutError:
                continue
            try:
                if self.chat_reply_status != "READY":
                    self.chat_replies_failed += 1
                    continue
                loop = asyncio.get_running_loop()
                wait = CHAT_REPLY_INTERVAL_SECONDS - (loop.time() - last_attempt)
                if wait > 0:
                    await asyncio.sleep(wait)
                token = await get_host_token(self.settings, self.sessions)
                if not token:
                    self.chat_reply_status = "NEEDS_AUTH"
                    self.chat_replies_failed += 1
                    continue
                if not host_has_chat_write_scope(self.settings, self.sessions):
                    self.chat_reply_status = "REAUTH_REQUIRED"
                    self.chat_replies_failed += 1
                    continue
                last_attempt = loop.time()
                if await self.send_chat_message(token, parent_id, message):
                    self.chat_replies_sent += 1
                else:
                    self.chat_replies_failed += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - no API details in logs or health
                self.chat_replies_failed += 1
                LOGGER.warning("Twitch chat reply failed (%s)", type(exc).__name__)
            finally:
                self._reply_queue.task_done()

    async def subscribe(self, token: str, session_id: str) -> None:
        request = {
            "type": "channel.chat.message",
            "version": "1",
            "condition": {
                "broadcaster_user_id": self.settings.twitch_broadcaster_id,
                "user_id": self.settings.twitch_reader_id,
            },
            "transport": {"method": "websocket", "session_id": session_id},
        }
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.post(
                HELIX + "/eventsub/subscriptions",
                json=request,
                headers={
                    "Client-Id": self.settings.twitch_client_id,
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            if resp.status_code != 202:
                raise RuntimeError("Twitch did not return subscription confirmation")
            try:
                subscriptions = resp.json().get("data", [])
                subscription = subscriptions[0]
                transport = subscription["transport"]
                condition = subscription["condition"]
            except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
                raise RuntimeError("Twitch returned an invalid subscription confirmation") from exc
            if (
                subscription.get("status") != "enabled"
                or subscription.get("type") != "channel.chat.message"
                or str(subscription.get("version")) != "1"
                or condition.get("broadcaster_user_id") != self.settings.twitch_broadcaster_id
                or condition.get("user_id") != self.settings.twitch_reader_id
                or transport.get("method") != "websocket"
                or transport.get("session_id") != session_id
            ):
                raise RuntimeError("Twitch returned an invalid subscription confirmation")

    async def consume(self, token: str) -> None:
        """Read EventSub, preserving the old session until a reconnect welcome."""
        ws = await websockets.connect(EVENTSUB_WS, ping_interval=None, open_timeout=10)
        self.status = "CONNECTING"
        try:
            need_subscription = True
            keepalive = 30
            while not self._stop.is_set():
                raw = await asyncio.wait_for(ws.recv(), timeout=keepalive + 12)
                msg = json.loads(raw)
                if not isinstance(msg, dict):
                    continue
                metadata = msg.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                kind = metadata.get("message_type")
                if kind == "session_welcome":
                    session = msg["payload"]["session"]
                    keepalive = max(
                        10, min(int(session.get("keepalive_timeout_seconds") or 30), 600)
                    )
                    if need_subscription:
                        # Initial subscription must be created within Twitch's welcome window.
                        await self.subscribe(token, session["id"])
                    need_subscription = False
                    self.status = "LIVE_TWITCH"
                elif kind == "notification":
                    notification = msg.get("payload")
                    if not isinstance(notification, dict):
                        continue
                    subscription = notification.get("subscription")
                    event = notification.get("event")
                    if (
                        not isinstance(subscription, dict)
                        or not isinstance(event, dict)
                        or subscription.get("type") != "channel.chat.message"
                        or str(subscription.get("version")) != "1"
                        or event.get("broadcaster_user_id") != self.settings.twitch_broadcaster_id
                    ):
                        continue
                    message = event.get("message")
                    content = message.get("text", "") if isinstance(message, dict) else ""
                    msg_id = event.get("message_id") or metadata.get("message_id")
                    if msg_id and event.get("chatter_user_id"):
                        self.chat_notifications_received += 1
                        self.last_event = datetime.now(UTC).isoformat()
                        try:
                            result = await asyncio.to_thread(
                                self.service.process_chat,
                                str(msg_id),
                                str(event["chatter_user_id"]),
                                str(event.get("chatter_user_name") or "Viewer"),
                                content,
                            )
                        except Exception as exc:  # noqa: BLE001 - surface only safe aggregate telemetry
                            self.last_chat_outcome = "PROCESSING_ERROR"
                            self.chat_outcomes["PROCESSING_ERROR"] += 1
                            LOGGER.warning(
                                "EventSub chat processing failed (%s)", type(exc).__name__
                            )
                        else:
                            self._record_chat_outcome(result)
                            self._queue_chat_reply(str(msg_id), result)
                elif kind == "session_reconnect":
                    url = msg["payload"]["session"]["reconnect_url"]
                    parsed = urlparse(url)
                    if parsed.scheme != "wss" or parsed.hostname != "eventsub.wss.twitch.tv":
                        raise ValueError("Refusing untrusted EventSub reconnect URL")
                    replacement = await websockets.connect(url, ping_interval=None, open_timeout=10)
                    try:
                        first = json.loads(await asyncio.wait_for(replacement.recv(), timeout=12))
                        if first.get("metadata", {}).get("message_type") != "session_welcome":
                            raise RuntimeError("Reconnect did not return a welcome")
                        new_session = first["payload"]["session"]
                        keepalive = max(
                            10, min(int(new_session.get("keepalive_timeout_seconds") or 30), 600)
                        )
                    except BaseException:
                        await replacement.close()
                        raise
                    # Twitch keeps subscriptions on the new session; no POST required.
                    await ws.close()
                    ws = replacement
                    self.status = "LIVE_TWITCH"
                elif kind == "revocation":
                    self.status = "REVOKED"
                    subscription = msg.get("payload", {}).get("subscription", {})
                    reason = str(subscription.get("status", "revoked"))[:80]
                    raise EventSubRevoked("Twitch EventSub subscription revoked: " + reason)
                elif kind == "session_keepalive":
                    continue
        finally:
            await ws.close()

    async def run_forever(self) -> None:
        if self.settings.mode != "live":
            return
        delay = 2
        worker = asyncio.create_task(self._reply_worker())
        try:
            while not self._stop.is_set():
                try:
                    token = await get_host_token(self.settings, self.sessions)
                    if not token:
                        self.status = "NEEDS_AUTH"
                        self.chat_reply_status = "NEEDS_AUTH"
                        await asyncio.sleep(4)
                        continue
                    self.chat_reply_status = (
                        "READY"
                        if host_has_chat_write_scope(self.settings, self.sessions)
                        else "REAUTH_REQUIRED"
                    )
                    await self.consume(token)
                    delay = 2
                except asyncio.CancelledError:
                    raise
                except EventSubRevoked as exc:
                    self.status = "REVOKED"
                    self.last_error = str(exc)
                    await self._stop.wait()
                except Exception as exc:  # noqa: BLE001 - connector must recover transient failures
                    self.status = "ERROR"
                    # Exception messages from HTTP/WebSocket clients can contain
                    # request URIs or provider details. Keep browser diagnostics redacted.
                    self.last_error = type(exc).__name__
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 45)
        finally:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                pass

    def stop(self) -> None:
        self._stop.set()
