"""
morph.core.field — Layer 2: Morphogenetic Field Theory (Tissue Formation)
=========================================================================

The morphogenetic field equation for structured document parsing::

    Phi(i -> j) = W(type_i, type_j) * A_directed(i, j) / d3(i, j)^alpha

    d3 = sqrt(dx^2 + dy^2 + (lambda_z * dz_norm)^2)
    z_norm = log10(|value| + 1)

The morphogenetic field equation. Validated on 362K values, 6,238 pages, 5 brands.

The fundamental insight: document space is three-dimensional.
    - x, y = position on page (WHERE you are)
    - z = value magnitude (WHAT you are)

Row binding (Y) is independent of column binding (X).
A directional Gaussian captures this human-layout invariant.
The third dimension z separates values of different scales by construction:
COP (z~0.7), weights (z~1.4), dB (z~1.7), prices (z~3.7) don't mix.

lambda_z auto-calibrates from the geometry of values.
lambda_z = 0 → pure 2D field. lambda_z > 0 → magnitude validation.

Requires sense.py (Layer 1b) as preprocessor: without spatial promotion
TEXT → SPEC_LABEL/MODEL, the field has no particles to compute Phi on.
Sensing + field = 95.2%, field alone = 36.5%.

Constants (invariant across all brands and documents)::

    alpha   = 0.5    — Distance decay exponent (sub-linear)
    sigma_y = 6 px   — Row tolerance (auto-calibratable)
    sigma_x = 30 px  — Column tolerance (auto-calibratable)
    W       = 8×8    — Interaction matrix (particle-type affinities)

Author: Eugeniu Tacu, 2026
"""

import bisect
import math
import re as _re
from collections import defaultdict

# ============================================================
# Field constants — invariant across all brands
# ============================================================

# Interaction matrix W: how strongly two types "want" to be near
W = {
    ('NUMERIC', 'SPEC_LABEL'):  1.0,   # strong row attraction
    ('NUMERIC', 'SIZE_HEADER'): 0.8,   # column attraction
    ('NUMERIC', 'MODEL'):       0.6,   # column attraction
    ('NUMERIC', 'KW_HEADER'):   0.8,   # column attraction
    ('NUMERIC', 'UNIT'):        0.7,   # row attraction (units)
    ('NUMERIC', 'NUMERIC'):     0.3,   # weak clustering
    ('NUMERIC', 'TEXT'):       -0.1,   # slight repulsion
    ('NUMERIC', 'SECTION'):     0.0,   # neutral
}

# Distance decay: alpha = 0.5 (square root)
# Slower than Coulomb (alpha=2) because document structure
# is extended: a SPEC at 300px is still "the same row" on A4.
ALPHA = 0.5

# Default sigma (auto-calibratable from geometry)
DEFAULT_SIGMA_Y = 6.0    # row tolerance: 6px = same baseline
DEFAULT_SIGMA_X = 30.0   # column tolerance: 30px = same column

# Particle types by structural role
COL_TYPES = frozenset({'MODEL', 'SIZE_HEADER', 'KW_HEADER'})
ROW_TYPES = frozenset({'SPEC_LABEL', 'UNIT'})

# z-axis: concentration gradient (value magnitude)
DEFAULT_LAMBDA_Z = 50.0   # relative weight of z vs x,y

# Regex to extract first number from text
_NUM_RE = _re.compile(r'[-+]?\d+[.,]?\d*')


# ============================================================
# z-coordinate — third dimension (concentration gradient)
# ============================================================

def _parse_z_norm(text: str) -> float | None:
    """Compute z_norm = log10(|value| + 1) from numeric text.

    Handles Italian decimals (comma) and takes the first number from
    complex formats (e.g., "6.29/4.62", "204x840x840").

    Args:
        text: Raw numeric text.

    Returns:
        z_norm value, or None if unparseable.
    """
    if not text:
        return None
    m = _NUM_RE.search(text.replace(' ', ''))
    if not m:
        return None
    s = m.group().replace(',', '.')
    try:
        v = abs(float(s))
        if v < 0.001:
            return 0.0
        return math.log10(v + 1)
    except (ValueError, OverflowError):
        return None


def _assign_z_to_specs(specs: list[dict], numerics: list[dict],
                       sigma_y: float) -> None:
    """Assign z_norm to SPEC_LABEL from median of NUMERIC on the same row.

    Biological analogy: Turing concentration gradient.
    Each spec "senses" the magnitude of nearby values and acquires
    a typical z. This lets the field distinguish specs with different
    value scales (COP ~4 vs weight ~25 vs noise ~55).

    Modifies particles in-place.

    Args:
        specs: SPEC_LABEL particles.
        numerics: NUMERIC particles with z_norm already computed.
        sigma_y: Row tolerance for neighbor matching.
    """
    nums_with_z = sorted(
        [(n['y'], n) for n in numerics if n.get('z_norm') is not None],
        key=lambda t: t[0],
    )
    if not nums_with_z:
        return

    num_ys = [t[0] for t in nums_with_z]
    tol = sigma_y * 3  # generous tolerance for z estimation

    for spec in specs:
        y = spec['y']
        lo = bisect.bisect_left(num_ys, y - tol)
        hi = bisect.bisect_right(num_ys, y + tol)

        nearby_z = [nums_with_z[i][1]['z_norm'] for i in range(lo, hi)]
        if nearby_z:
            nearby_z.sort()
            spec['z_norm'] = nearby_z[len(nearby_z) // 2]


def calibrate_lambda_z(numerics: list[dict], sigma_y: float) -> float:
    """Auto-calibrate lambda_z from value geometry.

    lambda_z = sigma_y / median_z_spread_per_row

    Logic: NUMERIC particles on the same Y row are values of the same
    spec type for different models (e.g., COP model A=4.0, model B=4.2).
    Their z-spread is small. lambda_z scales this spread to the Y distance
    between rows, making z discriminative.

    If z_spread is small → lambda high → z discriminates strongly.
    If z_spread is large → lambda low → z doesn't interfere.

    Args:
        numerics: NUMERIC particles with z_norm.
        sigma_y: Row tolerance.

    Returns:
        Calibrated lambda_z (clamped to [10, 500]).
    """
    rows_z = defaultdict(list)
    for n in numerics:
        z = n.get('z_norm')
        if z is not None:
            row_key = round(n['y'] / (sigma_y * 2))
            rows_z[row_key].append(z)

    # IQR per row (robust to outliers)
    spreads = []
    for zs in rows_z.values():
        if len(zs) >= 3:
            zs.sort()
            q1 = zs[len(zs) // 4]
            q3 = zs[3 * len(zs) // 4]
            iqr = q3 - q1
            if 0.01 < iqr < 2.0:
                spreads.append(iqr)

    if not spreads:
        return DEFAULT_LAMBDA_Z

    spreads.sort()
    median_spread = spreads[len(spreads) // 2]

    if median_spread < 0.01:
        return DEFAULT_LAMBDA_Z

    lz = sigma_y / median_spread
    return max(10.0, min(lz, 500.0))


# ============================================================
# Equation core
# ============================================================

def _directed_alignment(pi: dict, pj: dict, axis: str,
                        sigma_y: float, sigma_x: float) -> float:
    """Anisotropic directional alignment.

    axis='row':  only Y alignment counts (same row).
                 Bonus 1.2 if pj is to the left (spec left of value).
    axis='col':  only X alignment counts (same column).
                 Bonus 1.2 if pj is above (header above value).

    Args:
        pi: Source particle (NUMERIC).
        pj: Target particle (SPEC, MODEL, UNIT).
        axis: ``'row'`` or ``'col'``.
        sigma_y: Row tolerance (px).
        sigma_x: Column tolerance (px).

    Returns:
        Alignment score in [0, 1.2].
    """
    dy = abs(pi['y'] - pj['y'])
    dx = abs(pi['x'] - pj['x'])

    if axis == 'row':
        a = math.exp(-(dy * dy) / (sigma_y * sigma_y))
        return a * (1.2 if pj['x'] < pi['x'] else 0.8)

    if axis == 'col':
        a = math.exp(-(dx * dx) / (sigma_x * sigma_x))
        return a * (1.2 if pj['y'] < pi['y'] else 0.8)

    return 0.0


def _phi(num: dict, other: dict, axis: str,
         sigma_y: float, sigma_x: float,
         lambda_z: float = 0.0,
         sigma_font: float = 0.0,
         sigma_hierarchy: float = 0.0,
         sigma_color: float = 0.0) -> float:
    """The morphogenetic field potential: Phi(num -> other).

    v0.1 formula (pure geometric)::

        d = sqrt(dx^2 + dy^2 + (lambda_z * dz_norm)^2)

    v2.0 formula (multi-dimensional with typography/hierarchy)::

        d² = (dx/σx)² + (dy/σy)² + (df/σf)² + (dh/σh)² + (dc/σc)²

    Where:
        - df = font affinity (0=same, 1=different)
        - dh = hierarchy affinity (0=same span, 0.5=same line, 1=different block)
        - dc = color affinity (0=same, 1=different)

    z operates only on the 'row' axis (NUMERIC → SPEC_LABEL).
    For the 'col' axis (NUMERIC → MODEL), z makes no sense:
    a column contains different specs with different z values.

    Args:
        num: NUMERIC particle.
        other: Target particle (SPEC_LABEL, MODEL, UNIT, etc.).
        axis: ``'row'`` or ``'col'``.
        sigma_y: Row tolerance.
        sigma_x: Column tolerance.
        lambda_z: z-axis weight (0 = pure 2D).
        sigma_font: Font affinity weight (0 = disabled, v2.0).
        sigma_hierarchy: Hierarchy affinity weight (0 = disabled, v2.0).
        sigma_color: Color affinity weight (0 = disabled, v2.0).

    Returns:
        Field potential value. Higher = stronger structural binding.
    """
    w = W.get(('NUMERIC', other['type']), 0.0)
    if w <= 0:
        return 0.0

    a = _directed_alignment(num, other, axis, sigma_y, sigma_x)

    dx = num['x'] - other['x']
    dy = num['y'] - other['y']

    # Geometric distance (v0.1 compatibility)
    dx_scaled = dx / sigma_x if sigma_x > 0 else dx
    dy_scaled = dy / sigma_y if sigma_y > 0 else dy

    # z contributes only to row matching (magnitude validation)
    dz_scaled = 0.0
    if axis == 'row' and lambda_z > 0:
        z1 = num.get('z_norm')
        z2 = other.get('z_norm')
        if z1 is not None and z2 is not None:
            dz_scaled = lambda_z * (z1 - z2)

    # Multi-dimensional distance (v2.0)
    d_squared = dx_scaled * dx_scaled + dy_scaled * dy_scaled + dz_scaled * dz_scaled

    # Font affinity (v2.0)
    if sigma_font > 0:
        font1 = num.get('font', '')
        font2 = other.get('font', '')
        df = 0.0 if font1 and font2 and font1 == font2 else 1.0
        d_squared += (df / sigma_font) ** 2

    # Hierarchy affinity (v2.0)
    if sigma_hierarchy > 0:
        span1, line1, block1 = num.get('span_num'), num.get('line_num'), num.get('block_num')
        span2, line2, block2 = other.get('span_num'), other.get('line_num'), other.get('block_num')

        if all(x is not None for x in [span1, line1, block1, span2, line2, block2]):
            if block1 == block2 and line1 == line2 and span1 == span2:
                dh = 0.0  # Same span → extremely close
            elif block1 == block2 and line1 == line2:
                dh = 0.5  # Same line, different span → close
            elif block1 == block2:
                dh = 0.8  # Same block, different line → moderate
            else:
                dh = 1.0  # Different block → far
        else:
            dh = 1.0  # Missing hierarchy info → assume far

        d_squared += (dh / sigma_hierarchy) ** 2

    # Color affinity (v2.0)
    if sigma_color > 0:
        color1 = num.get('color', 0)
        color2 = other.get('color', 0)
        dc = 0.0 if color1 == color2 else 1.0
        d_squared += (dc / sigma_color) ** 2

    d = math.sqrt(d_squared)
    if d < 1.0:
        d = 1.0

    return w * a / (d ** ALPHA)


def _phi_repel(num: dict, other: dict, axis: str,
               all_particles: list[dict],
               R: float = 0.0,
               sigma_ws: float = 30.0) -> float:
    """Repulsive field from whitespace (v2.0).

    Whitespace generates repulsion. Large gaps → strong repulsion.
    Boundaries emerge where Φ_total = Φ_attract + Φ_repel = 0.

    Formula::

        Φ_repel = -R * exp(-whitespace / σ_ws)

    Where whitespace is the gap between num and other, accounting for
    intervening particles.

    Args:
        num: NUMERIC particle.
        other: Target particle (SPEC_LABEL, MODEL, etc.).
        axis: 'row' or 'col'.
        all_particles: All particles on page (to detect intervening ones).
        R: Repulsion strength (0 = disabled, v2.0).
        sigma_ws: Whitespace tolerance.

    Returns:
        Negative potential (repulsion). Higher magnitude = stronger repulsion.
    """
    if R <= 0:
        return 0.0

    # Calculate whitespace between num and other
    if axis == 'col':
        # Horizontal whitespace (X-axis)
        x1, x2 = sorted([num['x'], other['x']])
        gap = abs(x2 - x1) - (num['x1'] - num['x0']) / 2 - (other['x1'] - other['x0']) / 2

        # Check for intervening particles in the same Y-band
        y_min, y_max = min(num['y'], other['y']) - 10, max(num['y'], other['y']) + 10
        intervening = [
            p for p in all_particles
            if x1 < p['x'] < x2 and y_min < p['y'] < y_max
        ]

        # If particles in between, reduce gap
        if intervening:
            gap = gap / (len(intervening) + 1)

    else:  # axis == 'row'
        # Vertical whitespace (Y-axis)
        y1, y2 = sorted([num['y'], other['y']])
        gap = abs(y2 - y1) - (num['y1'] - num['y0']) / 2 - (other['y1'] - other['y0']) / 2

        # Check for intervening particles in the same X-band
        x_min, x_max = min(num['x'], other['x']) - 20, max(num['x'], other['x']) + 20
        intervening = [
            p for p in all_particles
            if y1 < p['y'] < y2 and x_min < p['x'] < x_max
        ]

        if intervening:
            gap = gap / (len(intervening) + 1)

    # Repulsive potential (negative, exponential decay)
    if gap > 0:
        phi_rep = -R * math.exp(-gap / sigma_ws)
    else:
        phi_rep = -R  # Maximum repulsion when overlapping

    return phi_rep


# ============================================================
# Pre-processing
# ============================================================

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


# ============================================================
# Auto-calibration (thermoregulation)
# ============================================================

def calibrate_sigma(particles: list[dict]) -> tuple[float, float]:
    """Auto-calibrate sigma_y and sigma_x from page geometry.

    sigma_y = median_row_spacing * 0.6 (clamped [4, 20])
    sigma_x = median_col_spacing * 0.5 (clamped [15, 60])

    Args:
        particles: All particles on the page.

    Returns:
        Tuple (sigma_y, sigma_x).
    """
    numerics = sorted(
        [p for p in particles if p['type'] == 'NUMERIC'],
        key=lambda p: p['y'],
    )
    if len(numerics) < 3:
        return DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X

    # Y spacing: gap between consecutive NUMERIC by Y
    y_gaps = []
    for i in range(1, len(numerics)):
        gap = abs(numerics[i]['y'] - numerics[i - 1]['y'])
        if 3 < gap < 50:
            y_gaps.append(gap)

    # X spacing: gap between NUMERIC on the same row
    rows = defaultdict(list)
    for p in numerics:
        row_key = round(p['y'] / 10) * 10
        rows[row_key].append(p['x'])

    x_gaps = []
    for xs in rows.values():
        xs_sorted = sorted(xs)
        for i in range(1, len(xs_sorted)):
            gap = xs_sorted[i] - xs_sorted[i - 1]
            if 10 < gap < 150:
                x_gaps.append(gap)

    sy = sorted(y_gaps)[len(y_gaps) // 2] * 0.6 if y_gaps else DEFAULT_SIGMA_Y
    sx = sorted(x_gaps)[len(x_gaps) // 2] * 0.5 if x_gaps else DEFAULT_SIGMA_X

    return (max(4.0, min(sy, 20.0)),
            max(15.0, min(sx, 60.0)))


# ============================================================
# Extraction via field — the main algorithm
# ============================================================

def extract_page(particles: list[dict],
                 sigma_font: float = 0.0,
                 sigma_hierarchy: float = 0.0,
                 sigma_color: float = 0.0,
                 R: float = 0.0,
                 sigma_ws: float = 30.0) -> dict:
    """Full page extraction via the morphogenetic field.

    Takes typed particles, computes Phi for each NUMERIC, assigns to
    the spec (row) and column (entity) with maximum Phi.

    Pipeline::

        1. merge_multiline_specs (pre-processing)
        2. calibrate_sigma (thermoregulation)
        3. Compute z_norm for NUMERIC and SPEC_LABEL
        4. calibrate_lambda_z (auto z-axis weight)
        5. For each NUMERIC: argmax(Phi) → (spec, entity, unit)
        6. Assemble output

    v2.0 Multi-dimensional distance:
        With sigma_font/hierarchy/color > 0, distance becomes rich:
        d² = (dx/σx)² + (dy/σy)² + (df/σf)² + (dh/σh)² + (dc/σc)²

    v2.0 Dual field (attractive-repulsive):
        With R > 0, whitespace generates repulsion:
        Φ_total = Φ_attract + Φ_repel
        Boundaries emerge where Φ_total = 0.

    Args:
        particles: Particles from typify.extract_particles().
        sigma_font: Font affinity weight (0 = disabled, v2.0).
        sigma_hierarchy: Hierarchy affinity weight (0 = disabled, v2.0).
        sigma_color: Color affinity weight (0 = disabled, v2.0).
        R: Repulsion strength (0 = disabled, v2.0).
        sigma_ws: Whitespace tolerance for repulsion (v2.0).

    Returns:
        Dict with keys:
            - ``columns``: List of detected columns
            - ``sections``: List of section markers
            - ``model_prefix``: Common model prefix (currently empty)
            - ``data``: ``{entity_name: {spec_key: {value, unit, ...}}}``
            - ``stats``: ``{mapped, unmapped, entities, total_specs, lambda_z}``
            - ``unmapped``: List of NUMERIC particles not assigned
    """
    _EMPTY = {
        'columns': [], 'sections': [], 'model_prefix': '',
        'data': {},
        'stats': {'mapped': 0, 'unmapped': 0, 'entities': 0,
                  'total_specs': 0},
        'unmapped': [],
    }

    # Apoptosis: page without structural vitality
    type_counts = defaultdict(int)
    for p in particles:
        type_counts[p['type']] += 1

    if type_counts['NUMERIC'] < 2:
        return _EMPTY

    # Pre-processing: merge multi-line specs
    particles = merge_multiline_specs(particles)

    # Auto-calibrate sigma from geometry
    sigma_y, sigma_x = calibrate_sigma(particles)

    # Partition by type
    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    specs = [p for p in particles if p['type'] == 'SPEC_LABEL']
    col_headers = [p for p in particles if p['type'] in COL_TYPES]
    units = [p for p in particles if p['type'] == 'UNIT']
    sections = [p for p in particles if p['type'] == 'SECTION']

    if not specs and not col_headers:
        return _EMPTY

    # ------- THIRD DIMENSION z (concentration gradient) -------
    for n in numerics:
        n['z_norm'] = _parse_z_norm(n.get('text', ''))

    _assign_z_to_specs(specs, numerics, sigma_y)

    lambda_z = calibrate_lambda_z(numerics, sigma_y)

    # ------- THE 3D FIELD -------
    data = defaultdict(dict)
    unmapped = []
    mapped_count = 0

    for num in numerics:
        # Best SPEC (row) — Y axis + z (magnitude validation)
        # v2.0: Φ_total = Φ_attract + Φ_repel
        best_spec = None
        best_phi_spec = 0.0
        for s in specs:
            phi_attract = _phi(num, s, 'row', sigma_y, sigma_x, lambda_z,
                              sigma_font, sigma_hierarchy, sigma_color)
            phi_repel = _phi_repel(num, s, 'row', particles, R, sigma_ws)
            phi_total = phi_attract + phi_repel

            if phi_total > best_phi_spec:
                best_phi_spec = phi_total
                best_spec = s

        # Best column (entity) — X axis (no z: column has diverse specs)
        best_col = None
        best_phi_col = 0.0
        for c in col_headers:
            phi_attract = _phi(num, c, 'col', sigma_y, sigma_x, 0.0,
                              sigma_font, sigma_hierarchy, sigma_color)
            phi_repel = _phi_repel(num, c, 'col', particles, R, sigma_ws)
            phi_total = phi_attract + phi_repel

            if phi_total > best_phi_col:
                best_phi_col = phi_total
                best_col = c

        # Best UNIT (row) — Y axis (no z: unit has no magnitude)
        best_unit = None
        best_phi_unit = 0.0
        for u in units:
            phi_attract = _phi(num, u, 'row', sigma_y, sigma_x, 0.0,
                              sigma_font, sigma_hierarchy, sigma_color)
            phi_repel = _phi_repel(num, u, 'row', particles, R, sigma_ws)
            phi_total = phi_attract + phi_repel

            if phi_total > best_phi_unit:
                best_phi_unit = phi_total
                best_unit = u

        if best_spec is not None:
            entity = best_col['text'] if best_col else 'UNKNOWN'
            spec_key = best_spec['text']
            unit_text = best_unit['text'] if best_unit else None

            existing = data[entity].get(spec_key)
            if existing is None or best_phi_spec > existing['phi_spec']:
                data[entity][spec_key] = {
                    'value': num.get('text', ''),
                    'unit': unit_text,
                    'x': num['x'],
                    'y': num['y'],
                    'phi_spec': round(best_phi_spec, 4),
                    'phi_col': round(best_phi_col, 4),
                }
            mapped_count += 1
        else:
            unmapped.append(num)

    # Assemble columns for compatibility
    columns_out = []
    seen_cols = set()
    for c in col_headers:
        key = c['text']
        if key not in seen_cols:
            columns_out.append({
                'x': c['x'],
                'label': c['text'],
                'type': c['type'],
            })
            seen_cols.add(key)

    # Assemble sections
    sections_out = []
    for s in sorted(sections, key=lambda p: p['y']):
        sections_out.append({
            'name': s['text'],
            'y_min': s.get('y0', s['y']),
            'y_max': s.get('y1', s['y']),
        })

    return {
        'columns': columns_out,
        'sections': sections_out,
        'model_prefix': '',
        'data': dict(data),
        'stats': {
            'mapped': mapped_count,
            'unmapped': len(unmapped),
            'entities': len(data),
            'total_specs': sum(len(v) for v in data.values()),
            'lambda_z': round(lambda_z, 1),
        },
        'unmapped': unmapped,
    }
