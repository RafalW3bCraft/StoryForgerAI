# Test and verification report

**Run date:** 2026-11-02 UTC
**Checkout:** `main`; latest verified source/test commit `5c6b54946fbcdef2b3573618bf0b55070ac8581b`
**Runtime:** Linux, Python 3.14.7. The project declares Python 3.12+.
**Key installed versions:** FastAPI 0.162.0, Starlette 1.10.0, SQLAlchemy 2.1.6, Pydantic 2.14.2, cryptography 50.0.2, httpx 0.28.1, httpx2 2.16.0 (installed in the environment but no longer required by project tests), websockets 17.4, pytest 9.2.0, pytest-cov 7.1.0, Ruff 0.17.3, mypy 2.4.1.

## Nov 2 follow-up: OAuth origin and runtime diagnostics

The starting checkout was `d6aa6ff7fce8ce2b82bcba05d6c42cb183d1a874`. Prior fixes are committed locally; the two operator-provided untracked audit/prompt files remain untouched. The AI fix and regression are in commit `5c6b54946fbcdef2b3573618bf0b55070ac8581b`. Python 3.14.7 was used for the checks below.

| Check | Current result | Evidence |
|---|---|---|
| OAuth origin regressions | **PASS** | `.venv/bin/python -m pytest -q tests/test_app.py -k 'all_off_origin or oauth_token_exchange_failure or twitch_oauth_login or host_oauth_callback or app_runner'`: **6 passed, 17 deselected**. |
| Full regression suite | **PASS** | `timeout 45s .venv/bin/python -m pytest -q -o faulthandler_timeout=10` outside the sandbox after the AI fix: **69 passed in 5.88s**. |
| Full coverage | **PASS** | `timeout 45s .venv/bin/python -m pytest --cov=storyforge --cov-report=term-missing -q -W error::ResourceWarning` outside the sandbox: **69 passed**, **84% total coverage**, no ResourceWarnings. |
| AI integration and diagnostic tests | **PASS** | `.venv/bin/python -m pytest -q tests/test_integrations.py -k ai_provider`: **4 passed, 11 deselected**; `.venv/bin/python -m pytest -q tests/test_diagnostics.py -k live_ai_diagnostic`: **4 passed, 10 deselected**. |
| Sandbox-bound test run | **BLOCKED (environment only)** | A sandbox-bound run stalls when FastAPI dispatches synchronous routes through AnyIO's worker queue. The same full suite passes outside the sandbox; no application handler was moved onto the event loop. |
| Ruff, formatting, mypy, compileall, pip check | **PASS** | Final runs passed in the Python 3.14.7 environment after all source/test changes. |
| Dependency vulnerability audit | **PASS, dependencies only** | `pip-audit 2.10.1` initially found seven advisories in `cryptography 47.0.0`; the dependency floor was raised to `50.0.2`. Reruns against the clean Python 3.13 install and current `.venv` report no known vulnerabilities. The local `ai-storyforge` package is skipped because it is not published on PyPI. |
| Bandit source scan | **PASS for Medium/High** | Bandit 1.9.4 reported zero Medium/High findings. Its 13 Low findings were reviewed: deterministic cosmetic randomness, the live-rejected demo sentinel, diagnostic field/help labels, and a fixed-argv subprocess with no shell and a timeout. The two Medium SQL-string findings from the first run were removed by using a fixed-name main-database table inside a rolled-back transaction. |
| Redacted local doctor | **PASS, local only** | All 13 recognized variable names and roles were printed without values; each local validation passed and the SQLite write probe passed. |
| Twitch OAuth | **PASS** | `.venv/bin/python -m storyforge doctor --probe twitch`: **VERIFIED (host token and broadcaster identity)**. The current `APP_BASE_URL` is `http://localhost:8000`; the login route's generated `redirect_uri` was verified as `http://localhost:8000/auth/callback`. |
| AI provider | **PASS** | `.venv/bin/python -m storyforge doctor --probe ai`: **VERIFIED (live response passed `NarrativeProposal` validation)** after the provider-specific fix. |
| Live app health | **PASS** | `GET http://localhost:8000/health`: HTTP 200, `twitch=LIVE_TWITCH`, `eventsub_subscribed=true`, `ai_last_generation=VERIFIED`; no real chat message has been seen. |
| Persisted AI story and host approval | **PASS** | Read-only SQLite check: `generation_status=AI-GENERATED`, story stage `VOTING`, current canonical node provenance `AI`, `is_canon=true`. No narrative text was printed. |
| Clean Python 3.13 dependency install | **PASS** | Installed `.[dev]` into `/tmp/storyforge-py313-venv`; `pip check` passed. The environment's event-loop/thread bridge still timed out independently of StoryForge. |

The prior OAuth issue included an HTTPS request to a plain-HTTP listener and a stale running process using `127.0.0.1` while `.env` now specifies `localhost`. The app was restarted from the current configuration; it prints `http://localhost:8000`. The registered and generated callback is `http://localhost:8000/auth/callback`. `ConfiguredOriginMiddleware` redirects off-origin HTTP requests to the fixed `APP_BASE_URL`; TLS sent to this plain HTTP listener fails before ASGI and cannot be redirected. The subsequent redacted Twitch probe now verifies the encrypted host token and broadcaster identity.

The earlier sandbox-bound attempt stalled in the execution host's AnyIO worker bridge. The final complete run outside that sandbox passed all 68 tests, including the three HTTP acceptance tests, so the suite is no longer blocked. StoryForge keeps synchronous SQLite handlers on FastAPI's normal worker-dispatch path.

The dependency audit found seven advisories in the previous `cryptography 47.0.0` pin, whose `<48` ceiling prevented patched versions from being installed. `pyproject.toml` now requires `cryptography>=50.0.2,<51`; the project and ignored environments were reinstalled, the full suite passed outside the sandbox, and the repeated audit reported no known dependency vulnerabilities. `httpx2>=2,<3` was briefly added to the dev extra to test Starlette's current TestClient adapter; it removed a deprecation warning but did not fix the worker stall, so it was removed after the HTTP tests moved to `httpx.AsyncClient`.

The first Bandit scan raised two Medium B608 findings on the diagnostic's f-string table names. The identifier came from a UUID and was not controllable by users, but the probe now uses a fixed-name main-database table inside a transaction that is rolled back, removing dynamic SQL and the findings while still testing database write access. The remaining Low findings were reviewed as false positives for this app's usage; the full scan with `--ignore-nosec` found zero Medium/High issues.

An earlier pre-fix `doctor --live` run found no host token and an empty model response. That state was superseded: the current redacted `doctor --probe twitch` verifies the host token and broadcaster identity, and `doctor --probe ai` verifies a real response against `NarrativeProposal`. The running app health now reports an active Twitch connection and accepted EventSub subscription. No real chat message has been observed and no scene has yet been saved through Host Studio or host-approved.

## Nov 2 follow-up: Featherless Qwen empty content

The live failure reproduced as an HTTP-success response with an empty assistant `content` field. Configuration inspection, with secrets withheld, identified `api.featherless.ai/v1` and `Qwen/Qwen3.8-27B`. A bounded real request using Featherless's `chat_template_kwargs: {"enable_thinking": false}` returned non-empty output (`finish_reason=stop`, 892 content characters); the full StoryForge probe then passed `NarrativeProposal` validation. Featherless documents this switch for reasoning models in its [chat-template kwargs guide](https://featherless.ai/docs/chat-template-kwargs).

Added the option only for Featherless-hosted Qwen3 model IDs; other OpenAI-compatible providers retain their original payload. The new regression failed before the fix because the request omitted `chat_template_kwargs`, then passed after the fix. Verification: AI integration tests **4 passed**, AI diagnostic tests **4 passed**, full suite **69 passed**, coverage **84%**, Ruff/format/mypy/compile passed. After restart, Host Studio saved and approved a live proposal. A read-only database check confirmed `AI-GENERATED`, `VOTING`, and a canonical node with `AI` provenance. The next live evidence needed is real chat delivery and votes; health still reports no real chat message.

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

The latest separate redacted live probes and app health produced these results:

- **Twitch OAuth API: VERIFIED** — the host token and configured broadcaster identity passed the redacted live doctor.
- **AI provider: VERIFIED** — a real response passed `NarrativeProposal` validation after disabling Featherless Qwen3 thinking mode.
- **Application runtime: VERIFIED** — `/health` returned HTTP 200; Twitch is `LIVE_TWITCH`, EventSub subscription is active, and no real message has yet been observed.
- **Saved AI generation: VERIFIED** — app health and a read-only database check show an `AI-GENERATED` canonical node; the story is in `VOTING` after host approval.

Mocked EventSub tests are not live evidence. No actual `!join`, `!persona scholar`, `!trait curious`, or `!vote A` was sent in a Twitch channel. No real AI scene was approved. Browser and OBS verification were unavailable.

## Security and provenance checks

- `.env` and the local SQLite database are ignored and are not tracked in the current Git index. `.env.example` is tracked as a placeholder template.
- A high-confidence credential-pattern scan of tracked working files and reachable Git history found no probable credential values. The scanner suppressed values. This is not a substitute for a full secret scanner.
- `pip-audit` reports no known dependency vulnerabilities, and Bandit reports zero Medium/High findings. Trivy, Gitleaks, and an independent security review remain outstanding; no independent security certification is claimed.
- Manual review covered OAuth state, immutable Twitch identity binding, CSRF, session use, EventSub replay and broadcaster checks, token encryption, prompt boundaries, template escaping, AI request validation, and host-only operations.
- A previous operator audit reports that a `.env` was included in an external ZIP. Treat any credentials present in that archive as exposed and rotate them before release.
- A failing pytest diagnostic exposed a configured secret because the `Settings` dataclass's generated representation included secret fields. The secret fields now use `repr=False`, covered by a sentinel regression. Treat the value visible in the earlier diagnostic output as exposed and rotate it; no value is repeated here.
- The requested Codex `/status` session ID was not available through this execution interface. A local session-index identifier is not accepted as a substitute.
- Local code/test commit `144e3a3849ace53325211ecd5b77549fdc73ba1e` was created after explicit elevated filesystem approval. No push was performed. The configured remote was not checked for public accessibility.

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
