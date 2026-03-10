#!/usr/bin/env python3
"""
Test: differenziazione continua — W_eff per TEXT particles.

Ogni TEXT riceve P(header) basato su evidenza spaziale:
  - Quanti NUMERIC ha sotto di sé (entro sigma_x di tolleranza)
  - P(header) = min(1.0, n_below / 3)

W_eff(TEXT) = W(TEXT) + P(header) * (W(MODEL) - W(TEXT))
  = -0.1 + P * 0.7

Confronto A/B: campo originale vs campo con W continuo.

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

from morph.core import typify_word, sense_page, extract_page
from morph.core.layer2_field.phi import (
    _phi, _directed_alignment, _parse_z_norm, _assign_z_to_specs,
    COL_TYPES, ALPHA, W, DEFAULT_SIGMA_X,
)
from morph.core.layer2_field.calibrate import calibrate_sigma, calibrate_lambda_z
from morph.core.layer2_field.merge import merge_multiline_specs
from morph.bench.pubtables import (
    json_to_particles, parse_gt, _gt_cell, find_pairs,
    evaluate_field_bonds,
)


def compute_p_header(particles: list[dict], sigma_x: float) -> None:
    """Calcola P(header) per ogni TEXT basandosi su evidenza spaziale.

    Modifica in-place: aggiunge 'p_header' a ogni particella.
    - NUMERIC/SPEC_LABEL/MODEL/etc → p_header = 0 (tipo gia' assegnato)
    - TEXT → p_header = min(1.0, n_numerics_below / 3)
    """
    numerics = [p for p in particles if p['type'] == 'NUMERIC']

    for p in particles:
        if p['type'] != 'TEXT':
            p['p_header'] = 0.0
            continue

        # Conta NUMERIC sotto questo TEXT (entro sigma_x su X, Y > p.y)
        px, py = p['x'], p['y']
        n_below = 0
        for n in numerics:
            if (abs(n['x'] - px) < sigma_x and
                    n['y'] > py + 5):  # almeno 5px sotto
                n_below += 1

        p['p_header'] = min(1.0, n_below / 3.0)


def extract_page_continuous(particles: list[dict]) -> dict:
    """Come extract_page ma con W continuo per TEXT particles.

    TEXT con p_header > 0 partecipano come col_headers con peso ridotto.
    """
    _EMPTY = {
        'columns': [], 'sections': [], 'model_prefix': '',
        'data': {},
        'stats': {'mapped': 0, 'unmapped': 0, 'entities': 0,
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

    # Calcola P(header) per TEXT
    compute_p_header(particles, sigma_x)

    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    specs = [p for p in particles if p['type'] == 'SPEC_LABEL']
    # Col headers: classici + TEXT con p_header > 0
    col_headers = [p for p in particles if p['type'] in COL_TYPES]
    text_headers = [p for p in particles
                    if p['type'] == 'TEXT' and p.get('p_header', 0) > 0.1]
    col_headers = col_headers + text_headers
    units = [p for p in particles if p['type'] == 'UNIT']
    sections = [p for p in particles if p['type'] == 'SECTION']

    if not specs and not col_headers:
        return _EMPTY

    # z-axis
    for n in numerics:
        n['z_norm'] = _parse_z_norm(n.get('text', ''))
    _assign_z_to_specs(specs, numerics, sigma_y)
    lambda_z = calibrate_lambda_z(numerics, sigma_y)

    # THE FIELD (con W continuo)
    W_MODEL = W.get(('NUMERIC', 'MODEL'), 0.6)
    W_TEXT = W.get(('NUMERIC', 'TEXT'), -0.1)

    data = defaultdict(dict)
    unmapped = []
    mapped_count = 0

    for num in numerics:
        # Best SPEC (riga) — invariato
        best_spec = None
        best_phi_spec = 0.0
        for s in specs:
            p = _phi(num, s, 'row', sigma_y, sigma_x, lambda_z)
            if p > best_phi_spec:
                best_phi_spec = p
                best_spec = s

        # Best column — con W continuo per TEXT
        best_col = None
        best_phi_col = 0.0
        for c in col_headers:
            if c['type'] in COL_TYPES:
                # Tipo classico: usa _phi normale
                p = _phi(num, c, 'col', sigma_y, sigma_x)
            else:
                # TEXT con p_header: W_eff continuo
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

        # Best UNIT
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
            columns_out.append({
                'x': c['x'],
                'label': c['text'],
                'type': c['type'],
            })
            seen_cols.add(key)

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


def evaluate_ab(pair):
    """Test A/B su una tabella: campo originale vs continuo."""
    json_path, xml_path = pair

    with open(json_path) as f:
        words = json.load(f)

    gt = parse_gt(xml_path)
    particles = json_to_particles(words, domain=False)
    if len(particles) < 3:
        return None

    sense_result = sense_page(particles)
    sensed = sense_result['particles']

    # A: campo originale
    field_a = extract_page(sensed)
    bonds_a = evaluate_field_bonds(field_a, gt)

    # B: campo con W continuo
    # Serve una copia perché compute_p_header modifica in-place
    sensed_b = [dict(p) for p in sensed]
    field_b = extract_page_continuous(sensed_b)
    bonds_b = evaluate_field_bonds(field_b, gt)

    # Conta text_headers usati
    sigma_y, sigma_x = calibrate_sigma(sensed_b)
    compute_p_header(sensed_b, sigma_x)
    n_text_headers = sum(1 for p in sensed_b
                         if p['type'] == 'TEXT' and p.get('p_header', 0) > 0.1)

    return {
        'a_col': bonds_a['bond_col_acc'],
        'a_row': bonds_a['bond_row_acc'],
        'a_cell': bonds_a['bond_cell_acc'],
        'a_n': bonds_a['n_bonds'],
        'b_col': bonds_b['bond_col_acc'],
        'b_row': bonds_b['bond_row_acc'],
        'b_cell': bonds_b['bond_cell_acc'],
        'b_n': bonds_b['n_bonds'],
        'n_text_headers': n_text_headers,
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dataset', default='pubtables')
    args = parser.parse_args()

    pairs = find_pairs(dataset=args.dataset)
    random.seed(args.seed)
    if args.n > 0 and args.n < len(pairs):
        pairs = random.sample(pairs, args.n)

    print(f"Test A/B: W discreto vs W continuo su {len(pairs)} tabelle ({args.dataset})")
    print("=" * 70)

    t0 = time.time()
    results = []
    skipped = 0

    for i, pair in enumerate(pairs):
        r = evaluate_ab(pair)
        if r is None:
            skipped += 1
            continue
        results.append(r)

        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  {i+1}/{len(pairs)} tabelle, {elapsed:.0f}s")

    elapsed = time.time() - t0

    if not results:
        print("Nessun risultato!")
        return

    # Filtra tabelle con bonds
    with_bonds = [r for r in results if r['a_n'] > 0 or r['b_n'] > 0]

    print(f"\nCompletato: {len(results)} tabelle ({len(with_bonds)} con bonds), "
          f"{elapsed:.1f}s")
    print()

    # Medie pesate per n_bonds
    def weighted_avg(key, data):
        total_n = sum(r['a_n'] if 'a' in key else r['b_n'] for r in data)
        if total_n == 0:
            return 0.0
        n_key = 'a_n' if key.startswith('a_') else 'b_n'
        return sum(r[key] * r[n_key] for r in data) / total_n

    a_col = weighted_avg('a_col', with_bonds) * 100
    a_row = weighted_avg('a_row', with_bonds) * 100
    a_cell = weighted_avg('a_cell', with_bonds) * 100
    b_col = weighted_avg('b_col', with_bonds) * 100
    b_row = weighted_avg('b_row', with_bonds) * 100
    b_cell = weighted_avg('b_cell', with_bonds) * 100

    total_text_h = sum(r['n_text_headers'] for r in results)
    avg_text_h = total_text_h / len(results)

    print("=" * 70)
    print("RISULTATI A/B")
    print("=" * 70)
    print(f"{'':>20} {'Col %':>10} {'Row %':>10} {'Cell %':>10}")
    print("-" * 55)
    print(f"{'A (W discreto)':>20} {a_col:>9.1f}% {a_row:>9.1f}% {a_cell:>9.1f}%")
    print(f"{'B (W continuo)':>20} {b_col:>9.1f}% {b_row:>9.1f}% {b_cell:>9.1f}%")
    print("-" * 55)
    print(f"{'Delta (B-A)':>20} {b_col-a_col:>+9.1f}pp {b_row-a_row:>+9.1f}pp "
          f"{b_cell-a_cell:>+9.1f}pp")

    print()
    print(f"  TEXT promossi a quasi-header (media/tabella): {avg_text_h:.1f}")
    print(f"  TEXT promossi a quasi-header (totale): {total_text_h}")

    print()
    if b_cell - a_cell > 2:
        print("  → W continuo MIGLIORA. Il principio funziona.")
    elif b_cell - a_cell > 0:
        print("  → Miglioramento marginale. Segnale debole.")
    elif b_cell - a_cell > -1:
        print("  → Nessun effetto significativo.")
    else:
        print("  → W continuo PEGGIORA. Troppo rumore dai TEXT promossi.")

    # Breakdown: tabelle SENZA col_types originali vs CON
    no_col = [r for r in with_bonds
              if r['a_n'] > 0 and r['n_text_headers'] > 0]
    if no_col:
        a_cell_nc = weighted_avg('a_cell', no_col) * 100
        b_cell_nc = weighted_avg('b_cell', no_col) * 100
        print()
        print(f"  Solo tabelle con TEXT quasi-header ({len(no_col)}):")
        print(f"    A (discreto): {a_cell_nc:.1f}%  →  B (continuo): {b_cell_nc:.1f}%  "
              f"(delta: {b_cell_nc-a_cell_nc:+.1f}pp)")


if __name__ == '__main__':
    main()
