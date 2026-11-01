# AI StoryForge — Every Viewer Becomes a Character. Every Choice Becomes a Story.

**Submission draft — external links and live evidence remain incomplete. Do not mark submitted until the checklist is complete.**

## Inspiration

Twitch is most compelling when viewers affect what happens live. AI StoryForge combines collective authorship with persistent fictional identity so chat decisions become lasting scenes, not disposable polls.

## What it does

A streamer acts as a Story Master and character in a branching story. Viewers register fictional personas, customize original procedural avatars, vote on scene choices and contribute dialogue or twists that the host moderates. Each approved scene advances a persistent canonical path while alternative timelines remain accessible. A browser-source overlay lets the audience follow the story and participating characters.

## Built with

Python, FastAPI, Jinja2, CSS, SQLAlchemy/SQLite, Pydantic, httpx, websockets, cryptography and original Python-generated SVG assets.

## How Twitch was integrated

An EventSub WebSocket adapter subscribes to `channel.chat.message` using Twitch OAuth and maps broadcaster-bound, authenticated chat events into the persona, moderation and voting engines. The adapter handles welcome, keepalive, reconnect migration, duplicate delivery and revocation. **The local implementation is not yet verified against a real channel.**

## How AI is used

A configurable OpenAI-compatible chat-completions provider generates validated narrative proposals. The host approves publication. The local fallback is a deterministic demonstration, labeled DEMO. **Live model inference is not yet verified.**

## How Codex was used

The initial MVP predates the current Codex session. This session made substantive Python changes: persisted voting pause origin and database open-round protection, bounded canonical context, AI response validation, and EventSub error/identity handling. The local session index identifies `01a1959c-5725-74e1-afc2-c3d3e45f1091`; confirm it with `/status` in the primary Codex UI before publishing.

## How ECC was used

ECC guidance was read from the local marketplace checkout for TDD, security review and verification. Native plugin registration was not present (`installed: []`), so this is not proof of an ECC plugin run. Add the real plugin evidence before submission.

## Challenges, accomplishments and future

Implemented persistent personas, original stable avatars, hosted story approval, alternate branch preservation, and a testable no-keys demo mode. Next challenges: live Twitch/OAuth verification, a compatible real AI provider, smoother Python-driven browser updates, more robust rate limiting and deployment security.

## Demo and code links

**Repository: not published. Video: not recorded. These must be added before Devpost submission.**
