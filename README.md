# AI StoryForge — The Living Twitch Narrative

**A new Python-authored interactive storytelling MVP for Twitch.** A streamer acts as a Story Master and playable character. Viewers join chat as persistent personas with original procedural avatars, contribute dialogue and twists, vote on story branches, and see the canon evolve in an OBS browser overlay.

> **Release status (2026-11-01):** Functional local demo with passing domain/integration checks; **not a finished hackathon submission**. Live Twitch OAuth/EventSub and provider inference remain unverified in this environment. The current Codex session applied substantive fixes; its session-index ID is `01a1959c-5725-74e1-afc2-c3d3e45f1091`, but the operator must confirm it with `/status`. No usable repository Git history, ECC plugin registration, public repository, demo video, or Devpost submission is available here. See `docs/RELEASE_REPORT.md`.

## Implemented

- Python-only FastAPI/Jinja2/CSS application, without authored JavaScript/TypeScript.
- Session-protected Host Studio, with an authenticated demo host or verified Twitch broadcaster OAuth flow.
- OAuth login for viewers and browser-based persona editing (when Twitch credentials are configured).
- Persistent Twitch-ID-bound personas with original, Python-generated SVG portraits, archetypes, traits, colors, emblems, and revision records.
- Twitch EventSub `channel.chat.message` WebSocket adapter, OAuth token refresh, encrypted host token storage, reconnect migration, and event receipt deduplication. **Implementation has not been live-verified.**
- Twitch chat commands: `!join`, `!persona <archetype>`, `!trait <trait>`, `!avatar random`, `!vote A`, `!line <text>`, `!act <text>`, `!twist <text>`, `!profile`, `!story`, `!recap`, `!leave`, `!help`.
- Host-approved contributions, scene proposals, story branch votes, persistent canonical decisions, and non-destructive forks retaining alternate timelines.
- Validated JSON narrative generation through a configurable OpenAI-compatible API, plus a clearly labeled deterministic demo generator.
- OBS-compatible presentation page and Python-generated SVG branch graph.
- Identity authorization, CSRF forms, bounded inputs, read-only overlay, and sanitized template text.
- Voting pause/resume restores the effective `READY` or `VOTING` state; SQLite enforces at most one open round per story session.
- Canonical model context is a deterministic, bounded synopsis of the active ancestry, approved contributions, participating personas, and host character.

## Quick start (Linux/macOS; Python 3.12+)

```bash
# Extract the provided ai-storyforge.zip, then:
cd ai-storyforge
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
# Change STORYFORGE_SECRET to a long random string
# Change DEMO_ADMIN_PASSWORD to a strong password
python -m storyforge
```

No repository has been published by this build. These commands work directly from the extracted source directory.

Run at `http://127.0.0.1:8000`.

If you already have dependencies and want to run without installation from a checked-out directory:

```bash
PYTHONPATH=src python -m storyforge
```

The process binds to **127.0.0.1** by default; avoid exposing the demo password form on the public internet.

### Demo walkthrough

1. Open the homepage and sign in using the `DEMO_ADMIN_PASSWORD` from `.env`.
2. Create **The Last Library of Tomorrow** and generate its first scene (marked **DEMO**, not AI).
3. Approve the scene, then open voting.
4. In the Host Studio's **Simulate viewer chat commands** form, send `!join` for `Starlight`, then `!persona scholar`, then `!vote B`. Repeat with a second named viewer.
5. Send `!line I found the key beneath the stars` as a viewer. Approve it from the moderation queue.
6. Close voting, generate the next scene and approve it.
7. View `/overlay` (for OBS) and `/graph.svg` (for the story graph). The overlay refreshes every three seconds using standard HTML metadata, with **no custom JavaScript**.
8. Revisit an earlier node from Host Studio, start a new vote, and generate a different branch. The old branch remains in the timeline.

> Demo synthetic Twitch events are clearly labeled. They exercise exactly the same command processor and persistence rules but **are not proof of Twitch connectivity**.

## Real Twitch setup

1. Register a Twitch Developer application: https://dev.twitch.tv/console/apps. Set the OAuth redirect URI to the exact `APP_BASE_URL/auth/callback` configured below.
2. Configure `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `TWITCH_BROADCASTER_ID`, `TWITCH_READER_ID`, `STORYFORGE_SECRET`, `TOKEN_ENCRYPTION_KEY`, and `APP_BASE_URL` in `.env`.
3. For this single-broadcaster MVP, `TWITCH_READER_ID` **must equal** `TWITCH_BROADCASTER_ID` and host login must authorize this same Twitch account. Twitch EventSub uses `channel.chat.message` (v1) with the user token's `user:read:chat` scope.
4. Generate a secret key using `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` and put the value in `TOKEN_ENCRYPTION_KEY`.
5. Set `STORYFORGE_MODE=live`, run the app, and select **Sign in with Twitch as Host**. The host must complete Twitch OAuth.
6. Once the browser callback succeeds, the EventSub connector reads the encrypted token, subscribes, and processes chat events; verify the `/health` status changes to `LIVE_TWITCH` and **test an actual chat message**.
7. A viewer can use **Connect Twitch Persona** to authenticate a browser profile editor. The authorized viewer's Twitch ID is bound to the profile. No browser editing of somebody else's ID is allowed.

For public deployment, use an HTTPS reverse proxy and update `APP_BASE_URL` accordingly. Do not rely on local demo credentials for public operation. Explicitly configure TLS, proxy trust and security headers before public hosting; this MVP has **not** undergone a production security review.

Official documentation: https://dev.twitch.tv/docs/eventsub/handling-websocket-events/ and https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/.

### AI generation

Default: a **deterministic demo story generator**, not a model.

To use a real provider, configure all of:

```dotenv
AI_BASE_URL=https://your-openai-compatible-provider.example/v1
AI_API_KEY=your-secret
AI_MODEL=your-supported-model-id
```

External inference is enabled only when `STORYFORGE_MODE=live`; demo mode remains deterministic even if provider variables are present in the shell.

The adapter POSTs to `{AI_BASE_URL}/chat/completions` with `response_format: {type: json_object}` and validates `title`, `narrative`, and 2–3 choice strings through Pydantic. Choose a provider/model that actually supports this format. A failed model call leaves generation pending for a host retry; it never fabricates successful AI output.

No provider compatibility or live inference has been verified in this build environment.

## OBS

Add **Browser Source** in OBS, point it to `http://127.0.0.1:8000/overlay` when OBS is on the same machine, and set **1920 × 1080**. It refreshes every three seconds, which can cause a minor transition flicker. A richer server-push UI is an optional later upgrade once a Python-compatible mechanism is available and verified.

## Commands

| Command | Action |
|---|---|
| `!join` | Create or reconnect a persona |
| `!persona scholar` | Choose an approved archetype |
| `!trait brave` | Select an approved trait |
| `!avatar random` | Change the accessory deterministically |
| `!vote A` | Cast or change a vote during an open round |
| `!line ...`, `!act ...`, `!twist ...` | Queue text for host moderation |
| `!profile`, `!story`, `!recap`, `!help` | Record no state change; prompts for details are shown in the website, not posted into chat |
| `!leave` | Delete persona and pseudonymize historic participation |

The app intentionally does **not** auto-send messages to Twitch chat; doing so would require additional Twitch permissions and separate rate-limited send logic. Informational commands currently only produce internal processing results. This limitation is disclosed.

## Quality checks

```bash
python -m pytest -q
python -m pytest --cov=storyforge --cov-report=term-missing
python -m compileall -q src
```

The current Codex pass also ran `ruff check src tests`, `ruff format --check src tests`, `mypy src/storyforge`, and Python compilation. In the supplied Python 3.14.7 image, the existing FastAPI `TestClient` suite cannot start because AnyIO's blocking portal hangs before the first request; run the full suite in a normal Python 3.12/3.13 environment. Live Twitch and model checks still require operator credentials and network access. See `docs/TEST_REPORT.md`.

## Security and data scope

Only the Twitch account owner can edit their authenticated persona through the web UI. Chat commands are bound to server-received Twitch identity. The app does not store emails, raw photographs, or microphone audio. Host privileges do not derive from a fictional character's role. Viewer contributions require host approval. The overlay and graph are read-only.

OAuth token values are encrypted at rest with Fernet and are never stored in cookie sessions. Use HTTPS, secret rotation, and secure reverse proxy configuration for public deployment. Browser sessions contain only signed identity/role metadata. A compromised live DB **and** encryption key would permit token recovery.

No work from the old Poketar source tree, old images, or remote assets was copied. All SVG avatar shapes are original Python generated geometry.

## Hackathon submission status

The Codex × TwitchCon Hackathon requires code built during the permitted window, actual Codex use and a session ID, a video under 3 minutes showing real Twitch and Codex, and a complete Devpost submission. This local build **does not satisfy those external verification steps yet**. The project is suitable as a foundation for continuing with Codex and ECC, not a claim that the eligibility or tool-use criteria are already fulfilled.

Read: `AGENTS.md`, `docs/ECC_WORKFLOW.md`, `docs/RELEASE_REPORT.md`, `docs/JUDGE_TESTING.md`.
