# AI StoryForge — engineering release report

**Date:** November 1, 2026
**Version:** 0.1.0
**Assessment:** Codex-enhanced local Python MVP; **not yet hackathon submission-ready**.

| Capability | Implemented | Automated evidence | Live external evidence |
|---|---|---|---|
| Python-only application and HTML/CSS browser UI | Yes | Prior app tests; current HTTP suite blocked by AnyIO/TestClient hang | No current browser verification |
| Persistent viewer personas | Yes | Profile CRUD/revision tests | Twitch-authorized user pending |
| Deterministic original SVG avatar renderer | Yes | Determinism/validation tests | Local rendering |
| Twitch OAuth/EventSub/WebSocket client | Yes | Mocked reconnect and token-vault tests | Not tested with Twitch |
| Chat commands/votes | Yes | Commands and voting tests | Synthetic only |
| Scene proposals and approval | Yes | Full story test | AI model pending |
| Configurable AI generator | Yes | Mocked JSON provider test | Model pending |
| Deterministic demo narrative generator | Yes | Integration tests | Offline only |
| Canonical branching/alternate forks | Yes | Non-destructive fork test | Offline only |
| Host controls and persona interaction | Basic | Prior HTTP integration tests; current HTTP suite blocked by environment | Local only |
| OBS overlay | Yes, periodic page refresh | Prior route/presentation tests; not rerun this session | OBS desktop app not tested |
| Viewer authenticated profile editor | Yes | Host/profile access checks | Twitch OAuth callback not tested |
| Voting pause/resume invariant | Fixed | Regression tests + partial unique SQLite index | Restart/production concurrency not externally tested |
| Canonical context continuity | Fixed, bounded | Multi-chapter regression test | Live model continuity pending |
| ECC installed and applied | No native registration | Guidance read and applied; `installed: []` | Operator must install/enable ECC |
| Codex development session and ID | Substantive fixes in current turn | Session-index ID `01a1959c-5725-74e1-afc2-c3d3e45f1091`; `/status` not captured | Operator must confirm `/status` and publish evidence |
| 3-minute YouTube demo | No | — | Must be filmed after true live verification |
| Published repo and Devpost submission | No | ZIP source package only | Must be done by operator |

Known restrictions: single-process SQLite, in-memory command cooldown (not a distributed limiter), no image-model provider, no microphone/camera features, manual host refresh, OBS overlay refresh rather than push, no outbound Twitch informational responses, no deployed HTTPS reverse proxy, no independent security audit, no official Devpost eligibility determination, no usable local Git history, and no real Twitch/model/network evidence.

Recommended next critical steps:

1. Install this package on an operator's Python 3.12+ system and run `python -m pytest -q`.
2. Open the repository with Codex and configure ECC; perform substantive code review, remediation, testing and implementation changes. Capture actual Codex `/status` session ID.
3. Configure Twitch OAuth and prove live EventSub `!join`, `!persona`, `!vote` from a real Twitch channel.
4. Configure a real AI model supporting the documented JSON completion format; validate generation and host review.
5. Record a real <3-minute YouTube demo showing Twitch functionality and Codex.
6. Publish a compliant repository and submit the required artifacts in Devpost by **November 2, 2026, 2:00 PM PST**.

## Release gates

| Gate | Status | Evidence / blocker |
|---|---|---|
| G0 clean installation | BLOCKED | No fresh install run in this network-restricted environment |
| G1 tests and compilation | BLOCKED | `compileall` passes and 24 selected tests pass; full HTTP suite hangs in AnyIO/TestClient |
| G2 lint, format, type, security | BLOCKED | Ruff/format/mypy pass; no independent security scan or full app-suite run |
| G3 voting-state correction | PASS | Persisted pause origin, open-round index, and regression tests |
| G4 Twitch OAuth | BLOCKED | Live config currently fails Fernet-key validation; no OAuth browser/session and host token vault is empty |
| G5 live EventSub chat | BLOCKED | No live channel/event evidence |
| G6 persistent personas | PASS (offline) | Targeted persistence/avatar/revision tests |
| G7 real AI generation | BLOCKED | Configured-looking provider attempt failed DNS resolution |
| G8 host actions/permissions | BLOCKED | Prior tests exist; current HTTP client cannot start |
| G9 live vote changes canon | BLOCKED | Offline service path passes; no real Twitch event |
| G10 OBS visual verification | BLOCKED | OBS/browser not available in this session |
| G11 Codex implementation/session ID | BLOCKED | Substantive fixes made and session-index ID recovered; `/status` confirmation and Git history are still absent |
| G12 ECC workflow | BLOCKED | Guidance applied, but native plugin registration reports `installed: []` |
| G13 public repository | FAIL | No repository URL or usable local Git history |
| G14 YouTube demo | FAIL | No video recorded or URL supplied |
| G15 Devpost submission | FAIL | Not submitted |

Overall decision: **NOT READY**. Mandatory external evidence is absent; this report does not claim eligibility or submission completion.
