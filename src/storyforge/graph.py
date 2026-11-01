"""Pure-Python SVG renderer with canonical and alternate branch differentiation."""

from collections import defaultdict
from html import escape

from .models import StoryNode


def render_tree(nodes: list[StoryNode]) -> str:
    if not nodes:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 100"><text x="20" y="50" fill="#cfd7eb">No story nodes yet.</text></svg>'
    nodes = nodes[:32]
    by_id = {n.id: n for n in nodes}
    depths: dict[int, int] = {}

    def depth(n: StoryNode) -> int:
        if n.id in depths:
            return depths[n.id]
        if not n.parent_node_id or n.parent_node_id not in by_id:
            d = 0
        else:
            d = 1 + depth(by_id[n.parent_node_id])
        depths[n.id] = d
        return d

    groups = defaultdict(list)
    for n in nodes:
        groups[depth(n)].append(n)
    max_wide = max(len(v) for v in groups.values())
    width, height = max(640, max_wide * 290 + 50), max(150, (max(groups) + 1) * 140 + 30)
    positions = {}
    for d, members in groups.items():
        for i, n in enumerate(members):
            positions[n.id] = ((i + 0.5) * width / len(members), 52 + d * 135)
    segments = []
    boxes = []
    for n in nodes:
        x, y = positions[n.id]
        if n.parent_node_id in positions:
            px, py = positions[n.parent_node_id]
            segments.append(
                f'<path d="M{px} {py + 25} Q{px} {py + 70} {x} {y - 24}" fill="none" stroke="{"#69dabc" if n.is_canon else "#71809e"}" stroke-width="2.5"/>'
            )
        fill, stroke = ("#1e584c", "#69dabc") if n.is_canon else ("#303347", "#8790aa")
        label = escape(n.title[:31], quote=True)
        boxes.append(
            f'<rect x="{x - 124}" y="{y - 23}" width="248" height="48" rx="11" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/><text x="{x}" y="{y + 5}" text-anchor="middle" fill="#f3efff" font-size="13">#{n.id} {label}</text>'
        )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="Current green canon and grey preserved alternate story branches">'
        + "".join(segments + boxes)
        + "</svg>"
    )
