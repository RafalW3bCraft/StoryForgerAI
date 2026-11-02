# Codex and ECC workflow evidence

## Availability

Codex CLI 0.166.0 was present. The local Codex plugin query reported `installed: []`; the native ECC plugin was not installed in this runtime. The cached official ECC checkout was readable, so its applicable guidance was read and applied as engineering process. No `$configure-ecc`, plugin agent invocation, or plugin execution is claimed.

The following cached ECC skills were read for this pass:

- `tdd-workflow` — RED test before implementation, focused GREEN rerun, verification evidence.
- `security-review` — secret handling, identity/authorization, input validation, CSRF, XSS, rate limits and errors.
- `test-collaboration` — durable regression coverage for requirements and boundary behavior; distinguish mocked and real integration evidence.
- `verification-loop` — build/type/lint/test/security/diff review and separate target acceptance from local validation.

The local marketplace being readable is not equivalent to native plugin installation. Marketplace listing could not be confirmed online in this restricted environment.

## Cycles applied

1. **EventSub trust boundary:** added failing tests for missing/wrong broadcaster identity and invalid subscription acknowledgments; tightened notification filtering and response validation; reran the EventSub broadcaster, confirmation, reconnect, and revocation tests.
2. **AI response correctness:** added a failing test for a response marked truncated despite valid-looking JSON; rejected truncation reasons and reran valid, malformed, empty, and truncated completion tests.
3. **Configuration/security:** added failing live callback/Twitch ID validation tests; required secure callback origins and numeric IDs; introduced a redacted diagnostic for all recognized environment settings.
4. **Chat resource control:** reproduced cross-command cooldown bypass, invalid-vote spam, replay of cooldown-rejected IDs, and durable receipts for unknown/info commands; added per-viewer cooldowns, bounded rejected-ID dedupe, and no-write handling for unknown/info commands.
5. **Endpoint safety and error redaction:** rejected credential-bearing or duplicated AI base URLs and stopped surfacing raw transient EventSub exception messages; tests first demonstrated both defects.
6. **Generation provenance:** a review test reproduced approval overwriting `AI-GENERATED`/`DEMO-GENERATED`; removed that overwrite while keeping canonical approval represented by the resolved proposal and story node. Focused regression passed.
7. **Security review:** a direct route test showed remote access to the demo password login; restricted it to loopback. A sentinel regression showed secret-bearing `Settings.__repr__`; marked secrets non-representable. A configured secret appeared in the earlier failure output; rotate it before release.
8. **Model request cost control:** a blocking fake provider regression showed concurrent host retries could issue two model requests. Added a per-app async lock; simultaneous retries now make one provider call. This remains single-process protection.
9. **Verification and error-path repair:** final Ruff review found an exception variable referenced outside its handler; fixed it and reran Ruff/mypy. Final targeted run: 51 passed, 3 HTTP tests deselected, 76% coverage; Ruff, format, mypy, compileall, Jinja parsing, and `pip check` passed. Bounded external probes and limitations are in `docs/TEST_REPORT.md`.
10. **OAuth origin/session failure:** cached ECC TDD and Python-testing guidance was applied with failing route regressions first. Redacted origin metadata reproduced the `localhost` versus `127.0.0.1` cookie mismatch. Login now redirects to the fixed configured origin before writing OAuth state; an off-origin callback forwards only the OAuth code and state to the configured callback; missing-session callbacks return to the configured home. Invalid state remains rejected without consuming a valid pending state. Uvicorn access logging is disabled to avoid recording OAuth query strings. The cached Python reviewer artifact and security-review checklist were used to review redirect trust, cookie scope, logs, and state handling. See the Nov 2 continuation in `docs/TEST_REPORT.md` for current evidence and known test-runner limits. The native ECC plugin remains uninstalled and no plugin invocation is claimed.
11. **Dependency security:** `pip-audit` reproduced seven advisories for installed `cryptography 47.0.0`; its project constraint `<48` blocked patched releases. Raised the floor to `50.0.2`, reinstalled both ignored environments, reran dependency audits with no known findings, and reran the available 58-test suite.
12. **Diagnostic SQL review:** Bandit reported two Medium B608 findings in the SQLite write probe. The generated UUID identifier was not user-controlled, but the probe was simplified to a fixed-name main-database table created and rolled back inside a write transaction. Its rollback regression passed; Bandit then reported zero Medium/High findings. Low heuristic findings were reviewed and annotated with their non-security use.
13. **HTTP/OAuth follow-up:** Local `.env` diagnostics passed shape checks without printing values; the app prints a loopback HTTP URL, matching the plain HTTP runner. Added a regression that every off-origin HTTP request redirects directly to the configured origin before session middleware, safe OAuth status feedback, and startup guidance for TLS-vs-HTTP. The sandbox-bound test runner stalled in worker dispatch, but the complete 68-test suite, including all HTTP acceptance tests, passed outside the sandbox. No application sync handler was moved onto the event loop.
14. **Live generation failure:** Added a failing payload regression for the configured Featherless Qwen3 model, confirmed the RED failure omitted the provider's reasoning toggle, then added `chat_template_kwargs.enable_thinking=false` only for that provider/model family. Focused tests passed and a real full-prompt probe passed `NarrativeProposal` validation. The complete suite now reports 69 passed and 84% coverage; see the AI follow-up in `docs/TEST_REPORT.md`.

These are skill-guidance applications in the Codex session, not native ECC plugin evidence. The primary Codex `/status` session ID was not exposed through this interface. A local session-index entry must not be substituted.

The cached ECC `agent-architecture-audit` and benchmark-optimization artifacts were inspected. They were not invoked: the OAuth cookie-origin failure is ordinary web/session boundary debugging, and this change makes no performance claim. No standalone Python-review *skill* is installed; the cached `agents/python-reviewer.md` artifact was read and used as a manual review checklist.

## Commit and release limitations

The ECC TDD skill recommends Git checkpoints after RED and GREEN. Initial sandbox access could not write `.git`, so the requested local commit was created after explicit elevated filesystem approval: `144e3a3849ace53325211ecd5b77549fdc73ba1e`. The two operator-provided untracked audit/prompt files were not staged. No push was performed.

The native ECC plugin should be installed and verified in the operator's Codex environment if available. The actual `/status` ID, live Twitch operation, successful model output, browser/OBS evidence, and submission artifacts remain outstanding. Full local tests and static checks are recorded in `docs/TEST_REPORT.md`.

## Nov 2 finalization cycle

The latest active tool environment did not expose ECC skill files or a registered native plugin. I used the repository's documented ECC-style cycle manually and do not claim a native ECC invocation for this turn.

1. **AI response contract:** reproduced the live provider's HTTP-200 response failing `NarrativeProposal` because choices were objects instead of strings. Added an exact JSON example and plain-string instruction. A fresh live provider probe then passed Pydantic validation.
2. **EventSub scheduling and malformed data:** moved synchronous `process_chat` to sequential `asyncio.to_thread` dispatch and added guards for malformed envelope/payload fields. Extended the loop responsiveness regression to a 50-message simulated burst. It stalled in the restricted sandbox's worker wakeup path, then passed outside the sandbox in 0.46 seconds with ordered receipt calls and no event-loop stall. This is only local simulated evidence.
3. **Secret and database file permissions:** first added a failing regression showing new SQLite files were created as `0644`. Added owner-only POSIX database creation/restriction and applied it to the doctor write probe. Restricted the existing `.env` and database from `0644` to `0600`. New/existing-file tests passed.
4. **Configuration loading:** removed import-time `.env` loading, made the CLI load it explicitly, and made live startup fail if the AI URL, key, or model is absent. Config and diagnostics regressions passed.
5. **Final verification:** Python 3.13.15 full suite **76 passed**; coverage **85%** with ResourceWarnings treated as errors; Ruff, formatter, mypy (12 files), compileall, pip check, pip-audit and Bandit Medium/High checks passed. Current real health/DB evidence still has zero viewer notifications, personas, receipts, or votes.

The two existing operator files stayed untouched and unstaged. No `/status` ID could be read from the tool interface. Native ECC installation/registration, live viewer testing, OBS recording, video publication, and Devpost submission are still external blockers.

The final code/test commit is `9a36319112e8fd83200abcc2b43c81861176d183`; report commits `4ef8e3ea16a0562df9a66e1b42ece05242d48449` and documentation-only `9e6a514b951aa81b0155b88f619c52c11f4255e9` were pushed to public `main`. GitHub Actions run `41420537063` passed on the latest SHA for Python 3.12 and 3.13. This records Codex engineering and GitHub CI evidence, not a native ECC plugin run.
