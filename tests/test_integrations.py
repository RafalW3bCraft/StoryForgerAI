import asyncio
import json
import sqlite3
from contextlib import closing
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


def test_sqlite_database_file_is_owner_only(tmp_path):
    import os
    import stat

    if os.name == "nt":
        pytest.skip("POSIX file permission bits are not supported on Windows")

    database = tmp_path / "private.db"
    engine = make_engine("sqlite+pysqlite:///" + str(database))
    try:
        assert stat.S_IMODE(database.stat().st_mode) == 0o600
    finally:
        engine.dispose()


def test_existing_database_migrates_generation_status_column(tmp_path):
    database = tmp_path / "legacy.db"
    with closing(sqlite3.connect(database)) as connection, connection:
        connection.execute(
            "CREATE TABLE story_sessions ("
            "id INTEGER PRIMARY KEY, world_id INTEGER NOT NULL, stage VARCHAR(24) NOT NULL, "
            "current_node_id INTEGER, active_round_id INTEGER, active_proposal_id INTEGER, "
            "created_at DATETIME)"
        )
        connection.execute(
            "INSERT INTO story_sessions (id, world_id, stage) VALUES (1, 1, 'READY')"
        )

    engine = make_engine("sqlite+pysqlite:///" + str(database))
    with engine.connect() as connection:
        columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info('story_sessions')"))
        }
        status = connection.execute(
            text("SELECT generation_status FROM story_sessions WHERE id = 1")
        ).scalar_one()
    assert {"paused_from_stage", "generation_status"} <= columns
    assert status == "UNKNOWN"
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

    settings = Settings(
        mode="demo",
        database=str(tmp_path / "twitch.db"),
        secret="x" * 40,
        twitch_broadcaster_id="channel-1",
        twitch_reader_id="channel-1",
    )
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    service = StoryService(sessions)
    clock = [100.0]

    def tick():
        clock[0] += 1.0
        return clock[0]

    monkeypatch.setattr(service, "_clock", tick)
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
                    "broadcaster_user_id": "channel-1",
                    "message_id": "chat-1",
                    "chatter_user_id": "user-1",
                    "chatter_user_name": "Ada",
                    "message": {"text": "!join"},
                },
                "subscription": {"type": "channel.chat.message", "version": "1"},
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
                    "broadcaster_user_id": "channel-1",
                    "message_id": "chat-2",
                    "chatter_user_id": "user-1",
                    "chatter_user_name": "Ada",
                    "message": {"text": "!persona scholar"},
                },
                "subscription": {"type": "channel.chat.message", "version": "1"},
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
    assert connector.last_chat_outcome == "ACCEPTED"
    assert connector.chat_outcomes["ACCEPTED"] == 2
    engine.dispose()


def test_eventsub_chat_processing_does_not_block_event_loop_during_burst(monkeypatch, tmp_path):
    import time

    from storyforge import twitch

    settings = Settings(
        mode="demo",
        database=str(tmp_path / "chat-worker.db"),
        secret="x" * 40,
        twitch_broadcaster_id="channel-1",
        twitch_reader_id="channel-1",
    )
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    service = StoryService(sessions)

    processed_ids = []

    def slow_process_chat(message_id, *_args):
        time.sleep(0.002)
        processed_ids.append(message_id)
        return "JOINED"

    monkeypatch.setattr(service, "process_chat", slow_process_chat)
    connector = TwitchConnector(settings, sessions, service)
    messages = [
        json.dumps(
            {
                "metadata": {"message_type": "session_welcome"},
                "payload": {"session": {"id": "session-1", "keepalive_timeout_seconds": 30}},
            }
        )
    ]
    messages.extend(
        json.dumps(
            {
                "metadata": {"message_type": "session_notification"},
                "payload": {
                    "subscription": {"type": "channel.chat.message", "version": "1"},
                    "event": {
                        "broadcaster_user_id": "channel-1",
                        "message_id": f"chat-{index}",
                        "chatter_user_id": f"viewer-{index}",
                        "chatter_user_name": "Viewer",
                        "message": {"text": "!join"},
                    },
                },
            }
        )
        for index in range(50)
    )

    class FakeSocket:
        async def recv(self):
            message = messages.pop(0)
            if not messages:
                connector.stop()
            return message

        async def close(self):
            pass

    async def fake_connect(*_args, **_kwargs):
        return FakeSocket()

    async def no_op_subscribe(_token, _session_id):
        return None

    connector.subscribe = no_op_subscribe
    monkeypatch.setattr(twitch.websockets, "connect", fake_connect)

    async def run():
        consume_task = asyncio.create_task(connector.consume("fake-token"))
        heartbeat_task = asyncio.create_task(asyncio.sleep(0.01))
        done, _pending = await asyncio.wait(
            {consume_task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
        )
        consume_finished_first = consume_task in done
        await asyncio.gather(consume_task, heartbeat_task)
        return consume_finished_first

    assert asyncio.run(run()) is False
    assert connector.last_chat_outcome == "ACCEPTED"
    assert processed_ids == [f"chat-{index}" for index in range(50)]
    assert connector.chat_notifications_received == 50
    assert connector.chat_outcomes["ACCEPTED"] == 50
    engine.dispose()


def test_eventsub_malformed_chat_isolated_and_duplicate_receipt_counted(monkeypatch, tmp_path):
    from storyforge import twitch

    settings = Settings(
        mode="demo",
        database=str(tmp_path / "chat-boundary.db"),
        secret="x" * 40,
        twitch_broadcaster_id="channel-1",
        twitch_reader_id="channel-1",
    )
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    service = StoryService(sessions)
    connector = TwitchConnector(settings, sessions, service)

    def notification(message_id, message):
        return json.dumps(
            {
                "metadata": {"message_type": "session_notification"},
                "payload": {
                    "subscription": {"type": "channel.chat.message", "version": "1"},
                    "event": {
                        "broadcaster_user_id": "channel-1",
                        "message_id": message_id,
                        "chatter_user_id": "viewer-1",
                        "chatter_user_name": "Viewer",
                        "message": message,
                    },
                },
            }
        )

    messages = [
        json.dumps(
            {
                "metadata": {"message_type": "session_welcome"},
                "payload": {"session": {"id": "session-1", "keepalive_timeout_seconds": 30}},
            }
        ),
        notification("malformed-1", None),
        notification("chat-1", {"text": "!join"}),
        notification("chat-1", {"text": "!join"}),
    ]

    class FakeSocket:
        async def recv(self):
            message = messages.pop(0)
            if not messages:
                connector.stop()
            return message

        async def close(self):
            pass

    async def fake_connect(*_args, **_kwargs):
        return FakeSocket()

    async def no_op_subscribe(_token, _session_id):
        return None

    connector.subscribe = no_op_subscribe
    monkeypatch.setattr(twitch.websockets, "connect", fake_connect)
    asyncio.run(connector.consume("fake-token"))

    assert connector.chat_notifications_received == 3
    assert connector.chat_outcomes["IGNORED"] == 1
    assert connector.chat_outcomes["ACCEPTED"] == 1
    assert connector.chat_outcomes["DUPLICATE"] == 1
    assert service.persona("viewer-1") is not None
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


def test_eventsub_error_status_does_not_expose_exception_details(monkeypatch, tmp_path):
    from storyforge import twitch

    settings = Settings(
        mode="live",
        database=str(tmp_path / "error-redaction.db"),
        secret="x" * 40,
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
    )
    engine = make_engine(settings.db_url)
    connector = TwitchConnector(settings, factory(engine), StoryService(factory(engine)))
    sentinel = "private-token-in-error-detail"

    async def fail_token(_settings, _sessions):
        raise RuntimeError(sentinel)

    async def stop_after_error(_delay):
        connector.stop()

    monkeypatch.setattr(twitch, "get_host_token", fail_token)
    monkeypatch.setattr(twitch.asyncio, "sleep", stop_after_error)
    asyncio.run(connector.run_forever())

    assert connector.status == "ERROR"
    assert sentinel not in str(connector.last_error)
    engine.dispose()


def test_websocket_ignores_chat_without_exact_broadcaster_identity(monkeypatch, tmp_path):
    from storyforge import twitch

    settings = Settings(
        mode="demo",
        database=str(tmp_path / "broadcaster.db"),
        secret="x" * 40,
        twitch_broadcaster_id="broadcaster-1",
        twitch_reader_id="broadcaster-1",
    )
    engine = make_engine(settings.db_url)
    sessions = factory(engine)
    service = StoryService(sessions)
    connector = TwitchConnector(settings, sessions, service)

    def event(message_id, user_id, broadcaster_id=None):
        data = {
            "message_id": message_id,
            "chatter_user_id": user_id,
            "chatter_user_name": user_id,
            "message": {"text": "!join"},
        }
        if broadcaster_id is not None:
            data["broadcaster_user_id"] = broadcaster_id
        return json.dumps(
            {
                "metadata": {"message_type": "session_notification"},
                "payload": {
                    "subscription": {"type": "channel.chat.message", "version": "1"},
                    "event": data,
                },
            }
        )

    messages = [
        json.dumps(
            {
                "metadata": {"message_type": "session_welcome"},
                "payload": {"session": {"id": "session-1", "keepalive_timeout_seconds": 15}},
            }
        ),
        event("missing-broadcaster", "missing-id"),
        event("wrong-broadcaster", "wrong-id", "other-channel"),
        event("right-broadcaster", "valid-id", "broadcaster-1"),
    ]

    class FakeSocket:
        async def recv(self):
            message = messages.pop(0)
            if not messages:
                connector.stop()
            return message

        async def close(self):
            pass

    async def fake_connect(url, **kwargs):
        return FakeSocket()

    async def fake_subscribe(token, session_id):
        assert session_id == "session-1"

    monkeypatch.setattr(twitch.websockets, "connect", fake_connect)
    connector.subscribe = fake_subscribe
    asyncio.run(connector.consume("test-token"))

    assert service.persona("missing-id") is None
    assert service.persona("wrong-id") is None
    assert service.persona("valid-id") is not None
    engine.dispose()


def test_eventsub_subscription_response_must_confirm_enabled_chat_subscription(
    monkeypatch, tmp_path
):
    from storyforge import twitch

    settings = Settings(
        mode="live",
        database=str(tmp_path / "subscription.db"),
        secret="x" * 40,
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
    )
    engine = make_engine(settings.db_url)
    connector = TwitchConnector(settings, factory(engine), StoryService(factory(engine)))

    class Response:
        status_code = 202

        def __init__(self, body):
            self.body = body

        def raise_for_status(self):
            pass

        def json(self):
            return self.body

    class Client:
        body: ClassVar[dict] = {
            "data": [
                {
                    "status": "enabled",
                    "type": "channel.chat.message",
                    "version": "1",
                    "condition": {"broadcaster_user_id": "111", "user_id": "111"},
                    "transport": {"method": "websocket", "session_id": "session-1"},
                }
            ]
        }

        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json, headers):
            assert url == twitch.HELIX + "/eventsub/subscriptions"
            assert json["type"] == "channel.chat.message"
            return Response(self.body)

    monkeypatch.setattr(twitch.httpx, "AsyncClient", Client)
    asyncio.run(connector.subscribe("test-token", "session-1"))

    Client.body = {"data": [{"status": "websocket_disconnected"}]}
    with pytest.raises(RuntimeError, match="subscription confirmation"):
        asyncio.run(connector.subscribe("test-token", "session-1"))
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
            assert "chat_template_kwargs" not in json
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


def test_featherless_qwen_disables_thinking_for_final_narrative(monkeypatch):
    from storyforge import ai

    settings = Settings(
        mode="live",
        ai_base_url="https://api.featherless.ai/v1",
        ai_api_key="fake",
        ai_model="Qwen/Qwen3.8-27B",
    )
    sent_payload = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            proposal = {
                "title": "The Atlas Opens",
                "narrative": "The sealed atlas opens and paints a silver road across the library floor.",
                "choices": ["Follow the silver road", "Ask the librarian for help"],
            }
            return {"choices": [{"message": {"content": json.dumps(proposal)}}]}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json, headers):
            sent_payload.update(json)
            return Response()

    monkeypatch.setattr(ai.httpx, "AsyncClient", Client)
    asyncio.run(
        OpenAICompatibleGenerator(settings).generate(
            world="A library of memories",
            history="",
            decision="open the atlas",
            personas=["Aster (scholar)"],
            contributions=[],
        )
    )

    assert sent_payload["chat_template_kwargs"] == {"enable_thinking": False}
    system_prompt = sent_payload["messages"][0]["content"]
    assert '"choices": ["option one", "option two"]' in system_prompt
    assert "plain string, never an object" in system_prompt


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
    with pytest.raises(ValueError, match="omitted choices"):
        asyncio.run(
            generator.generate(
                world="An original world",
                history="",
                decision="open gate",
                personas=[],
                contributions=[],
            )
        )
    FakeClient.body = {"choices": [{"message": {}}]}
    with pytest.raises(ValueError, match="omitted assistant content"):
        asyncio.run(
            generator.generate(
                world="An original world",
                history="",
                decision="open gate",
                personas=[],
                contributions=[],
            )
        )
    FakeClient.body = {"choices": [{"message": {"content": ""}}]}
    with pytest.raises(ValueError, match="empty narrative text"):
        asyncio.run(
            generator.generate(
                world="An original world",
                history="",
                decision="open gate",
                personas=[],
                contributions=[],
            )
        )
    FakeClient.body = {"choices": [{"message": {"content": [{"image": "private"}]}}]}
    with pytest.raises(ValueError, match="content blocks without text"):
        asyncio.run(
            generator.generate(
                world="An original world",
                history="",
                decision="open gate",
                personas=[],
                contributions=[],
            )
        )


def test_ai_provider_rejects_truncated_structured_completion(monkeypatch):
    from storyforge import ai

    settings = Settings(
        mode="demo",
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake",
        ai_model="test-model",
    )

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "A Truncated Scene",
                                    "narrative": "A response may look valid while the provider says it was cut short.",
                                    "choices": ["Open the old door", "Leave the atlas behind"],
                                }
                            )
                        },
                    }
                ]
            }

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, json, headers):
            return Response()

    monkeypatch.setattr(ai.httpx, "AsyncClient", Client)
    with pytest.raises(ValueError, match="truncated"):
        asyncio.run(
            OpenAICompatibleGenerator(settings).generate(
                world="A short premise.",
                history="",
                decision="open the door",
                personas=[],
                contributions=[],
            )
        )


def test_ai_provider_rejects_unsafe_or_duplicated_base_url():
    settings = Settings(
        mode="live",
        ai_base_url="https://user:password@provider.test/v1/chat/completions",
        ai_api_key="fake",
        ai_model="test-model",
    )
    with pytest.raises(ValueError, match="AI_BASE_URL"):
        OpenAICompatibleGenerator(settings)
