# Codex engineering log

**Date:** 2026-11-01 UTC
**Primary Codex `/status` ID:** not captured; this execution interface does not expose the primary Codex `/status` command. Do not use a local session-index ID as a substitute.
**Git commit:** latest source/test commit `5c6b54946fbcdef2b3573618bf0b55070ac8581b`; no push. The two operator-provided untracked audit/prompt files remain untouched.
**Starting revision:** `d6aa6ff` on `main`.

The initial AI StoryForge MVP predates this Codex pass and was bootstrapped in its original ChatGPT/container context. This log records only the work performed in the current Codex engineering pass; it does not attribute the original MVP to Codex.

## Work and evidence

### Baseline and security review

- Read repository instructions, the supplied finalization mission, implementation, tests, current docs, and Git state. Preserved the two pre-existing untracked operator prompt/audit files.
- Python 3.14.7 project venv was present. Ruff, formatting, mypy, compilation, and `pip check` passed after the changes.
- The baseline full suite hung at the first `TestClient` test. A bare FastAPI `TestClient` reproduced the same lifespan-startup hang. The host OS also rejected local loopback bind/connect with `Operation not permitted`.
- A Python 3.12.14 interpreter was available, but fresh offline dependency installation failed because FastAPI was not cached and network access was disabled.
- Reviewed OAuth state and identity binding, CSRF/session use, EventSub replay and broadcaster checks, Fernet token storage, AI prompt boundaries and response validation, Jinja escaping, and host-only actions. High-confidence tracked-file/history scanning found no probable credential values after excluding the intentional `.env.example` template. No independent dependency/security scanner was available.

### RED/GREEN cycles

| Change | RED evidence | GREEN evidence |
|---|---|---|
| EventSub broadcaster and subscription acceptance | New notification-boundary test showed missing broadcaster ID was accepted; subscription test showed a non-enabled response was accepted. Both failed before the fix. | Both passed after exact broadcaster/type/version validation and validation of Twitch's HTTP 202 subscription response. Existing reconnect and revocation tests also passed. |
| Redacted environment diagnostic | Two new diagnostic tests failed because `storyforge.diagnostics` did not exist. | Diagnostic tests passed after adding `python -m storyforge doctor`, listing all 13 recognized variables without values and marking external checks `NOT CHECKED`. |
| AI truncation | A valid-looking body with `finish_reason="length"` was accepted; the regression test failed before the fix. | The generator now rejects truncated completion reasons; malformed, empty, valid, and truncated provider tests passed. |
| Live URL validation | New tests showed public HTTP callbacks and nonnumeric Twitch IDs were accepted; both failed before validation was added. | Live config tests passed after enforcing HTTPS except loopback development and requiring numeric matching Twitch IDs. |
| Repeated chat writes | A repeated `!join` wrote another receipt; cooldown regression failed before implementation. | A bounded cross-command cooldown now throttles all recognized commands per viewer; story command and pause/resume tests passed. |
| AI endpoint safety | New test showed userinfo plus a duplicated `/chat/completions` path was accepted; the test failed before the fix. | AI base URL validation now rejects credentials, query/fragment data, and duplicated completion paths; the regression passed. |
| Error-detail redaction | New test showed EventSub error status retained an exception message containing a token-like sentinel; it failed before the fix. | Connector status now exposes only exception type for transient errors; sentinel redaction test passed. |
| OAuth callback route | Direct endpoint tests were added for state mismatch, wrong broadcaster, and successful identity binding. | All three local route tests pass with provider responses mocked; they are not real OAuth evidence. |
| Generation provenance after approval | Review regression failed because approval changed `DEMO-GENERATED` to `APPROVED`. | Removed the status overwrite; proposal/node approval remains recorded and persisted generation provenance survives. Focused test and final targeted suite passed. |
| Chat command abuse | Regressions reproduced cross-command cooldown bypass, invalid-vote spam, cooldown-event replay, and receipts for unknown/info commands. | Applied cross-command viewer cooldown, bounded rejected-ID dedupe, invalid-vote throttling and no-write unknown/info handling; all focused tests pass. |
| Demo route and secret representation | Direct remote-login regression failed because public requests could use demo password; sentinel test showed `Settings.__repr__` included secret fields. | Demo login now requires loopback client/Host; secret fields use `repr=False`. The earlier test failure output contained a configured secret; treat it as exposed and rotate it. |
| Concurrent model requests | A blocking fake provider test showed two simultaneous host retries both reached the generator. | Added an app-instance lock around scene creation and generation; concurrent retry now starts one provider call. This remains single-process protection. |
| Concurrent model requests | A blocking fake provider test showed two simultaneous host retries both reached the generator. | Added an app-instance generation lock covering scene creation/generation; concurrent retry test now observes one provider call. |

The requested ECC red-test checkpoint commit could not be created because `.git` is read-only. No commit reference is claimed. Work remains in the current working tree.

## Final checks

The final review caught a host error-handler exception-variable bug; it was fixed and lint, typing, and targeted tests rerun. Actual commands and results are recorded in `docs/TEST_REPORT.md`. The final targeted run reported **51 passed, 3 deselected**, **76% total coverage**. Full pytest remains blocked by the installed Starlette TestClient/AnyIO worker hang. Ruff, formatting, mypy, compileall, five-template Jinja parsing, and pip dependency consistency passed.

The redacted `doctor --live` run reported Twitch OAuth **BLOCKED** (no encrypted host token), AI provider **FAILED** (bounded probe timed out), and EventSub chat **NOT VERIFIED**. No real Twitch message or live AI scene is claimed.

## Remaining release evidence

- Obtain the actual primary-session `/status` ID.
- Create verifiable Git commits from a writable checkout and push the finished code.
- Run full tests and security/dependency checks in a clean supported environment.
- Verify actual Twitch OAuth/EventSub, real chat commands, real model generation, browser/OBS, YouTube video, repository access, and Devpost submission.

## Nov 2 continuation — OAuth callback 403

**Starting revision:** `d6aa6ff` on `main`; the prior working-tree changes and the two pre-existing untracked operator files were preserved. No Git commit was possible because `.git` is read-only.

### Analysis and reproduction

- The configured local origin was checked without printing its value: it is a `localhost` loopback origin, while the documented local address was `127.0.0.1`. Browser cookies are scoped by hostname, so starting OAuth on one name and receiving the callback on the other omits the signed session cookie containing `oauth_state`.
- RED regression: `test_twitch_oauth_login_rejects_a_different_browser_origin` failed because `/auth/twitch` redirected instead of rejecting the mismatched origin.
- A second RED regression showed that a callback without the session cookie returned the same generic 403 as an invalid state and that an invalid state consumed the pending valid state.

### Fix and verification

- `/auth/twitch` and `/auth/callback` now require the request origin to match configured `APP_BASE_URL`. The guard compares normalized scheme, hostname and port; it does not trust a request host to construct the redirect URI.
- A missing OAuth session cookie now returns an actionable 400; a supplied but incorrect state remains a 403 and does not consume the pending state. Startup prints the configured address, and README/judge instructions now tell the operator to use that exact origin.
- GREEN: `./.venv/bin/python -m pytest -q tests/test_app.py -k 'host_oauth_callback or twitch_oauth_login'` — **3 passed**.
- Broader regression: **57 passed, 3 deselected**. Coverage run with `-W error::ResourceWarning`: **78% total**, no resource warnings.
- Full suite: 60 tests collected; the new origin test passed, then the first existing `TestClient` flow stalled in `TestClient.__enter__`. A bounded 18-second run exited 124; a bare `FastAPI()` `TestClient` reproduces the AnyIO portal stall.
- Ruff, format check, mypy, compileall, `pip check`, and the redacted local doctor passed. Doctor reported SQLite writable and left all remote integrations `NOT CHECKED`.

The current `.env` values were not printed and no live request was made. The audit treats credentials from the earlier archive/test output as exposed; obtain rotated credentials before Twitch or paid model probes. The exact principal Codex `/status` ID remains unavailable through this execution interface; no ID or new commit is claimed.

## Nov 2 continuation — canonical OAuth redirects and log hygiene

- Changed off-origin `/auth/twitch` requests to redirect directly to the configured `APP_BASE_URL/auth/twitch` before creating OAuth state. The callback forwards only `code` and `state` to the fixed configured callback when it arrives on another origin; callback failures return to the configured app home with a generic message rather than a JSON error.
- Retained constant-time comparison and rejection for a supplied state mismatch. Redirect hosts are never built from the incoming Host header.
- Set Uvicorn `access_log=False` so routine access logs omit OAuth callback query values. Added a runner regression and updated the user and judge instructions, threat model, ADR, release evidence, and ECC workflow record.
- RED/GREEN: three new assertions failed on the old origin guard / runner behavior, then the focused OAuth set passed (**4 passed, 17 deselected**).
- Verification: available regression suite **58 passed, 3 deselected**; **78%** coverage; Ruff, formatting, mypy, compileall, pip check, and redacted local doctor passed. `pytest --collect-only -q` found 61 tests. A clean Python 3.13 install passed, and its same partial suite passed. A bounded full run passed the OAuth-origin test, then timed out at `test_host_authorization_and_csrf` while entering `TestClient` (exit 124); installing Starlette's `httpx2` dev adapter did not resolve it. The full suite cannot be claimed green.
- No live API test was run; doctor reported external status `NOT CHECKED`. The patched dependency set was installed in the temporary Python 3.13 environment and current `.venv`; no commit, public upload, or external submission was performed. The primary Codex `/status` ID is still not exposed in this interface.
- Security review found seven `cryptography 47.0.0` advisories with the old `<48` constraint blocking fixes. Raised the runtime floor to `50.0.2`; `pip-audit 2.10.1` reruns on Python 3.13 and current `.venv` reported no known dependency vulnerabilities. The first Bandit run found two Medium B608 findings in the SQLite diagnostic's dynamic table identifier; replaced it with a fixed-name main-database table rolled back inside a transaction, then Bandit reported zero Medium/High findings. Its 13 Low flags were reviewed as false positives for deterministic cosmetic output, labels, the live-rejected demo sentinel, and a fixed-argv subprocess. Added Starlette's `httpx2` TestClient adapter to dev extras; it removes the deprecation warning but does not resolve the AnyIO portal stall. Trivy, Gitleaks, and independent security review remain outstanding.

## Nov 2 continuation — direct canonical app URL and live probe

- Redacted `python -m storyforge doctor` output: all 13 recognized variables passed local shape validation and SQLite's rolled-back write probe passed. `STORYFORGE_MODE` is live; the configured origin is loopback HTTP on port 8000. No values were printed. The user's server output gives the exact URL `http://127.0.0.1:8000`.
- Analysis: the repeated Uvicorn `Invalid HTTP request received` lines are consistent with HTTPS/TLS bytes being sent to this plain HTTP listener. TLS fails before ASGI, so the app cannot redirect those requests. The built-in runner now prints a plain-HTTP instruction; README/Judge Testing state to use the printed URL as-is. Public HTTPS requires a TLS reverse proxy.
- Added `ConfiguredOriginMiddleware`, a pure ASGI boundary that redirects every HTTP request from a different scheme/host/port to fixed `APP_BASE_URL` before session cookies are evaluated, preserving path and query and never trusting the incoming Host. Its regression confirms an off-origin request reaches the configured location with no JSON detail response.
- Added safe OAuth callback diagnostics: an HTTP status or exception type may be shown/logged, never the one-time code, response body, token, or provider URL. A mocked HTTP 400 regression confirms this boundary. This does not claim a successful live callback.
- Live doctor: Twitch is blocked because the SQLite vault has no encrypted host token; AI generation timed out; app `/health` returned `ConnectError`; EventSub and real chat remain unverified. No real `!join`, `!persona`, or `!vote` was received.
- Regression evidence: focused OAuth/origin cases **6 passed, 17 deselected**. Runnable suite **60 passed, 3 deselected**, **78% coverage**. The 63-test full run is still blocked: after two passes, a sync FastAPI route waits on the AnyIO worker queue. Bare `FastAPI()` TestClient and `asyncio.to_thread()` also hang; a plain thread and `ThreadPoolExecutor` succeed. The three HTTP tests now use HTTPX async ASGI transport, but the environment still cannot execute sync route dispatch. Sync app handlers were preserved.
- Verification after changes: Ruff check/format, mypy (12 source files), compileall, pip check, pip-audit (no known vulnerabilities), Bandit Medium/High (zero findings), and `git diff --check` pass. No public push or Devpost action occurred. `.git` is read-only, and the actual Codex `/status` session ID remains unavailable.

## Nov 2 final verification update

- Full suite outside the sandbox: `timeout 45s .venv/bin/python -m pytest -q -o faulthandler_timeout=10` — **68 passed in 3.35s**. Coverage: `timeout 45s .venv/bin/python -m pytest --cov=storyforge --cov-report=term-missing -q -W error::ResourceWarning` — **68 passed, 84% total**, no ResourceWarnings. This supersedes the earlier partial-suite and worker-stall checkpoints above.
- Static/dependency/security commands passed: `.venv/bin/ruff check src tests`; `.venv/bin/ruff format --check src tests`; `.venv/bin/mypy src/storyforge`; `.venv/bin/python -m compileall -q src`; `.venv/bin/python -m pip check`; `/tmp/storyforge-py313-venv/bin/python -m pip_audit --skip-editable`; `/tmp/storyforge-py313-venv/bin/bandit -r src --ignore-nosec --severity-level medium --confidence-level medium -q`; `git diff --check`. Bandit reported no Medium/High findings; pip-audit reported no known vulnerabilities for audited dependencies.
- Final redacted `python -m storyforge doctor --live`: Twitch OAuth **BLOCKED** (no encrypted host token); AI **FAILED** because assistant content was empty; application runtime and database-backed snapshot **VERIFIED**; EventSub/chat **NOT VERIFIED**; saved provider generation **NOT GENERATED**. No actual `!join`, `!persona`, or `!vote` succeeded in evidence. A separate read-only Twitch authorize endpoint request returned HTTP 302, without user consent or token exchange.
- The configured startup address is plain HTTP `http://127.0.0.1:8000`; the exact local callback is `http://127.0.0.1:8000/auth/callback`. TLS bytes sent to this plain HTTP listener can cause Uvicorn's `Invalid HTTP request received` warnings before the request reaches StoryForge. Use the printed HTTP address locally; HTTPS needs a TLS reverse proxy.
- The genuine primary Codex `/status` session ID was unavailable. Native ECC plugin is not installed; cached ECC workflow guidance was applied and documented. Local code/test commit `144e3a3849ace53325211ecd5b77549fdc73ba1e` was created after explicit elevated filesystem approval; no push was performed. The untracked operator prompt and audit files remain untouched. No video or Devpost submission exists.

## Nov 2 live AI generation repair

- Reproduced the live model failure with `.venv/bin/python -m storyforge doctor --probe ai`: Featherless returned HTTP success but an empty assistant `content` field. Effective redacted model configuration identified the Featherless API and `Qwen/Qwen3.8-27B`; no API key or generated text was logged.
- A bounded provider request with `chat_template_kwargs: {"enable_thinking": false}` returned a stopped completion with non-empty content. Featherless documents `enable_thinking` as a reasoning/template control. Added it only for Featherless-hosted Qwen3 model IDs; other OpenAI-compatible request payloads remain unchanged.
- RED/GREEN: `test_featherless_qwen_disables_thinking_for_final_narrative` failed before the fix because the request omitted the option; after the fix it passed. The live full-prompt doctor probe now reports **AI provider: VERIFIED** with `NarrativeProposal` validation.
- Additional live check: `.venv/bin/python -m storyforge doctor --probe twitch` reports **VERIFIED** host token and broadcaster identity. Restarted StoryForge at `http://localhost:8000`; `/health` returns 200, `LIVE_TWITCH`, and an active EventSub subscription. No real chat message has been seen; `/health` still reports `ai_last_generation=NOT GENERATED` until Host Studio saves a proposal.
- Verification after the fix: full suite **69 passed**; coverage **84%** with `-W error::ResourceWarning`; AI integration tests **4 passed**, AI diagnostic tests **4 passed**; Ruff, format, mypy, and compileall passed. Code/test commit: `5c6b54946fbcdef2b3573618bf0b55070ac8581b`; no push.
