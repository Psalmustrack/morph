"""
morph.core.layer1b_sense.rows — Row Detection
=============================================

Detect horizontal rows and row spacing for particle grouping.
"""

import statistics

from .columns import _cluster_by_x


def _estimate_row_spacing(particles: list[dict]) -> float:
    """Estimate typical row spacing from NUMERIC Y-distribution.

    Biological analogy: a cell measures the distance to its neighbors
    to calibrate its own sensitivity radius.

    Returns:
        Median row spacing in pixels (default 15.0 if insufficient data).
    """
    ys = sorted(set(
        round(p['y0']) for p in particles if p['type'] == 'NUMERIC'
    ))
    if len(ys) < 3:
        return 15.0

    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    if not gaps:
        return 15.0

    gaps.sort()
    median_gap = gaps[len(gaps) // 2]
    # Filter anomalous gaps (section jumps > 2.5x median)
    normal_gaps = [g for g in gaps if 0 < g < median_gap * 2.5]

    return statistics.median(normal_gaps) if normal_gaps else 15.0


def _estimate_row_spacing_all(particles: list[dict]) -> float:
    """Estimate row spacing from ALL particles (not just NUMERIC).

    Needed for text-heavy tables where NUMERIC particles are sparse.

    Returns:
        Median row spacing in pixels.
    """
    ys = sorted(set(round(p['y0']) for p in particles))
    if len(ys) < 3:
        return 15.0
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    if not gaps:
        return 15.0
    gaps.sort()
    median_gap = gaps[len(gaps) // 2]
    normal_gaps = [g for g in gaps if 0 < g < median_gap * 2.5]
    return statistics.median(normal_gaps) if normal_gaps else 15.0


def _group_into_rows(particles: list[dict],
                     y_tolerance: float | None = None) -> list[list[dict]]:
    """Group particles into rows by Y-axis proximity.

    Perceptual grouping: particles that share the same Y-band belong
    to the same row. Tolerance is adaptive — computed from local
    row spacing to handle both dense and sparse layouts.

    Used by sensing (implicitly via detect_columns) and by the
    benchmark layer (explicitly for row-mode voting).

    Args:
        particles: Particles to group.
        y_tolerance: Max Y distance for same row. If None, auto-computed
                     as ``max(4.0, row_spacing * 0.5)``.

    Returns:
        List of rows, each a list of particle dicts.
    """
    if not particles:
        return []
    if y_tolerance is None:
        row_spacing = _estimate_row_spacing_all(particles)
        y_tolerance = max(4.0, row_spacing * 0.5)

    rows = []
    for p in sorted(particles, key=lambda p: p['y0']):
        placed = False
        for row in rows:
            row_y = sum(it['y0'] for it in row) / len(row)
            if abs(p['y0'] - row_y) < y_tolerance:
                row.append(p)
                placed = True
                break
        if not placed:
            rows.append([p])

    return rows


def assign_row_ids(particles: list[dict]) -> list[dict]:
    """Assign ``row_id`` to each particle based on Y-proximity clustering.

    Each particle gets a ``row_id`` integer (0 = topmost row).
    Particles in the same visual row share the same ``row_id``.

    This is the public API for row segmentation. Called by
    :func:`sense_page` as the last step in Layer 1b.

    Args:
        particles: All particles on the page (modified in-place).

    Returns:
        List of row descriptors: ``{row_id, y_center, y_min, y_max}``.
    """
    rows = _group_into_rows(particles)

    row_info = []
    for row_id, row_particles in enumerate(rows):
        y_values = [p.get('y0', p.get('y', 0)) for p in row_particles]
        y_center = sum(y_values) / len(y_values)
        y_min = min(y_values)
        y_max = max(y_values)

        for p in row_particles:
            p['row_id'] = row_id

        row_info.append({
            'row_id': row_id,
            'y_center': y_center,
            'y_min': y_min,
            'y_max': y_max,
        })

    return row_info


def promote_orphan_sections(particles: list[dict]) -> list[dict]:
    """Promote SECTION → SPEC_LABEL in rows that have NUMERICs but no spec.

    When a row contains NUMERIC particles but no SPEC_LABEL, the
    numerics become orphans (no spec to bind to). If the row has
    a SECTION particle, promote it to SPEC_LABEL so it can act
    as the row header.

    Example: "N° di unità collegabili (min - max)" is classified
    as SECTION but has NUMERIC values 1-5, 1-6 in the same row.

    Requires ``row_id`` to be assigned first via :func:`assign_row_ids`.

    Args:
        particles: Particles with ``row_id`` assigned (modified in-place).

    Returns:
        List of promoted particles.
    """
    # Group by row_id
    rows = {}
    for p in particles:
        rid = p.get('row_id')
        if rid is not None:
            rows.setdefault(rid, []).append(p)

    promoted = []
    for rid, row_ps in rows.items():
        has_numeric = any(p['type'] == 'NUMERIC' for p in row_ps)
        has_spec = any(p['type'] == 'SPEC_LABEL' for p in row_ps)

        if has_numeric and not has_spec:
            # Look for SECTION to promote
            for p in row_ps:
                if p['type'] == 'SECTION':
                    p['type'] = 'SPEC_LABEL'
                    p['_sensed'] = 'orphan_section_promoted'
                    promoted.append(p)
                    break  # One spec per row

    return promoted


def detect_row_label_column(particles, columns, x_max_gap=50):
    """Detect a row-label column to the left of the first structural column.

    Looks for TEXT particles vertically aligned by x0 (left edge) to the
    left of the first column, within the Y bounding box of detected columns.
    Promotes them to SPEC_LABEL.

    Uses x0 instead of x-center: "Weight" and "Sound pressure level" have
    different x-centers but identical x0 because they are left-aligned.

    Args:
        particles: All particles on the page.
        columns: Output of :func:`detect_columns`.
        x_max_gap: Max horizontal gap from first column (px).

    Returns:
        List of promoted particles.
    """
    if not columns:
        return []

    table_y_min = min(c['y_min'] for c in columns)
    table_y_max = max(c['y_max'] for c in columns)
    first_col_x = columns[0]['x']

    texts_left = [p for p in particles
                  if p['type'] == 'TEXT'
                  and p['x0'] < first_col_x - x_max_gap * 0.3
                  and p['y0'] >= table_y_min - 20
                  and p['y0'] <= table_y_max + 20]

    if len(texts_left) < 3:
        return []

    clusters = _cluster_by_x(texts_left, threshold=12, x_key='x0')

    best = None
    for c in clusters:
        if len(c['items']) >= 3:
            if best is None or len(c['items']) > len(best['items']):
                best = c

    if best is None:
        return []

    promoted = []
    for p in best['items']:
        p['type'] = 'SPEC_LABEL'
        p['_sensed'] = 'row_label_column'
        promoted.append(p)

    return promoted
