# StoryForge operations runbook

**Current support level:** single-process local hackathon/OBS demo. This is not a production deployment guide or approval for public internet exposure.

## Local live demo startup

1. Use Python 3.12 or 3.13 and install the project in an isolated environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install -e '.[dev]'
   ```

2. Configure the 13 values listed in `.env.example`. For live mode, configure all Twitch credentials, matching numeric broadcaster/reader IDs, a Fernet key, a unique session secret, the exact local `APP_BASE_URL`, and all three AI provider values. Live startup fails if the AI provider is incomplete.

3. Keep `.env` and the SQLite database in owner-controlled locations. On POSIX, make `.env` owner-only (`chmod 600 .env`); application startup creates or restricts the SQLite file to mode `0600`. The parent directory and backups must also be private. Never copy these files into Git or a recording.

4. Check configuration without printing values, then start the server:

   ```bash
   python -m storyforge doctor
   python -m storyforge
   ```

   Open exactly the URL printed at startup. This runner serves HTTP on loopback; do not switch to HTTPS. In Twitch's developer console, the redirect URI must exactly match `APP_BASE_URL/auth/callback`. `doctor --live` makes a real provider request, may incur model cost, may refresh the encrypted host token, and does not prove chat delivery.

5. Host signs in as the configured broadcaster and checks `/health` for `twitch=LIVE_TWITCH`, `eventsub_subscribed=true`, and the expected AI provenance. Subscription status alone is not evidence of a received chat message. The redacted counters record received notifications and aggregate accepted/ignored/cooldown/invalid/duplicate/error outcomes; they expose no user IDs or message text.

6. With two real viewer accounts in the configured channel, first approve the current proposal in Host Studio and open its vote. Send separate commands at least one second apart: `!join`; then `!persona scholar`, `!trait brave`, `!avatar random`; then `!vote A` or `!vote B`. Confirm the overlay and story stage change. Do not use the demo simulator as live evidence.

7. In OBS, add a Browser Source at `APP_BASE_URL/overlay` and set it to 1920×1080. The page refreshes every three seconds. Check scene, personas and vote counts, and keep the browser source read-only.

8. Stop with Ctrl+C and wait for the application shutdown message. The current story, persona revisions, AI provenance, accepted receipts and votes are stored in SQLite. Restart and inspect `/health` and Host Studio to confirm persistence before resetting or archiving anything.

## Backup, restore and credential rotation

- The SQLite file contains story content, Twitch-linked identities, votes and encrypted host tokens. Stop StoryForge before copying the DB for a consistent backup, restrict the backup to owner-only permissions, and store it separately from `.env`.
- A restore drill is not yet evidenced. Before relying on a backup, restore a copy into a separate directory and verify story head, proposal/node provenance, personas, revisions, voting state and the ability to decrypt or reauthorize the host token.
- Rotate a Twitch client secret in Twitch Developer Console and update `.env`; complete a new browser OAuth flow to prove the new secret works. The existing encrypted token does not validate a newly configured client secret.
- Rotate the AI key through its provider and verify with one bounded `doctor --probe ai` request. Keep spend limits at the provider.
- Rotate `STORYFORGE_SECRET` to invalidate existing signed sessions; log in again.
- Do not replace `TOKEN_ENCRYPTION_KEY` while the only token is encrypted under the old key. Back up the database, then either migrate the vault by decrypting and re-encrypting with both keys in a controlled offline step, or generate a new host OAuth token and save it under the new key. Verify EventSub reconnect before retiring the old key/backup.

## Public production gap

Do not expose the current Uvicorn process directly to the internet. Production still needs trusted HTTPS termination and proxy configuration, a deployment identity/secret store, health/readiness separation, database migrations, tested backup/restore and rollback, dependency locking, log/metrics retention, abuse/provider spend controls, and independent security review.

The application supports one process and local SQLite. SQLite with one writer may be suitable for a small controlled demo, but cross-process cooldowns and EventSub coordination are not implemented. A multi-worker deployment needs PostgreSQL plus distributed event ownership, replay/deduplication, and shared rate limits; simply increasing Uvicorn workers is unsupported.
