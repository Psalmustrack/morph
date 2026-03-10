"""
morph.core.layer1b_sense.promote — Type Promotion
=================================================

Promote TEXT particles to structural types based on spatial context.
"""

import bisect
import statistics

from .rows import _estimate_row_spacing


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
