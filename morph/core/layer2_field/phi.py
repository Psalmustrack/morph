"""
morph.core.layer2_field.phi — Morphogenetic Field Equation
==========================================================

The core field potential computations and z-coordinate logic.
"""

import bisect
import math
import re as _re

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
