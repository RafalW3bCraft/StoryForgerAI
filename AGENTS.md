# StoryForge engineering instructions for Codex and ECC

Use OpenAI Codex as the substantive coding agent when the operator resumes development. Configure the official [Everything Claude Code](https://github.com/affaan-m/ECC) plugin in Codex if available. This project was initially bootstrapped by ChatGPT in a container without Codex CLI or an ECC installation; **do not claim Codex/ECC evidence exists until it has actually been generated**.

## Mandatory architecture constraints

- First-party executable application code must remain Python. Jinja2 HTML templates and CSS are declarative; do not add custom JavaScript or TypeScript. The current OBS overlay refreshes its page every three seconds.
- Preserve Twitch identity binding to immutable Twitch IDs. Never authorize an edit based solely on a display name or user-submitted ID.
- Keep untrusted chat, narrative generation, and privileged host operations separated.
- Do not copy older Poketar application files or branded images; clean-room implementation only. See `docs/POKETAR_PROVENANCE.md`.
- SQLite is authoritative. `StorySession.current_node_id` is the head of canon; historical nodes are never deleted by a fork.
- `SceneProposal` remains noncanonical until approved by the authenticated host.
- All scene proposals must validate through `NarrativeProposal` (Pydantic). A deterministic generator is explicitly marked DEMO.
- No secrets or raw provider tokens in the browser, source repo, or logs. Tokens are encrypted at rest.
- Never report a simulated event as real Twitch connectivity.

## ECC-style cycle

For each change: **Analyze → Plan → Write tests → Implement → Review → Verify → Record evidence**. Use actually available ECC skills for Python review, security review, test-driven development, and architecture. Do not fabricate skill invocations.

## Test commands

```bash
python -m pytest -q
python -m pytest --cov=storyforge --cov-report=term-missing
python -m compileall -q src
```

When installed: `ruff check src tests`, `ruff format --check src tests`, and `mypy src/storyforge` (fix issues found; avoid pretending these checks passed if unavailable). Tests must remain green. A genuine live Twitch test requires OAuth credentials and an actual broadcaster channel; fixtures do not satisfy this gate.

## Release rule

No submission-ready claim until real Twitch, real configured model, Codex session ID, ECC workflow evidence, complete public/unlisted demo video, GitHub repository URL, and final Devpost submission are confirmed. Do not invent any of these artifacts.
