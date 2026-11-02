# AI StoryForge release gate report

**Assessment date:** November 2, 2026 (latest live smoke check 11:00 UTC)

**Audited baseline:** `44fa0f4b33804826c78947ac781799a13f7f3940` on `main`

**Tested code/test commit:** `9a36319112e8fd83200abcc2b43c81861176d183` (`Harden live StoryForge integration and finalize evidence`), committed at 2026-11-02 09:06:41 UTC; included in the published release snapshot below.

**Published release snapshot:** `4ef8e3ea16a0562df9a66e1b42ece05242d48449`; public GitHub API returned HTTP 200 and `private=false`, the repository page returned HTTP 200, `git ls-remote` matched this SHA, and GitHub Actions run [`41419869542`](https://github.com/RafalW3bCraft/StoryForgerAI/actions/runs/41419869542) succeeded for both Python 3.12 and 3.13 matrix jobs. Later documentation-only commits may advance `main` without changing the tested source.

**Latest verified main at 09:26 UTC:** `9e6a514b951aa81b0155b88f619c52c11f4255e9`, documentation-only after the release snapshot above. GitHub Actions run [`41420537063`](https://github.com/RafalW3bCraft/StoryForgerAI/actions/runs/41420537063) passed on that exact SHA for both Python 3.12 and 3.13.

**Latest live chat evidence:** after correcting Twitch's EventSub `notification` type, a real health snapshot at 10:44 UTC showed 17 received messages, 7 accepted commands, 9 ignored, 1 invalid, and 8 replies confirmed by Twitch (`is_sent=true`), with zero processing/send errors or drops. The operator was chatting from the broadcaster account, so this does not prove a second viewer persona or voting. The host inbox and AI responder below are new local changes and need a restart/new message before their live UI can be exercised. No real AI chat response is claimed.

**Restarted app smoke check:** at 11:00 UTC `/health` returned `LIVE_TWITCH`, `eventsub_subscribed=true`, `chat_reply_status=READY`, and `ai_last_generation=VERIFIED`. Counters are zero in the fresh process. A no-cookie request to `/host/chat` returned 403 and `/overlay` returned HTTP 200 HTML. A new real chat message is required to verify the new inbox with live data; no AI-generated Twitch reply is claimed.

**Current source state:** implementation/test commit `5e33a5ed201e98c061447f2a3497c0387d59f3de` is on local `main`; the evidence-document follow-up is being committed separately. Latest fetched `origin/main` is `e4c526934fc529d7e9d96cab3560530c874f7dd3`; neither local commit is pushed yet. The last verified remote CI remains run `41420537063` on `9e6a514b951aa81b0155b88f619c52c11f4255e9`.

**Remote comparison:** `git fetch --prune origin` succeeded; latest fetched `origin/main` is `e4c526934fc529d7e9d96cab3560530c874f7dd3`. Local `main` is ahead by the EventSub fix and host inbox commits; current CI on `e4c526…` has not been independently checked.

**Decision:** **NOT READY** for hackathon submission or production.

This report supersedes older release decisions in the dated records below. The implementation changes and tests described here were checked in the live checkout. The two pre-existing operator files `StoryForgerAI_Codex_ECC_Finalization_Prompt.md` and `StoryForgerAI_Verified_Audit_2026-11-01.md` were preserved and not included in engineering changes.

## Evidence summary

| Area | Result | Evidence |
|---|---|---|
| Python architecture | PASS | Python 3.12/3.13 application matrix; Python modules, Jinja2, CSS and Python-generated SVG only. No application JavaScript or TypeScript added. |
| Automated checks | PASS locally | Python 3.13.15 final run results are recorded in `docs/TEST_REPORT.md`; `ResourceWarning` is treated as an error; Ruff, formatter, mypy, compileall, `pip check`, pip-audit and Bandit Medium/High passed. |
| Install and runtime configuration | PASS locally | `python -m pip install -e '.[dev]'` succeeded in the isolated Python 3.13.15 environment. `doctor` listed all 13 variables without values; local validations and the SQLite write probe passed. |
| Local file permissions | PASS after fix | Existing `.env` and SQLite files were mode `0644`; they are now `0600`. New file-backed databases and the doctor probe enforce owner-only POSIX mode. Regression tests pass. |
| Twitch host identity | PASS, limited | `doctor --live` verified the encrypted stored host token and broadcaster identity. This does **not** validate the currently configured client secret through a new authorization-code exchange. |
| Twitch EventSub | PASS, subscription and broadcaster receive | Live probe/health confirmed `channel.chat.message`; 17 real notifications reached the handler. The protocol uses `channel.chat.message` v1 and `user:read:chat` scope as specified by [Twitch's subscription documentation](https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types). |
| Real Twitch chat | PASS for broadcaster receive/reply | Live health at 10:44 UTC: 17 notifications, 7 accepted, 9 ignored, 1 invalid, 8 Twitch-confirmed replies; zero processing errors, send failures, or drops. Two-viewer persona/vote behavior remains unverified. |
| AI provider | PASS, live probe | A real configured-model response passed `NarrativeProposal` validation. Prompt now specifies an exact JSON structure with two or three plain-string choices. |
| Story persistence and host approval | PARTIAL | Read-only SQLite check after live chat: 1 broadcaster/host persona, 4 durable chat receipts, 0 votes, story stage `REVIEW`, and four AI-provenance canonical nodes. The broadcaster's `!join` reuses the host identity; a second viewer is needed to verify a distinct viewer persona and voting. |
| Browser and OBS | PARTIAL | Host inbox and CSRF-protected AI toggle pass HTTP tests; live app returns 403 to unauthenticated `/host/chat` and 200 to `/overlay`. Chat markup is escaped and excluded from `/health` and `/overlay`. No authenticated browser or visual OBS capture at 1920×1080 exists. |
| Security/dependency checks | PARTIAL PASS | pip-audit found no known vulnerabilities among audited dependencies; Bandit reported no Medium/High findings. A high-confidence credential-signature scan of all 6 Git commits found 0 matches; `.env` is ignored and no `.env`/database file is tracked. Gitleaks, Trivy, and an independent security review are unavailable/not run. |
| Git source and CI | PARTIAL | Public repository and earlier CI are verified; run `41420537063` passed on `9e6a514…` for Python 3.12/3.13. Fetched `origin/main` is now `e4c526…`; its CI result is not checked, and local commit `5e33a5e…` has no remote CI yet. |
| Codex contribution | PARTIAL | This Codex pass made material code, regression-test, workflow and documentation changes. The primary-thread `/status` ID is not available to this tool interface and is still required. |
| ECC | PARTIAL, guidance only | Earlier documented ECC skill guidance was applied as recorded in `docs/ECC_WORKFLOW.md`; this active environment did not provide the native ECC plugin. No plugin execution is claimed. |
| New-project eligibility | BLOCKED / organizer interpretation needed | The repository's first commit falls in the event period, but the StoryForge MVP predates this Codex pass. A commit timestamp alone does not establish that the project was newly created during the submission window. |
| YouTube and Devpost | FAIL / not complete | No qualifying public or unlisted YouTube video and no submitted Devpost entry were available. A saved draft is not a submission. |

## Reproduced defects and corrections

| Defect | Reproduction and correction | Verification |
|---|---|---|
| Live EventSub chat messages were ignored | The app checked for `session_notification`, but Twitch documents EventSub event deliveries as `notification`. Updated the handler and mock envelopes to use the actual protocol value. | RED regression with `notification` left the reply queue empty before the fix; after the fix, the full suite passed 96 tests and the live app received 17 messages and sent 8 Twitch-confirmed replies. |
| Live model returned a JSON object with invalid choice item types | The provider responded HTTP 200, but `choices` contained objects rather than `NarrativeProposal`'s required strings. The prompt now gives an exact JSON example and says each choice must be a plain string. | Live `doctor --live` returned `AI provider: VERIFIED`; response passed `NarrativeProposal`. Prompt regression is included in the 76-test run. |
| Synchronous SQLite/service work could block the EventSub event loop | `consume()` called synchronous `process_chat()` in its async receive loop. It now awaits that call through `asyncio.to_thread`, one notification at a time, preserving order. | 50-event simulated burst regression passed outside the sandbox; IDs were processed in order, all 50 had accepted outcomes, and the event-loop heartbeat completed first. This is not real chat evidence. |
| Malformed EventSub payload shapes could raise before boundary checks | Added dictionary/type checks at metadata, payload, subscription, event and message boundaries. | Malformed envelope and duplicate receipt regression passed. |
| Live mode could silently run without a configured AI provider | Live settings now fail validation unless all three AI settings are present; importing settings no longer loads `.env` as a module side effect. | Configuration and app regressions pass; `doctor` distinguishes present/local validity from external checks. |
| `.env` and SQLite data were group/world readable | Restricted the existing files and added an owner-only SQLite file setup used by application startup and the diagnostic write probe. | Existing-file doctor test and new-database test pass; observed modes are `0600`. |
| Diagnostics could imply real chat success from subscription alone | `/health` exposes aggregate notification and outcome counters without chat text or Twitch IDs. | Health regression confirms redaction; latest real counter snapshot is 17 notifications, 7 accepted, 8 sent. |

## Gate decisions

| Gate | Status | Cause and evidence needed to close |
|---|---|---|
| A — Install, tests, type/lint/dependencies | PASS | Python 3.13.15 clean dev install and full checks recorded in `docs/TEST_REPORT.md`. Actions run `41420537063` passed on latest verified main `9e6a514…` for Python 3.12 and 3.13. |
| B — 13 runtime variables and live probes | PARTIAL | Redacted local check passed. Twitch host token/identity, EventSub subscription, and AI response are externally verified. A fresh OAuth exchange to validate `TWITCH_CLIENT_SECRET`, actual redirect registration, and full production database backup/restore are not verified. |
| C — Real Twitch chat and voting | PARTIAL | Real broadcaster messages reached the app and two acknowledgments were accepted by Twitch. Need two distinct viewers, persona edits, votes, and canonical transition. |
| D — AI story end to end | PARTIAL | Real model response and persisted AI provenance are evidenced; current AI proposal is pending in `REVIEW`. Host approval, real vote resolution, second-scene continuity, and cross-restart live workflow remain incomplete. |
| E — Browser and OBS | PARTIAL | Host inbox routes, escaping, health privacy, and overlay isolation pass automated HTTP tests. Need real browser/OBS 1920×1080 visual evidence. |
| F — Production security/operations | FAIL | No independent assessment, HTTPS deployment, backup/restore drill, rotation/migration, deployment/rollback exercise, cross-process coordination, or operational monitoring evidence. Single-process SQLite remains the supported MVP profile. |
| G — Hackathon submission package | FAIL | Public source and CI are verified. Need live two-viewer Twitch/OBS demo, genuine `/status` ID, YouTube video under 3 minutes, eligibility determination, complete Devpost form and final **Submit** verification. |

## Required operator actions

1. In the primary Codex thread, run `/status` and record the actual session ID. Do not substitute this tool session or an environment/index ID.
2. Reauthorize the broadcaster through the browser using the exact configured origin. This is needed to exercise the current Twitch client secret; do not expose the authorization code or callback URL in a recording.
3. After the EventSub fix, send a fresh `!join` in the existing `noviced3v` channel and confirm health notification/accepted/queued/sent counters increase. Then, with two distinct viewers, send standalone commands at least one second apart: `!join`; one viewer sends `!persona scholar`, `!trait brave`, and `!avatar random`; then each sends `!vote A` or `!vote B`. First approve the pending proposal in Host Studio and open its vote. Do not create a new story over the active one. Observe the Twitch acknowledgments, Host Studio, and `/overlay`; then confirm `/health`, SQLite receipts/revisions/votes, and the canonical transition.
4. Verify the overlay in OBS at 1920×1080, record the demonstrated flow and Codex work in a YouTube video shorter than three minutes, then verify the link as an unauthenticated viewer.
5. Rotate credentials that may have appeared in the earlier ZIP or diagnostic output. Reauthorize or migrate the encrypted token before rotating `TOKEN_ENCRYPTION_KEY`; do not strand the existing vault token.
6. Resolve the “newly created during the Submission Period” ambiguity with the organizer. The initial MVP predates the Codex pass, so the first commit timestamp does not settle eligibility.
7. Complete every Devpost field and click **Submit**, then verify the entry shows Submitted. Do not stop at Save Draft.

## Deadline and final verdicts

The [official rules](https://twitchcon-codex.devpost.com/rules) state November 2, 2026 at 2:00 PM Pacific Time, while the [FAQ](https://twitchcon-codex.devpost.com/resources) labels 2:00 PM PT as 9:00 PM UTC. The conversions conflict for this date. Follow the conservative earlier 21:00 UTC interpretation and the live Devpost countdown; do not wait until the last minute.

**HACKATHON SUBMISSION READY: NO** — genuine session ID, real viewer/chat/vote/OBS evidence, qualifying video, eligibility determination, final source verification, and submitted Devpost entry are absent.

**PRODUCTION READY: NO** — broadcaster chat works, but multi-viewer voting and production security/operations gates remain open.
