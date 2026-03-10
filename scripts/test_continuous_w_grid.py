#!/usr/bin/env python3
"""Grid search: parametri ottimali per W continuo.

Testa combinazioni di:
  - sigma_factor: quanto restringere sigma_x (0.3, 0.5, 1.0)
  - min_below: minimo NUMERIC sotto per promuovere (3, 5, 8)
  - p_threshold: soglia P(header) per partecipare (0.3, 0.5, 0.7)

Autore: Eugeniu Tacu, 2026
"""

import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morph.core.sense import sense_page
from morph.core.field import (
    _phi, _directed_alignment, calibrate_sigma, merge_multiline_specs,
    calibrate_lambda_z, _parse_z_norm, _assign_z_to_specs,
    COL_TYPES, ALPHA, W, DEFAULT_SIGMA_X,
    extract_page,
)
from morph.bench.pubtables import (
    json_to_particles, parse_gt, find_pairs,
    evaluate_field_bonds,
)


def compute_p_header(particles, sigma_x, sigma_factor, min_below):
    """P(header) con parametri configurabili."""
    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    threshold_x = sigma_x * sigma_factor

    for p in particles:
        if p['type'] != 'TEXT':
            p['p_header'] = 0.0
            continue

        px, py = p['x'], p['y']
        n_below = 0
        for n in numerics:
            if (abs(n['x'] - px) < threshold_x and
                    n['y'] > py + 5):
                n_below += 1

        p['p_header'] = min(1.0, n_below / min_below)


def extract_page_continuous(particles, p_threshold):
    """Campo con W continuo, soglia configurabile."""
    _EMPTY = {
        'columns': [], 'sections': [], 'model_prefix': '',
        'data': {}, 'stats': {'mapped': 0, 'unmapped': 0, 'entities': 0,
                              'total_specs': 0, 'lambda_z': 0.0},
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
    text_headers = [p for p in particles
                    if p['type'] == 'TEXT' and p.get('p_header', 0) > p_threshold]
    col_headers = col_headers + text_headers
    units = [p for p in particles if p['type'] == 'UNIT']

    if not specs and not col_headers:
        return _EMPTY

    for n in numerics:
        n['z_norm'] = _parse_z_norm(n.get('text', ''))
    _assign_z_to_specs(specs, numerics, sigma_y)
    lambda_z = calibrate_lambda_z(numerics, sigma_y)

    W_MODEL = W.get(('NUMERIC', 'MODEL'), 0.6)
    W_TEXT = W.get(('NUMERIC', 'TEXT'), -0.1)

    data = defaultdict(dict)
    unmapped = []
    mapped_count = 0

    for num in numerics:
        best_spec = None
        best_phi_spec = 0.0
        for s in specs:
            p = _phi(num, s, 'row', sigma_y, sigma_x, lambda_z)
            if p > best_phi_spec:
                best_phi_spec = p
                best_spec = s

        best_col = None
        best_phi_col = 0.0
        for c in col_headers:
            if c['type'] in COL_TYPES:
                p = _phi(num, c, 'col', sigma_y, sigma_x)
            else:
                ph = c.get('p_header', 0.0)
                w_eff = W_TEXT + ph * (W_MODEL - W_TEXT)
                if w_eff <= 0:
                    continue
                a = _directed_alignment(num, c, 'col', sigma_y, sigma_x)
                dx = num['x'] - c['x']
                dy = num['y'] - c['y']
                d = math.sqrt(dx * dx + dy * dy)
                if d < 1.0:
                    d = 1.0
                p = w_eff * a / (d ** ALPHA)

            if p > best_phi_col:
                best_phi_col = p
                best_col = c

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
                    'x': num['x'], 'y': num['y'],
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
            columns_out.append({'x': c['x'], 'label': c['text'], 'type': c['type']})
            seen_cols.add(key)

    return {
        'columns': columns_out,
        'sections': [],
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


def evaluate_config(pairs, sigma_factor, min_below, p_threshold):
    """Valuta una configurazione su tutte le coppie."""
    results_a = []
    results_b = []

    for json_path, xml_path in pairs:
        with open(json_path) as f:
            words = json.load(f)

        gt = parse_gt(xml_path)
        particles = json_to_particles(words, domain=False)
        if len(particles) < 3:
            continue

        sense_result = sense_page(particles)
        sensed = sense_result['particles']

        # A: originale
        field_a = extract_page(sensed)
        bonds_a = evaluate_field_bonds(field_a, gt)
        if bonds_a['n_bonds'] > 0:
            results_a.append(bonds_a)

        # B: continuo
        sensed_b = [dict(p) for p in sensed]
        sigma_y, sigma_x = calibrate_sigma(sensed_b)
        compute_p_header(sensed_b, sigma_x, sigma_factor, min_below)
        field_b = extract_page_continuous(sensed_b, p_threshold)
        bonds_b = evaluate_field_bonds(field_b, gt)
        if bonds_b['n_bonds'] > 0:
            results_b.append(bonds_b)

    def weighted_metric(results, key):
        total_n = sum(r['n_bonds'] for r in results)
        if total_n == 0:
            return 0.0
        return sum(r[key] * r['n_bonds'] for r in results) / total_n

    a_cell = weighted_metric(results_a, 'bond_cell_acc') * 100
    b_cell = weighted_metric(results_b, 'bond_cell_acc') * 100
    a_col = weighted_metric(results_a, 'bond_col_acc') * 100
    b_col = weighted_metric(results_b, 'bond_col_acc') * 100
    a_row = weighted_metric(results_a, 'bond_row_acc') * 100
    b_row = weighted_metric(results_b, 'bond_row_acc') * 100

    return {
        'a_cell': a_cell, 'b_cell': b_cell,
        'a_col': a_col, 'b_col': b_col,
        'a_row': a_row, 'b_row': b_row,
        'delta_cell': b_cell - a_cell,
        'delta_col': b_col - a_col,
        'delta_row': b_row - a_row,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=500)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dataset', default='pubtables')
    args = parser.parse_args()

    pairs = find_pairs(dataset=args.dataset)
    random.seed(args.seed)
    if 0 < args.n < len(pairs):
        pairs = random.sample(pairs, args.n)

    print(f"Grid search W continuo su {len(pairs)} tabelle ({args.dataset})")
    print("=" * 80)

    # Griglia parametri
    sigma_factors = [0.3, 0.5, 1.0]
    min_belows = [3, 5, 8]
    p_thresholds = [0.3, 0.5, 0.7]

    best_delta = -999
    best_config = None
    all_results = []

    total = len(sigma_factors) * len(min_belows) * len(p_thresholds)
    i = 0

    for sf in sigma_factors:
        for mb in min_belows:
            for pt in p_thresholds:
                i += 1
                t0 = time.time()
                r = evaluate_config(pairs, sf, mb, pt)
                elapsed = time.time() - t0
                print(f"  [{i}/{total}] σ_f={sf}, min_b={mb}, p_t={pt} "
                      f"→ Δcell={r['delta_cell']:+.1f}pp "
                      f"(Δcol={r['delta_col']:+.1f}, Δrow={r['delta_row']:+.1f}) "
                      f"[{elapsed:.1f}s]")

                all_results.append((sf, mb, pt, r))
                if r['delta_cell'] > best_delta:
                    best_delta = r['delta_cell']
                    best_config = (sf, mb, pt, r)

    print()
    print("=" * 80)
    print("TOP 5 CONFIGURAZIONI (per Δcell)")
    print("=" * 80)
    all_results.sort(key=lambda x: x[3]['delta_cell'], reverse=True)
    print(f"{'σ_factor':>10} {'min_below':>10} {'p_threshold':>12} "
          f"{'Δcol':>8} {'Δrow':>8} {'Δcell':>8} {'B_cell':>8}")
    print("-" * 75)
    for sf, mb, pt, r in all_results[:5]:
        print(f"{sf:>10.1f} {mb:>10} {pt:>12.1f} "
              f"{r['delta_col']:>+7.1f}pp {r['delta_row']:>+7.1f}pp "
              f"{r['delta_cell']:>+7.1f}pp {r['b_cell']:>7.1f}%")

    print()
    print("BASELINE (A):", f"{all_results[0][3]['a_cell']:.1f}% cell")

    if best_delta > 0:
        sf, mb, pt, r = best_config
        print(f"\n→ MIGLIOR CONFIG: σ_f={sf}, min_b={mb}, p_t={pt}")
        print(f"  Δcell = {r['delta_cell']:+.1f}pp (B = {r['b_cell']:.1f}%)")
    else:
        print("\n→ Nessuna configurazione migliora il baseline.")
        print("  Il W continuo con evidenza spaziale non è la strada giusta.")


if __name__ == '__main__':
    main()
