"""Authenticated Twitch OAuth and EventSub WebSocket adapter (no fixture masquerading)."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode, urlparse

import httpx
import websockets
from cryptography.fernet import Fernet
from sqlalchemy.orm import sessionmaker

from .config import Settings
from .models import TokenVault
from .service import StoryService

HELIX = "https://api.twitch.tv/helix"
OAUTH = "https://id.twitch.tv/oauth2"
EVENTSUB_WS = "wss://eventsub.wss.twitch.tv/ws"


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
        "scope": "user:read:chat" if role == "host" else "",
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
        self._stop = asyncio.Event()

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
                kind = msg.get("metadata", {}).get("message_type")
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
                elif kind == "session_notification":
                    notification = msg.get("payload", {})
                    subscription = notification.get("subscription", {})
                    event = notification.get("event", {})
                    if (
                        subscription.get("type") != "channel.chat.message"
                        or str(subscription.get("version")) != "1"
                        or event.get("broadcaster_user_id") != self.settings.twitch_broadcaster_id
                    ):
                        continue
                    content = event.get("message", {}).get("text", "")
                    msg_id = event.get("message_id") or msg.get("metadata", {}).get("message_id")
                    if msg_id and event.get("chatter_user_id"):
                        self.service.process_chat(
                            str(msg_id),
                            str(event["chatter_user_id"]),
                            str(event.get("chatter_user_name") or "Viewer"),
                            content,
                        )
                        self.last_event = datetime.now(UTC).isoformat()
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
        while not self._stop.is_set():
            try:
                token = await get_host_token(self.settings, self.sessions)
                if not token:
                    self.status = "NEEDS_AUTH"
                    await asyncio.sleep(4)
                    continue
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

    def stop(self) -> None:
        self._stop.set()
