#!/usr/bin/env python3
"""
Test diretto del principio percettivo su tutti i dataset benchmark.

Lancia bench/boundaries.py su TUTTE le tabelle PubTables + FinTabNet + HVAC,
asse X e Y, e stampa il report completo.

Uso::

    python tests/test_principle.py
    python tests/test_principle.py --axis x
    python tests/test_principle.py --axis y
"""

import argparse
import random
import time

from morph.bench.boundaries import (
    evaluate_table,
    find_pairs_hvac,
    print_report,
)
from morph.bench.pubtables import find_pairs as find_pairs_pubtables
from morph.bench.grits import find_pairs_fintabnet
from multiprocessing import Pool


def _init_worker(axis):
    global _AXIS
    _AXIS = axis


def _eval_worker(args):
    json_path, xml_path = args
    return evaluate_table(json_path, xml_path, axis=_AXIS)


def run_dataset(name, pairs, axis, cores):
    print(f"\n  {name}: {len(pairs)} tabelle ...")
    t0 = time.time()

    results = []
    skipped = 0

    if cores > 1 and len(pairs) > 4:
        with Pool(cores, initializer=_init_worker, initargs=(axis,)) as pool:
            for r in pool.imap_unordered(_eval_worker, pairs, chunksize=64):
                if r is None:
                    skipped += 1
                else:
                    results.append(r)
    else:
        for json_path, xml_path in pairs:
            r = evaluate_table(json_path, xml_path, axis=axis)
            if r is None:
                skipped += 1
            else:
                results.append(r)

    elapsed = time.time() - t0
    speed = len(results) / elapsed if elapsed > 0 else 0
    print(f"  Tempo: {elapsed:.1f}s ({speed:.0f} tab/s), {skipped} skipped")

    if results:
        print_report(results, name, axis)

    return results


def main():
    parser = argparse.ArgumentParser(description='Test principio percettivo — FULL')
    parser.add_argument('--axis', choices=['x', 'y', 'both'], default='x')
    parser.add_argument('--cores', type=int, default=4)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    axis_label = {'x': 'colonne (X)', 'y': 'righe (Y)', 'both': 'entrambi'}

    print(f"\n{'=' * 65}")
    print(f"  TEST COMPLETO DEL PRINCIPIO PERCETTIVO")
    print(f"  _natural_threshold su TUTTE le tabelle benchmark")
    print(f"  Asse: {axis_label[args.axis]}  cores={args.cores}")
    print(f"{'=' * 65}")

    random.seed(args.seed)
    pub_pairs = find_pairs_pubtables(limit=None)
    random.seed(args.seed)
    fin_pairs = find_pairs_fintabnet(limit=None)
    hvac_pairs = find_pairs_hvac()

    t_start = time.time()

    all_results = []
    pub_results = run_dataset('PubTables-1M', pub_pairs, args.axis, args.cores)
    all_results.extend(pub_results)
    fin_results = run_dataset('FinTabNet', fin_pairs, args.axis, args.cores)
    all_results.extend(fin_results)
    if hvac_pairs:
        hvac_results = run_dataset('HVAC', hvac_pairs, args.axis, args.cores)
        all_results.extend(hvac_results)

    t_total = time.time() - t_start

    # Riepilogo cross-domain
    total_gaps = sum(r['total'] for r in all_results)
    total_tables = len(all_results)

    print(f"\n{'=' * 65}")
    print(f"  RIEPILOGO")
    print(f"{'=' * 65}")
    print(f"  Tabelle: {total_tables:,}")
    print(f"  Gap classificati: {total_gaps:,}")
    print(f"  Tempo totale: {t_total:.1f}s")
    print()


if __name__ == '__main__':
    main()
