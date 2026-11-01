# Architecture decision log

- **ADR-001 — Python-authored frontend:** NiceGUI could not be installed in the offline build container. Use Jinja2-rendered HTML/CSS through FastAPI without author-written JS. OBS uses 3-second HTML refresh. Reconsider a Python UI framework once a package-connected environment is available.
- **ADR-002 — SQLite first:** Single-process transactional DB is appropriate for a hackathon MVP; do not deploy multiple uncoordinated workers.
- **ADR-003 — Clean-room Poketar inspiration:** Preserve original ideas (customize/iterate/preview) but copy neither legacy code nor franchise assets.
- **ADR-004 — Strict story approval:** AI emits structured proposals. Only an authenticated host can approve canonical changes.
- **ADR-005 — EventSub first:** Twitch WebSocket user-token subscription is simpler for a quick live proof than Extension deployment and review.
- **ADR-006 — Deterministic offline generator:** Offline mode is explicitly labeled and allows judges to exercise the UI without AI credentials. It does not satisfy proof of real AI generation or live Twitch connectivity.
- **ADR-007 — Non-destructive branching:** Old story nodes persist, canon is the ancestor chain of the selected head, and forks mark previously chosen paths as alternatives.
- **ADR-008 — Persisted pause origin:** A paused story stores its prior effective stage. Resuming a paused vote returns to `VOTING`; it does not silently create a new `READY` state or accept votes while paused.
- **ADR-009 — Database voting invariant:** A partial unique SQLite index permits at most one `OPEN` voting round per story session. Service checks remain the user-facing error path, while the index protects concurrent writers.
- **ADR-010 — Bounded canonical context:** Generation receives at most six canonical ancestors and a 3,800-character synopsis, plus bounded approved contributions and persona descriptors. Alternate branches and private Twitch identifiers are excluded.
