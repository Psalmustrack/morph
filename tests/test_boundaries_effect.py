#!/usr/bin/env python3
"""
Test: effetto dei confini max-jump sull'estrazione.

Confronta extract_page (campo libero) vs extract_page con confini colonna
che limitano il raggio di ricerca del campo. Se i confini aiutano,
mapped aumenta e/o gli errori di assegnazione diminuiscono.

Lancia con:
    python tests/test_boundaries_effect.py [--pages N] [--brand BRAND]
"""

import copy
import math
import sys
from collections import defaultdict
from pathlib import Path

# Aggiungi project root al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morph.io.reader import open_pdf
from morph.core import extract_particles, sense_page, extract_page
from morph.core.layer1b_sense.rows import _group_into_rows
from morph.core.layer1b_sense.columns import _natural_threshold
from morph.core.layer2_field.merge import merge_multiline_specs
from morph.core.layer2_field.calibrate import calibrate_sigma, calibrate_lambda_z
from morph.core.layer2_field.phi import (
    _parse_z_norm, _assign_z_to_specs, _phi,
    COL_TYPES, ROW_TYPES,
)
from morph.brands import get_brand_patterns


# =============================================================================
# Nuova funzione: estrazione con confini colonna
# =============================================================================

def find_col_boundaries(particles: list[dict]) -> list[float]:
    """Trova le posizioni X dei confini colonna con max-jump.

    Raccoglie tutti i gap tra particelle consecutive per riga,
    poi usa il threshold naturale per identificare i confini.
    I confini sono le posizioni X (midpoint dei gap grandi).

    Returns:
        Lista ordinata di posizioni X dei confini.
    """
    rows = _group_into_rows(particles)

    # Raccogli tutti i gap e le loro posizioni
    all_gaps = []
    gap_positions = []

    for row in rows:
        if len(row) < 2:
            continue
        ps = sorted(row, key=lambda p: p['x0'])
        for i in range(len(ps) - 1):
            gap = ps[i + 1]['x0'] - ps[i]['x1']
            if gap > 0:
                pos = (ps[i]['x1'] + ps[i + 1]['x0']) / 2
                all_gaps.append(gap)
                gap_positions.append((gap, pos))

    if len(all_gaps) < 3:
        return []

    threshold = _natural_threshold(all_gaps)

    # Se nessun break naturale, nessun confine
    if threshold > max(all_gaps):
        return []

    # Raccogli tutte le posizioni dei gap sopra soglia
    boundary_xs = sorted(pos for gap, pos in gap_positions if gap > threshold)

    if not boundary_xs:
        return []

    # Cluster i confini vicini (entro 30px)
    clusters = [[boundary_xs[0]]]
    for x in boundary_xs[1:]:
        if x - clusters[-1][-1] < 30:
            clusters[-1].append(x)
        else:
            clusters.append([x])

    # Voto: almeno 2 righe devono concordare
    min_votes = max(2, len(rows) * 0.15)
    boundaries = []
    for cluster in clusters:
        if len(cluster) >= min_votes:
            boundaries.append(sum(cluster) / len(cluster))

    return sorted(boundaries)


def _find_zone(x: float, boundaries: list[float]) -> int:
    """Trova la zona di una particella data la sua X."""
    for i, bx in enumerate(boundaries):
        if x < bx:
            return i
    return len(boundaries)


def extract_page_bounded(particles: list[dict],
                         boundaries: list[float]) -> dict:
    """extract_page con confini colonna: il campo non attraversa i confini.

    Identica a extract_page ma:
    - Ogni NUMERIC cerca col_headers solo nella sua zona
    - SPEC_LABEL e UNIT cercano in tutta la pagina (sono sulla riga)
    """
    _EMPTY = {
        'columns': [], 'sections': [], 'model_prefix': '',
        'data': {},
        'stats': {'mapped': 0, 'unmapped': 0, 'entities': 0,
                  'total_specs': 0},
        'unmapped': [],
    }

    type_counts = defaultdict(int)
    for p in particles:
        type_counts[p['type']] += 1

    if type_counts['NUMERIC'] < 2:
        return _EMPTY

    particles = merge_multiline_specs(particles)
    sigma_y, sigma_x = calibrate_sigma(particles)

    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    specs = [p for p in particles if p['type'] == 'SPEC_LABEL']
    col_headers = [p for p in particles if p['type'] in COL_TYPES]
    units = [p for p in particles if p['type'] == 'UNIT']
    sections = [p for p in particles if p['type'] == 'SECTION']

    if not specs and not col_headers:
        return _EMPTY

    for n in numerics:
        n['z_norm'] = _parse_z_norm(n.get('text', ''))

    _assign_z_to_specs(specs, numerics, sigma_y)
    lambda_z = calibrate_lambda_z(numerics, sigma_y)

    # Partiziona col_headers per zona
    if boundaries:
        zone_headers = defaultdict(list)
        for c in col_headers:
            zone = _find_zone(c['x'], boundaries)
            zone_headers[zone].append(c)
    else:
        zone_headers = None

    data = defaultdict(dict)
    unmapped = []
    mapped_count = 0

    for num in numerics:
        # Best SPEC (row) — cerca su tutta la pagina
        best_spec = None
        best_phi_spec = 0.0
        for s in specs:
            p = _phi(num, s, 'row', sigma_y, sigma_x, lambda_z)
            if p > best_phi_spec:
                best_phi_spec = p
                best_spec = s

        # Best column — cerca SOLO nella zona del NUMERIC
        best_col = None
        best_phi_col = 0.0
        if zone_headers is not None:
            zone = _find_zone(num['x'], boundaries)
            candidates = zone_headers.get(zone, [])
        else:
            candidates = col_headers

        for c in candidates:
            p = _phi(num, c, 'col', sigma_y, sigma_x)
            if p > best_phi_col:
                best_phi_col = p
                best_col = c

        # Best UNIT (row)
        best_unit = None
        best_phi_unit = 0.0
        for u in units:
            p = _phi(num, u, 'row', sigma_y, sigma_x)
            if p > best_phi_unit:
                best_phi_unit = p
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

    columns_out = []
    seen_cols = set()
    for c in col_headers:
        key = c['text']
        if key not in seen_cols:
            columns_out.append({'x': c['x'], 'label': key, 'type': c['type']})
            seen_cols.add(key)

    sections_out = [{'name': s['text'], 'y_min': s.get('y0', s['y']),
                     'y_max': s.get('y1', s['y'])}
                    for s in sorted(sections, key=lambda p: p['y'])]

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


# =============================================================================
# Confronto assegnazioni: stessa entity o diversa?
# =============================================================================

def compare_assignments(result_free, result_bounded):
    """Confronta le assegnazioni del campo libero vs confinato.

    Guarda quanti NUMERIC finiscono su entity diverse tra i due metodi.
    """
    # Costruisci lookup: (x, y) → entity per entrambi
    map_free = {}
    for entity, specs in result_free['data'].items():
        for spec_key, info in specs.items():
            key = (round(info['x'], 1), round(info['y'], 1))
            map_free[key] = entity

    map_bounded = {}
    for entity, specs in result_bounded['data'].items():
        for spec_key, info in specs.items():
            key = (round(info['x'], 1), round(info['y'], 1))
            map_bounded[key] = entity

    # Confronta
    all_keys = set(map_free.keys()) | set(map_bounded.keys())
    same = 0
    diff = 0
    only_free = 0
    only_bounded = 0
    diff_examples = []

    for k in all_keys:
        e_free = map_free.get(k)
        e_bounded = map_bounded.get(k)
        if e_free and e_bounded:
            if e_free == e_bounded:
                same += 1
            else:
                diff += 1
                if len(diff_examples) < 5:
                    diff_examples.append(
                        f"    pos=({k[0]:.0f},{k[1]:.0f}): "
                        f"free→{e_free[:25]}, bounded→{e_bounded[:25]}"
                    )
        elif e_free:
            only_free += 1
        else:
            only_bounded += 1

    return {
        'same': same, 'diff': diff,
        'only_free': only_free, 'only_bounded': only_bounded,
        'examples': diff_examples,
    }


# =============================================================================
# Main
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages', type=int, default=15,
                        help='Max pagine per catalogo')
    parser.add_argument('--brand', type=str, default=None,
                        help='Testa solo questo brand')
    args = parser.parse_args()

    # Trova tutti i PDF
    all_pdfs = []
    for brand_dir in sorted(Path('brands').iterdir()):
        if not brand_dir.is_dir():
            continue
        brand = brand_dir.name
        if args.brand and brand != args.brand:
            continue
        inp = brand_dir / 'input'
        if not inp.exists():
            continue
        for p in sorted(inp.glob('*.pdf')):
            all_pdfs.append((brand, p))

    # Legacy hitachi
    if not args.brand or args.brand == 'hitachi':
        for p in sorted(Path('input').glob('*.pdf')):
            all_pdfs.append(('hitachi', p))

    print(f"Confronto: campo LIBERO vs campo CONFINATO (max-jump boundaries)")
    print(f"PDF: {len(all_pdfs)}, max {args.pages} pagine/catalogo")
    print()

    grand = {
        'pages': 0, 'pages_with_boundaries': 0,
        'mapped_free': 0, 'mapped_bounded': 0,
        'unmapped_free': 0, 'unmapped_bounded': 0,
        'entities_free': 0, 'entities_bounded': 0,
        'assign_same': 0, 'assign_diff': 0,
    }

    for brand, pdf_path in all_pdfs:
        try:
            model_pats, size_pats = get_brand_patterns(brand)
        except Exception:
            model_pats, size_pats = [], []

        cat_stats = defaultdict(int)

        try:
            with open_pdf(str(pdf_path)) as doc:
                max_pg = min(args.pages, len(doc))
                for pg_idx in range(max_pg):
                    page = doc[pg_idx]
                    particles_raw = extract_particles(page, model_pats, size_pats)
                    if len(particles_raw) < 8:
                        continue

                    # Applica sensing (Layer 1b)
                    p_free = copy.deepcopy(particles_raw)
                    sense_page(p_free)

                    p_bounded = copy.deepcopy(particles_raw)
                    sense_page(p_bounded)

                    # Trova confini
                    boundaries = find_col_boundaries(p_bounded)

                    # Estrai con entrambi i metodi
                    r_free = extract_page(p_free)
                    r_bounded = extract_page_bounded(p_bounded, boundaries)

                    grand['pages'] += 1
                    if boundaries:
                        grand['pages_with_boundaries'] += 1

                    grand['mapped_free'] += r_free['stats']['mapped']
                    grand['mapped_bounded'] += r_bounded['stats']['mapped']
                    grand['unmapped_free'] += r_free['stats']['unmapped']
                    grand['unmapped_bounded'] += r_bounded['stats']['unmapped']
                    grand['entities_free'] += r_free['stats']['entities']
                    grand['entities_bounded'] += r_bounded['stats']['entities']

                    # Confronta assegnazioni
                    cmp = compare_assignments(r_free, r_bounded)
                    grand['assign_same'] += cmp['same']
                    grand['assign_diff'] += cmp['diff']

                    cat_stats['pages'] += 1
                    cat_stats['diff'] += cmp['diff']
                    cat_stats['same'] += cmp['same']
                    cat_stats['m_free'] += r_free['stats']['mapped']
                    cat_stats['m_bounded'] += r_bounded['stats']['mapped']

        except Exception as e:
            print(f"  ERRORE {brand}/{pdf_path.name}: {e}")
            continue

        if cat_stats['pages'] > 0:
            delta_m = cat_stats['m_bounded'] - cat_stats['m_free']
            print(f"  {brand:20s} {pdf_path.name[:42]:44s} "
                  f"pg={cat_stats['pages']:3d}  "
                  f"mapped: {cat_stats['m_free']:4d}→{cat_stats['m_bounded']:4d} "
                  f"({delta_m:+4d})  "
                  f"reassign={cat_stats['diff']:3d}")

    # Riepilogo
    print()
    print("=" * 70)
    print("RIEPILOGO GLOBALE")
    print("=" * 70)
    print(f"  Pagine analizzate:        {grand['pages']}")
    print(f"  Pagine con confini:       {grand['pages_with_boundaries']} "
          f"({grand['pages_with_boundaries']/grand['pages']*100:.0f}%)"
          if grand['pages'] else "")
    print()
    print(f"  Mapped (libero):          {grand['mapped_free']}")
    print(f"  Mapped (confinato):       {grand['mapped_bounded']}  "
          f"(delta={grand['mapped_bounded']-grand['mapped_free']:+d})")
    print(f"  Unmapped (libero):        {grand['unmapped_free']}")
    print(f"  Unmapped (confinato):     {grand['unmapped_bounded']}  "
          f"(delta={grand['unmapped_bounded']-grand['unmapped_free']:+d})")
    print()
    print(f"  Entities (libero):        {grand['entities_free']}")
    print(f"  Entities (confinato):     {grand['entities_bounded']}  "
          f"(delta={grand['entities_bounded']-grand['entities_free']:+d})")
    print()
    total_assign = grand['assign_same'] + grand['assign_diff']
    if total_assign > 0:
        print(f"  Assegnazioni identiche:   {grand['assign_same']} "
              f"({grand['assign_same']/total_assign*100:.1f}%)")
        print(f"  Assegnazioni diverse:     {grand['assign_diff']} "
              f"({grand['assign_diff']/total_assign*100:.1f}%)")
    print()


if __name__ == '__main__':
    main()
