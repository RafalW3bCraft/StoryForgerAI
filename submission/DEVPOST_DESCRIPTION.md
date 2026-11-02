# AI StoryForge — Every Viewer Becomes a Character. Every Choice Becomes a Story.

**Submission copy draft. Not a completed Devpost submission. Fill the actual Codex session ID and video URL only after verifying them, then review the eligibility concern with the organizer.**

## Inspiration

Twitch chat moves quickly, and audience ideas can disappear when a poll ends. AI StoryForge gives a streaming community a shared, branching story where viewers can return as persistent fictional characters and shape the next canonical scene.

## What it does

The streamer acts as Story Master. Viewers join through Twitch chat, build persistent personas with procedural SVG avatars, contribute bounded lines or plot twists for host review, and vote on scene choices. The host reviews AI-generated proposals and contributions before they become canonical. SQLite stores personas, revisions, votes, the current story head, and alternate branches. A Jinja2 browser-source page displays the story for OBS and refreshes every three seconds. Commands update Host Studio and the overlay; StoryForge does not reply in Twitch chat.

## How it is built

AI StoryForge uses Python, FastAPI, Jinja2, CSS, SQLAlchemy, SQLite, Pydantic, HTTPX and WebSockets. It contains no application-authored JavaScript or TypeScript. Twitch identity is bound to immutable Twitch user IDs. EventSub uses the `channel.chat.message` subscription with host-only authorization and rejects messages from an unexpected broadcaster. OAuth state is held in the signed session; encrypted host tokens remain server-side. Scene output is validated against `NarrativeProposal` before persistence. The deterministic offline generator is marked DEMO and is not a fallback for failed live generation.

## How Codex contributed

The existing MVP predates this Codex engineering pass. In the recorded Codex work, Codex added or repaired EventSub identity and subscription validation, OAuth origin handling, live configuration checks, AI response validation, chat cooldown and replay handling, aggregate redacted diagnostics, database permission enforcement, the Python 3.12/3.13 CI workflow, regression tests, and release documentation. The latest public `main` snapshot checked at audit time was `9e6a514b951aa81b0155b88f619c52c11f4255e9`; Actions run `41420537063` passed on that SHA. The actual primary-thread Codex session ID is still required before submission.

## Verification and limitations

The latest Python 3.13.15 run passed **76 tests** with **85% coverage**; Ruff, formatting, mypy, compileall, dependency checks, pip-audit and Bandit Medium/High checks passed. A live configured-model response passed `NarrativeProposal` validation. The stored Twitch host token/broadcaster identity and active EventSub subscription are verified, but actual viewer chat messages, persona changes, votes, and the resulting canonical branch transition have not yet been evidenced. The current story has a pending AI proposal in `REVIEW`; a previous canonical node has AI provenance. No browser/OBS capture or qualifying demonstration video has been recorded.

The first Git commit is in the submission window, but the original MVP predates this Codex pass. The first commit timestamp alone cannot establish that this is a newly created project under the event rules; organizer interpretation is needed. This entry remains a draft until that question and all live demonstration requirements are resolved.

## Links and required fields

- Source repository: <https://github.com/RafalW3bCraft/StoryForgerAI>
- Demo video: **not recorded**
- Primary Codex `/status` session ID: **not available**
- Devpost status: **not submitted**
- ECC native plugin: **not installed in this runtime**; do not claim plugin execution.
