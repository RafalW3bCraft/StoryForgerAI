# AI StoryForge — Every Viewer Becomes a Character. Every Choice Becomes a Story.

**Submission copy draft. Do not paste as final until the live demo, repository access, Codex session ID, eligibility, and all claims are verified.**

## Inspiration

Twitch chat moves quickly, and most audience choices disappear as soon as a poll ends. AI StoryForge turns a stream into a shared story where viewers return as persistent characters, influence decisions, and see their choices shape a canonical timeline.

## What it does

The streamer directs the story as its Story Master and appears as a character. Viewers join with Twitch-linked personas, customize archetypes and traits, and receive original procedural SVG avatars. Viewers vote on branching scene choices and submit lines or twists for host review. The host approves proposals and contributions before they become part of the story. SQLite preserves the canonical head and alternative branches across restarts. A browser-source overlay presents the story, character cards, and voting state for OBS.

## How it is built

The application is Python-first: FastAPI, Jinja2, CSS, SQLAlchemy, SQLite, Pydantic, httpx, websockets, and Python-generated SVG. It has no application-authored JavaScript or TypeScript. Twitch identity is bound to immutable user IDs; the host has separate authorization and CSRF-protected controls. EventSub welcome, keepalive, reconnect, revocation, duplicate delivery, and broadcaster identity checks are implemented. The OBS page uses a three-second refresh rather than server push.

Narrative proposals use a configurable OpenAI-compatible chat completion endpoint and are validated against a Pydantic schema before the host can approve them. A deterministic DEMO generator supports offline evaluation and is never silently substituted for a failed live model request.

## How Codex contributed

The original MVP existed before this Codex engineering pass. Codex made substantive changes to EventSub identity and subscription validation, AI truncation/endpoint checks, live OAuth configuration validation, chat cooldowns, redacted environment diagnostics, and regression coverage. The final Codex `/status` session ID must be added from the actual primary Codex session before submission; no session-index ID is substituted here.

## How ECC contributed

The available ECC TDD, security-review, test-collaboration, and verification-loop skill guidance was read and applied. The native ECC plugin was not installed in this runtime, so this entry does not claim a native plugin run.

## Verification and current status

Local verification reports 68 passed, including the three HTTP acceptance tests, and 84% coverage. Ruff, formatting, mypy, compilation, `pip check`, pip-audit, and Bandit Medium/High checks pass. These are local test results; no real Twitch event or provider-generated story has been verified.

No real Twitch OAuth or EventSub message was verified: the local database has no encrypted host token. The live model probe returned an empty assistant-content field, so no real proposal was validated. The app health endpoint and SQLite snapshot responded, but browser/OBS visuals were not captured. Do not describe live operation as verified until it has been demonstrated in a real Twitch channel and a real validated AI proposal has been generated.

The initial MVP predates this Codex session. The hackathon rules require a project newly created during the submission period; the project’s eligibility must be checked against the complete development history. Do not claim organizer approval that has not been obtained.

## Links and submission state

- Configured repository remote: <https://github.com/RafalW3bCraft/StoryForgerAI>
- Public/judge access: not yet verified for the completed working tree.
- Demo video: not recorded; no URL exists.
- Devpost status: not submitted.
