"""
morph.core.layer2_field.merge — Multi-line Spec Merging
=======================================================

Pre-processing: merge SPEC_LABEL spanning multiple rows.
"""

import bisect


def merge_multiline_specs(particles: list[dict],
                          y_tolerance: float = 9.0,
                          x_tolerance: float = 80.0) -> list[dict]:
    """Merge SPEC_LABEL on adjacent rows into a single composite label.

    "Sound" (y=688) + "pressure level" (y=695) → a single particle
    "Sound pressure level" with averaged Y.

    Guard: do NOT merge if there is a NUMERIC between the two candidate
    specs at the same Y — that means they are on different data rows.

    Args:
        particles: All particles on the page.
        y_tolerance: Max Y distance between lines to merge.
        x_tolerance: Max X distance between lines to merge.

    Returns:
        Particle list with multi-line specs consolidated.
    """
    specs = sorted(
        [p for p in particles if p['type'] == 'SPEC_LABEL'],
        key=lambda p: (p['y'], p['x']),
    )
    if len(specs) < 2:
        return particles

    num_ys = sorted(p['y'] for p in particles if p['type'] == 'NUMERIC')

    def _has_numeric_between(y_lo: float, y_hi: float) -> bool:
        """Check if any NUMERIC exists strictly between y_lo and y_hi."""
        if not num_ys:
            return False
        lo = bisect.bisect_right(num_ys, y_lo)
        hi = bisect.bisect_left(num_ys, y_hi)
        return lo < hi

    groups = [[specs[0]]]
    for s in specs[1:]:
        prev = groups[-1][-1]
        dy = abs(s['y'] - prev['y'])
        dx = abs(s['x'] - prev['x'])
        y_lo, y_hi = min(s['y'], prev['y']), max(s['y'], prev['y'])
        numeric_between = _has_numeric_between(y_lo, y_hi) if dy > 2 else False
        if dy < y_tolerance and dx < x_tolerance and not numeric_between:
            groups[-1].append(s)
        else:
            groups.append([s])

    merged_ids = set()
    new_particles = []
    for group in groups:
        if len(group) < 2:
            continue
        group.sort(key=lambda p: (p['y'], p['x']))
        merged = {
            'text': ' '.join(p['text'] for p in group)[:80],
            'x': min(p['x'] for p in group),
            'y': sum(p['y'] for p in group) / len(group),
            'x0': min(p.get('x0', p['x']) for p in group),
            'x1': max(p.get('x1', p['x']) for p in group),
            'y0': min(p.get('y0', p['y']) for p in group),
            'y1': max(p.get('y1', p['y']) for p in group),
            'type': 'SPEC_LABEL',
            'size': max(p.get('size', 0) for p in group),
        }
        new_particles.append(merged)
        for p in group:
            merged_ids.add(id(p))

    result = [p for p in particles if id(p) not in merged_ids]
    result.extend(new_particles)
    return result
