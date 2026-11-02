"""Redacted local configuration checks and opt-in external integration probes."""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import sqlite3
import subprocess  # nosec B404
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from .config import Settings

ENVIRONMENT_VARIABLES = (
    "STORYFORGE_MODE",
    "STORYFORGE_DATABASE",
    "STORYFORGE_SECRET",
    "DEMO_ADMIN_PASSWORD",
    "APP_BASE_URL",
    "TWITCH_CLIENT_ID",
    "TWITCH_CLIENT_SECRET",
    "TWITCH_BROADCASTER_ID",
    "TWITCH_READER_ID",
    "TOKEN_ENCRYPTION_KEY",
    "AI_BASE_URL",
    "AI_API_KEY",
    "AI_MODEL",
)

# This mapping contains Settings field names, never configured values.
_SETTINGS_FIELDS = {
    "STORYFORGE_MODE": "mode",
    "STORYFORGE_DATABASE": "database",
    "STORYFORGE_SECRET": "secret",  # nosec B105
    "DEMO_ADMIN_PASSWORD": "demo_password",  # nosec B105
    "APP_BASE_URL": "base_url",
    "TWITCH_CLIENT_ID": "twitch_client_id",
    "TWITCH_CLIENT_SECRET": "twitch_client_secret",  # nosec B105
    "TWITCH_BROADCASTER_ID": "twitch_broadcaster_id",
    "TWITCH_READER_ID": "twitch_reader_id",
    "TOKEN_ENCRYPTION_KEY": "token_key",  # nosec B105
    "AI_BASE_URL": "ai_base_url",
    "AI_API_KEY": "ai_api_key",
    "AI_MODEL": "ai_model",
}
# Role text below explains variables; it contains no credential material.
ENVIRONMENT_ROLES = {
    "STORYFORGE_MODE": "Selects demo or live operation; live mode never silently falls back.",
    "STORYFORGE_DATABASE": "Path to the authoritative SQLite story and persona database.",
    "STORYFORGE_SECRET": "Signs the host and viewer session cookies; use a unique high-entropy value.",  # nosec B105
    "DEMO_ADMIN_PASSWORD": "Loopback-only demo host login password; not used in live mode.",  # nosec B105
    "APP_BASE_URL": "Application origin used to build the exact Twitch OAuth callback URL.",
    "TWITCH_CLIENT_ID": "Identifies the registered Twitch application for OAuth and Helix.",
    "TWITCH_CLIENT_SECRET": "Authenticates server-side Twitch OAuth code exchange and token refresh.",  # nosec B105
    "TWITCH_BROADCASTER_ID": "Immutable Twitch user ID authorized as the host and channel.",
    "TWITCH_READER_ID": "Immutable Twitch user ID used by the EventSub chat reader.",
    "TOKEN_ENCRYPTION_KEY": "Fernet key that encrypts the host OAuth token vault at rest.",  # nosec B105
    "AI_BASE_URL": "HTTPS base URL for the configured OpenAI-compatible narrative provider.",
    "AI_API_KEY": "Server-side credential used for live narrative generation.",
    "AI_MODEL": "Exact provider model ID requested for Pydantic-validated narrative output.",
}
_LOCAL_ONLY_VARIABLES = frozenset(
    {"STORYFORGE_MODE", "STORYFORGE_DATABASE", "STORYFORGE_SECRET", "DEMO_ADMIN_PASSWORD"}
)
_TWITCH_VARIABLES = frozenset(
    {
        "TWITCH_CLIENT_ID",
        "TWITCH_CLIENT_SECRET",
        "TWITCH_BROADCASTER_ID",
        "TWITCH_READER_ID",
        "TOKEN_ENCRYPTION_KEY",
    }
)
_AI_VARIABLES = frozenset({"AI_BASE_URL", "AI_API_KEY", "AI_MODEL"})
LIVE_PROBE_TIMEOUTS = {"twitch": 40, "ai": 60, "runtime": 10}


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    role: str
    present: bool
    local: str
    external: str = "NOT CHECKED"


def _check_value(name: str, value: str, settings: Settings) -> str:
    if name == "STORYFORGE_MODE":
        return "PASS" if value in {"demo", "live"} else "FAIL"
    if name == "STORYFORGE_DATABASE":
        return "PASS" if value.strip() else "FAIL"
    if name == "STORYFORGE_SECRET":
        secure = _has_secret_entropy(value) and value != "development-only-change-me"
        return "PASS" if secure else ("FAIL" if settings.mode == "live" else "WARN")
    if name == "DEMO_ADMIN_PASSWORD":
        if settings.mode != "demo":
            return "NOT USED IN LIVE MODE"
        if not value:
            return "NOT CONFIGURED"
        return "PASS" if _has_secret_entropy(value, minimum_length=16) else "FAIL"
    if name == "APP_BASE_URL":
        try:
            parsed = urlsplit(value)
            valid_origin = parsed.scheme == "https" or (
                parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            )
            return (
                "PASS"
                if valid_origin
                and parsed.hostname
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
                and parsed.path in {"", "/"}
                else "FAIL"
            )
        except ValueError:
            return "FAIL"
    if name in {"TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET"}:
        if value:
            return "PASS"
        if settings.mode == "live":
            return "FAIL"
        return "NOT CONFIGURED"
    if name in {"TWITCH_BROADCASTER_ID", "TWITCH_READER_ID"}:
        twitch_configured = bool(
            settings.twitch_client_id
            or settings.twitch_client_secret
            or settings.twitch_broadcaster_id
        )
        if not value:
            return "FAIL" if settings.mode == "live" or twitch_configured else "NOT CONFIGURED"
        ids_match = settings.twitch_reader_id == settings.twitch_broadcaster_id
        numeric = value.isascii() and value.isdecimal()
        return "PASS" if numeric and ids_match else "FAIL"
    if name == "TOKEN_ENCRYPTION_KEY":
        if not value:
            return "FAIL" if settings.mode == "live" else "NOT CONFIGURED"
        try:
            from cryptography.fernet import Fernet

            Fernet(value.encode("ascii"))
            return "PASS"
        except (ValueError, UnicodeEncodeError):
            return "FAIL"
    if name == "AI_BASE_URL":
        if not value:
            return "NOT CONFIGURED" if not (settings.ai_api_key or settings.ai_model) else "FAIL"
        try:
            parsed = urlsplit(value)
            local_http = (
                settings.mode == "demo"
                and parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            )
            valid = (
                (parsed.scheme == "https" or local_http)
                and bool(parsed.hostname)
                and not parsed.username
                and not parsed.password
                and not parsed.query
                and not parsed.fragment
                and not parsed.path.rstrip("/").endswith("/chat/completions")
            )
            return "PASS" if valid else "FAIL"
        except ValueError:
            return "FAIL"
    if name in {"AI_API_KEY", "AI_MODEL"}:
        configured = bool(settings.ai_base_url or settings.ai_api_key or settings.ai_model)
        if value:
            return "PASS"
        return "FAIL" if configured else "NOT CONFIGURED"
    return "NOT CHECKED"


def _has_secret_entropy(value: str, *, minimum_length: int = 32) -> bool:
    """Apply a non-revealing strength heuristic; this cannot prove how a secret was made."""
    if len(value) < minimum_length or len(set(value)) < 12:
        return False
    counts = {character: value.count(character) for character in set(value)}
    entropy = -sum(
        (count / len(value)) * math.log2(count / len(value)) for count in counts.values()
    )
    return entropy >= 3.5


def probe_database_writable(settings: Settings) -> str:
    """Confirm SQLite can acquire a write transaction without persisting a probe table."""
    connection = None
    try:
        if not settings.database:
            return "FAIL"
        connection = sqlite3.connect(settings.database, timeout=5)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("CREATE TABLE storyforge_doctor_probe (value INTEGER NOT NULL)")
        connection.execute("INSERT INTO storyforge_doctor_probe (value) VALUES (1)")
        result = connection.execute("SELECT value FROM storyforge_doctor_probe").fetchone()
        connection.rollback()
        return "PASS" if result == (1,) else "FAIL"
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return "FAIL"
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()


def inspect_environment(
    settings: Settings | None = None,
    *,
    environment: Mapping[str, str] | None = None,
    database_status: str | None = None,
    external_status: Mapping[str, str] | None = None,
) -> list[EnvironmentCheck]:
    """Inspect recognized configuration names without returning their values."""
    settings = settings or Settings()
    environment = os.environ if environment is None else environment
    external_status = external_status or {}
    checks = []
    for name in ENVIRONMENT_VARIABLES:
        value = str(getattr(settings, _SETTINGS_FIELDS[name]) or "")
        local = _check_value(name, value, settings)
        if name == "STORYFORGE_DATABASE" and database_status is not None:
            local = database_status
        checks.append(
            EnvironmentCheck(
                name=name,
                role=ENVIRONMENT_ROLES[name],
                present=bool(str(environment.get(name, "")).strip()),
                local=local,
                external=external_status.get(
                    name,
                    "NOT APPLICABLE" if name in _LOCAL_ONLY_VARIABLES else "NOT CHECKED",
                ),
            )
        )
    return checks


def render_report(checks: list[EnvironmentCheck]) -> str:
    rows = [
        "StoryForge configuration diagnostic (values redacted)",
        "NAME | PRESENT | LOCAL VALIDATION | EXTERNAL VERIFICATION | ROLE",
    ]
    rows.extend(
        f"{check.name} | {'yes' if check.present else 'no'} | {check.local} | "
        f"{check.external} | {check.role}"
        for check in checks
    )
    rows.extend(
        [
            "",
            "NOT CHECKED means no live request was attempted; NOT APPLICABLE means the value is local-only.",
            "Local validation does not prove remote OAuth, EventSub, or provider acceptance.",
        ]
    )
    return "\n".join(rows)


async def _verify_twitch_api(settings: Settings) -> str:
    if not (settings.twitch_client_id and settings.token_key):
        return "Twitch OAuth API: BLOCKED (required client configuration absent)"
    from .db import factory, make_engine
    from .twitch import get_host_token, user_for_token

    engine = make_engine(settings.db_url)
    try:
        sessions = factory(engine)
        token = await get_host_token(settings, sessions)
        if not token:
            return "Twitch OAuth API: BLOCKED (no encrypted host token in local database)"
        user = await user_for_token(settings, token)
        if str(user.get("id", "")) != settings.twitch_broadcaster_id:
            return "Twitch OAuth API: FAILED (authenticated user is not configured broadcaster)"
        return "Twitch OAuth API: VERIFIED (host token and broadcaster identity)"
    finally:
        engine.dispose()


async def _verify_ai_provider(settings: Settings) -> str:
    if not settings.ai_enabled:
        return "AI provider: BLOCKED (AI_BASE_URL, AI_API_KEY and AI_MODEL are not all configured in live mode)"
    from .ai import OpenAICompatibleGenerator

    try:
        proposal = await OpenAICompatibleGenerator(settings).generate(
            world="A library keeps the memories of a small group of travelers.",
            history="",
            decision="open the sealed atlas",
            personas=["Aster (scholar)"],
            contributions=[],
        )
    except httpx.HTTPStatusError as exc:
        return f"AI provider: FAILED (HTTP {exc.response.status_code})"
    except httpx.TimeoutException:
        return "AI provider: FAILED (probe timed out)"
    except httpx.RequestError as exc:
        return f"AI provider: FAILED (request error: {type(exc).__name__})"
    except (TypeError, ValueError) as exc:
        reason = {
            "AI provider returned a truncated completion": "response was truncated",
            "AI provider response omitted choices": "response omitted choices (OpenAI-compatible chat format required)",
            "AI provider response had an invalid choice shape": "response had an invalid choice shape",
            "AI provider response omitted the assistant message": "response omitted the assistant message",
            "AI provider response omitted assistant content": "response omitted assistant content",
            "AI provider returned an error object": "provider returned an error object",
            "AI provider returned a non-object response": "response was not a JSON object",
            "AI provider refused the narrative request": "provider refused the narrative request",
            "AI provider returned a tool call instead of narrative content": "response contained a tool call, not narrative content",
            "AI provider returned content blocks without text": "assistant content blocks contained no text",
            "AI provider returned empty narrative text": "assistant content field was empty",
            "AI provider narrative content was not text": "assistant content had an unsupported type",
            "AI provider returned invalid narrative JSON": "response failed narrative validation",
        }.get(str(exc), "provider returned an invalid response")
        return f"AI provider: FAILED ({reason})"
    if proposal.title and proposal.narrative and len(proposal.choices) in {2, 3}:
        return "AI provider: VERIFIED (live response passed NarrativeProposal validation)"
    return "AI provider: FAILED (response did not satisfy the narrative schema)"


async def _verify_runtime(settings: Settings) -> str:
    """Read only the status fields exposed by the configured application's health route."""
    try:
        settings.validate()
        async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
            response = await client.get(settings.base_url + "/health")
        if response.status_code != 200:
            raise ValueError("health endpoint did not return HTTP 200")
        health = response.json()
        if not isinstance(health, dict) or health.get("status") != "ok":
            raise ValueError("health response was not ready")
    except Exception as exc:  # noqa: BLE001 - never expose URLs, response bodies, or credentials
        return "\n".join(
            (
                f"Application runtime: NOT VERIFIED ({type(exc).__name__})",
                "Twitch EventSub subscription: NOT VERIFIED",
                "Last real Twitch chat event: NOT VERIFIED",
                "Saved AI generation from provider: NOT VERIFIED",
            )
        )

    eventsub = "VERIFIED" if health.get("eventsub_subscribed") is True else "NOT VERIFIED"
    real_chat = "VERIFIED" if health.get("last_real_chat_event_seen") is True else "NOT VERIFIED"
    ai_state = str(health.get("ai_last_generation", "NOT VERIFIED"))
    if ai_state not in {"VERIFIED", "DEMO", "NOT GENERATED"}:
        ai_state = "NOT VERIFIED"
    return "\n".join(
        (
            "Application runtime: VERIFIED (health endpoint and database-backed snapshot)",
            f"Twitch EventSub subscription: {eventsub}",
            f"Last real Twitch chat event: {real_chat}",
            f"Saved AI generation from provider: {ai_state}",
        )
    )


# This subprocess uses an enumerated probe name, fixed argv, no shell, and a timeout.
def _run_external_probe(name: str) -> str:
    labels = {
        "twitch": "Twitch OAuth API",
        "ai": "AI provider",
        "runtime": "Application runtime",
    }
    label = labels[name]
    try:
        completed = subprocess.run(  # nosec B603
            [
                sys.executable,
                "-m",
                "storyforge.diagnostics",
                "doctor",
                "--probe",
                name,
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=LIVE_PROBE_TIMEOUTS[name],
        )
    except subprocess.TimeoutExpired:
        return f"{label}: FAILED (probe timed out)"
    except OSError as exc:
        return f"{label}: FAILED ({type(exc).__name__})"
    if completed.returncode != 0:
        return f"{label}: FAILED (probe process exited {completed.returncode})"
    output = completed.stdout.strip()
    prefix = label + ": "
    if output.startswith(prefix):
        return output
    return f"{label}: FAILED (probe returned no status)"


def _verification_state(result: str, label: str) -> str:
    prefix = label + ": "
    if not result.startswith(prefix):
        return "NOT VERIFIED"
    detail = result[len(prefix) :].upper()
    for status in ("VERIFIED", "FAILED", "BLOCKED", "NOT VERIFIED", "NOT CHECKED"):
        if detail.startswith(status):
            return status
    return "NOT VERIFIED"


def _external_statuses(twitch: str, ai: str, runtime: str) -> dict[str, str]:
    twitch_state = _verification_state(twitch, "Twitch OAuth API")
    ai_state = _verification_state(ai, "AI provider")
    eventsub_state = (
        "VERIFIED" if "Twitch EventSub subscription: VERIFIED" in runtime else "NOT VERIFIED"
    )
    statuses = {name: "NOT CHECKED" for name in ENVIRONMENT_VARIABLES}
    for name in _LOCAL_ONLY_VARIABLES:
        statuses[name] = "NOT APPLICABLE"
    statuses["TWITCH_CLIENT_ID"] = twitch_state
    # A valid, unexpired vault token does not exercise the client secret itself.
    # This is a status label, not a credential value.
    statuses["TWITCH_CLIENT_SECRET"] = "NOT VERIFIED (no OAuth exchange required by probe)"  # nosec B105
    statuses["TWITCH_BROADCASTER_ID"] = twitch_state
    statuses["TWITCH_READER_ID"] = eventsub_state
    statuses["TOKEN_ENCRYPTION_KEY"] = twitch_state
    for name in _AI_VARIABLES:
        statuses[name] = ai_state
    return statuses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="storyforge")
    subparsers = parser.add_subparsers(dest="command")
    doctor_parser = subparsers.add_parser("doctor", help="print redacted configuration diagnostics")
    doctor_parser.add_argument(
        "--probe", choices=("twitch", "ai", "runtime"), help=argparse.SUPPRESS
    )
    doctor_parser.add_argument(
        "--live",
        action="store_true",
        help="make bounded Twitch OAuth and AI provider requests; may refresh the stored host token",
    )
    args = parser.parse_args(argv)
    if args.command != "doctor":
        from .app import main as run_app

        run_app()
        return 0

    settings = Settings()
    if args.probe:
        try:
            if args.probe == "twitch":
                result = asyncio.run(_verify_twitch_api(settings))
            elif args.probe == "ai":
                result = asyncio.run(_verify_ai_provider(settings))
            else:
                result = asyncio.run(_verify_runtime(settings))
        except Exception as exc:  # noqa: BLE001 - do not expose provider response or key
            label = {
                "twitch": "Twitch OAuth API",
                "ai": "AI provider",
                "runtime": "Application runtime",
            }[args.probe]
            result = f"{label}: FAILED ({type(exc).__name__})"
        print(result)
        return 0

    database_status = probe_database_writable(settings)
    twitch_result = "Twitch OAuth API: NOT CHECKED"
    ai_result = "AI provider: NOT CHECKED"
    runtime_result = "Application runtime: NOT CHECKED"
    if args.live:
        twitch_result = _run_external_probe("twitch")
        ai_result = _run_external_probe("ai")
        runtime_result = _run_external_probe("runtime")
    statuses = _external_statuses(twitch_result, ai_result, runtime_result)
    checks = inspect_environment(
        settings,
        database_status=database_status,
        external_status=statuses if args.live else None,
    )
    print(render_report(checks))
    print(f"\nSQLite database writable: {database_status}")
    if args.live:
        print("\nLive provider and runtime verification")
        print(twitch_result)
        print(ai_result)
        for line in runtime_result.splitlines():
            print(line)
        runtime_ready = database_status == "PASS" and runtime_result.startswith(
            "Application runtime: VERIFIED"
        )
        print("Runtime readiness: PASS" if runtime_ready else "Runtime readiness: NOT VERIFIED")
    else:
        print("Twitch EventSub subscription: NOT CHECKED")
        print("Last real Twitch chat event: NOT CHECKED")
        print("Saved AI generation from provider: NOT CHECKED")
        print("Runtime readiness: NOT CHECKED")
    invalid = any(check.local == "FAIL" for check in checks)
    external_failed = args.live and any(
        marker in result
        for result in (twitch_result, ai_result, runtime_result)
        for marker in (": FAILED", ": BLOCKED", ": NOT VERIFIED")
    )
    return 1 if invalid or database_status == "FAIL" or external_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
