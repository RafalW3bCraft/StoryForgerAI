# Judge testing instructions

This repository contains an offline demo and a real Twitch mode. The two must remain clearly labeled. The synthetic simulator is useful for judging story and persona behavior, but it is not evidence of Twitch connectivity.

## Clean local setup

Use Python 3.12 or newer in a clean environment:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
```

Set a unique session secret and demo password, run `python -m storyforge doctor`, then start `python -m storyforge`. Open the exact `http://...` address printed at startup (for `.env.example`, `http://127.0.0.1:8000`). The built-in runner speaks plain HTTP. If Uvicorn prints repeated `Invalid HTTP request received` warnings, confirm the browser did not upgrade the address to HTTPS: TLS sent to this HTTP port cannot reach the app. Twitch sign-in requests from another hostname are redirected to the configured `APP_BASE_URL` before session handling; continue using that configured origin so the browser sends its signed session cookie to the callback.

## Offline product flow

1. Create **The Last Library of Tomorrow** and inspect the initial proposal.
2. Approve it; the approved scene becomes canonical.
3. Start a vote. Use the explicitly labeled host simulator to send `!join`, `!persona scholar`, and `!vote A` for one viewer, and `!join`/`!vote B` for another.
4. Inspect the persona cards, avatar routes, vote totals, and contribution queue.
5. Approve a contribution, close the vote, inspect the next proposal, and approve it.
6. Revisit an earlier node and fork. Confirm the old branch remains stored as an alternative.
7. Pause during an open vote, confirm new votes are rejected, resume, and confirm the same round continues.
8. Restart with the same SQLite database and confirm personas, round/history, and current canon remain intact.
9. Open `/overlay` and `/graph.svg`. OBS Browser Source dimensions are 1920×1080. The overlay refreshes the page every three seconds.

## Real Twitch and AI acceptance

Before the real flow, register Twitch's exact redirect URI as `APP_BASE_URL/auth/callback`, configure `STORYFORGE_MODE=live`, and ensure `TWITCH_READER_ID` equals the configured broadcaster ID. Authorize the host through Twitch and confirm the app reaches `LIVE_TWITCH` only after an enabled EventSub subscription is accepted. Send `!join`, `!persona scholar`, `!trait curious`, and `!vote A` in the actual channel; check persisted identity-bound results.

Configure a provider/model that supports the configured `/chat/completions` request and JSON-object response format. `python -m storyforge doctor --live` makes a bounded host-token identity check and a small live inference request; it may refresh the stored token and may incur provider charges. It does not verify EventSub delivery. Confirm a returned proposal is validated, visibly labeled AI, and remains pending until host approval.

Do not label simulated events or mocked API fixtures as live Twitch or AI evidence. EventSub does not replay messages lost during a connection gap.

## Commands and evidence

```bash
python -m storyforge doctor
python -m storyforge doctor --live
python -m pytest -q
python -m pytest --cov=storyforge --cov-report=term-missing
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src/storyforge
python -m compileall -q src
```

The 2026-11-02 audit could not complete the three HTTP acceptance tests because this execution environment stalls dispatching synchronous FastAPI routes through AnyIO; it also did not complete a real OAuth grant, receive EventSub chat, validate live AI generation, or inspect browser/OBS output. See `docs/TEST_REPORT.md` for exact evidence. The built-in runner is plain HTTP, and public HTTPS requires a TLS-terminating reverse proxy.
