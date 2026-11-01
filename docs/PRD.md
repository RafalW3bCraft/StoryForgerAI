# AI StoryForge PRD — MVP

## Intended users

Streamer hosts who want a recurring live format combining audience input with original fiction; viewers who want to participate as persistent characters rather than anonymous chat votes.

## Primary user stories

- As host, I authenticate, create a world, review an AI-generated scene and open a timed or manually managed vote.
- As viewer, I opt in through Twitch `!join`, choose my archetype and trait, and see my original avatar represented in the stream.
- As viewer, I cast or change a vote while voting is open and see totals in the overlay.
- As viewer, I submit a line/twist/action that does not appear publicly until approved by the host.
- As host, I approve a scene and see it committed to canonical story history.
- As host, I revisit an earlier node and fork without deleting the previous path.
- As an authenticated viewer, I edit my own character through a protected profile editor.

## Functional acceptance

- Real EventSub message creates a persona and vote after the host connects Twitch.
- All persona attributes survive restart in SQLite.
- Identical persona seed and appearance data render identical SVG output.
- A valid narrative proposal contains exactly 2–3 distinct branches and is only published upon host approval.
- OBS view displays canonical scene, active choices, vote counts, and character cards.
- There is no admin authority through fictional persona roles.

## Constraints

Strict Python-authored application logic; no copied Poketar assets; no synthetic evidence represented as live; demo mode accessible without Twitch keys; production live integration requires explicit secrets.

## Future features outside MVP

Native NiceGUI (when available), smoother browser updates, voice narration, optional camera-assisted customization, character relationships and cosmetics, audience fairness rules, server-side cooldowns, durable multi-stream support, image generation, rich recap exports.
