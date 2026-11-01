import asyncio
import json
from typing import ClassVar

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from storyforge.ai import OpenAICompatibleGenerator
from storyforge.config import Settings
from storyforge.db import factory, make_engine
from storyforge.service import StoryService
from storyforge.twitch import TwitchConnector, get_host_token, save_host_token


def test_encrypted_host_token_roundtrip(tmp_path):
    key = Fernet.generate_key().decode()
    settings = Settings(
        mode="demo", database=str(tmp_path / "vault.db"), secret="x" * 40, token_key=key
    )
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    save_host_token(
        settings,
        sessions,
        {"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_in": 3600},
    )
    with sessions() as db:
        from storyforge.models import TokenVault

        stored = db.get(TokenVault, "host").encrypted_json
        assert "access-secret" not in stored
        assert "refresh-secret" not in stored
    assert asyncio.run(get_host_token(settings, sessions)) == "access-secret"
    engine.dispose()


def test_database_enforces_one_open_round_index(tmp_path):
    engine = make_engine("sqlite+pysqlite:///" + str(tmp_path / "index.db"))
    with engine.connect() as connection:
        indexes = {row[1] for row in connection.execute(text("PRAGMA index_list('voting_rounds')"))}
    assert "uq_open_voting_round_per_session" in indexes
    engine.dispose()


def test_expired_host_token_refresh_is_encrypted_and_replaced(monkeypatch, tmp_path):
    from storyforge import twitch

    key = Fernet.generate_key().decode()
    settings = Settings(
        mode="live",
        database=str(tmp_path / "refresh.db"),
        secret="x" * 40,
        token_key=key,
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
    )
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    save_host_token(
        settings,
        sessions,
        {"access_token": "old-access", "refresh_token": "old-refresh", "expires_in": 0},
    )

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "access_token": "fresh-access",
                "refresh_token": "fresh-refresh",
                "expires_in": 3600,
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            assert url == twitch.OAUTH + "/token"
            assert data["grant_type"] == "refresh_token"
            assert data["refresh_token"] == "old-refresh"
            return Response()

    monkeypatch.setattr(twitch.httpx, "AsyncClient", Client)
    assert asyncio.run(twitch.get_host_token(settings, sessions)) == "fresh-access"
    assert asyncio.run(twitch.get_host_token(settings, sessions)) == "fresh-access"
    engine.dispose()


def test_oauth_helpers_use_exact_callback_and_authenticated_user(monkeypatch, tmp_path):
    from storyforge import twitch

    settings = Settings(
        mode="live",
        database=str(tmp_path / "oauth.db"),
        secret="x" * 40,
        token_key=Fernet.generate_key().decode(),
        base_url="https://storyforge.example",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
    )

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, data):
            assert data["redirect_uri"] == "https://storyforge.example/auth/callback"
            return Response()

        async def get(self, url, headers):
            assert headers["Authorization"] == "Bearer access"
            return type(
                "UserResponse",
                (),
                {
                    "raise_for_status": lambda self: None,
                    "json": lambda self: {"data": [{"id": "111", "display_name": "Host"}]},
                },
            )()

    monkeypatch.setattr(twitch.httpx, "AsyncClient", Client)
    token = asyncio.run(twitch.exchange_code(settings, "one-time-code"))
    assert token["access_token"] == "access"
    user = asyncio.run(twitch.user_for_token(settings, "access"))
    assert user["id"] == "111"


def test_websocket_mock_reconnect_preserves_subscription(monkeypatch, tmp_path):
    from storyforge import twitch

    settings = Settings(mode="demo", database=str(tmp_path / "twitch.db"), secret="x" * 40)
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    service = StoryService(sessions)
    connector = TwitchConnector(settings, sessions, service)
    subscription_ids = []

    async def fake_subscribe(token, sid):
        subscription_ids.append((token, sid))

    connector.subscribe = fake_subscribe

    def msg(kind, payload):
        return json.dumps(
            {
                "metadata": {"message_type": kind, "message_id": f"envelope-{kind}"},
                "payload": payload,
            }
        )

    old = [
        msg("session_welcome", {"session": {"id": "old-1", "keepalive_timeout_seconds": 15}}),
        msg(
            "session_notification",
            {
                "event": {
                    "message_id": "chat-1",
                    "chatter_user_id": "user-1",
                    "chatter_user_name": "Ada",
                    "message": {"text": "!join"},
                }
            },
        ),
        msg(
            "session_reconnect",
            {"session": {"reconnect_url": "wss://eventsub.wss.twitch.tv/ws?ticket=abc"}},
        ),
    ]
    new = [
        msg("session_welcome", {"session": {"id": "new-2", "keepalive_timeout_seconds": 15}}),
        msg(
            "session_notification",
            {
                "event": {
                    "message_id": "chat-2",
                    "chatter_user_id": "user-1",
                    "chatter_user_name": "Ada",
                    "message": {"text": "!persona scholar"},
                }
            },
        ),
    ]
    connections = []

    class FakeSocket:
        def __init__(self, events, signal=False):
            self.events = iter(events)
            self.closed = False
            self.signal = signal

        async def recv(self):
            value = next(self.events)
            if self.signal and "chat-2" in value:
                connector.stop()
            return value

        async def close(self):
            self.closed = True

    async def fake_connect(url, **kwargs):
        assert url.startswith("wss://eventsub.wss.twitch.tv/ws")
        ws = FakeSocket(old if not connections else new, signal=bool(connections))
        connections.append(ws)
        return ws

    monkeypatch.setattr(twitch.websockets, "connect", fake_connect)
    asyncio.run(connector.consume("fake-token"))
    assert subscription_ids == [("fake-token", "old-1")]
    assert len(connections) == 2
    assert connections[0].closed and connections[1].closed
    assert connector.status == "LIVE_TWITCH"
    assert service.persona("user-1").archetype == "scholar"
    engine.dispose()


def test_websocket_revocation_is_terminal(monkeypatch, tmp_path):
    from storyforge import twitch

    settings = Settings(mode="demo", database=str(tmp_path / "revoked.db"), secret="x" * 40)
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    connector = TwitchConnector(settings, sessions, StoryService(sessions))

    raw = json.dumps(
        {
            "metadata": {"message_type": "revocation", "message_id": "revoked-1"},
            "payload": {"subscription": {"status": "authorization_revoked"}},
        }
    )

    class FakeSocket:
        closed = False

        async def recv(self):
            return raw

        async def close(self):
            self.closed = True

    socket = FakeSocket()

    async def fake_connect(url, **kwargs):
        return socket

    monkeypatch.setattr(twitch.websockets, "connect", fake_connect)
    with pytest.raises(twitch.EventSubRevoked):
        asyncio.run(connector.consume("fake-token"))
    assert connector.status == "REVOKED"
    assert socket.closed
    engine.dispose()


def test_ai_provider_validated_structured_mock(monkeypatch):
    from storyforge import ai

    settings = Settings(
        mode="demo",
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake",
        ai_model="test-model",
    )

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            result = {
                "title": "A Different World",
                "narrative": "The library lights fall on a doorway that was never there before.",
                "choices": ["Open the luminous doorway", "Return to the shadowed archives"],
            }
            return {"choices": [{"message": {"content": json.dumps(result)}}]}

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json, headers):
            assert url == "https://provider.test/v1/chat/completions"
            assert json["model"] == "test-model"
            return FakeResponse()

    monkeypatch.setattr(ai.httpx, "AsyncClient", FakeClient)
    generated = asyncio.run(
        OpenAICompatibleGenerator(settings).generate(
            world="An original world",
            history="",
            decision="open gate",
            personas=["Ada (scholar)"],
            contributions=[],
        )
    )
    assert len(generated.choices) == 2


def test_ai_provider_rejects_malformed_or_empty_content(monkeypatch):
    from storyforge import ai

    settings = Settings(
        mode="demo",
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake",
        ai_model="test-model",
    )

    class FakeResponse:
        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    class FakeClient:
        body: ClassVar[dict] = {"choices": [{"message": {"content": "not json"}}]}

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json, headers):
            return FakeResponse(self.body)

    monkeypatch.setattr(ai.httpx, "AsyncClient", FakeClient)
    generator = OpenAICompatibleGenerator(settings)
    with pytest.raises(ValueError, match="invalid narrative JSON"):
        asyncio.run(
            generator.generate(
                world="An original world",
                history="",
                decision="open gate",
                personas=[],
                contributions=[],
            )
        )
    FakeClient.body = {"choices": []}
    with pytest.raises(ValueError, match="no narrative content"):
        asyncio.run(
            generator.generate(
                world="An original world",
                history="",
                decision="open gate",
                personas=[],
                contributions=[],
            )
        )
