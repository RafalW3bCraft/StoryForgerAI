# Final StoryForge evidence report

**Evidence captured:** 2026-11-02 through 09:03 UTC

**Working directory:** `/mnt/hostname/ai-storyforge`

**Audited base:** `main` at `44fa0f4b33804826c78947ac781799a13f7f3940`; `git fetch --prune origin` completed and `origin/main` matched this SHA before the finalization changes.

**Python:** default system Python 3.14.7; required verification ran in isolated Python 3.13.15 at `/tmp/storyforge-py313-venv`.

**Tested source/test commit:** `9a36319112e8fd83200abcc2b43c81861176d183` (`Harden live StoryForge integration and finalize evidence`). The two operator-owned untracked files remain untouched. Remote publication and judge access must be verified separately after push.

The operator's pre-existing `StoryForgerAI_Codex_ECC_Finalization_Prompt.md` and `StoryForgerAI_Verified_Audit_2026-11-01.md` files were preserved and excluded from engineering staging. No secrets or database files were intentionally read into output or added to Git.

## Automated engineering evidence

| Check | Exact command | Result |
|---|---|---|
| Install | `/tmp/storyforge-py313-venv/bin/python -m pip install -e '.[dev]'` | PASS, exit 0; clean isolated Python 3.13.15 environment. |
| Full tests | `/tmp/storyforge-py313-venv/bin/python -m pytest -q -o faulthandler_timeout=15` | PASS, exit 0; **76 passed in 8.06s**. |
| Coverage/resources | `/tmp/storyforge-py313-venv/bin/python -m pytest --cov=storyforge --cov-report=term-missing -q -W error::ResourceWarning` | PASS, exit 0; **76 passed in 10.66s; 85% total coverage**, no ResourceWarning. |
| Ruff | `/tmp/storyforge-py313-venv/bin/python -m ruff check src tests` | PASS, exit 0. |
| Formatter | `/tmp/storyforge-py313-venv/bin/python -m ruff format --check src tests` | PASS, exit 0; 19 files already formatted. |
| Types | `/tmp/storyforge-py313-venv/bin/python -m mypy src/storyforge` | PASS, exit 0; 12 source files. |
| Compilation | `/tmp/storyforge-py313-venv/bin/python -m compileall -q src` | PASS, exit 0. |
| Dependency consistency | `/tmp/storyforge-py313-venv/bin/python -m pip check` | PASS, exit 0; no broken requirements. A local pip cache permission warning was emitted. |
| Dependency audit | `/tmp/storyforge-py313-venv/bin/python -m pip_audit --skip-editable` | PASS, exit 0; no known vulnerabilities among audited distributions; editable project skipped. |
| Static security | `/tmp/storyforge-py313-venv/bin/python -m bandit -r src --ignore-nosec --severity-level medium --confidence-level medium -q` | PASS, exit 0; no Medium/High findings. |
| Whitespace/conflict check | `git diff --check` | PASS, exit 0. |
| 50-event worker test | `/tmp/storyforge-py313-venv/bin/python -m pytest -q tests/test_integrations.py::test_eventsub_chat_processing_does_not_block_event_loop_during_burst` outside the sandbox | PASS, **1 passed in 0.46s**. Processed all 50 simulated IDs in order while the event-loop heartbeat completed. |
| Tracked history signature scan | Custom `git grep` scan across all 6 commits for high-confidence API-token and credential-assignment patterns | PASS, 0 matches. `.env` is ignored; no `.env` or database file is tracked. Gitleaks is not installed, so this is a limited scan. |

The same 50-event test hung inside the restricted sandbox's worker-thread wakeup path and was interrupted (exit 130). The complete test suite and coverage both passed outside the sandbox. This is a test-environment constraint, not evidence of a production runner result.

GitHub Actions configuration is present at `.github/workflows/ci.yml`, with Python 3.12/3.13, least-privilege contents permissions, concurrency cancellation, timeout, full tests, coverage, Ruff, formatting, mypy, compile, pip check, pip-audit and Bandit. The workflow file is not a passing CI run; no run on the final pushed SHA has yet been observed.

## Configuration and security diagnostics

`/tmp/storyforge-py313-venv/bin/python -m storyforge doctor` listed all 13 supported environment variable names with values redacted. Local shape checks passed for live settings; `DEMO_ADMIN_PASSWORD` was marked `NOT USED IN LIVE MODE`; the SQLite write probe passed. The secret-strength check is a local heuristic, not proof of secret provenance.

| Variable | Local result | External result | Evidence / limit |
|---|---|---|---|
| `STORYFORGE_MODE` | LOCALLY VALID | Not applicable | Live mode selected. |
| `STORYFORGE_DATABASE` | LOCALLY VALID | Not applicable | SQLite write transaction passed; DB is now owner-only mode `0600`. Backup/restore is not tested. |
| `STORYFORGE_SECRET` | LOCALLY VALID | Not applicable | Local strength heuristic passed; rotate if it appeared in prior shared material. |
| `DEMO_ADMIN_PASSWORD` | NOT USED IN LIVE MODE | Not applicable | Live mode denies demo-password host login. |
| `APP_BASE_URL` | LOCALLY VALID | BLOCKED / NOT VERIFIED | Loopback origin validated and host OAuth route generated the matching `/auth/callback`; exact Twitch Console registration and a fresh callback were not independently verified. |
| `TWITCH_CLIENT_ID` | LOCALLY VALID | EXTERNALLY VERIFIED | Live Twitch probe succeeded with configured client ID. |
| `TWITCH_CLIENT_SECRET` | LOCALLY VALID | BLOCKED / NOT VERIFIED | Existing vault token does not test the current secret; no fresh OAuth code exchange occurred. |
| `TWITCH_BROADCASTER_ID` | LOCALLY VALID | EXTERNALLY VERIFIED | Live user identity matched the configured broadcaster. |
| `TWITCH_READER_ID` | LOCALLY VALID | EXTERNALLY VERIFIED | Live EventSub subscription used the configured reader condition. |
| `TOKEN_ENCRYPTION_KEY` | LOCALLY VALID | EXTERNALLY VERIFIED | Encrypted host token decrypted and was used for the live identity probe. Rotation requires token migration or new OAuth. |
| `AI_BASE_URL` | LOCALLY VALID | EXTERNALLY VERIFIED | Live provider request succeeded. |
| `AI_API_KEY` | LOCALLY VALID | EXTERNALLY VERIFIED | Live provider accepted the configured key; the value was not shown. |
| `AI_MODEL` | LOCALLY VALID | EXTERNALLY VERIFIED | A real response passed the `NarrativeProposal` schema. |

The local `.env` and SQLite files were observed as `0644`; they were changed to `0600`. A startup helper now applies POSIX owner-only mode to file-backed SQLite databases, and the doctor probe uses the same helper. The previous ZIP may have exposed `.env`, and an earlier diagnostic/test failure printed a configured secret. Rotate affected Twitch, AI, session, demo and Fernet credentials before public release; preserve/re-authorize the encrypted host token before retiring its Fernet key.

## Real Twitch, AI, story and browser evidence

`/tmp/storyforge-py313-venv/bin/python -m storyforge doctor --live` completed with exit 0 and reported:

- **Twitch OAuth API: VERIFIED** — existing encrypted broadcaster token and Twitch identity.
- **TWITCH_CLIENT_SECRET: NOT VERIFIED** — no authorization-code exchange was performed.
- **AI provider: VERIFIED** — live response passed `NarrativeProposal` validation after the exact choice-type prompt repair.
- **Application runtime: VERIFIED** — health endpoint and database-backed snapshot responded.
- **Twitch EventSub subscription: VERIFIED** — active `channel.chat.message` WebSocket subscription.
- **Last real Twitch chat event: NOT VERIFIED.**
- **Saved AI generation: VERIFIED.**

The running app was restarted with the final source and then returned HTTP 200 from `/health`, `mode=live`, `twitch=LIVE_TWITCH`, `eventsub_subscribed=true`, and `ai_last_generation=VERIFIED`. At that check, `last_real_chat_event_seen=false` and all notification/accepted/ignored/cooldown/invalid/duplicate/error counters were zero.

A read-only snapshot after restart confirmed persistence of the existing active story: stage `REVIEW`, generation status `AI-GENERATED`, canonical node provenance `AI`, and active AI proposal status `PENDING`. Counts were one host persona, zero viewer personas, seven persona revisions, zero chat receipts, and zero votes. The pending proposal is preserved and has not been approved by this audit.

Read-only HTTP route checks against the restarted app:

| Route | Result | Notes |
|---|---|---|
| `/` | 200 HTML | CSP header present. |
| `/host` | 403 JSON | Expected without host session; CSP present. |
| `/profile` | 403 JSON | Expected without Twitch viewer session; CSP present. |
| `/overlay` | 200 HTML | CSP present. No real visual browser or OBS capture. |
| `/graph.svg` | 200 SVG | CSP present. |
| `/health` | 200 JSON | Aggregate redacted status only. |
| `/auth/twitch?role=host` | 307 | Generated callback matched the configured origin; no grant/token exchange. |
| `/auth/callback` with synthetic access-denied state | 303 | Safe redirect to configured origin; no JSON detail response. |

No actual `!join`, `!persona`, `!trait`, `!avatar`, `!vote`, contribution, two-viewer vote, or canonical branch transition has been verified. StoryForge does not reply in Twitch chat; verify commands through the redacted counters, persisted state, Host Studio and `/overlay`. The mock 50-event burst is not a substitute. No real OBS Browser Source, 1920×1080 capture, or YouTube footage was produced.

## Codex, ECC, provenance and submission

- The current Codex work materially changed the model prompt, EventSub processing/telemetry, configuration loading and validation, SQLite permissions, tests, CI, and release documentation. The working tree and ensuing Git commits are the provenance evidence; do not attribute the original pre-existing MVP to this pass.
- Codex CLI 0.166.0 was available. The genuine primary-thread session ID cannot be obtained through this interface; it must come from `/status` in that Codex thread.
- ECC native plugin was not installed/registered. Previously documented ECC skill guidance and the manual RED/GREEN/security loop are not native plugin evidence.
- The first Git commit falls inside the submission period, while the existing MVP predates this Codex pass. The timestamp alone cannot establish the official “newly created” criterion; organizer interpretation is required.
- No valid under-three-minute public/unlisted YouTube demo exists. No Devpost entry is known to have been submitted. Only the operator can complete and verify the final Devpost **Submit** action.

## Evidence status table

| Requirement | Status | Cause, correction, and evidence needed |
|---|---|---|
| Python-only architecture and tests | PASS | 76 tests, 85% coverage; no custom JS/TS added. |
| Secure redacted configuration | PARTIAL PASS | All 13 names checked; values withheld; `.env` and DB now `0600`. Rotate any previously exposed credentials. |
| Stored Twitch host identity | PASS | Live token decrypt and broadcaster identity verified. |
| Fresh Twitch OAuth/client secret | BLOCKED | Requires operator browser authorization with current secret; capture successful token exchange without exposing code. |
| Active EventSub subscription | PASS | Live probe and health show enabled subscription. |
| Real EventSub chat delivery | BLOCKED | Counters/receipts remain zero; two real viewers must issue standalone commands. |
| Real persona and vote state | BLOCKED | Zero viewer personas, receipts, and votes; verify two identities, revisions, votes, and a canonical successor. |
| Live model response | PASS | Actual response passed Pydantic schema. |
| Current proposal approval/branch flow | BLOCKED | AI proposal remains `PENDING` in `REVIEW`; host approval and real vote required. Existing AI canonical provenance persisted after app restart. |
| Browser/OBS and demonstration | BLOCKED | HTTP routes pass; no visual OBS capture/video. |
| Dependency and Bandit scans | PASS, scoped | pip-audit clean for audited packages; no Bandit Medium/High. Trivy/Gitleaks/independent security review not run. |
| GitHub final revision / CI | BLOCKED pending publication | Need final push, exact `ls-remote` SHA/public-page check, and a passing Actions run on that SHA. |
| Genuine Codex ID / ECC | BLOCKED / PARTIAL | `/status` ID unavailable; ECC plugin absent. |
| Eligibility / video / Devpost | BLOCKED / FAIL | Need organizer interpretation, <3-minute public/unlisted video, and actual Submitted status. |
| Production operations | FAIL | No TLS deployment, restore drill, migration/rollback, distributed concurrency, operational monitoring or independent security assessment. |

The official [rules](https://twitchcon-codex.devpost.com/rules) state a 2:00 PM Pacific deadline on November 2, while the [FAQ](https://twitchcon-codex.devpost.com/resources) says 9:00 PM UTC. Use the earlier 21:00 UTC interpretation and the live Devpost countdown. Do not assume saving a draft submits the project.

**HACKATHON SUBMISSION READY: NO**

**PRODUCTION READY: NO**
