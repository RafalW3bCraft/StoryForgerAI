# Independent judging instructions

The current package is a local MVP, not a submitted Devpost artifact. It has no hosted instance or YouTube demonstration URL yet.

## Offline evaluation

1. Unzip, install Python 3.12+, create virtualenv and install the package via `pip install -e '.[dev]'`.
2. Copy `.env.example` to `.env`. Change the demo password and session secret.
3. Run `python -m storyforge` and open `http://127.0.0.1:8000`.
4. Sign in to Host Studio using your configured demo password.
5. Create a story; approve its initial scene; start voting.
6. Use the labeled simulator to register `Starlight`, select `scholar`, and vote `A`; register `Moonkeeper` and vote `B`. Add and approve a dialogue contribution.
7. Close voting, approve next scene, inspect `/overlay` and `/graph.svg`.
8. Revisit a previous node and generate another branch. Verify the first branch is still present but marked alternative.
9. Restart the process using the same SQLite path; verify that personas and story nodes persisted.

**The simulator is not a substitute for the hackathon's required real Twitch demonstration.**

## Real Twitch evaluation

Supply your own Twitch Developer client ID/secret, broadcaster/reader ID and authorized broadcaster account. Configure `STORYFORGE_MODE=live`, `TOKEN_ENCRYPTION_KEY`, `APP_BASE_URL` and `STORYFORGE_SECRET`. Finish host OAuth and confirm EventSub status `LIVE_TWITCH` in `/health`. Enter `!join` and `!vote A` in the actual configured Twitch channel and inspect the results. Do not claim this step completed until logs and UI confirm it.

## Real AI evaluation

Configure an actual OpenAI-compatible JSON-output chat-completion provider and model. Generate a scene, inspect the `AI` provenance label, verify its structured options, and approve only after review.

## Verification commands

`python -m pytest -q` · `python -m pytest --cov=storyforge --cov-report=term-missing` · `python -m ruff check src tests` · `python -m ruff format --check src tests` · `python -m mypy src/storyforge` · `python -m compileall -q src`.

If Python 3.14/AnyIO hangs before the first `TestClient` request, use Python 3.12 or 3.13 and a clean virtual environment; the targeted service/integration checks remain runnable in the supplied image.

The project intentionally does not bundle secret credentials, a generated Codex session ID, or a fabricated demo video.
