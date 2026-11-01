# Build phases and exit gates

1. **Foundation:** Python package and FastAPI routes, DB schemas, config and startup. Complete for local MVP.
2. **Persona Forge:** persistent Twitch user IDs, profile editing, version history and deterministic original SVG avatars. Implemented and tested; live OAuth pending.
3. **Narrative Engine:** Pydantic schema, deterministic story fallback, optional live model adapter, host approval. Implemented and tested with mocks; live model pending.
4. **Twitch and Votes:** EventSub subscription, duplicate suppression, chat parsing and transactional votes. Implemented with unit/mock tests; real Twitch pending.
5. **Host / OBS:** Host Studio, contribution queue, fork controls, browser-source overlay and graph. Implemented; OBS application smoke test pending.
6. **Security / Quality:** access controls, CSRF, SVG assets, basic OAuth, test coverage. Automated tests passing; deployed security review pending.
7. **ECC / Codex:** install and apply official ECC from Codex, perform material development iterations and record session ID. **Not started; external requirement.**
8. **Hackathon:** external Twitch demo, real AI demo, 3-min video, repository publication, Devpost submission. **Not started.**

Prioritize real Twitch verification and Codex/ECC tool use above optional cosmetic features.
