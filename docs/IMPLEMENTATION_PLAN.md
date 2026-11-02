# Build phases and exit gates

1. **Foundation:** Python package and FastAPI routes, DB schemas, config and startup. Complete for local MVP.
2. **Persona Forge:** persistent Twitch user IDs, profile editing, version history and deterministic original SVG avatars. Implemented and tested; live OAuth pending.
3. **Narrative Engine:** Pydantic schema, deterministic story fallback, optional live model adapter, host approval. Implemented and tested with mocks; live model pending.
4. **Twitch and Votes:** EventSub subscription, duplicate suppression, chat parsing and transactional votes. Implemented with unit/mock tests; real Twitch pending.
5. **Host / OBS:** Host Studio, contribution queue, fork controls, browser-source overlay and graph. Implemented; OBS application smoke test pending.
6. **Security / Quality:** access controls, CSRF, SVG assets, OAuth checks, regression coverage and manual review. Targeted checks pass; full HTTP acceptance and independent scanners are blocked.
7. **ECC / Codex:** substantive Codex engineering changes and cached official ECC skill guidance applied. Native plugin was unavailable; actual `/status` ID and Git commits remain blocked.
8. **Hackathon:** real Twitch and model demos, browser/OBS verification, sub-3-minute video, public repository verification, organizer eligibility interpretation and Devpost submission remain incomplete.

Prioritize real Twitch verification and Codex/ECC tool use above optional cosmetic features.
