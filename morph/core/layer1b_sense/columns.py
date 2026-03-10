"""
morph.core.layer1b_sense.columns — Column Detection
===================================================

Detect vertical alignment of particles to identify table columns.
"""

import statistics


def _cluster_by_x(items: list[dict], threshold: float = 15,
                  x_key: str = 'x') -> list[dict]:
    """Group items by X-axis proximity (agglomerative clustering).

    Args:
        items: Particles or dicts with positional keys.
        threshold: Max distance to belong to same cluster (px).
        x_key: Key for X coordinate. ``'x'`` = center (default),
               ``'x0'`` = left edge (more stable for variable-width text).

    Returns:
        List of cluster dicts: ``{'x_mean': float, 'items': [...]}``.
    """
    clusters = []
    for item in sorted(items, key=lambda p: p[x_key]):
        matched = False
        for c in clusters:
            if abs(c['x_mean'] - item[x_key]) < threshold:
                c['items'].append(item)
                c['x_mean'] = (
                    sum(i[x_key] for i in c['items']) / len(c['items'])
                )
                matched = True
                break
        if not matched:
            clusters.append({'x_mean': item[x_key], 'items': [item]})
    return clusters


def _natural_threshold(gaps: list[float]) -> float:
    """Find natural boundary threshold from the maximum relative jump.

    The perceptual principle: boundaries emerge from the maximum
    discontinuity in the gap distribution. Where the spacing "jumps"
    the most, there is a structural boundary.

    Used by sensing to calibrate where groups of particles begin and
    end — enabling correct promotion of headers, labels, sections.

    Args:
        gaps: List of positive gaps (pixels).

    Returns:
        Threshold (midpoint of the max jump), or above all gaps if no break.
    """
    if len(gaps) < 3:
        return statistics.median(gaps) if gaps else 10
    sorted_gaps = sorted(gaps)

    best_ratio = 1.0
    best_idx = 0
    for i in range(len(sorted_gaps) - 1):
        if sorted_gaps[i] > 0:
            ratio = sorted_gaps[i + 1] / sorted_gaps[i]
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i

    if best_ratio < 1.5:
        return sorted_gaps[-1] + 1  # above all → no boundary

    return (sorted_gaps[best_idx] + sorted_gaps[best_idx + 1]) / 2


def _nn_column_evidence(row_particles: list[dict],
                        all_particles: list[dict]) -> list[bool]:
    """Nearest-neighbor direction evidence for column boundaries.

    Docstrum principle (O'Gorman 1993): if a word's nearest neighbor
    across all particles is NOT the next word on its row, there is
    likely a column boundary between them. The NN "escapes" vertically
    because the next column is farther than the next row.

    Complements _natural_threshold: gap magnitude detects bimodal
    distributions; NN direction detects boundaries even in equispaced
    tables where gaps are uniform (no bimodality).

    Args:
        row_particles: Particles on one row, sorted by x0.
        all_particles: All particles on the page.

    Returns:
        List of bool (one per gap). True = NN evidence for boundary.
    """
    if len(row_particles) < 2:
        return []

    sorted_row = sorted(row_particles, key=lambda p: p['x0'])
    row_ids = set(id(p) for p in sorted_row)

    evidence = []
    for i in range(len(sorted_row) - 1):
        p = sorted_row[i]
        next_p = sorted_row[i + 1]

        # Distance to next word on this row
        dx = p['x'] - next_p['x']
        dy = p['y'] - next_p['y']
        d_next = (dx * dx + dy * dy) ** 0.5

        # Is there a particle in a DIFFERENT row that is:
        # (a) significantly closer than next_p (< 70% of d_next)
        # (b) more vertical than horizontal (dy > dx)
        # This filters diagonal neighbors and marginal cases.
        has_vertical_nn = False
        for q in all_particles:
            if id(q) in row_ids:
                continue
            dx2 = abs(p['x'] - q['x'])
            dy2 = abs(p['y'] - q['y'])
            d2 = (dx2 * dx2 + dy2 * dy2) ** 0.5
            if d2 < d_next * 0.5 and dy2 > dx2:
                has_vertical_nn = True
                break

        evidence.append(has_vertical_nn)

    return evidence


def _crystallize_columns(all_particles: list[dict]) -> list[float]:
    """Find column boundaries from vertical alignment (crystallization).

    When horizontal gaps within a row are equispaced (no bimodality),
    the vertical alignment of X-centers across ALL rows reveals columns:
    particles in the same column cluster at similar X positions.

    Collects X-centers from all particles, sorts them, computes gaps
    between consecutive centers. Intra-column gaps are tiny (vertical
    alignment jitter), inter-column gaps are large → bimodal.
    Applies _natural_threshold to find the column boundaries.

    Args:
        all_particles: All particles in the table.

    Returns:
        Sorted list of X positions where column boundaries fall.
        Empty if no columnar pattern found.
    """
    if len(all_particles) < 4:
        return []

    x_centers = sorted(p['x'] for p in all_particles)

    # Gap tra centri X consecutivi (ignora sovrapposti)
    gaps = []
    positions = []
    for i in range(len(x_centers) - 1):
        g = x_centers[i + 1] - x_centers[i]
        if g > 0.5:  # ignora duplicati
            gaps.append(g)
            positions.append((x_centers[i] + x_centers[i + 1]) / 2)

    if len(gaps) < 3:
        return []

    threshold = _natural_threshold(gaps)
    if threshold > max(gaps):
        return []  # nessuna bimodalita' nemmeno qui

    return [pos for g, pos in zip(gaps, positions) if g > threshold]


def _extract_vertical_lines(drawings: list[dict],
                             min_height: float = 5) -> list[float]:
    """Extract vertical line X positions from page drawings.

    Parses stroke/fill paths and extracts vertical line segments.
    A vertical line has x1≈x2 with significant |y2-y1|.

    Args:
        drawings: Output from page.extract_drawings()
        min_height: Minimum line height to consider (px)

    Returns:
        Sorted list of X positions (average of x1, x2)
    """
    if not drawings:
        return []

    vertical_xs = []

    for d in drawings:
        # Process stroke/fill paths
        if d.get('type') not in ('s', 'f', 'fs'):
            continue

        items = d.get('items', [])
        for item in items:
            # item format: ('l', Point(x1, y1), Point(x2, y2))
            if not isinstance(item, tuple) or len(item) < 3:
                continue

            cmd = item[0]
            if cmd != 'l':  # line segments only
                continue

            # Extract points (handle both Point objects and tuples)
            p1 = item[1]
            p2 = item[2]

            # Get coordinates (Point objects have .x, .y attributes)
            x1 = p1.x if hasattr(p1, 'x') else p1[0]
            y1 = p1.y if hasattr(p1, 'y') else p1[1]
            x2 = p2.x if hasattr(p2, 'x') else p2[0]
            y2 = p2.y if hasattr(p2, 'y') else p2[1]

            # Check if vertical
            dx = abs(x2 - x1)
            dy = abs(y2 - y1)

            if dy >= min_height and dx < 3:  # vertical tolerance 3px
                x_mid = (x1 + x2) / 2
                vertical_xs.append(x_mid)

    return sorted(set(vertical_xs))  # unique, sorted


def detect_columns_from_drawings(particles: list[dict],
                                   drawings: list[dict]) -> list[dict]:
    """Detect columns using vertical lines from drawings (bordered tables).

    Uses exact boundaries from vector drawings instead of geometric clustering.
    Each vertical line defines a column boundary. Particles are assigned to
    columns based on which boundaries they fall between.

    Args:
        particles: All particles on the page
        drawings: Output from page.extract_drawings()

    Returns:
        Sorted list of column dicts: {'x', 'y_min', 'y_max', 'count'}
        Empty if no vertical lines found
    """
    vertical_xs = _extract_vertical_lines(drawings)
    if len(vertical_xs) < 2:
        return []  # need at least 2 lines to define 1 column

    # Define column ranges from boundaries
    # vertical_xs = [x1, x2, x3, x4] → columns: [x1-x2], [x2-x3], [x3-x4]
    structured_types = {'NUMERIC', 'SPEC_LABEL', 'MODEL', 'MODEL_CODE',
                        'UNIT', 'SECTION', 'SIZE_HEADER', 'KW_HEADER'}
    structured = [p for p in particles if p['type'] in structured_types]

    if not structured:
        return []

    columns = []
    for i in range(len(vertical_xs) - 1):
        x_left = vertical_xs[i]
        x_right = vertical_xs[i + 1]
        x_mid = (x_left + x_right) / 2

        # Find particles in this column
        col_particles = [
            p for p in structured
            if x_left <= p['x'] <= x_right
        ]

        if len(col_particles) >= 3:  # minimum column size
            ys = [p['y0'] for p in col_particles]
            distinct_ys = len(set(round(y) for y in ys))

            if distinct_ys >= 2:  # at least 2 rows
                columns.append({
                    'x': x_mid,
                    'y_min': min(ys),
                    'y_max': max(ys),
                    'count': len(col_particles),
                })

    return sorted(columns, key=lambda c: c['x'])


def detect_columns(particles: list[dict],
                   min_size: int = 3,
                   x_threshold: float = 15,
                   drawings: list[dict] | None = None) -> list[dict]:
    """Detect vertical columns of aligned structured particles.

    **v2.0 Phase 6: Hybrid boundary detection**
    - If drawings provided with vertical lines → use exact boundaries (bordered tables)
    - Otherwise → fallback to geometric clustering (borderless tables)

    A column requires:
        - 3+ structured particles with similar X (within x_threshold)
        - At least 2 distinct Y values (not all on the same row)

    Uses structured particles only (NUMERIC, SPEC_LABEL, MODEL, UNIT, etc.).
    Raw TEXT is too noisy (captions, disclaimers, notes outside the table).

    Biological analogy: recognizing columnar tissue from the regular
    vertical distribution of differentiated cells.

    Args:
        particles: All particles on the page.
        min_size: Minimum particles per column.
        x_threshold: Max X distance for same column (px).
        drawings: Optional drawings from page.extract_drawings() (v2.0).

    Returns:
        Sorted list of column dicts: ``{'x', 'y_min', 'y_max', 'count'}``.
    """
    # v2.0: Try drawing-based detection first (exact boundaries)
    if drawings:
        cols_from_drawings = detect_columns_from_drawings(particles, drawings)
        if cols_from_drawings:
            return cols_from_drawings

    # Fallback: geometric clustering (v0.1 behavior)
    structured_types = {'NUMERIC', 'SPEC_LABEL', 'MODEL', 'MODEL_CODE',
                        'UNIT', 'SECTION', 'SIZE_HEADER', 'KW_HEADER'}
    structured = [p for p in particles if p['type'] in structured_types]
    if len(structured) < min_size:
        return []

    clusters = _cluster_by_x(structured, threshold=x_threshold)

    columns = []
    for c in clusters:
        if len(c['items']) < min_size:
            continue
        distinct_ys = len(set(round(p['y0']) for p in c['items']))
        if distinct_ys < 2:
            continue

        ys = [p['y0'] for p in c['items']]
        columns.append({
            'x': c['x_mean'],
            'y_min': min(ys),
            'y_max': max(ys),
            'count': len(c['items']),
        })

    return sorted(columns, key=lambda c: c['x'])
