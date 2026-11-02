# Live demonstration script — target 2m45s

**Record only after the real acceptance flow succeeds.** Use a running StoryForge instance, an authorized Twitch channel with genuine viewer messages, one real validated AI scene, and the actual Codex development thread. Do not substitute simulator activity or static screenshots for Twitch operation.

| Time | Show and say |
|---|---|
| 0:00–0:15 | Show the real Twitch channel beside StoryForge/OBS. Point to `LIVE_TWITCH` and the channel identity without showing credentials. Introduce chat-driven branching stories. |
| 0:15–0:40 | Viewer A and Viewer B send `!join`. Show both distinct persistent personas and Python-generated avatars. Viewer A changes to `!persona scholar` and `!trait curious`. |
| 0:40–1:05 | Host creates **The Last Library of Tomorrow**. Show the real AI request, structured proposal and `AI-GENERATED` provenance, then approve it as host. |
| 1:05–1:35 | Start a vote. Show Viewer A sending `!vote A` and Viewer B sending `!vote B` in the actual channel. Show both votes in one persisted round, close it, and identify the single resolved choice. |
| 1:35–2:00 | Show a real viewer contribution waiting for moderation. Approve it, then show the host adding an in-character line or plot twist and generating the next scene from approved context. |
| 2:00–2:25 | Show the updated 1920×1080 OBS overlay, current canonical chapter, personas, vote result, connection status, and the retained alternative branch in `/graph.svg`. |
| 2:25–2:45 | Show the actual Codex session and test results. Run `/status` in the primary Codex thread and show its genuine session ID. Show the ECC skills actually applied and distinguish skill guidance from native plugin execution. |

## Evidence checklist

- [ ] `LIVE_TWITCH` follows a successful broadcaster OAuth and enabled EventSub subscription.
- [ ] Real viewer A and B messages are visible in the actual channel and change persisted StoryForge state.
- [ ] Persona customization, votes, approval, canonical branch, and restart persistence are shown live.
- [ ] AI provenance is shown only after a real provider response passes `NarrativeProposal` validation.
- [ ] Host-only controls and CSRF-protected actions are demonstrated.
- [ ] OBS overlay and story graph reflect the same live story state.
- [ ] Codex development activity and actual `/status` session ID are shown.
- [ ] No access token, refresh token, client secret, API key, authorization header, session cookie, or `.env` value appears on screen.
- [ ] The video is under three minutes, publicly visible on YouTube, contains no unlicensed music/assets, and is checked before adding its URL to Devpost.
- [ ] No simulated chat is presented as real Twitch evidence.

**Status:** not recordable from the current environment. Live Twitch, live model, browser/OBS, `/status`, and the YouTube URL remain unverified or unavailable. No video link has been invented.
