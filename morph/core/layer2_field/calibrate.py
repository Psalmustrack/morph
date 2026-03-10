"""
morph.core.layer2_field.calibrate — Auto-Calibration
====================================================

Auto-calibrate field parameters from page geometry.
"""

from collections import defaultdict

from .phi import DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X, DEFAULT_LAMBDA_Z


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
