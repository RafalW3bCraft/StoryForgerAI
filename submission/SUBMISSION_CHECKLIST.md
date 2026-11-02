# Codex × TwitchCon submission checklist

**Assessment date:** November 2, 2026 UTC
**Current decision:** **NOT READY**. Keep this checklist open until every mandatory item has direct evidence.

## Engineering work completed in this Codex pass

- [x] Preserved the existing Python/FastAPI/Jinja2/SQLite product and the two pre-existing untracked operator prompt/audit files.
- [x] Added regression coverage for EventSub broadcaster/subscription validation, OAuth callback outcomes, AI truncation and endpoint safety, chat cooldowns, persisted generation provenance, and redacted diagnostics.
- [x] Added a redacted environment diagnostic and bounded optional live API probes.
- [x] Persisted scene-generation outcomes and made the UI distinguish `FAILED`, `AWAITING`, `AI-GENERATED`, and `DEMO-GENERATED`; canonical approval preserves provenance.
- [x] Throttled recognized commands across per-viewer command types, suppressed receipts for unknown/info commands, bounded rejected-event dedupe, and clarified web/OBS feedback.
- [x] Restricted demo host-password login to loopback and redacted secret fields from `Settings.__repr__`.
- [x] Kept every browser request on `APP_BASE_URL` with a fixed-origin pure ASGI redirect before session handling; callback errors do not show JSON details and Uvicorn access logs omit OAuth query strings.
- [x] Full current suite: 68 passed, including all three HTTP acceptance tests; coverage is 84%. Ruff, formatting, mypy, compileall, `pip check`, pip-audit, and Bandit Medium/High checks pass. Exact commands are in `docs/TEST_REPORT.md`.
- [x] Added safe OAuth exchange failure feedback with only HTTP status/category; regression confirms the one-time code and provider body are absent from UI output and logs.
- [x] Added startup guidance to use the exact printed HTTP address and clarified the TLS reverse-proxy requirement for an HTTPS `APP_BASE_URL`.
- [x] `pip-audit` found seven advisories in the former `cryptography 47.0.0` pin; raised the minimum to 50.0.2 and confirmed no known dependency vulnerabilities on rerun.
- [x] Bandit found two Medium SQL-string warnings in the SQLite diagnostic; changed the probe to a fixed-name main-database table created and rolled back inside a write transaction and reran with zero Medium/High findings. Reviewed the remaining 13 Low findings as non-exploitable for their specific uses.
- [x] Read and applied available official ECC TDD, security-review, test-collaboration, and verification-loop skill guidance. Native ECC plugin was unavailable; no native plugin invocation is claimed.

## Mandatory submission evidence still required

- [x] Complete the full local test gate. The sandbox-bound attempt stalled in its worker bridge, then the complete suite passed outside the sandbox: 68 passed, including all HTTP acceptance tests.
- [ ] Complete a real Twitch broadcaster OAuth flow and verify broadcaster identity. A read-only authorize request received HTTP 302, but no user grant/token exchange occurred; `doctor --live` finds no encrypted host token. Set the Developer Console callback to exactly `http://127.0.0.1:8000/auth/callback` for the current printed local URL, then complete the browser grant.
- [ ] Establish EventSub `channel.chat.message` delivery on the real channel, then prove real `!join`, persona customization, and votes modify persisted state.
- [ ] Generate and validate a real provider scene; confirm its saved status is `AI-GENERATED` and obtain host approval.
- [ ] Complete the host/viewer/voting/canonical-branch/restart acceptance flow with two actual viewers.
- [ ] Verify the overlay in a browser and OBS at 1920×1080 using the real running session.
- [ ] Capture the actual primary Codex `/status` session ID. No substitute ID is acceptable.
- [ ] Run the full change set from a writable Git checkout, create reviewable commits, push the current changes, and verify judge access to the repository. The current `.git` mount is read-only.
- [ ] Review eligibility against the official “newly created” rule and obtain an organizer interpretation if needed. The first Git commit is dated within the entry period, but the original MVP predates this Codex pass and the timestamp alone does not establish eligibility.
- [ ] Record and verify a public YouTube demo shorter than three minutes showing real Twitch operation and the actual Codex development session; add its real URL only after verification.
- [ ] Complete all Devpost fields and verify the entry is marked **Submitted** before November 2, 2026, 2:00 PM PST.
- [ ] Confirm rotation of credentials that may have appeared in the previously supplied ZIP or this pass's earlier pytest failure output before live verification/publication; do not record them in this repository or demo.

## External state verified in this pass

- [ ] Twitch OAuth: **blocked**. `doctor --live` found no encrypted host token in the local database; no user grant or callback was completed. The user-visible local origin is `http://127.0.0.1:8000`; its callback is `/auth/callback` on that exact origin.
- [ ] EventSub and live chat: **not verified**. No live subscription/event was received; no actual `!join`, `!persona`, or `!vote` succeeded in evidence.
- [ ] AI provider: **failed probe**. The endpoint returned an empty assistant-content field; no validated live proposal or host approval exists. Configure a compatible model response and rerun.
- [ ] Browser/OBS: **not verified**. The application health endpoint and database-backed snapshot responded in the final live doctor, but no browser visual or OBS capture exists.
- [ ] GitHub judge access: **not verified**. Latest changes are uncommitted and unpushed because `.git` is read-only here.
- [ ] Codex session ID, video URL, and Devpost submission: **not available**.

See [the release gate report](../docs/RELEASE_REPORT.md) and [the exact test evidence](../docs/TEST_REPORT.md). The official rules require an eligible newly created project, Codex evidence, accessible repository, a qualifying YouTube video, and a completed Devpost submission: https://twitchcon-codex.devpost.com/rules
