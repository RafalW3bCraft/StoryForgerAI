# Test report (2026-11-01 Codex verification)

Environment: Python 3.14.7 (project declares Python >=3.12), Linux, FastAPI 0.162.0, Starlette 1.10.0, SQLAlchemy 2.1.6, httpx 0.28.1, websockets 17.4, Pydantic 2.14.2, pytest 9.2.0, Ruff 0.17.3 and mypy 2.4.1.

## Current results

- Targeted service/integration/app-configuration selection (HTTP request tests deselected): **24 passed, 3 deselected**.
- Targeted coverage command: **24 passed, 72% total repository coverage** (the blocked HTTP routes account for most misses).
- `python -m ruff check src tests`: **PASS**.
- `python -m ruff format --check src tests`: **PASS**.
- `python -m mypy src/storyforge`: **PASS** (11 source files).
- `python -m compileall -q src`: **PASS**.
- `python -m pip check`: **PASS** (no installed dependency conflicts). `pip-audit`, Bandit, Trivy and Gitleaks are not installed, so no third-party vulnerability scan is claimed.
- Full `python -m pytest -q`: **BLOCKED by environment**. AnyIO 4.15's `start_blocking_portal()` hangs in this Python 3.14 image, including a minimal FastAPI `TestClient`, before the first HTTP request. This is not reported as a passing app-suite run.

Commands executed in the build environment:

```bash
PYTHONPATH=src python -m pytest -q
PYTHONPATH=src python -m pytest --cov=storyforge --cov-report=term-missing -q
PYTHONPATH=src python -m compileall -q src
```

The previous report's 16-test/82% result was not reproduced in this environment. The current targeted result is authoritative for this session.

Implemented tested scenarios:

- Stable original SVG portrait and persona revision.
- Profile validation and opt-out.
- Durable story, scene approval, vote changes, duplicate event handling and deterministic tie-breaks.
- Non-destructive story fork retaining an alternative path.
- Host contribution moderation and legal state transitions.
- The full FastAPI demo flow was reported by the prior build, but is not reclassified as current evidence because the HTTP test client cannot start in this environment.
- CSRF form protection and unauthorized host/profile action rejection.
- OAuth URL scopes and rejection of incomplete live configuration.
- Fernet token encryption/decryption roundtrip.
- Mocked EventSub welcome/notification/reconnect migration with one initial subscription.
- Mocked OpenAI-compatible JSON narrative response parsing and validation.
- Voting pause/resume restores the original effective state and rejects votes while paused.
- Paused voting state and its open round survive a database restart.
- Bounded canonical ancestry context includes prior decisions and excludes alternate branches/private IDs.
- Revocation is terminal until the host re-authenticates; EventSub notifications are broadcaster-bound.
- Contribution chat commands have a short single-process cooldown in addition to bounded input lengths.

Limitations:

- The environment had configured-looking values in `.env`, but `Settings.validate()` rejects the configured `TOKEN_ENCRYPTION_KEY` as an invalid Fernet key; no encrypted host token, Twitch OAuth/session, or actual chat event was available. **Live Twitch blocked/unverified.**
- A live provider attempt reached `api.featherless.ai` but failed DNS resolution (`ConnectError: Temporary failure in name resolution`). **Live AI failed/unverified.**
- Codex CLI is present, but ECC is not registered (`codex plugin list --json` reported no installed plugins). The local session index identifies `01a1959c-5725-74e1-afc2-c3d3e45f1091`; `/status` confirmation is still required. **Submission evidence incomplete.**
- Fresh dependency installation and full browser compatibility testing were not verified. A local Uvicorn/HTTP smoke test and Chromium navigation were not rerun in this session.

The app is an MVP foundation requiring real integration, Codex/ECC iteration and release hardening before Devpost submission.
