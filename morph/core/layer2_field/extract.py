"""
morph.core.layer2_field.extract — Page Extraction Pipeline
==========================================================

Main entry point: extract_page() orchestrates the full field computation.
"""

from collections import defaultdict

from .calibrate import calibrate_sigma, calibrate_lambda_z
from .cell_span import expand_merged_cells
from .merge import merge_multiline_specs
from .phi import (
    _parse_z_norm, _assign_z_to_specs,
    _phi, _phi_repel,
    COL_TYPES,
)


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
    # v2.1: Row segmentation — constrain spec/unit search to same row
    _has_rows = any('row_id' in p for p in numerics)

    # Pre-index specs and units by row_id for O(1) lookup
    _specs_by_row = defaultdict(list)
    _units_by_row = defaultdict(list)
    if _has_rows:
        for s in specs:
            _specs_by_row[s.get('row_id')].append(s)
        for u in units:
            _units_by_row[u.get('row_id')].append(u)

    data = defaultdict(dict)
    unmapped = []
    mapped_count = 0

    for num in numerics:
        num_row = num.get('row_id')

        # Row-constrained candidates (v2.1) or all (legacy fallback)
        if _has_rows and num_row is not None:
            candidate_specs = _specs_by_row.get(num_row, [])
            candidate_units = _units_by_row.get(num_row, [])
        else:
            candidate_specs = specs
            candidate_units = units

        # Best SPEC (row) — Y axis + z (magnitude validation)
        # v2.0: Φ_total = Φ_attract + Φ_repel
        best_spec = None
        best_phi_spec = 0.0
        for s in candidate_specs:
            phi_attract = _phi(num, s, 'row', sigma_y, sigma_x, lambda_z,
                              sigma_font, sigma_hierarchy, sigma_color)
            phi_repel = _phi_repel(num, s, 'row', particles, R, sigma_ws)
            phi_total = phi_attract + phi_repel

            if phi_total > best_phi_spec:
                best_phi_spec = phi_total
                best_spec = s

        # Best column (entity) — X axis (no row constraint for columns)
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

        # Best UNIT (row) — same-row constraint (v2.1)
        best_unit = None
        best_phi_unit = 0.0
        for u in candidate_units:
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

    # Expand merged cells (v2.1) — values centered across multiple columns
    entities = list(data.keys())
    if entities:
        data = expand_merged_cells(data, particles, entities)

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
