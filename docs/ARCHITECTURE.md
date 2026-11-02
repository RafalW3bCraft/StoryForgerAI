# Architecture & domain contracts

## Processes

One FastAPI process serves the host dashboard, public story page, Twitch OAuth callback, persona editor, deterministic/avatar renderer, OBS page and Graph SVG. A pure ASGI middleware redirects every off-origin HTTP request to the fixed `APP_BASE_URL` before session handling and adds security headers. Its lifespan starts one background `TwitchConnector` task in live mode. SQLite is authoritative; SQLAlchemy sessions are committed in transactions. Running multiple Uvicorn workers is **not supported** without redesigning the EventSub lease and writer coordination.

No authored JavaScript or TypeScript is used. Browser UI is Jinja2-rendered HTML/CSS. OBS synchronization is HTML refresh every three seconds; host actions return full page responses.

## Persona identity

`Persona.twitch_user_id` is unique. `PersonaRevision` stores original selected appearance attributes. `render_avatar` derives a local stable seed from persisted random seed, archetype and trait, and emits inert SVG. Avatar visibility is checked server-side. Browser edits require OAuth identity from a signed session. Chat edits require the sender identity from Twitch EventSub. Preview without authentication is not persisted.

## Story lifecycle

`StorySession.stage`: `GENERATING` → `REVIEW` → `READY` → `VOTING` → `GENERATING`, repeating. READY can PAUSE or FINISH. A proposal (`SceneProposal`) cannot become canonical until authenticated host approval. Approving writes `StoryNode`, updates active head and marks ancestors as canonical. A host may `fork_from` an older committed node only when READY, then open voting and create another child. Old nodes remain in SQLite and display as alternate branches.

`VotingRound` records choice labels and a unique effective vote per `(round_id, viewer_id)`. A viewer can change the selection before closure. A tie or zero votes selects the first available choice; the rule is deterministic and visible in the tests. Closing a round records the winning choice and moves to GENERATING. If the model fails, the state stays GENERATING and the host can retry without re-resolving the round.

## Narrative provider

`DemoGenerator` is a separate deterministic renderer. `OpenAICompatibleGenerator` targets a configured `/chat/completions` endpoint that supports structured JSON. A `NarrativeProposal` is validated using Pydantic before persistence. Viewer contributions are passed as untrusted fiction and cannot invoke arbitrary system tools. Host-approved content is bounded to a small selection.

## Twitch

The EventSub adapter uses `channel.chat.message` v1 and a user OAuth token with `user:read:chat` scope. The broadcaster and reader must be the same configured OAuth user. Token vault stores encrypted access/refresh tokens. A background process creates the subscription upon a WebSocket welcome, handles `notification` messages, keepalives, reconnection URL migration, revocation, and reconnect after a lost connection. Official Twitch docs say lost events cannot be replayed. The connector refuses untrusted reconnect hosts. Accepted commands get bounded fixed threaded replies via Helix when `user:write:chat` is authorized. Ordinary chat can receive an AI reply only when the host explicitly enables the persisted preference; replies are capped at six per minute and share the paced outbound queue.

Recent incoming messages and reply states are held in a bounded in-memory transcript and rendered only in the host-authenticated `/host/chat` page. It refreshes every three seconds. Raw chat text is not written to SQLite and is not exposed by `/health` or the public OBS overlay.

## Known architectural limitations

- Host dashboard refreshes manually; overlay page refreshes every three seconds, not streaming DOM deltas.
- The AI chat responder has unit/mock verification only; an actual model-generated chat reply has not been confirmed on Twitch.
- Single process/SQLite is the supported operating model.
- `StoryService.process_chat` writes receipts only for recognized state-changing commands, persists accepted message IDs, and uses bounded process-local per-viewer cooldown and rejected-event replay caches. The app also serializes model generation with an in-process lock. These controls do not coordinate multiple workers, and accepted receipt retention/cleanup remains a deployment concern.
- Persona relationships, voice capture, camera guidance, image-generation models, richer alternate-timeline exploration, and multi-stream collaboration are not implemented.
- The stored Twitch host identity, active EventSub subscription, one real schema-validated AI narrative, and broadcaster chat/reply flow have been verified with configured credentials. Two-viewer participation/voting, reconnect under live traffic, and browser/OBS visual acceptance remain unverified; see `FINAL_EVIDENCE_REPORT.md`.
