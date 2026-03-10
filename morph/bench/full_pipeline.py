#!/usr/bin/env python3
"""
morph.bench.full_pipeline — Benchmark completo Morph su PubTables-1M + FinTabNet
==================================================================================

Pipeline completa: typify → sense → field → confronto con ground truth.
Misura col_exact, row_exact, entities, mapped su entrambi i dataset.

Uso::

    python -m morph.bench.full_pipeline --n 100000 --cores 4
    python -m morph.bench.full_pipeline --n 1000 --cores 4  # quick test

Author: Eugeniu Tacu, 2026
"""

import json
import random
import time
from collections import Counter
from multiprocessing import Pool

from morph.core import typify_word, sense_page, extract_page
from morph.bench.grid import count_columns_universal, count_rows_universal

from morph.bench.pubtables import (
    find_pairs as find_pairs_pubtables,
    json_to_particles,
    parse_gt,
)
from morph.bench.grits import find_pairs_fintabnet


# ---------------------------------------------------------------------------
# Valutazione singola tabella
# ---------------------------------------------------------------------------

def evaluate_table(json_path: str, xml_path: str) -> dict | None:
    """Pipeline completa Morph su una tabella, confronto con ground truth.

    typify → sense → field → confronto col/row/entities/mapped.
    """
    with open(json_path) as f:
        words = json.load(f)

    gt = parse_gt(xml_path)
    if not gt['columns'] or not gt['rows']:
        return None

    gt_cols = len(gt['columns'])
    gt_rows = len(gt['rows'])
    has_spanning = len(gt.get('spanning_cells', [])) > 0

    # Filtra tabelle troppo grandi (outlier)
    if gt_rows > 50 or gt_cols > 30:
        return None

    particles = json_to_particles(words, domain=False)
    if len(particles) < 3:
        return None

    # === Pipeline Morph completa ===
    sense_result = sense_page(particles)
    sensed = sense_result['particles']
    field_result = extract_page(sensed)

    det_cols = count_columns_universal(sensed)
    det_rows = count_rows_universal(sensed)
    det_entities = field_result['stats']['entities']
    det_mapped = field_result['stats']['mapped']
    det_unmapped = field_result['stats']['unmapped']

    type_dist = Counter(p['type'] for p in sensed)

    return {
        'gt_cols': gt_cols,
        'gt_rows': gt_rows,
        'det_cols': det_cols,
        'det_rows': det_rows,
        'col_exact': 1 if det_cols == gt_cols else 0,
        'row_exact': 1 if det_rows == gt_rows else 0,
        'col_delta': det_cols - gt_cols,
        'det_entities': det_entities,
        'det_mapped': det_mapped,
        'det_unmapped': det_unmapped,
        'has_spanning': has_spanning,
        'types': dict(type_dist),
    }


# ---------------------------------------------------------------------------
# Multiprocessing
# ---------------------------------------------------------------------------

def _eval_worker(args):
    json_path, xml_path = args
    return evaluate_table(json_path, xml_path)


# ---------------------------------------------------------------------------
# Runner per un dataset
# ---------------------------------------------------------------------------

def run_dataset(pairs: list[tuple], cores: int, label: str) -> list[dict]:
    """Lancia benchmark su un dataset, ritorna risultati."""
    results = []
    skipped = 0
    t0 = time.time()

    if cores > 1:
        work = [(j, x) for j, x in pairs]
        with Pool(cores) as pool:
            for i, r in enumerate(
                pool.imap_unordered(_eval_worker, work, chunksize=64),
            ):
                if r is None:
                    skipped += 1
                    continue
                results.append(r)
                done = i + 1
                if done % 2000 == 0:
                    elapsed = time.time() - t0
                    rate = done / elapsed
                    remaining = (len(pairs) - done) / rate
                    print(f"  [{done}/{len(pairs)}] "
                          f"{rate:.0f} tab/s  "
                          f"~{remaining:.0f}s rimanenti")
    else:
        for i, (json_path, xml_path) in enumerate(pairs):
            r = evaluate_table(json_path, xml_path)
            if r is None:
                skipped += 1
                continue
            results.append(r)
            if (i + 1) % 500 == 0:
                elapsed = time.time() - t0
                print(f"  [{i + 1}/{len(pairs)}] "
                      f"{(i + 1) / elapsed:.0f} tab/s ...")

    elapsed = time.time() - t0
    n = len(results)
    rate = n / elapsed if elapsed > 0 else 0

    print(f"\n  {label}: {n} tabelle, {skipped} skipped, "
          f"{elapsed:.1f}s ({rate:.0f} tab/s)")

    return results


# ---------------------------------------------------------------------------
# Report per un dataset
# ---------------------------------------------------------------------------

def print_report(results: list[dict], label: str):
    """Stampa report per un dataset."""
    n = len(results)
    if n == 0:
        print(f"  {label}: nessun risultato!")
        return

    col_exact = sum(r['col_exact'] for r in results)
    row_exact = sum(r['row_exact'] for r in results)
    col_deltas = Counter(r['col_delta'] for r in results)
    avg_mapped = sum(r['det_mapped'] for r in results) / n
    avg_unmapped = sum(r['det_unmapped'] for r in results) / n
    avg_entities = sum(r['det_entities'] for r in results) / n

    has_span = [r for r in results if r['has_spanning']]
    no_span = [r for r in results if not r['has_spanning']]

    print(f"\n  {'=' * 60}")
    print(f"  {label}  (N={n})")
    print(f"  {'=' * 60}")
    print(f"  COLONNE:")
    print(f"    Exact match: {col_exact}/{n} = {100 * col_exact / n:.1f}%")
    print(f"    Delta distribution: "
          f"{dict(sorted(col_deltas.items(), key=lambda x: x[0]))}")
    print(f"  RIGHE:")
    print(f"    Exact match: {row_exact}/{n} = {100 * row_exact / n:.1f}%")
    print(f"  CAMPO Phi:")
    print(f"    Media mapped={avg_mapped:.1f}  unmapped={avg_unmapped:.1f}  "
          f"entities={avg_entities:.1f}")

    if has_span and no_span:
        span_col = sum(r['col_exact'] for r in has_span) / len(has_span)
        nospan_col = sum(r['col_exact'] for r in no_span) / len(no_span)
        print(f"  SPANNING CELLS:")
        print(f"    Con ({len(has_span)}):  col_exact={100 * span_col:.1f}%")
        print(f"    Senza ({len(no_span)}): col_exact={100 * nospan_col:.1f}%")

    # Tipi particelle
    type_totals = Counter()
    for r in results:
        for t, c in r['types'].items():
            type_totals[t] += c
    total_p = sum(type_totals.values())
    print(f"  PARTICELLE ({total_p:,} totali):")
    for t, c in type_totals.most_common(8):
        print(f"    {t:15s}: {c:>10,} ({100 * c / total_p:.1f}%)")

    return {
        'n': n,
        'col_exact': col_exact / n,
        'row_exact': row_exact / n,
        'avg_mapped': avg_mapped,
        'avg_entities': avg_entities,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Morph full pipeline benchmark — PubTables + FinTabNet',
    )
    parser.add_argument('--n', type=int, default=1000,
                        help='Max tabelle per dataset (0 = tutte)')
    parser.add_argument('--cores', type=int, default=4)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dataset', choices=['both', 'pubtables', 'fintabnet'],
                        default='both', help='Quale dataset')
    args = parser.parse_args()

    n = args.n if args.n > 0 else None
    random.seed(args.seed)

    print(f"\n{'=' * 65}")
    print(f"  Morph Full Pipeline Benchmark")
    print(f"  typify → sense → field → confronto GT")
    print(f"  N={'ALL' if n is None else n}  seed={args.seed}  cores={args.cores}")
    print(f"{'=' * 65}")

    stats = {}

    # PubTables-1M
    if args.dataset in ('both', 'pubtables'):
        random.seed(args.seed)
        pairs_pub = find_pairs_pubtables(limit=n)
        print(f"\n  PubTables-1M: {len(pairs_pub)} tabelle ...")
        results_pub = run_dataset(pairs_pub, args.cores, 'PubTables-1M')
        stats['pubtables'] = print_report(results_pub, 'PubTables-1M')

    # FinTabNet
    if args.dataset in ('both', 'fintabnet'):
        random.seed(args.seed)
        pairs_fin = find_pairs_fintabnet(limit=n)
        print(f"\n  FinTabNet: {len(pairs_fin)} tabelle ...")
        results_fin = run_dataset(pairs_fin, args.cores, 'FinTabNet')
        stats['fintabnet'] = print_report(results_fin, 'FinTabNet')

    # Cross-domain summary
    if 'pubtables' in stats and 'fintabnet' in stats:
        print(f"\n  {'=' * 60}")
        print(f"  CROSS-DOMAIN SUMMARY")
        print(f"  {'=' * 60}")
        p = stats['pubtables']
        f = stats['fintabnet']
        gap_col = abs(p['col_exact'] - f['col_exact'])
        print(f"  {'':20s}  {'PubTables':>12s}  {'FinTabNet':>12s}  {'Gap':>8s}")
        print(f"  {'-' * 55}")
        print(f"  {'Col exact':20s}  {100*p['col_exact']:>11.1f}%  "
              f"{100*f['col_exact']:>11.1f}%  {100*gap_col:>7.1f}pp")
        print(f"  {'Row exact':20s}  {100*p['row_exact']:>11.1f}%  "
              f"{100*f['row_exact']:>11.1f}%")
        print(f"  {'Avg mapped':20s}  {p['avg_mapped']:>12.1f}  "
              f"{f['avg_mapped']:>12.1f}")
        print(f"  {'Avg entities':20s}  {p['avg_entities']:>12.1f}  "
              f"{f['avg_entities']:>12.1f}")
        print()


if __name__ == '__main__':
    main()
