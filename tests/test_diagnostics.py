from storyforge.config import Settings


def test_diagnostic_lists_every_supported_variable_redacted_and_unverified():
    from storyforge.diagnostics import ENVIRONMENT_VARIABLES, inspect_environment, render_report

    sentinel = "private-sentinel-that-must-not-appear"
    settings = Settings(
        mode="demo",
        database="./storyforge.db",
        secret=sentinel,
        demo_password="another-private-sentinel",
        twitch_client_id="client-id-private",
        twitch_client_secret="client-secret-private",
        twitch_broadcaster_id="12345",
        twitch_reader_id="12345",
        token_key="invalid-private-fernet-key",
        ai_base_url="https://provider.example/v1",
        ai_api_key="ai-private-key",
        ai_model="model-private-name",
    )

    rows = inspect_environment(
        settings,
        environment={name: "configured" for name in ENVIRONMENT_VARIABLES},
    )
    assert {row.name for row in rows} == set(ENVIRONMENT_VARIABLES)
    assert rows[0].external == "NOT APPLICABLE"
    assert rows[ENVIRONMENT_VARIABLES.index("TWITCH_CLIENT_ID")].external == "NOT CHECKED"
    report = render_report(rows)
    assert "NOT CHECKED means no live request was attempted" in report
    assert all(name in report for name in ENVIRONMENT_VARIABLES)
    for private_value in (
        sentinel,
        "another-private-sentinel",
        "client-id-private",
        "client-secret-private",
        "invalid-private-fernet-key",
        "ai-private-key",
        "model-private-name",
    ):
        assert private_value not in report


def test_diagnostic_flags_local_config_mismatch_without_claiming_external_success():
    from storyforge.diagnostics import inspect_environment

    settings = Settings(
        mode="live",
        database="./storyforge.db",
        secret="short",
        base_url="http://public.example",
        twitch_broadcaster_id="12345",
        twitch_reader_id="67890",
    )
    rows = {row.name: row for row in inspect_environment(settings)}
    assert rows["STORYFORGE_SECRET"].local == "FAIL"
    assert rows["APP_BASE_URL"].local == "FAIL"
    assert rows["TWITCH_READER_ID"].local == "FAIL"
    assert rows["AI_API_KEY"].external == "NOT CHECKED"


def test_demo_local_ai_endpoint_is_reported_as_valid():
    from storyforge.diagnostics import inspect_environment

    settings = Settings(
        mode="demo",
        database="./storyforge.db",
        secret="s" * 40,
        ai_base_url="http://127.0.0.1:8001/v1",
    )

    rows = {row.name: row for row in inspect_environment(settings)}

    assert rows["AI_BASE_URL"].local == "PASS"


def test_live_diagnostic_kills_timed_out_external_probe(monkeypatch):
    from storyforge import diagnostics

    def timeout(*args, **kwargs):
        raise diagnostics.subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(diagnostics.subprocess, "run", timeout)
    assert diagnostics._run_external_probe("twitch") == "Twitch OAuth API: FAILED (probe timed out)"
    assert diagnostics._run_external_probe("ai") == "AI provider: FAILED (probe timed out)"
    assert (
        diagnostics._run_external_probe("runtime")
        == "Application runtime: FAILED (probe timed out)"
    )


def test_live_ai_probe_outer_timeout_exceeds_provider_request_timeout(monkeypatch):
    from types import SimpleNamespace

    from storyforge import diagnostics

    seen = []

    def completed(_args, **kwargs):
        seen.append(kwargs["timeout"])
        return SimpleNamespace(returncode=0, stdout="AI provider: VERIFIED (validated)")

    monkeypatch.setattr(diagnostics.subprocess, "run", completed)

    assert diagnostics._run_external_probe("ai") == "AI provider: VERIFIED (validated)"
    assert seen == [60]


def test_live_ai_diagnostic_reports_provider_http_status_without_body(monkeypatch):
    import asyncio

    import httpx

    from storyforge import ai, diagnostics

    settings = Settings(
        mode="live",
        database="./storyforge.db",
        secret="s" * 48,
        ai_base_url="https://provider.example/v1",
        ai_api_key="private-api-key-sentinel",
        ai_model="private-model-sentinel",
    )
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx.Response(401, request=request)

    class FailingGenerator:
        def __init__(self, _settings):
            pass

        async def generate(self, **_kwargs):
            raise httpx.HTTPStatusError(
                "private provider error body", request=request, response=response
            )

    monkeypatch.setattr(ai, "OpenAICompatibleGenerator", FailingGenerator)

    result = asyncio.run(diagnostics._verify_ai_provider(settings))

    assert result == "AI provider: FAILED (HTTP 401)"
    assert "private-api-key-sentinel" not in result
    assert "private-model-sentinel" not in result
    assert "private provider error body" not in result


def test_live_ai_diagnostic_reports_schema_failure_without_generated_text(monkeypatch):
    import asyncio

    from storyforge import ai, diagnostics

    settings = Settings(
        mode="live",
        database="./storyforge.db",
        secret="s" * 48,
        ai_base_url="https://provider.example/v1",
        ai_api_key="private-api-key-sentinel",
        ai_model="private-model-sentinel",
    )

    class InvalidGenerator:
        def __init__(self, _settings):
            pass

        async def generate(self, **_kwargs):
            raise ValueError("AI provider returned invalid narrative JSON")

    monkeypatch.setattr(ai, "OpenAICompatibleGenerator", InvalidGenerator)

    result = asyncio.run(diagnostics._verify_ai_provider(settings))

    assert result == "AI provider: FAILED (response failed narrative validation)"
    assert "private-api-key-sentinel" not in result
    assert "private-model-sentinel" not in result


def test_live_ai_diagnostic_identifies_incompatible_response_shape_safely(monkeypatch):
    import asyncio

    from storyforge import ai, diagnostics

    settings = Settings(
        mode="live",
        database="./storyforge.db",
        secret="s" * 48,
        ai_base_url="https://provider.example/v1",
        ai_api_key="private-api-key-sentinel",
        ai_model="private-model-sentinel",
    )

    class IncompatibleGenerator:
        def __init__(self, _settings):
            pass

        async def generate(self, **_kwargs):
            raise ValueError("AI provider response omitted choices")

    monkeypatch.setattr(ai, "OpenAICompatibleGenerator", IncompatibleGenerator)

    result = asyncio.run(diagnostics._verify_ai_provider(settings))

    assert result == (
        "AI provider: FAILED (response omitted choices (OpenAI-compatible chat format required))"
    )
    assert "private-api-key-sentinel" not in result
    assert "private-model-sentinel" not in result


def test_live_ai_diagnostic_distinguishes_empty_provider_content(monkeypatch):
    import asyncio

    from storyforge import ai, diagnostics

    settings = Settings(
        mode="live",
        database="./storyforge.db",
        secret="s" * 48,
        ai_base_url="https://provider.example/v1",
        ai_api_key="private-api-key-sentinel",
        ai_model="private-model-sentinel",
    )

    class EmptyGenerator:
        def __init__(self, _settings):
            pass

        async def generate(self, **_kwargs):
            raise ValueError("AI provider returned empty narrative text")

    monkeypatch.setattr(ai, "OpenAICompatibleGenerator", EmptyGenerator)

    result = asyncio.run(diagnostics._verify_ai_provider(settings))

    assert result == "AI provider: FAILED (assistant content field was empty)"
    assert "private-api-key-sentinel" not in result
    assert "private-model-sentinel" not in result


def test_diagnostic_distinguishes_unset_variables_from_defaults():
    from storyforge.diagnostics import ENVIRONMENT_ROLES, inspect_environment, render_report

    rows = inspect_environment(Settings(), environment={})
    assert all(not row.present for row in rows)

    report = render_report(rows)
    assert "ROLE" in report.splitlines()[1]
    assert ENVIRONMENT_ROLES["AI_API_KEY"] in report
    assert "development-only-change-me" not in report


def test_database_write_probe_rolls_back_and_rejects_missing_parent(tmp_path):
    import sqlite3
    from contextlib import closing

    from storyforge.diagnostics import probe_database_writable

    database = tmp_path / "storyforge.sqlite3"
    settings = Settings(database=str(database))
    assert probe_database_writable(settings) == "PASS"

    with closing(sqlite3.connect(database)) as connection:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    assert tables == []

    missing_parent = Settings(database=str(tmp_path / "missing" / "storyforge.sqlite3"))
    assert probe_database_writable(missing_parent) == "FAIL"


def test_doctor_reports_live_runtime_evidence_as_unverified_by_default(
    monkeypatch, capsys, tmp_path
):
    from storyforge import diagnostics

    settings = Settings(
        mode="live",
        database=str(tmp_path / "storyforge.sqlite3"),
        secret="s" * 48,
        base_url="https://storyforge.example",
        twitch_client_id="client-id-private",
        twitch_client_secret="client-secret-private",
        twitch_broadcaster_id="12345",
        twitch_reader_id="12345",
        token_key="invalid-private-fernet-key",
        ai_base_url="https://provider.example/v1",
        ai_api_key="ai-private-key",
        ai_model="model-private-name",
    )
    monkeypatch.setattr(diagnostics, "Settings", lambda: settings)
    monkeypatch.setattr(diagnostics.os, "environ", {})

    diagnostics.main(["doctor"])
    output = capsys.readouterr().out

    assert "SQLite database writable: PASS" in output
    assert "Twitch EventSub subscription: NOT CHECKED" in output
    assert "Last real Twitch chat event: NOT CHECKED" in output
    assert "Saved AI generation from provider: NOT CHECKED" in output
    assert "Runtime readiness: NOT CHECKED" in output
    for private_value in (
        "client-id-private",
        "client-secret-private",
        "invalid-private-fernet-key",
        "ai-private-key",
        "model-private-name",
    ):
        assert private_value not in output


def test_live_probe_reports_app_runtime_eventsub_chat_and_saved_ai(monkeypatch):
    from storyforge import diagnostics

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "status": "ok",
                "twitch": "LIVE_TWITCH",
                "eventsub_subscribed": True,
                "last_real_chat_event_seen": True,
                "ai_last_generation": "VERIFIED",
            }

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            assert url == "https://storyforge.example/health"
            return FakeResponse()

    monkeypatch.setattr(diagnostics.httpx, "AsyncClient", FakeClient)
    settings = Settings(
        mode="demo",
        database="./storyforge.db",
        secret="s" * 48,
        base_url="https://storyforge.example",
    )

    import asyncio

    result = asyncio.run(diagnostics._verify_runtime(settings))

    assert "Application runtime: VERIFIED" in result
    assert "Twitch EventSub subscription: VERIFIED" in result
    assert "Last real Twitch chat event: VERIFIED" in result
    assert "Saved AI generation from provider: VERIFIED" in result


def test_health_endpoint_reports_only_integration_status(tmp_path):
    import secrets

    from cryptography.fernet import Fernet

    from storyforge.ai import NarrativeProposal
    from storyforge.app import create_app

    settings = Settings(
        mode="live",
        database=str(tmp_path / "storyforge.sqlite3"),
        secret=secrets.token_urlsafe(40),
        base_url="https://storyforge.example",
        twitch_client_id="client-id-private",
        twitch_client_secret="client-secret-private",
        twitch_broadcaster_id="12345",
        twitch_reader_id="12345",
        token_key=Fernet.generate_key().decode(),
        ai_base_url="https://provider.example/v1",
        ai_api_key="ai-private-key",
        ai_model="model-private-name",
    )
    app = create_app(settings)
    app.state.service.create_story("The Quiet Atlas", "A cartographer finds a door.", "mystery")
    app.state.service.save_proposal(
        NarrativeProposal(
            title="The Door Beneath the Map",
            narrative="A narrow stair leads from the map room into a chamber of stars.",
            choices=["Follow the blue staircase", "Question the silent cartographer"],
        ),
        "AI",
    )
    app.state.connector.status = "LIVE_TWITCH"
    app.state.connector.last_event = "2026-11-02T00:00:00+00:00"
    endpoint = next(
        route.endpoint for route in app.routes if getattr(route, "path", None) == "/health"
    )

    report = endpoint()

    assert report["eventsub_subscribed"] is True
    assert report["last_real_chat_event_seen"] is True
    assert report["ai_last_generation"] == "VERIFIED"
    assert "A narrow stair" not in str(report)
    assert "client-secret-private" not in str(report)
