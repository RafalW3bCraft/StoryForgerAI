import asyncio
from contextlib import asynccontextmanager
from html.parser import HTMLParser

import httpx
import pytest

from storyforge.app import create_app


@asynccontextmanager
async def _client(app, base_url):
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=base_url) as client,
    ):
        yield client


async def _login(client, password="s3cure-demo-pass"):
    r = await client.get("/")
    parser = _CSRFParser()
    parser.feed(r.text)
    csrf = parser.token
    response = await client.post(
        "/auth/demo", data={"csrf_token": csrf, "password": password}, follow_redirects=False
    )
    return response, csrf


class _CSRFParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.token = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("name") == "csrf_token":
            self.token = attributes.get("value", "")


def _callback_endpoint(settings, session, request_origin=None):
    from urllib.parse import urlsplit

    from starlette.requests import Request

    app = create_app(settings)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/auth/callback")
    parsed = urlsplit(request_origin or settings.base_url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    host_header = parsed.hostname if port in {80, 443} else f"{parsed.hostname}:{port}"
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "server": (parsed.hostname, port),
        "client": ("127.0.0.1", 1234),
        "scheme": parsed.scheme,
        "method": "GET",
        "root_path": "",
        "path": "/auth/callback",
        "raw_path": b"/auth/callback",
        "query_string": b"",
        "headers": [(b"host", host_header.encode())],
        "session": session,
    }
    return route.endpoint, Request(scope), app


def test_twitch_oauth_login_redirects_a_different_browser_origin_to_configured_url(tmp_path):
    from cryptography.fernet import Fernet
    from starlette.requests import Request

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "oauth-origin.db"),
        secret="s" * 40,
        base_url="http://localhost:8000",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    app = create_app(settings)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/auth/twitch")
    endpoint = route.endpoint
    wrong_origin = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "method": "GET",
            "root_path": "",
            "path": "/auth/twitch",
            "raw_path": b"/auth/twitch",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8000")],
            "session": {},
        }
    )

    response = endpoint(wrong_origin, role="viewer")
    assert response.status_code == 307
    assert response.headers["location"] == "http://localhost:8000/auth/twitch?role=viewer"
    assert "detail" not in response.body.decode()
    assert wrong_origin.session == {}

    matching_origin = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "method": "GET",
            "root_path": "",
            "path": "/auth/twitch",
            "raw_path": b"/auth/twitch",
            "query_string": b"",
            "headers": [(b"host", b"localhost:8000")],
            "session": {},
        }
    )
    response = endpoint(matching_origin, role="viewer")
    assert response.status_code == 307
    assert matching_origin.session["oauth_state"]


def test_all_off_origin_requests_redirect_to_configured_app_url(tmp_path):
    from storyforge.app import ConfiguredOriginMiddleware
    from storyforge.config import Settings

    settings = Settings(
        database=str(tmp_path / "canonical-origin.db"),
        secret="s" * 40,
        base_url="http://localhost:8000",
    )
    app_instance = create_app(settings)
    configured_middleware = next(
        middleware
        for middleware in app_instance.user_middleware
        if middleware.cls is ConfiguredOriginMiddleware
    )
    assert app_instance.user_middleware[0] is configured_middleware

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "server": ("127.0.0.1", 8000),
        "client": ("127.0.0.1", 1234),
        "scheme": "http",
        "method": "GET",
        "root_path": "",
        "path": "/host",
        "raw_path": b"/host",
        "query_string": b"msg=continue",
        "headers": [(b"host", b"127.0.0.1:8000")],
    }
    called = []
    messages = []

    async def app(_scope, _receive, _send):
        called.append(True)
        raise AssertionError("off-origin requests should redirect before route handling")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    middleware = ConfiguredOriginMiddleware(app, base_url=settings.base_url)
    asyncio.run(middleware(scope, receive, send))
    response_headers = dict(messages[0]["headers"])

    assert messages[0]["status"] == 307
    assert response_headers[b"location"] == b"http://localhost:8000/host?msg=continue"
    assert b"detail" not in b"".join(message.get("body", b"") for message in messages)
    assert not called


@pytest.mark.asyncio
async def test_host_authorization_and_csrf(settings):
    app = create_app(settings)
    async with _client(app, settings.base_url) as c:
        assert (await c.get("/")).status_code == 200
        assert (await c.get("/host")).status_code == 403
        response, _csrf = await _login(c, password="wrong")
        assert response.status_code == 303
        assert (await c.get("/host")).status_code == 403
        response, _csrf = await _login(c)
        assert response.status_code == 303
        assert (await c.get("/host")).status_code == 200
        invalid_story = await c.post(
            "/host/story",
            data={
                "csrf_token": "wrong",
                "title": "Test World",
                "premise": "An extremely memorable test world appears.",
            },
        )
        assert invalid_story.status_code == 403


@pytest.mark.asyncio
async def test_host_chat_inbox_is_private_escaped_and_not_exposed_by_health(settings):
    app = create_app(settings)
    app.state.connector.record_chat_message(
        "private-message-id", "<viewer>", "<script>alert('chat')</script> hello"
    )
    async with _client(app, settings.base_url) as client:
        assert (await client.get("/host/chat")).status_code == 403
        response, _csrf = await _login(client)
        assert response.status_code == 303

        inbox = await client.get("/host/chat")
        assert inbox.status_code == 200
        assert "Live Twitch Chat" in inbox.text
        assert '<meta http-equiv="refresh" content="3">' in inbox.text
        assert "&lt;viewer&gt;" in inbox.text
        assert "&lt;script&gt;alert(&#39;chat&#39;)&lt;/script&gt; hello" in inbox.text
        assert "<script>alert(" not in inbox.text

        overlay = await client.get("/overlay")
        assert overlay.status_code == 200
        assert "alert('chat')" not in overlay.text

        health = await client.get("/health")
        assert health.status_code == 200
        assert "alert('chat')" not in health.text
        assert "private-message-id" not in health.text


@pytest.mark.asyncio
async def test_ai_chat_control_requires_host_csrf_and_live_provider(settings):
    app = create_app(settings)
    async with _client(app, settings.base_url) as client:
        assert (
            await client.post("/host/chat-settings", data={"enabled": "true"})
        ).status_code == 403
        _response, csrf = await _login(client)
        host_page = await client.get("/host")
        assert "Enable automatic AI replies to ordinary chat" in host_page.text
        assert "disabled" in host_page.text

        response = await client.post(
            "/host/chat-settings",
            data={"csrf_token": csrf, "enabled": "true"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert "require a configured live AI provider" in response.text
        assert app.state.service.ai_chat_replies_enabled() is False

        response = await client.post(
            "/host/chat-settings", data={"csrf_token": csrf}, follow_redirects=True
        )
        assert response.status_code == 200
        assert "AI chat replies disabled" in response.text


def test_live_host_can_enable_ai_chat_replies_with_valid_csrf(tmp_path):
    from cryptography.fernet import Fernet
    from starlette.requests import Request

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "live-chat-setting.db"),
        secret="s" * 48,
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-provider-key",
        ai_model="test-model",
    )
    app = create_app(settings)
    route = next(
        route for route in app.routes if getattr(route, "path", None) == "/host/chat-settings"
    )
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "server": ("localhost", 8000),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "method": "POST",
            "root_path": "",
            "path": "/host/chat-settings",
            "raw_path": b"/host/chat-settings",
            "query_string": b"",
            "headers": [(b"host", b"localhost:8000")],
            "session": {"role": "host", "csrf": "valid-csrf"},
        }
    )

    response = route.endpoint(request, csrf_token="valid-csrf", enabled=True)

    assert response.status_code == 303
    assert app.state.service.ai_chat_replies_enabled() is True


@pytest.mark.asyncio
async def test_end_to_end_web_demo(settings):
    app = create_app(settings)
    async with _client(app, settings.base_url) as c:
        response, csrf = await _login(c)
        assert response.status_code == 303
        r = await c.post(
            "/host/story",
            data={
                "csrf_token": csrf,
                "title": "The Glass Archive",
                "premise": "A place where memories are stored in glass forever.",
                "tone": "mystery",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200
        assert "AWAITING APPROVAL" in r.text
        await c.post("/host/action", data={"csrf_token": csrf, "action": "approve"})
        r = await c.post(
            "/host/action", data={"csrf_token": csrf, "action": "start_vote"}, follow_redirects=True
        )
        assert "VOTING" in r.text
        tick = iter(range(100, 1000))
        app.state.service._clock = lambda: float(next(tick))
        for viewer, command in [
            ("Luna", "!join"),
            ("Luna", "!persona scholar"),
            ("Luna", "!vote B"),
            ("Sol", "!join"),
            ("Sol", "!vote B"),
            ("Sol", "!line I found a map"),
        ]:
            r = await c.post(
                "/host/simulate",
                data={"csrf_token": csrf, "viewer": viewer, "command": command},
                follow_redirects=True,
            )
            assert r.status_code == 200
        snap = app.state.service.snapshot()
        assert snap["round"]["votes"]["B"] == 2
        assert len(snap["personas"]) >= 3
        assert any(x.status == "PENDING" for x in snap["contributions"])
        await c.post("/host/action", data={"csrf_token": csrf, "action": "close_vote"})
        r = await c.post(
            "/host/action", data={"csrf_token": csrf, "action": "approve"}, follow_redirects=True
        )
        assert r.status_code == 200
        assert len(app.state.service.snapshot()["nodes"]) == 2
        assert (await c.get("/overlay")).status_code == 200
        assert "SYNTHETIC DEMO" in (await c.get("/overlay")).text
        assert (await c.get("/graph.svg")).status_code == 200
        p = app.state.service.list_personas()[0]
        assert "<svg" in (await c.get(f"/avatar/{p.id}.svg")).text


@pytest.mark.asyncio
async def test_public_routes_do_not_expose_host_mutations(settings):
    app = create_app(settings)
    async with _client(app, settings.base_url) as c:
        assert (await c.get("/profile")).status_code == 403
        assert (await c.get("/host")).status_code == 403
        assert (
            await c.post("/host/action", data={"action": "finish", "csrf_token": "bad"})
        ).status_code == 403
        assert (
            await c.post("/profile/edit", data={"alias": "Intruder", "csrf_token": "bad"})
        ).status_code == 403
        invalid_simulation = await c.post(
            "/host/simulate",
            data={"viewer": "X", "command": "!join", "csrf_token": "bad"},
        )
        assert invalid_simulation.status_code == 403
        callback = await c.get("/auth/callback?code=bogus&state=bogus", follow_redirects=False)
        assert callback.status_code == 303
        assert callback.headers["location"].startswith(settings.base_url + "?")


def test_live_config_requires_credentials(tmp_path):

    from storyforge.config import Settings

    with pytest.raises(ValueError):
        create_app(
            Settings(
                mode="live",
                database=str(tmp_path / "bad.db"),
                secret="x" * 40,
                twitch_client_id="",
                twitch_client_secret="",
                twitch_broadcaster_id="",
                twitch_reader_id="",
                token_key="",
            )
        )


def test_live_oauth_configuration_rejects_missing_secrets(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    s = Settings(
        mode="live",
        database=str(tmp_path / "live.db"),
        secret="z" * 40,
        twitch_client_id="id",
        twitch_client_secret="secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    create_app(s)
    from storyforge.twitch import login_url

    url = login_url(s, role="host", state="state-abc")
    assert "user%3Aread%3Achat" in url
    assert "state-abc" in url
    with pytest.raises(ValueError):
        login_url(s, role="admin", state="bad")


def test_live_configuration_requires_single_account_reader(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "live.db"),
        secret="z" * 40,
        twitch_client_id="id",
        twitch_client_secret="secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="222",
        token_key=Fernet.generate_key().decode(),
    )
    with pytest.raises(ValueError, match="TWITCH_READER_ID"):
        settings.validate()


def test_live_configuration_rejects_public_http_oauth_callback(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "live.db"),
        secret="z" * 40,
        base_url="http://storyforge.example",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
    )
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        settings.validate()


def test_live_configuration_accepts_local_http_and_requires_numeric_twitch_ids(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "live.db"),
        secret="z" * 40,
        base_url="http://127.0.0.1:8000",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="not-a-numeric-id",
        twitch_reader_id="not-a-numeric-id",
        token_key=Fernet.generate_key().decode(),
    )
    with pytest.raises(ValueError, match="TWITCH_BROADCASTER_ID"):
        settings.validate()


def test_demo_mode_never_implicitly_enables_external_ai():
    from storyforge.config import Settings

    settings = Settings(
        mode="demo",
        ai_base_url="https://provider.test/v1",
        ai_api_key="configured-but-not-live",
        ai_model="test-model",
    )
    assert settings.ai_enabled is False


def test_live_mode_requires_configured_ai_provider(tmp_path):
    from cryptography.fernet import Fernet

    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "live-without-ai.db"),
        secret="s" * 48,
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
    )

    with pytest.raises(ValueError, match="AI_BASE_URL, AI_API_KEY and AI_MODEL"):
        settings.validate()


def test_settings_read_environment_for_each_new_instance(monkeypatch):
    from storyforge.config import Settings

    monkeypatch.setenv("STORYFORGE_MODE", "live")
    assert Settings().mode == "live"


def test_settings_repr_redacts_secret_fields():
    from storyforge.config import Settings

    secrets = (
        "session-secret-sentinel",
        "demo-password-sentinel",
        "twitch-client-secret-sentinel",
        "fernet-key-sentinel",
        "ai-api-key-sentinel",
    )
    settings = Settings(
        secret=secrets[0],
        demo_password=secrets[1],
        twitch_client_secret=secrets[2],
        token_key=secrets[3],
        ai_api_key=secrets[4],
    )

    representation = repr(settings)

    assert all(secret not in representation for secret in secrets)


def test_host_oauth_callback_success_binds_only_configured_broadcaster(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    from storyforge import app as app_module
    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "oauth-callback.db"),
        secret="s" * 40,
        base_url="https://storyforge.example",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    stored_tokens = []

    async def exchange(_settings, code):
        assert code == "one-time-code"
        return {
            "access_token": "access-test",
            "refresh_token": "refresh-test",
            "scope": ["user:read:chat", "user:write:chat"],
        }

    async def user_for_token(_settings, access_token):
        assert access_token == "access-test"
        return {"id": "111", "display_name": "ConfiguredHost"}

    monkeypatch.setattr(app_module, "exchange_code", exchange)
    monkeypatch.setattr(app_module, "user_for_token", user_for_token)
    monkeypatch.setattr(
        app_module,
        "save_host_token",
        lambda _settings, _sessions, token: stored_tokens.append(token),
    )
    endpoint, request, app = _callback_endpoint(
        settings, {"oauth_state": "state-1", "oauth_role": "host"}
    )

    response = asyncio.run(endpoint(request, code="one-time-code", state="state-1"))

    assert response.status_code == 303
    assert request.session["role"] == "host"
    assert request.session["twitch_user_id"] == "111"
    assert stored_tokens and app.state.service.persona("111").is_host
    assert app.state.connector.chat_reply_status == "READY"


def test_host_oauth_callback_rejects_state_mismatch_and_wrong_broadcaster(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    from storyforge import app as app_module
    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "oauth-reject.db"),
        secret="s" * 40,
        base_url="https://storyforge.example",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    calls = []

    async def exchange(_settings, code):
        calls.append(code)
        return {"access_token": "access-test", "refresh_token": "refresh-test"}

    async def other_user(_settings, access_token):
        return {"id": "222", "display_name": "OtherAccount"}

    monkeypatch.setattr(app_module, "exchange_code", exchange)
    monkeypatch.setattr(app_module, "user_for_token", other_user)
    endpoint, request, _app = _callback_endpoint(
        settings, {"oauth_state": "state-1", "oauth_role": "host"}
    )
    mismatch = asyncio.run(endpoint(request, code="never-exchanged", state="wrong-state"))
    assert mismatch.status_code == 303
    assert mismatch.headers["location"].startswith(settings.base_url + "?")
    assert "detail" not in mismatch.body.decode()
    assert request.session["oauth_state"] == "state-1"
    assert calls == []

    endpoint, request, _app = _callback_endpoint(settings, {})
    missing_session = asyncio.run(
        endpoint(request, code="one-time-code", state="state-without-cookie")
    )
    assert missing_session.status_code == 303
    assert missing_session.headers["location"].startswith(settings.base_url + "?")
    assert "detail" not in missing_session.body.decode()
    assert calls == []

    endpoint, request, _app = _callback_endpoint(
        settings,
        {"oauth_state": "state-redirect", "oauth_role": "host"},
        request_origin="http://127.0.0.1:8000",
    )
    redirect = asyncio.run(endpoint(request, code="one-time-code", state="state-redirect"))
    assert redirect.status_code == 307
    assert redirect.headers["location"] == (
        "https://storyforge.example/auth/callback?code=one-time-code&state=state-redirect"
    )
    assert calls == []

    endpoint, request, _app = _callback_endpoint(
        settings, {"oauth_state": "state-2", "oauth_role": "host"}
    )
    wrong_account = asyncio.run(endpoint(request, code="one-time-code", state="state-2"))
    assert wrong_account.status_code == 303
    assert wrong_account.headers["location"].startswith(settings.base_url + "?")
    assert "detail" not in wrong_account.body.decode()
    assert calls == ["one-time-code"]


def test_oauth_token_exchange_failure_shows_safe_http_status(monkeypatch, caplog, tmp_path):
    from urllib.parse import parse_qs, urlsplit

    import httpx
    from cryptography.fernet import Fernet

    from storyforge import app as app_module
    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "oauth-http-error.db"),
        secret="s" * 40,
        base_url="https://storyforge.example",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    request = httpx.Request("POST", "https://id.twitch.tv/oauth2/token")
    response = httpx.Response(400, request=request)

    async def rejected_exchange(_settings, _code):
        raise httpx.HTTPStatusError("sensitive response body", request=request, response=response)

    monkeypatch.setattr(app_module, "exchange_code", rejected_exchange)
    endpoint, request, _app = _callback_endpoint(
        settings,
        {"oauth_state": "state-1", "oauth_role": "host"},
    )

    result = asyncio.run(endpoint(request, code="private-one-time-code", state="state-1"))
    message = parse_qs(urlsplit(result.headers["location"]).query)["msg"][0]

    assert result.status_code == 303
    assert "Twitch token exchange failed (HTTP 400)" in message
    assert "registered callback URL" in message
    assert "private-one-time-code" not in message
    assert "sensitive response body" not in message
    assert "HTTP 400" in caplog.text
    assert "private-one-time-code" not in caplog.text
    assert "sensitive response body" not in caplog.text


def test_app_runner_disables_access_logs_and_prints_configured_url(monkeypatch, capsys, tmp_path):
    import sys
    from types import SimpleNamespace

    from cryptography.fernet import Fernet

    from storyforge import app as app_module
    from storyforge.config import Settings

    settings = Settings(
        mode="live",
        database=str(tmp_path / "runner.db"),
        secret="s" * 40,
        base_url="https://storyforge.example",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    calls = []
    fake_uvicorn = SimpleNamespace(run=lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    settings_to_load = [settings]
    monkeypatch.setattr(
        app_module,
        "Settings",
        SimpleNamespace(from_environment=lambda: settings_to_load[0]),
    )

    app_module.main()

    assert calls[0][1]["access_log"] is False
    startup = capsys.readouterr().out
    assert "Open StoryForge at https://storyforge.example" in startup
    assert "TLS reverse proxy" in startup

    http_settings = Settings(
        mode="live",
        database=str(tmp_path / "runner-http.db"),
        secret="s" * 40,
        base_url="http://127.0.0.1:8000",
        twitch_client_id="client-id",
        twitch_client_secret="client-secret",
        twitch_broadcaster_id="111",
        twitch_reader_id="111",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.test/v1",
        ai_api_key="fake-ai-key",
        ai_model="test-model",
    )
    settings_to_load[0] = http_settings
    app_module.main()
    startup = capsys.readouterr().out
    assert "Open StoryForge at http://127.0.0.1:8000" in startup
    assert "plain HTTP" in startup
    assert "do not switch to https" in startup


def test_host_template_shows_persisted_generation_failure_and_retry():
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    templates = Environment(
        loader=FileSystemLoader(Path(__file__).parents[1] / "src" / "storyforge" / "templates")
    )
    snap = {
        "story": {"title": "A Quiet Future", "stage": "GENERATING", "generation_status": "FAILED"},
        "proposal": None,
        "node": None,
        "round": None,
        "personas": [],
        "contributions": [],
        "nodes": [],
    }
    rendered = templates.get_template("host.html").render(
        snap=snap,
        csrf="test-csrf",
        demo=True,
        host=True,
        status="NOT_CONFIGURED",
        message="",
        error=None,
    )
    assert "FAILED" in rendered
    assert "Retry generation" in rendered
    assert "AI-GENERATED" not in rendered

    snap["story"]["stage"] = "REVIEW"
    snap["proposal"] = {
        "provenance": "AI",
        "title": "A Validated Scene",
        "narrative": "A validated provider response waits for host review before it becomes canon.",
        "choices": {"A": "Open the eastern gate", "B": "Read the silver map"},
    }
    rendered = templates.get_template("host.html").render(
        snap=snap,
        csrf="test-csrf",
        demo=False,
        host=True,
        status="LIVE_TWITCH",
        message="",
        error=None,
    )
    assert "AWAITING APPROVAL" in rendered
    assert "AI-GENERATED" in rendered


def test_demo_host_login_rejects_remote_requests(settings):
    from fastapi import HTTPException
    from starlette.requests import Request

    app = create_app(settings)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/auth/demo")
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "server": ("storyforge.example", 443),
            "client": ("203.0.113.7", 1234),
            "scheme": "https",
            "method": "POST",
            "root_path": "",
            "path": "/auth/demo",
            "raw_path": b"/auth/demo",
            "query_string": b"",
            "headers": [(b"host", b"storyforge.example")],
            "session": {"csrf": "valid-csrf"},
        }
    )

    with pytest.raises(HTTPException) as blocked:
        route.endpoint(request, csrf_token="valid-csrf", password="s3cure-demo-pass")

    assert blocked.value.status_code == 403
    assert app.state.service.persona("demo-host") is None


def test_demo_host_login_accepts_loopback_request(settings):
    from starlette.requests import Request

    app = create_app(settings)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/auth/demo")
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "server": ("127.0.0.1", 8000),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "method": "POST",
            "root_path": "",
            "path": "/auth/demo",
            "raw_path": b"/auth/demo",
            "query_string": b"",
            "headers": [(b"host", b"127.0.0.1:8000")],
            "session": {"csrf": "valid-csrf"},
        }
    )

    response = route.endpoint(request, csrf_token="valid-csrf", password="s3cure-demo-pass")

    assert response.status_code == 303
    assert request.session["role"] == "host"
    assert request.session["twitch_user_id"] == "demo-host"


def test_index_explains_chat_feedback_is_on_web_and_no_chat_replies_are_sent():
    from pathlib import Path

    from jinja2 import Environment, FileSystemLoader

    templates = Environment(
        loader=FileSystemLoader(Path(__file__).parents[1] / "src" / "storyforge" / "templates")
    )
    rendered = templates.get_template("index.html").render(
        snap={
            "story": {
                "title": "Test world",
                "stage": "GENERATING",
                "generation_status": "AWAITING",
            },
            "node": None,
            "proposal": None,
            "personas": [],
        },
        csrf="csrf-test",
        host=False,
        demo=False,
        status="LIVE_TWITCH",
        message="",
        error=None,
    )
    assert "this website and the OBS overlay" in rendered
    assert "does not send replies to Twitch chat" in rendered


def test_failed_scene_generator_persists_failed_status(monkeypatch, settings):
    from starlette.requests import Request

    from storyforge import app as app_module

    class FailingGenerator:
        async def generate(self, **_kwargs):
            raise ValueError("provider failure with private details")

    monkeypatch.setattr(app_module, "DemoGenerator", FailingGenerator)
    app = create_app(settings)
    route = next(route for route in app.routes if getattr(route, "path", None) == "/host/story")
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "scheme": "http",
            "method": "POST",
            "root_path": "",
            "path": "/host/story",
            "raw_path": b"/host/story",
            "query_string": b"",
            "headers": [],
            "session": {"role": "host", "csrf": "valid-csrf"},
        }
    )

    response = asyncio.run(
        route.endpoint(
            request,
            csrf_token="valid-csrf",
            title="A Failed Request",
            premise="A story whose provider request fails must say so.",
            tone="mystery",
        )
    )

    assert response.status_code == 303
    assert "private+details" not in response.headers["location"]
    assert app.state.service.snapshot()["story"]["generation_status"] == "FAILED"


def test_concurrent_host_retries_start_only_one_generation(monkeypatch, settings):
    from starlette.requests import Request

    from storyforge import app as app_module
    from storyforge.ai import NarrativeProposal

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []

        class BlockingGenerator:
            async def generate(self, **_kwargs):
                calls.append("called")
                started.set()
                await release.wait()
                return NarrativeProposal(
                    title="A Quiet Response",
                    narrative="The archive door opens slowly while the visitors consider their next step.",
                    choices=["Read the hidden letter", "Follow the silver stair"],
                )

        generator = BlockingGenerator()
        monkeypatch.setattr(app_module, "DemoGenerator", lambda: generator)
        app = create_app(settings)
        app.state.service.create_story("A Quiet Future", "A library preserves one memory.")
        route = next(
            route for route in app.routes if getattr(route, "path", None) == "/host/action"
        )

        def request():
            return Request(
                {
                    "type": "http",
                    "asgi": {"version": "3.0", "spec_version": "2.3"},
                    "http_version": "1.1",
                    "server": ("127.0.0.1", 8000),
                    "client": ("127.0.0.1", 1234),
                    "scheme": "http",
                    "method": "POST",
                    "root_path": "",
                    "path": "/host/action",
                    "raw_path": b"/host/action",
                    "query_string": b"",
                    "headers": [(b"host", b"127.0.0.1:8000")],
                    "session": {"role": "host", "csrf": "valid-csrf"},
                }
            )

        async def retry():
            return await route.endpoint(
                request(), csrf_token="valid-csrf", action="retry_generation", item_id=0, text=""
            )

        first = asyncio.create_task(retry())
        await asyncio.wait_for(started.wait(), timeout=1)
        second = asyncio.create_task(retry())
        await asyncio.sleep(0)
        calls_before_release = len(calls)
        release.set()
        await asyncio.gather(first, second)
        assert calls_before_release == 1

    asyncio.run(scenario())
