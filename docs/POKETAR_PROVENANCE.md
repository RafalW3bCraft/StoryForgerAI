# Poketar concept provenance

Referenced repository: https://github.com/RafalW3bCraft/Poketar

Inspected on 2026-10-30: `README.md`, `app.py`, `main.py`, `templates/index.html`, `templates/scanner.html`, `pyproject.toml`, `LICENSE`, and the unrelated `pikachu-hook/index.html`.

Ideas taken as **conceptual inspiration**: iterative avatar previews, trait- and archetype-driven appearances, user-facing character customization and character cards.

Important factual distinctions: the old `analyze_face_features()` uses a random selection seeded partly by timestamp, not actual face landmark analysis. Poketar's scanned application code has no persistent Twitch viewer/persona records. Its templates rely on authored browser JavaScript, and its artwork includes Pokémon-themed imagery. None of these files, images, names, or remote scripts were copied into StoryForge.

New implementation: `avatars.py` uses deterministic original SVG geometry and a per-persona stored seed. `models.py` provides unique Twitch identities and persona revisions. New templates are Jinja2 + CSS with no authored JS. Story and EventSub engines are original Python code.

Hackathon provenance: the original MVP predated the current Codex engineering pass. This pass made substantive implementation and test changes, but does not claim to have created the original project. The first Git commit is dated November 1, 2026, within the published submission period; that timestamp does not prove when every component was created or establish organizer approval. Codex session ID and native ECC plugin evidence were unavailable in this execution environment. Resolve eligibility with the organizer rather than asserting an interpretation.
