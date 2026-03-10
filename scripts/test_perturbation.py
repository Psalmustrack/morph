#!/usr/bin/env python3
"""
Test rapido: la perturbazione del campo (σ_Φ) correla con gli errori?

Per ogni NUMERIC assegnato dal campo, calcoliamo:
  - confidence_col = 1 - (Φ_2nd_col / Φ_1st_col)  → quanto è sicura l'assegnazione a colonna
  - confidence_row = 1 - (Φ_2nd_row / Φ_1st_row)  → quanto è sicura l'assegnazione a riga

Se confidence bassa correla con errori → σ_Φ è un segnale reale.

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

# Setup paths
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morph.core.typify import typify_word
from morph.core.sense import sense_page
from morph.core.field import (
    _phi, calibrate_sigma, merge_multiline_specs,
    calibrate_lambda_z, _parse_z_norm, _assign_z_to_specs,
    COL_TYPES, ALPHA
)
from morph.bench.pubtables import (
    json_to_particles, parse_gt, _gt_cell, find_pairs,
)

DATASET = Path(os.environ.get(
    'PUBTABLES_ROOT',
    '/mnt/dati/home/Progetti/dataset/pubtables-1m',
))


def extract_with_confidence(particles: list[dict]) -> list[dict]:
    """Come extract_page ma raccoglie confidence per ogni NUMERIC.

    Returns:
        Lista di dict, uno per NUMERIC mappato:
        {x, y, entity, spec, phi_col_1st, phi_col_2nd,
         phi_row_1st, phi_row_2nd, conf_col, conf_row}
    """
    from collections import defaultdict

    type_counts = defaultdict(int)
    for p in particles:
        type_counts[p['type']] += 1

    if type_counts['NUMERIC'] < 2:
        return []

    particles = merge_multiline_specs(particles)
    sigma_y, sigma_x = calibrate_sigma(particles)

    numerics = [p for p in particles if p['type'] == 'NUMERIC']
    specs = [p for p in particles if p['type'] == 'SPEC_LABEL']
    col_headers = [p for p in particles if p['type'] in COL_TYPES]

    if not specs and not col_headers:
        return []

    # z-axis
    for n in numerics:
        n['z_norm'] = _parse_z_norm(n.get('text', ''))
    _assign_z_to_specs(specs, numerics, sigma_y)
    lambda_z = calibrate_lambda_z(numerics, sigma_y)

    results = []

    for num in numerics:
        # Tutti i Φ verso specs (righe)
        phi_specs = []
        for s in specs:
            p = _phi(num, s, 'row', sigma_y, sigma_x, lambda_z)
            phi_specs.append((p, s))
        phi_specs.sort(key=lambda x: x[0], reverse=True)

        # Tutti i Φ verso col_headers (colonne)
        phi_cols = []
        for c in col_headers:
            p = _phi(num, c, 'col', sigma_y, sigma_x)
            phi_cols.append((p, c))
        phi_cols.sort(key=lambda x: x[0], reverse=True)

        if not phi_specs or phi_specs[0][0] <= 0:
            continue
        if not phi_cols or phi_cols[0][0] <= 0:
            continue

        best_phi_row = phi_specs[0][0]
        second_phi_row = phi_specs[1][0] if len(phi_specs) > 1 else 0.0
        best_spec = phi_specs[0][1]

        best_phi_col = phi_cols[0][0]
        second_phi_col = phi_cols[1][0] if len(phi_cols) > 1 else 0.0
        best_col = phi_cols[0][1]

        # Confidence = 1 - (2nd / 1st)
        # 1.0 = assegnazione sicura (nessun competitore)
        # 0.0 = ambiguo (due candidati equivalenti)
        conf_col = 1.0 - (second_phi_col / best_phi_col) if best_phi_col > 0 else 1.0
        conf_row = 1.0 - (second_phi_row / best_phi_row) if best_phi_row > 0 else 1.0

        results.append({
            'x': num['x'],
            'y': num['y'],
            'entity': best_col['text'],
            'spec': best_spec['text'],
            'phi_col_1st': best_phi_col,
            'phi_col_2nd': second_phi_col,
            'phi_row_1st': best_phi_row,
            'phi_row_2nd': second_phi_row,
            'conf_col': conf_col,
            'conf_row': conf_row,
        })

    return results


def analyze_table(pair):
    """Analizza una tabella: confidence vs correttezza."""
    json_path, xml_path = pair

    with open(json_path) as f:
        words = json.load(f)

    gt = parse_gt(xml_path)
    particles = json_to_particles(words, domain=False)
    if len(particles) < 3:
        return None

    sense_result = sense_page(particles)
    sensed = sense_result['particles']

    # Estrai con confidence
    mappings = extract_with_confidence(sensed)
    if not mappings:
        return None

    # Majority voting (come evaluate_field_bonds)
    entity_cols = defaultdict(list)
    spec_rows = defaultdict(list)
    for m in mappings:
        gc, gr = _gt_cell(m['x'], m['y'], gt)
        m['gt_col'] = gc
        m['gt_row'] = gr
        if gc >= 0:
            entity_cols[m['entity']].append(gc)
        if gr >= 0:
            spec_rows[m['spec']].append(gr)

    entity_to_col = {}
    for entity, cols in entity_cols.items():
        entity_to_col[entity] = Counter(cols).most_common(1)[0][0]

    spec_to_row = {}
    for spec, rows in spec_rows.items():
        spec_to_row[spec] = Counter(rows).most_common(1)[0][0]

    # Classifica ogni NUMERIC
    records = []
    for m in mappings:
        col_correct = (m['gt_col'] >= 0 and
                       entity_to_col.get(m['entity']) == m['gt_col'])
        row_correct = (m['gt_row'] >= 0 and
                       spec_to_row.get(m['spec']) == m['gt_row'])
        cell_correct = col_correct and row_correct

        records.append({
            'conf_col': m['conf_col'],
            'conf_row': m['conf_row'],
            'col_ok': col_correct,
            'row_ok': row_correct,
            'cell_ok': cell_correct,
        })

    return records


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

    print(f"Test perturbazione campo su {len(pairs)} tabelle ({args.dataset})")
    print("=" * 70)

    t0 = time.time()
    all_records = []
    skipped = 0

    for i, pair in enumerate(pairs):
        records = analyze_table(pair)
        if records is None:
            skipped += 1
            continue
        all_records.extend(records)

        if (i + 1) % 200 == 0:
            elapsed = time.time() - t0
            print(f"  {i+1}/{len(pairs)} tabelle, "
                  f"{len(all_records)} NUMERIC, "
                  f"{elapsed:.0f}s")

    elapsed = time.time() - t0

    if not all_records:
        print("Nessun record!")
        return

    print(f"\nCompletato: {len(pairs)-skipped} tabelle, "
          f"{len(all_records)} NUMERIC, {elapsed:.1f}s")
    print()

    # Analisi per bins di confidence
    print("=" * 70)
    print("COLONNE: confidence vs accuracy")
    print("=" * 70)
    print(f"{'Conf range':>15} {'N':>8} {'Col OK %':>10} {'Cell OK %':>10}")
    print("-" * 50)

    bins = [(0.0, 0.1), (0.1, 0.2), (0.2, 0.3), (0.3, 0.4), (0.4, 0.5),
            (0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.001)]

    for lo, hi in bins:
        subset = [r for r in all_records if lo <= r['conf_col'] < hi]
        if not subset:
            continue
        n = len(subset)
        col_acc = sum(1 for r in subset if r['col_ok']) / n * 100
        cell_acc = sum(1 for r in subset if r['cell_ok']) / n * 100
        label = f"[{lo:.1f}, {hi:.1f})"
        print(f"{label:>15} {n:>8} {col_acc:>9.1f}% {cell_acc:>9.1f}%")

    # Totale
    total_col = sum(1 for r in all_records if r['col_ok']) / len(all_records) * 100
    total_cell = sum(1 for r in all_records if r['cell_ok']) / len(all_records) * 100
    print("-" * 50)
    print(f"{'TOTALE':>15} {len(all_records):>8} {total_col:>9.1f}% {total_cell:>9.1f}%")

    print()
    print("=" * 70)
    print("RIGHE: confidence vs accuracy")
    print("=" * 70)
    print(f"{'Conf range':>15} {'N':>8} {'Row OK %':>10} {'Cell OK %':>10}")
    print("-" * 50)

    for lo, hi in bins:
        subset = [r for r in all_records if lo <= r['conf_row'] < hi]
        if not subset:
            continue
        n = len(subset)
        row_acc = sum(1 for r in subset if r['row_ok']) / n * 100
        cell_acc = sum(1 for r in subset if r['cell_ok']) / n * 100
        label = f"[{lo:.1f}, {hi:.1f})"
        print(f"{label:>15} {n:>8} {row_acc:>9.1f}% {cell_acc:>9.1f}%")

    total_row = sum(1 for r in all_records if r['row_ok']) / len(all_records) * 100
    print("-" * 50)
    print(f"{'TOTALE':>15} {len(all_records):>8} {total_row:>9.1f}% {total_cell:>9.1f}%")

    # Riassunto: se conf < 0.3 vs conf >= 0.7
    low_conf = [r for r in all_records if r['conf_col'] < 0.3]
    high_conf = [r for r in all_records if r['conf_col'] >= 0.7]

    if low_conf and high_conf:
        low_acc = sum(1 for r in low_conf if r['cell_ok']) / len(low_conf) * 100
        high_acc = sum(1 for r in high_conf if r['cell_ok']) / len(high_conf) * 100
        print()
        print("=" * 70)
        print("VERDETTO")
        print("=" * 70)
        print(f"  Conf_col < 0.3 (ambigui):   {len(low_conf):>6} NUMERIC, "
              f"cell accuracy = {low_acc:.1f}%")
        print(f"  Conf_col >= 0.7 (sicuri):   {len(high_conf):>6} NUMERIC, "
              f"cell accuracy = {high_acc:.1f}%")
        print(f"  Gap:                         {high_acc - low_acc:+.1f}pp")
        print()
        if high_acc - low_acc > 10:
            print("  → σ_Φ CORRELA con gli errori. Il segnale c'è.")
        elif high_acc - low_acc > 5:
            print("  → Correlazione debole. Segnale presente ma non forte.")
        else:
            print("  → Nessuna correlazione significativa. L'idea non regge.")


if __name__ == '__main__':
    main()
