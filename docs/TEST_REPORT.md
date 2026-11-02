# Test and verification report

**Run date:** 2026-11-02 UTC
**Checkout:** `main` at `d6aa6ff` before this working-tree pass
**Runtime:** Linux, Python 3.14.7. The project declares Python 3.12+.
**Key installed versions:** FastAPI 0.162.0, Starlette 1.10.0, SQLAlchemy 2.1.6, Pydantic 2.14.2, cryptography 50.0.2, httpx 0.28.1, httpx2 2.16.0 (installed in the environment but no longer required by project tests), websockets 17.4, pytest 9.2.0, pytest-cov 7.1.0, Ruff 0.17.3, mypy 2.4.1.

## Nov 2 follow-up: OAuth origin and runtime diagnostics

The current checkout still has pre-existing uncommitted changes on `main` at `d6aa6ff`; this follow-up preserves them. Python 3.14.7 was used for the checks below.

| Check | Current result | Evidence |
|---|---|---|
| OAuth origin regressions | **PASS** | `.venv/bin/python -m pytest -q tests/test_app.py -k 'all_off_origin or oauth_token_exchange_failure or twitch_oauth_login or host_oauth_callback or app_runner'`: **6 passed, 17 deselected**. |
| Full regression suite | **PASS** | `timeout 45s .venv/bin/python -m pytest -q -o faulthandler_timeout=10` outside the sandbox: **68 passed in 3.35s**. |
| Full coverage | **PASS** | `timeout 45s .venv/bin/python -m pytest --cov=storyforge --cov-report=term-missing -q -W error::ResourceWarning` outside the sandbox: **68 passed**, **84% total coverage**, no ResourceWarnings. |
| Sandbox-bound test run | **BLOCKED (environment only)** | A sandbox-bound run stalls when FastAPI dispatches synchronous routes through AnyIO's worker queue. The same full suite passes outside the sandbox; no application handler was moved onto the event loop. |
| Ruff, formatting, mypy, compileall, pip check | **PASS** | Final runs passed in the Python 3.14.7 environment after all source/test changes. |
| Dependency vulnerability audit | **PASS, dependencies only** | `pip-audit 2.10.1` initially found seven advisories in `cryptography 47.0.0`; the dependency floor was raised to `50.0.2`. Reruns against the clean Python 3.13 install and current `.venv` report no known vulnerabilities. The local `ai-storyforge` package is skipped because it is not published on PyPI. |
| Bandit source scan | **PASS for Medium/High** | Bandit 1.9.4 reported zero Medium/High findings. Its 13 Low findings were reviewed: deterministic cosmetic randomness, the live-rejected demo sentinel, diagnostic field/help labels, and a fixed-argv subprocess with no shell and a timeout. The two Medium SQL-string findings from the first run were removed by using a fixed-name main-database table inside a rolled-back transaction. |
| Redacted local doctor | **PASS, local only** | All 13 recognized variable names and roles were printed without values; each local validation passed and the SQLite write probe passed. |
| Twitch authorization endpoint | **BLOCKED** | One read-only request built from local `TWITCH_CLIENT_ID` and `APP_BASE_URL/auth/callback` received HTTP 302 (`text/html`). No browser grant, code exchange, or token was requested; this response alone does not prove broadcaster authentication. |
| Redacted live probes | **BLOCKED** | Twitch probe found no encrypted host token; model endpoint returned an empty assistant-content field; the running app `/health` endpoint and SQLite snapshot verified. EventSub and real chat remain unverified. |
| Clean Python 3.13 dependency install | **PASS** | Installed `.[dev]` into `/tmp/storyforge-py313-venv`; `pip check` passed. The environment's event-loop/thread bridge still timed out independently of StoryForge. |

The prior OAuth failure was consistent with starting from one loopback hostname and returning to another, which gives the browser separate cookies. `ConfiguredOriginMiddleware` now redirects every off-origin HTTP request to the fixed `APP_BASE_URL` before session handling, preserving path and query without trusting the Host header. Callback state mismatches are rejected without exchanging the code and return the browser to app home, not a JSON detail response. Token-exchange failures now show only a safe HTTP status/category and log no code, response body, or credential. Access logging remains disabled. The user's latest startup output prints `http://127.0.0.1:8000`; the Twitch callback derived from that value is `http://127.0.0.1:8000/auth/callback`.

The earlier sandbox-bound attempt stalled in the execution host's AnyIO worker bridge. The final complete run outside that sandbox passed all 68 tests, including the three HTTP acceptance tests, so the suite is no longer blocked. StoryForge keeps synchronous SQLite handlers on FastAPI's normal worker-dispatch path.

The dependency audit found seven advisories in the previous `cryptography 47.0.0` pin, whose `<48` ceiling prevented patched versions from being installed. `pyproject.toml` now requires `cryptography>=50.0.2,<51`; the project and ignored environments were reinstalled, the full suite passed outside the sandbox, and the repeated audit reported no known dependency vulnerabilities. `httpx2>=2,<3` was briefly added to the dev extra to test Starlette's current TestClient adapter; it removed a deprecation warning but did not fix the worker stall, so it was removed after the HTTP tests moved to `httpx.AsyncClient`.

The first Bandit scan raised two Medium B608 findings on the diagnostic's f-string table names. The identifier came from a UUID and was not controllable by users, but the probe now uses a fixed-name main-database table inside a transaction that is rolled back, removing dynamic SQL and the findings while still testing database write access. The remaining Low findings were reviewed as false positives for this app's usage; the full scan with `--ignore-nosec` found zero Medium/High issues.

`python -m storyforge doctor --live` was run with values redacted and the AI watchdog set to 60 seconds. Final results: `Twitch OAuth API: BLOCKED (no encrypted host token in local database)`, `AI provider: FAILED (assistant content field was empty)`, `Application runtime: VERIFIED (health endpoint and database-backed snapshot)`, `Twitch EventSub subscription: NOT VERIFIED`, `Last real Twitch chat event: NOT VERIFIED`, `Saved AI generation from provider: NOT GENERATED`, and `Runtime readiness: PASS`. The model response had an empty assistant-content string, so it did not pass validation or get saved. A separate read-only Twitch authorization request returned HTTP 302 (`text/html`), but no browser grant, code exchange, or broadcaster identity was tested. No real chat command or host approval is evidenced. Local diagnostics confirmed live mode, all 13 variable shapes passing, and SQLite writable; this does not inspect the Developer Console entry. The callback must exactly match `APP_BASE_URL/auth/callback`.

## Earlier automated checkpoint before the Nov 2 OAuth continuation

| Check | Result | Evidence |
|---|---|---|
| Targeted non-HTTP suite | **PASS** | `51 passed, 3 deselected` |
| Targeted coverage | **76% total** | `51 passed, 3 deselected`; `pytest --cov=storyforge --cov-report=term-missing` with the three hanging TestClient tests deselected |
| Full suite | **BLOCKED** | `timeout 20s .venv/bin/python -m pytest -q` exited 124. The first HTTP test blocks during `TestClient` lifespan startup. A bare `FastAPI()` app also blocks in `TestClient.__enter__()`. The full suite collects 54 tests; three HTTP tests remain blocked. |
| Ruff | **PASS** | `.venv/bin/ruff check src tests` |
| Formatting | **PASS** | `.venv/bin/ruff format --check src tests` |
| Type checking | **PASS** | `.venv/bin/mypy src/storyforge` — 12 source files |
| Python compilation | **PASS** | `.venv/bin/python -m compileall -q src` |
| Installed dependency consistency | **PASS** | `.venv/bin/python -m pip check` — no broken requirements |
| Clean Python 3.12 dependency install | **BLOCKED** | `uv` found Python 3.12.14, but offline `uv pip install --python /tmp/storyforge-py312/bin/python --offline -e '.[dev]'` failed because FastAPI was not cached and network access is disabled. |

At an earlier checkpoint, three HTTP tests were deselected while investigating the sandbox worker stall. The final run restored and passed all three. No browser/OBS runtime was available for a visual run.

The final Ruff run caught a Python exception-variable lifetime error in the host error handler; it was corrected. A traced `ResourceWarning` identified a legacy-database test that used `sqlite3.Connection` as a transaction context without closing the connection; it now uses `contextlib.closing`. The integration suite then passed with `-W error::ResourceWarning`. The final targeted run emitted only the Starlette TestClient deprecation warning.

A final review found that approving a proposal overwrote its persisted generation provenance with `APPROVED`. A regression first failed with actual `APPROVED` versus expected `DEMO-GENERATED`; the assignment was removed so the canonical node/proposal carries approval and the story retains its AI/demo source. Additional RED/GREEN cycles closed cross-command cooldown bypass, invalid-vote spam, durable receipts for unknown/informational commands, demo-host login from remote addresses, secret-bearing `Settings.__repr__`, and missing UI notice that chat replies are not sent. The final targeted suite includes these regressions.

The targeted run covers OAuth callback success/state mismatch/wrong broadcaster through direct route invocation, persona persistence and deletion, chat processing, accepted and cooldown-rejected duplicate IDs, unknown/informational receipt suppression, invalid-vote and cross-command rate limiting, loopback-only demo host login, settings repr redaction, concurrent model-request suppression, the voting pause/resume/restart invariant, canonical branching and bounded context, mocked OAuth refresh, EventSub subscription shape/reconnect/revocation and broadcaster binding, AI schema errors/truncation/endpoint validation, and the redacted diagnostic.

## External integration evidence

`python -m storyforge doctor` reported all 13 supported environment settings present and passed their local shape checks. Values were not printed or recorded. This is configuration evidence only.

The final `python -m storyforge doctor --live` run produced these redacted external results:

- **Twitch OAuth API: BLOCKED** — no encrypted host token exists in the local SQLite vault; no actual OAuth callback or authenticated broadcaster was tested.
- **AI provider: FAILED (assistant content field was empty)** — the endpoint returned no narrative text, so no proposal passed `NarrativeProposal` validation or was saved.
- **Application runtime: VERIFIED** — the configured `/health` endpoint and SQLite-backed snapshot responded; EventSub remains **NOT VERIFIED**.
- **EventSub chat delivery: NOT VERIFIED** — no EventSub subscription or real channel message was observed.

Mocked EventSub tests are not live evidence. No actual `!join`, `!persona scholar`, `!trait curious`, or `!vote A` was sent in a Twitch channel. No real AI scene was approved. Browser and OBS verification were unavailable.

## Security and provenance checks

- `.env` and the local SQLite database are ignored and are not tracked in the current Git index. `.env.example` is tracked as a placeholder template.
- A high-confidence credential-pattern scan of tracked working files and reachable Git history found no probable credential values. The scanner suppressed values. This is not a substitute for a full secret scanner.
- `pip-audit` reports no known dependency vulnerabilities, and Bandit reports zero Medium/High findings. Trivy, Gitleaks, and an independent security review remain outstanding; no independent security certification is claimed.
- Manual review covered OAuth state, immutable Twitch identity binding, CSRF, session use, EventSub replay and broadcaster checks, token encryption, prompt boundaries, template escaping, AI request validation, and host-only operations.
- A previous operator audit reports that a `.env` was included in an external ZIP. Treat any credentials present in that archive as exposed and rotate them before release.
- A failing pytest diagnostic exposed a configured secret because the `Settings` dataclass's generated representation included secret fields. The secret fields now use `repr=False`, covered by a sentinel regression. Treat the value visible in the earlier diagnostic output as exposed and rotate it; no value is repeated here.
- The requested Codex `/status` session ID was not available through this execution interface. A local session-index identifier is not accepted as a substitute.
- The `.git` directory is mounted read-only. Git commit creation failed with `Unable to create ... .git/index.lock`; these changes are not committed or pushed.

## Reproduction commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest --cov=storyforge --cov-report=term-missing -q tests -k 'not test_host_authorization_and_csrf and not test_end_to_end_web_demo and not test_public_routes_do_not_expose_host_mutations'
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
.venv/bin/mypy src/storyforge
.venv/bin/python -m compileall -q src
.venv/bin/python -m pip check
.venv/bin/python -m storyforge doctor
.venv/bin/python -m storyforge doctor --live
```

The final full-suite evidence was collected with Python 3.14.7 using the commands in the Nov 2 follow-up table. The clean Python 3.13.15 dependency installation passed; a separate full test run in that environment was not performed. Re-run the suite after any further source or test changes.
