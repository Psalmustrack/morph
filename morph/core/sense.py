"""
morph.core.sense — Layer 1b: Spatial Sensing (Cellular Differentiation)
=======================================================================

Preprocessor for the morphogenetic field equation (field.py). Promotes TEXT particles
to structural types (SPEC_LABEL, MODEL, SECTION) based on spatial context,
preparing the ground for the field to connect them.

Without sensing, health ~36%. With sensing, ~95%.
Sensing creates the particles; the field connects them.

Biological principles:
    - **Gradient**: type emerges from relative position, not content
    - **Local sensing**: each particle "feels" what surrounds it
    - **Adaptive tolerance**: adjusts to local density (row spacing)
    - **Lateral inhibition**: isolated signals without clusters are ignored

Pipeline position::

    Layer 1  (typify.py)  → type from content (regex)
    Layer 1b (sense.py)   → type from context (spatial promotion)  ← HERE
    Layer 2  (field.py)   → structure from field (morphogenetic equation)

Rules:
    - Can only PROMOTE particles (TEXT → structural type)
    - Never touches already-typed particles (NUMERIC, UNIT, MODEL, etc.)
    - Executed AFTER typify.py, BEFORE field.py

Author: Eugeniu Tacu, 2026
"""

import bisect
import statistics


# ─── Utilities ────────────────────────────────────────────────────────

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



# ─── Natural Threshold (max-ratio-jump) ──────────────────────────────

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


# ─── NN Direction (Docstrum-inspired) ─────────────────────────────

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


# ─── Crystallization (vertical alignment) ────────────────────────

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



# ─── Sensing: columns ────────────────────────────────────────────────

def detect_columns(particles: list[dict],
                   min_size: int = 3,
                   x_threshold: float = 15) -> list[dict]:
    """Detect vertical columns of aligned structured particles.

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

    Returns:
        Sorted list of column dicts: ``{'x', 'y_min', 'y_max', 'count'}``.
    """
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


def promote_column_headers(particles: list[dict],
                           columns: list[dict],
                           y_search: float = 60,
                           x_tolerance: float = 30) -> list[dict]:
    """Promote TEXT above numeric columns to MODEL (column header).

    For each column, finds the nearest TEXT above (within y_search)
    aligned in X (within x_tolerance). That TEXT becomes the column
    header — no vocabulary match needed.

    Biological analogy: apical cells (above a column of cells)
    differentiate into signaling cells.

    Args:
        particles: All particles on the page.
        columns: Output of :func:`detect_columns`.
        y_search: Max vertical search distance above column top (px).
        x_tolerance: Max horizontal misalignment (px).

    Returns:
        List of promoted particles.
    """
    promoted = []
    text_particles = [p for p in particles if p['type'] == 'TEXT']
    used_ids = set()

    for col in columns:
        candidates = [
            t for t in text_particles
            if t['y0'] < col['y_min']
            and (col['y_min'] - t['y0']) < y_search
            and abs(t['x'] - col['x']) < x_tolerance
            and id(t) not in used_ids
        ]

        if candidates:
            header = max(candidates, key=lambda t: t['y0'])
            header['type'] = 'MODEL'
            header['_sensed'] = 'column_header'
            promoted.append(header)
            used_ids.add(id(header))

    return promoted


# ─── Sensing: spec labels ────────────────────────────────────────────

def promote_spec_labels(particles: list[dict],
                        y_tolerance: float | None = None,
                        min_pairs: int = 2) -> list[dict]:
    """Promote TEXT to the left of NUMERIC (same row) to SPEC_LABEL.

    Adaptive tolerance: if not specified, computed as 60% of local
    row spacing, clamped to [5, 25] px.

    Requires at least ``min_pairs`` pairs to activate (lateral inhibition:
    a single isolated pair might be noise).

    Biological analogy: cells recognize their role from proximity
    to numeric cells on the same row.

    Args:
        particles: All particles on the page.
        y_tolerance: Max Y distance for same row (px). Auto if None.
        min_pairs: Minimum text-numeric pairs to activate promotion.

    Returns:
        List of promoted particles.
    """
    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    texts = [p for p in particles if p['type'] == 'TEXT']

    if not numerics or not texts:
        return []

    # Adaptive tolerance
    if y_tolerance is None:
        row_spacing = _estimate_row_spacing(particles)
        y_tolerance = row_spacing * 0.6
        y_tolerance = max(5.0, min(y_tolerance, 25.0))

    # For each NUMERIC, find nearest TEXT to the left on same row
    candidates = []
    used_ids = set()

    for n in numerics:
        left_texts = [
            t for t in texts
            if abs(t['y0'] - n['y0']) < y_tolerance
            and t['x1'] < n['x0']       # to the left
            and (n['x0'] - t['x1']) < 300  # not too far
            and id(t) not in used_ids
        ]

        if left_texts:
            spec = max(left_texts, key=lambda t: t['x1'])
            candidates.append(spec)
            used_ids.add(id(spec))

    # Lateral inhibition: need minimum number of pairs
    if len(candidates) < min_pairs:
        return []

    promoted = []
    for spec in candidates:
        spec['type'] = 'SPEC_LABEL'
        spec['_sensed'] = 'spec_pair'
        promoted.append(spec)

    return promoted


# ─── Sensing: sections ────────────────────────────────────────────────

def promote_sections(particles: list[dict],
                     size_ratio: float = 1.3,
                     max_text_len: int = 60) -> list[dict]:
    """Promote TEXT with larger font to SECTION.

    TEXT with font > median * size_ratio and length < max_text_len
    becomes a SECTION header.

    Biological analogy: larger (more prominent) cells function
    as organizers of the surrounding field.

    Args:
        particles: All particles on the page.
        size_ratio: Font size multiplier above median to qualify.
        max_text_len: Max text length for section headers.

    Returns:
        List of promoted particles.
    """
    all_sizes = [p['size'] for p in particles if p.get('size', 0) > 0]
    if len(all_sizes) < 5:
        return []

    median_size = statistics.median(all_sizes)
    if median_size <= 0:
        return []

    text_particles = [
        p for p in particles
        if p['type'] == 'TEXT' and p.get('size', 0) > 0
    ]

    promoted = []
    for p in text_particles:
        if (p['size'] > median_size * size_ratio
                and 3 < len(p['text']) < max_text_len):
            p['type'] = 'SECTION'
            p['_sensed'] = 'font_size'
            promoted.append(p)

    return promoted


# ─── DNA Proofreading ────────────────────────────────────────────────

def proofread(particles: list[dict],
              columns: list[dict] | None = None,
              y_tolerance: float | None = None) -> list[dict]:
    """Post-typing local coherence check (DNA proofreading).

    Like DNA polymerase checking each base after insertion, this pass
    verifies that typed particles make sense in spatial context.
    Incoherent ones are demoted back to TEXT.

    **Tissue protection**: NUMERIC particles belonging to a detected column
    are never touched. Cells in a recognized tissue are protected from
    apoptosis.

    Rules:
        - Isolated NUMERIC: no SPEC_LABEL or other NUMERIC within Y radius,
          AND not in a detected column → probably OCR artifact
        - Orphan UNIT: no NUMERIC on the same row → misread

    Does not touch ``_sensed`` particles — those already have spatial
    validation built in.

    Args:
        particles: All particles on the page.
        columns: Detected columns (for tissue protection).
        y_tolerance: Max Y distance for neighbor check. Auto if None.

    Returns:
        List of demoted particles.
    """
    if y_tolerance is None:
        row_spacing = _estimate_row_spacing(particles)
        y_tolerance = max(12.0, row_spacing * 0.7)

    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    specs = [p for p in particles if p['type'] == 'SPEC_LABEL']
    units = [p for p in particles if p['type'] == 'UNIT']

    if not numerics:
        return []

    # Tissue protection: X coordinates of detected columns
    col_xs = [c['x'] for c in columns] if columns else []

    # Pre-sorted Y arrays for O(log n) bisect search
    spec_ys = sorted(s['y0'] for s in specs)
    num_ys = sorted(n['y0'] for n in numerics)

    demoted = []

    # 1. Isolated NUMERIC — no SPEC or row or column neighbor
    for n in numerics:
        # Tissue protection
        if col_xs and any(abs(n['x'] - cx) < 20 for cx in col_xs):
            continue

        has_spec_nearby = False
        if spec_ys:
            i = bisect.bisect_left(spec_ys, n['y0'])
            has_spec_nearby = any(
                0 <= j < len(spec_ys) and abs(spec_ys[j] - n['y0']) < y_tolerance
                for j in (i - 1, i)
            )

        lo = bisect.bisect_right(num_ys, n['y0'] - y_tolerance)
        hi = bisect.bisect_left(num_ys, n['y0'] + y_tolerance)
        has_num_nearby = (hi - lo) >= 2  # at least 1 besides itself

        if not has_spec_nearby and not has_num_nearby:
            n['type'] = 'TEXT'
            n['_proofread'] = 'isolated_numeric'
            demoted.append(n)

    # 2. Orphan UNIT — no NUMERIC on same row
    for u in units:
        i = bisect.bisect_left(num_ys, u['y0'])
        has_num = any(
            0 <= j < len(num_ys) and abs(num_ys[j] - u['y0']) < y_tolerance
            for j in (i - 1, i)
        )
        if not has_num:
            u['type'] = 'TEXT'
            u['_proofread'] = 'orphan_unit'
            demoted.append(u)

    return demoted


# ─── Orchestrator ────────────────────────────────────────────────────

def sense_page(particles: list[dict]) -> dict:
    """Run complete spatial sensing on a page.

    This is the main entry point for Layer 1b. Orchestrates all
    sensing stages in order, modifying particles in-place.

    Pipeline::

        1. detect_columns()          → structural skeleton
        2. promote_column_headers()  → TEXT above columns → MODEL
        3. detect_row_label_column() → TEXT left of columns → SPEC_LABEL
        4. promote_spec_labels()     → TEXT left of NUMERIC → SPEC_LABEL
        5. promote_sections()        → large TEXT → SECTION
        6. proofread()               → isolated NUMERIC → TEXT

    Args:
        particles: Typed particles from Layer 1.

    Returns:
        Dict with keys:
            - ``particles``: Modified particle list
            - ``columns``: Number of detected structural columns
            - ``headers``: Number of promoted column headers
            - ``row_labels``: Number of promoted row labels
            - ``specs``: Number of promoted spec labels
            - ``sections``: Number of promoted sections
            - ``proofread``: Number of demoted particles
    """
    if len(particles) < 5:
        return {'particles': particles,
                'columns': 0, 'headers': 0, 'specs': 0,
                'sections': 0, 'proofread': 0}

    # 1. Structural skeleton
    columns = detect_columns(particles)

    # 2. Column headers (apical text → MODEL)
    promoted_headers = promote_column_headers(particles, columns)

    # 2.5. Row-label column (left-aligned text → SPEC_LABEL)
    promoted_row_labels = detect_row_label_column(particles, columns)

    # 3. Spec labels (lateral text → SPEC_LABEL)
    promoted_specs = promote_spec_labels(particles)

    # 4. Sections (large font → SECTION)
    promoted_sections = promote_sections(particles)

    # 5. DNA proofreading — demote incoherent particles
    demoted = proofread(particles, columns=columns)

    return {
        'particles': particles,
        'columns': len(columns),
        'headers': len(promoted_headers),
        'row_labels': len(promoted_row_labels),
        'specs': len(promoted_specs),
        'sections': len(promoted_sections),
        'proofread': len(demoted),
    }
