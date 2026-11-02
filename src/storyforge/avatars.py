"""Original, deterministic, Python-generated SVG portraits. No remote assets or scripts."""

from __future__ import annotations

import random
from hashlib import sha256
from html import escape

from .models import Persona

ARCHETYPES = ("scholar", "guardian", "trickster", "explorer", "bard", "inventor")
TRAITS = ("curious", "brave", "kind", "mysterious", "clever", "playful")
PALETTES = {
    "violet": ("#382763", "#aa8cff", "#ecd7ff"),
    "emerald": ("#124b43", "#66e5b0", "#c9ffdf"),
    "ember": ("#603129", "#ff9b6a", "#ffe1b9"),
    "azure": ("#183a65", "#65bbff", "#d4f0ff"),
    "gold": ("#57421f", "#f5cf73", "#fff0b6"),
}
ACCESSORIES = ("star", "moon", "gem", "leaf", "gear")


def choose_random_seed() -> str:
    import secrets

    return secrets.token_hex(12)


def render_avatar(persona: Persona, *, size: int = 256, variation: int = 0) -> str:
    if size not in (128, 256, 512):
        raise ValueError("Unsupported avatar size")
    if not 0 <= variation <= 25:
        raise ValueError("Variation out of bounds")
    palette = PALETTES.get(persona.palette, PALETTES["violet"])
    seed = sha256(
        (persona.seed + persona.archetype + persona.trait + str(variation)).encode()
    ).digest()
    # Randomness only varies cosmetic output; it never creates tokens or identities.
    rng = random.Random(int.from_bytes(seed[:8], "big"))  # nosec B311
    skin = rng.choice(("#f1cbad", "#bc8369", "#e0ae82", "#765446", "#ddab9d"))
    eye = rng.choice(("#342e47", "#273b4c", "#60483e"))
    headgear = {
        "scholar": '<path d="M70 91 L93 29 L146 91 Z" fill="{accent}" stroke="{light}" stroke-width="4"/>',
        "guardian": '<path d="M65 92 Q107 21 150 92 L138 80 L79 80 Z" fill="{accent}" stroke="{light}" stroke-width="4"/>',
        "trickster": '<path d="M62 85 Q49 40 80 37 L92 76 Q111 22 145 40 L152 86 Z" fill="{accent}" stroke="{light}" stroke-width="4"/>',
        "explorer": '<path d="M51 86 Q110 26 164 86 Z" fill="{accent}" stroke="{light}" stroke-width="5"/>',
        "bard": '<path d="M70 77 Q107 40 148 75 L164 89 L57 90 Z" fill="{accent}" stroke="{light}" stroke-width="4"/>',
        "inventor": '<path d="M64 82 L72 48 L149 48 L156 82 Z" fill="{accent}" stroke="{light}" stroke-width="4"/>',
    }.get(persona.archetype, '<path d="M70 91 L93 29 L146 91 Z" fill="{accent}"/>')
    symbols = {
        "star": '<path d="M0 -15 L4 -4 L16 -4 L7 3 L10 15 L0 8 L-10 15 L-7 3 L-16 -4 L-4 -4 Z"/>',
        "moon": '<path d="M-5 -13 A14 14 0 1 0 13 7 A12 12 0 0 1 -5 -13 Z"/>',
        "gem": '<path d="M-13 -7 L0 -15 L13 -7 L10 9 L0 17 L-10 9 Z"/>',
        "leaf": '<path d="M-15 9 Q-8 -18 15 -13 Q10 13 -15 9 Z"/>',
        "gear": '<path d="M-4 -16 L4 -16 L6 -10 L12 -13 L16 -7 L12 -1 L16 5 L12 12 L5 9 L2 16 L-5 16 L-7 9 L-14 11 L-16 5 L-12 -2 L-15 -8 L-9 -12 L-4 -8 Z"/>',
    }
    symbol = symbols.get(persona.accessory, symbols["star"])
    pattern = "".join(
        f'<circle cx="{rng.randint(18, 202)}" cy="{rng.randint(18, 210)}" r="{rng.randint(1, 3)}" fill="{palette[2]}" opacity=".4"/>'
        for _ in range(20)
    )
    gear = headgear.format(accent=palette[1], light=palette[2])
    name = escape(persona.alias, quote=True)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 220 220" role="img" aria-label="Original portrait of {name}">
<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="{palette[0]}"/><stop offset="1" stop-color="#10142a"/></linearGradient></defs>
<rect width="220" height="220" rx="32" fill="url(#bg)"/>{pattern}
<circle cx="110" cy="104" r="76" fill="none" stroke="{palette[1]}" opacity=".5" stroke-width="3"/>
<path d="M27 219 Q29 159 110 153 Q192 157 194 219 Z" fill="{palette[1]}" stroke="{palette[2]}" stroke-width="4"/>
<path d="M81 157 Q110 184 138 157 L127 211 L93 211 Z" fill="{palette[0]}"/>
<rect x="93" y="133" width="34" height="32" rx="12" fill="{skin}"/>
<ellipse cx="110" cy="106" rx="45" ry="53" fill="{skin}" stroke="{palette[0]}" stroke-width="4"/>
{gear}
<ellipse cx="93" cy="112" rx="4" ry="6" fill="{eye}"/><ellipse cx="127" cy="112" rx="4" ry="6" fill="{eye}"/>
<path d="M96 134 Q110 144 124 134" stroke="{eye}" stroke-width="3" fill="none" stroke-linecap="round"/>
<g transform="translate(109 187)" fill="{palette[2]}" stroke="{palette[0]}" stroke-width="1.4">{symbol}</g>
</svg>'''
    return svg
