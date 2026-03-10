"""
morph.core.layer1_typify.fragments — Fragment Reassembly
========================================================

Merge fragmented glyphs that were split by PDF encoding.
"""

from .classify import typify_word


def _merge_fragments(particles: list[dict],
                     model_patterns: list = None,
                     size_patterns: list = None,
                     y_tolerance: float = 2,
                     x_gap_max: float = 8) -> list[dict]:
    """Reassemble fragmented glyphs on the same line.

    Some PDFs encode "6,5 kW" as 4 separate glyphs: "6", ",", "5", "kW".
    This pass fuses adjacent short fragments and re-classifies the result.

    Only fuses sequences of "atomic" particles (text <= 4 chars each,
    close in X) — does not touch already-complete words.

    Args:
        particles: List of typed particles.
        model_patterns: Brand-specific model patterns for re-typing.
        size_patterns: Brand-specific size patterns for re-typing.
        y_tolerance: Max Y gap to consider same row (px).
        x_gap_max: Max X gap between adjacent fragments (px).

    Returns:
        Particle list with fragments merged where beneficial.
    """
    if not particles:
        return particles

    # Group by row (same Y within tolerance)
    rows: list[list[dict]] = []
    for p in sorted(particles, key=lambda p: (p['y0'], p['x0'])):
        if rows and abs(p['y0'] - rows[-1][0]['y0']) <= y_tolerance:
            rows[-1].append(p)
        else:
            rows.append([p])

    merged = []
    for row in rows:
        if len(row) < 2:
            merged.extend(row)
            continue

        row.sort(key=lambda p: p['x0'])

        i = 0
        while i < len(row):
            # Find sequence of short adjacent fragments
            j = i
            while (j + 1 < len(row)
                   and len(row[j]['text']) <= 4
                   and len(row[j + 1]['text']) <= 4
                   and (row[j + 1]['x0'] - row[j]['x1']) < x_gap_max):
                j += 1

            if j > i:
                frag_texts = [row[k]['text'] for k in range(i, j + 1)]
                combined = ''.join(frag_texts)
                new_type = typify_word(combined, model_patterns, size_patterns)

                # Only merge if resulting type is "useful" (not generic TEXT)
                if new_type != 'TEXT':
                    y1_max = max(row[k]['y1'] for k in range(i, j + 1))
                    merged.append({
                        'text': combined[:80],
                        'x': (row[i]['x0'] + row[j]['x1']) / 2,
                        'y': (row[i]['y0'] + y1_max) / 2,
                        'y0': row[i]['y0'],
                        'y1': y1_max,
                        'x0': row[i]['x0'],
                        'x1': row[j]['x1'],
                        'type': new_type,
                        'size': row[i]['size'],
                    })
                    i = j + 1
                    continue

            merged.append(row[i])
            i += 1

    return merged
