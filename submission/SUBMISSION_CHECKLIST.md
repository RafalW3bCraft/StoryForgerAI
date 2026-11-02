# Codex × TwitchCon submission checklist

**Assessment date:** November 2, 2026 UTC

**Current decision:** **NOT READY**. The deadline shown by the official pages is November 2 at 2:00 PM Pacific. The rules and FAQ differ on UTC conversion; use the earlier 21:00 UTC interpretation and the live Devpost countdown.

## Completed engineering work

- [x] Preserved the Python/FastAPI/Jinja2/SQLite application, existing personas and active story data; no authored JavaScript or TypeScript was added.
- [x] Added regression coverage for redacted diagnostics, explicit live AI configuration, provider JSON shape, malformed EventSub payloads, duplicate receipts, nonblocking ordered chat processing, and private SQLite file modes.
- [x] Added a Python 3.12/3.13 GitHub Actions workflow with least-privilege contents access, timeouts, concurrency handling, test, coverage, Ruff, mypy, dependency and Bandit checks. A real Actions run on the final pushed SHA remains required.
- [x] Latest complete Python 3.13.15 suite: **76 passed**; coverage: **85%**, with `ResourceWarning` errors enabled. Ruff, formatter, mypy, compilation, `pip check`, pip-audit and Bandit Medium/High checks passed. See `../docs/TEST_REPORT.md`.
- [x] Reproduced the configured provider's invalid choice shape; explicit JSON shape instructions now produce a live response that passed `NarrativeProposal` validation.
- [x] Moved synchronous chat processing off the async WebSocket receive loop; the 50-event local regression completed in order without blocking the heartbeat.
- [x] Changed the existing local `.env` and SQLite permissions from `0644` to `0600`; new database files and the diagnostic probe also restrict POSIX permissions.
- [x] Added aggregate chat outcome health counters; no raw chat messages or Twitch user IDs are published by `/health`.
- [x] Committed the reviewed code, regression tests, CI workflow, and reports as `9a36319112e8fd83200abcc2b43c81861176d183` on `main`.

## External evidence and remaining requirements

- [x] **Stored Twitch host identity:** redacted live probe verified the encrypted host token and broadcaster ID.
- [ ] **Current Twitch client secret:** a fresh browser authorization-code exchange was not completed; the stored token alone does not verify the configured client secret.
- [x] **EventSub subscription:** live probe and running health check verified `LIVE_TWITCH` and an enabled `channel.chat.message` subscription.
- [ ] **Real chat:** latest redacted health and SQLite inspection show zero chat notifications/receipts. No real `!join`, `!persona`, `!trait`, `!avatar`, `!vote`, or canonical vote transition is evidenced.
- [ ] When validating chat, observe aggregate outcomes and persisted changes in Host Studio/`/overlay`; StoryForge intentionally does not send replies back into Twitch chat.
- [ ] **Two real viewer identities:** current DB has zero viewer personas; demonstrate two distinct Twitch IDs and persisted persona revisions.
- [x] **Real model request:** provider returned content that passed `NarrativeProposal` validation.
- [ ] **Current host approval and vote:** the preserved active story is at `REVIEW`; its current `AI` proposal is `PENDING`. Host Studio must approve it and open its vote before accepting viewer votes. An earlier canonical node with `AI` provenance remains in the story.
- [ ] **Live continuity/restart:** prove a real vote resolves into a canonical successor, then restart and verify personas, votes, and AI provenance remain.
- [ ] **Browser and OBS:** capture the actual overlay in OBS at 1920×1080 with live personas, votes, and branch transition. No visual capture exists yet.
- [ ] **Codex session ID:** run `/status` in the primary Codex thread and record its genuine ID. This tool interface cannot retrieve it; do not substitute an index or environment variable.
- [ ] **ECC evidence:** native ECC plugin is not installed in this runtime. Existing documented ECC skill-guidance use is distinct from native plugin use; do not claim plugin execution.
- [ ] **Public tested source:** push `9a36319112e8fd83200abcc2b43c81861176d183` and verify `origin/main`, GitHub page, and any Actions run against the exact final SHA. Do not include `.env`, database, cache, or operator audit/prompt files.
- [ ] **Eligibility:** ask the organizer how “newly created during the Submission Period” applies. The first Git commit is dated during the event, but the pre-existing MVP predates the current Codex pass and commit timestamp alone does not prove eligibility.
- [ ] **YouTube demo:** record a public or unlisted video under 3 minutes showing real Twitch messages, the host-approved AI scene, vote-to-canon transition, OBS, and Codex development. Check that it contains no credentials, OAuth callback parameters, private chat, or unlicensed material. No video URL exists.
- [ ] **Devpost:** complete all required fields in English, enter the real source/video/session URLs, then click **Submit** and verify the project is marked Submitted. Save Draft is not submission. No submission status is claimed.
- [ ] **Credential rotation:** rotate any Twitch, AI, session, demo-password, and Fernet values that may have appeared in the earlier shared ZIP or diagnostic output. Reauthorize/migrate the token vault before replacing the Fernet key.

## Draft asset status

- Source repository: <https://github.com/RafalW3bCraft/StoryForgerAI>
- Demo video URL: **not recorded**
- Primary Codex `/status` ID: **not available**
- Devpost project link/status: **not available / not submitted**

Use the evidence in `../docs/FINAL_EVIDENCE_REPORT.md` and the current release decision in `../docs/RELEASE_REPORT.md`. The official [rules](https://twitchcon-codex.devpost.com/rules) and [resources/FAQ](https://twitchcon-codex.devpost.com/resources) require the project eligibility, repository, description, Codex session ID, qualifying video, and a completed submission.
