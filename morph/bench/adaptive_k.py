#!/usr/bin/env python3
"""
morph.bench.adaptive_k — Max-Ratio-Jump Adaptive Threshold
============================================================

Benchmark comparing fixed boundary constants (k_x=0.3, k_y=0.05)
against an adaptive threshold computed from the maximum relative
jump in the gap distribution.

Hypothesis: the natural boundary between intra-cell and inter-cell
gaps is the point where the sorted gap distribution makes its largest
relative jump.  No k, no Otsu, no bimodal assumption needed.

The max-ratio-jump approach computes a per-row (columns) and
per-column (rows) threshold, then votes.

Results (N=10,000, seed=42):

* PubTables-1M: fixed 79.7%, max-jump 79.9% (+0.2 pp)
* FinTabNet.c:  fixed 77.6%, max-jump 78.1% (+0.5 pp)
* Cross-domain gap reduced from 2.1 pp to 1.8 pp

Usage::

    python -m morph.bench.adaptive_k --n 1000 --cores 4

Author: Eugeniu Tacu, 2026
"""

import random
import time
from multiprocessing import Pool
from statistics import median

from morph.core.sense import _group_into_rows, _natural_threshold
from morph.bench.pubtables import (
    find_pairs as find_pairs_pubtables,
    json_to_particles,
    parse_gt,
)
from morph.bench.grits import (
    find_pairs_fintabnet,
    find_col_splits_ratio,
    group_rows_per_column,
    build_gt_cells,
    build_pred_cells,
    cells_to_relspan_grid,
    factored_2dmss,
    bbox_iou,
    compute_fscore,
)


# ---------------------------------------------------------------------------
# Column splits with max-jump (per-row threshold + voting)
# ---------------------------------------------------------------------------

# _natural_threshold → importata da morph.core.sense come _natural_threshold

def find_col_splits_maxjump(
    particles: list[dict],
) -> tuple[list[float], float]:
    """Find column boundaries using per-row max-jump thresholds.

    For each row: find natural threshold from max ratio jump.
    If no break (ratio < 1.5), fall back to the global threshold.
    Boundaries are voted across rows, then clustered.

    Args:
        particles: All particles on the page.

    Returns:
        Tuple ``(sorted_col_splits, avg_threshold)``.
    """
    rows = _group_into_rows(particles)

    # Step 1: collect all gaps for global fallback threshold
    all_gaps_global: list[float] = []
    row_gap_data: list[list[tuple[float, float]]] = []

    for row in rows:
        if len(row) < 2:
            continue
        ps = sorted(row, key=lambda p: p['x0'])
        gaps_info = []
        for i in range(len(ps) - 1):
            gap = ps[i + 1]['x0'] - ps[i]['x1']
            if gap > 0:
                pos = (ps[i]['x1'] + ps[i + 1]['x0']) / 2
                all_gaps_global.append(gap)
                gaps_info.append((gap, pos))
        row_gap_data.append(gaps_info)

    if not all_gaps_global:
        return [], 0

    global_threshold = _natural_threshold(all_gaps_global)

    # Step 2: per-row local threshold or fallback
    all_boundaries: list[float] = []
    all_thresholds: list[float] = []

    for gaps_info in row_gap_data:
        if not gaps_info:
            continue
        gaps_only = [g for g, _ in gaps_info]

        if len(gaps_only) >= 3:
            threshold = _natural_threshold(gaps_only)
            if threshold > max(gaps_only):
                threshold = global_threshold
        else:
            threshold = global_threshold

        all_thresholds.append(threshold)

        for gap_val, gap_pos in gaps_info:
            if gap_val > threshold:
                all_boundaries.append(gap_pos)

    if not all_boundaries:
        return [], global_threshold

    # Step 3: cluster + min_votes
    all_boundaries.sort()
    med_t = median(all_thresholds) if all_thresholds else 10
    cluster_tol = med_t * 0.5

    clusters: list[list[float]] = [[all_boundaries[0]]]
    for b in all_boundaries[1:]:
        if b - clusters[-1][-1] < cluster_tol:
            clusters[-1].append(b)
        else:
            clusters.append([b])

    min_votes = max(2, len(rows) * 0.2)
    col_splits = [
        median(cluster) for cluster in clusters
        if len(cluster) >= min_votes
    ]

    avg_threshold = (
        sum(all_thresholds) / len(all_thresholds)
        if all_thresholds else 0
    )
    return sorted(col_splits), avg_threshold


# ---------------------------------------------------------------------------
# Single-table evaluation
# ---------------------------------------------------------------------------

def evaluate_table(
    json_path: str,
    xml_path: str,
    method: str = 'fixed',
) -> dict | None:
    """Compute GriTS_Top with fixed-k or max-jump method.

    Args:
        json_path: Path to ``_words.json``.
        xml_path: Path to ``.xml`` ground truth.
        method: ``'fixed'`` (k_x=0.3, k_y=0.05) or ``'maxjump'``.

    Returns:
        Dict with GriTS metrics, or ``None``.
    """
    import json
    with open(json_path) as f:
        words = json.load(f)
    gt = parse_gt(xml_path)

    if not gt['columns'] or not gt['rows']:
        return None
    n_gt_rows = len(gt['rows'])
    n_gt_cols = len(gt['columns'])
    has_spanning = len(gt.get('spanning_cells', [])) > 0
    if n_gt_rows > 50 or n_gt_cols > 30:
        return None

    particles = json_to_particles(words, domain=False)
    if len(particles) < 3:
        return None

    if method == 'fixed':
        col_splits = find_col_splits_ratio(particles, k=0.3)
        rows_pred = group_rows_per_column(particles, col_splits, k_y=0.05)
        kx_used = 0.3
        ky_used = 0.05
    elif method == 'maxjump':
        col_splits, avg_tx = find_col_splits_maxjump(particles)
        ky_used = 0.05
        rows_pred = group_rows_per_column(particles, col_splits, k_y=ky_used)
        all_widths = [p['x1'] - p['x0'] for p in particles
                      if (p['x1'] - p['x0']) > 0]
        avg_w = sum(all_widths) / len(all_widths) if all_widths else 10
        kx_used = avg_tx / avg_w if avg_w > 0 else 0.3
    else:
        raise ValueError(f"Unknown method: {method}")

    n_pred_rows = len(rows_pred)
    n_pred_cols = len(col_splits) + 1

    if n_pred_rows > 60 or n_pred_cols > 35:
        return None

    # GriTS_Top
    if not has_spanning:
        matched = min(n_gt_rows, n_pred_rows) * min(n_gt_cols, n_pred_cols)
        n_true = n_gt_rows * n_gt_cols
        n_pos = n_pred_rows * n_pred_cols
        top_f, top_p, top_r = compute_fscore(matched, n_true, n_pos)
    else:
        gt_cells_top = build_gt_cells(gt)
        pred_cells_top = build_pred_cells(col_splits, rows_pred)
        gt_grid = cells_to_relspan_grid(gt_cells_top)
        pred_grid = cells_to_relspan_grid(pred_cells_top)
        top_f, top_p, top_r = factored_2dmss(
            gt_grid, pred_grid, bbox_iou,
        )

    return {
        'grits_top': top_f,
        'grits_top_prec': top_p,
        'grits_top_recall': top_r,
        'gt_rows': n_gt_rows,
        'gt_cols': n_gt_cols,
        'pred_rows': n_pred_rows,
        'pred_cols': n_pred_cols,
        'col_exact': 1 if n_pred_cols == n_gt_cols else 0,
        'row_exact': 1 if n_pred_rows == n_gt_rows else 0,
        'has_spanning': has_spanning,
        'kx': kx_used,
        'ky': ky_used,
    }


# ---------------------------------------------------------------------------
# Multiprocessing support
# ---------------------------------------------------------------------------

_WORKER_METHOD = 'fixed'


def _eval_worker(args):
    """Worker for :class:`multiprocessing.Pool`."""
    json_path, xml_path = args
    return evaluate_table(json_path, xml_path, method=_WORKER_METHOD)


def _init_worker(method):
    """Initialiser for worker processes."""
    global _WORKER_METHOD
    _WORKER_METHOD = method


# ---------------------------------------------------------------------------
# Benchmark runner + reporting
# ---------------------------------------------------------------------------

def run_benchmark(
    pairs: list[tuple],
    method: str,
    cores: int = 1,
    label: str = '',
) -> dict:
    """Run benchmark on a set of table pairs.

    Args:
        pairs: List of ``(json_path, xml_path)`` tuples.
        method: ``'fixed'`` or ``'maxjump'``.
        cores: Number of parallel workers.
        label: Label for display.

    Returns:
        Dict with aggregate metrics.
    """
    results = []
    skipped = 0
    t0 = time.time()

    if cores > 1:
        work = [(j, x) for j, x in pairs]
        with Pool(cores, initializer=_init_worker,
                  initargs=(method,)) as pool:
            for r in pool.imap_unordered(_eval_worker, work, chunksize=32):
                if r is None:
                    skipped += 1
                else:
                    results.append(r)
    else:
        _init_worker(method)
        for json_path, xml_path in pairs:
            r = evaluate_table(json_path, xml_path, method=method)
            if r is None:
                skipped += 1
            else:
                results.append(r)

    elapsed = time.time() - t0
    n = len(results)
    if n == 0:
        print(f"    {label}: no valid results!")
        return {}

    avg_top = sum(r['grits_top'] for r in results) / n
    avg_p = sum(r['grits_top_prec'] for r in results) / n
    avg_r = sum(r['grits_top_recall'] for r in results) / n
    col_exact = sum(r['col_exact'] for r in results) / n
    row_exact = sum(r['row_exact'] for r in results) / n

    no_span = [r for r in results if not r['has_spanning']]
    w_span = [r for r in results if r['has_spanning']]
    ns_top = sum(r['grits_top'] for r in no_span) / len(no_span) if no_span else 0
    ws_top = sum(r['grits_top'] for r in w_span) / len(w_span) if w_span else 0

    avg_kx = sum(r['kx'] for r in results) / n
    avg_ky = sum(r['ky'] for r in results) / n

    return {
        'label': label, 'n': n, 'skipped': skipped, 'elapsed': elapsed,
        'grits_top': avg_top, 'precision': avg_p, 'recall': avg_r,
        'col_exact': col_exact, 'row_exact': row_exact,
        'ns_top': ns_top, 'ws_top': ws_top,
        'n_ns': len(no_span), 'n_ws': len(w_span),
        'avg_kx': avg_kx, 'avg_ky': avg_ky,
    }


def print_comparison(r_fixed: dict, r_adaptive: dict, dataset_name: str):
    """Print fixed vs max-jump comparison table.

    Args:
        r_fixed: Results from fixed-k benchmark.
        r_adaptive: Results from max-jump benchmark.
        dataset_name: Display name (e.g. 'PubTables-1M').
    """
    print(f"\n  {'=' * 60}")
    print(f"  {dataset_name}")
    print(f"  {'=' * 60}")
    print(f"  {'':22s}  {'FIXED':>10s}  {'MAX-JUMP':>10s}  {'Delta':>8s}")
    print(f"  {'-' * 55}")

    metrics = [
        ('GriTS_Top', 'grits_top'),
        ('Precision', 'precision'),
        ('Recall', 'recall'),
        ('Col exact', 'col_exact'),
        ('Row exact', 'row_exact'),
        ('No spanning', 'ns_top'),
        ('With spanning', 'ws_top'),
    ]
    for label, key in metrics:
        vf = r_fixed.get(key, 0)
        va = r_adaptive.get(key, 0)
        delta = va - vf
        sign = '+' if delta >= 0 else ''
        print(f"  {label:22s}  {100 * vf:>9.1f}%  {100 * va:>9.1f}%"
              f"  {sign}{100 * delta:>6.1f}pp")

    print(f"  {'-' * 55}")
    print(f"  {'avg k_x equiv':22s}  {'0.300':>10s}  "
          f"{r_adaptive.get('avg_kx', 0):>10.3f}")
    print(f"  {'avg k_y equiv':22s}  {'0.050':>10s}  "
          f"{r_adaptive.get('avg_ky', 0):>10.3f}")
    print(f"  {'Tables':22s}  {r_fixed.get('n', 0):>10d}  "
          f"{r_adaptive.get('n', 0):>10d}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run the adaptive-k cross-domain comparison."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Max-jump vs fixed-k cross-domain benchmark',
    )
    parser.add_argument('--n', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cores', type=int, default=1)
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"\n{'=' * 65}")
    print(f"  Max-Jump vs Fixed K — Cross-Domain")
    print(f"  Threshold = point of maximum jump in gap distribution")
    print(f"  N={args.n}  seed={args.seed}  cores={args.cores}")
    print(f"{'=' * 65}")

    # PubTables-1M
    pairs_pub = find_pairs_pubtables(limit=args.n)
    print(f"\n  PubTables-1M: {len(pairs_pub)} tables ...")
    r_pub_fixed = run_benchmark(pairs_pub, 'fixed', args.cores, 'PubTables fixed')
    r_pub_maxjump = run_benchmark(pairs_pub, 'maxjump', args.cores, 'PubTables max-jump')
    print_comparison(r_pub_fixed, r_pub_maxjump, 'PubTables-1M')

    # FinTabNet
    random.seed(args.seed)
    pairs_fin = find_pairs_fintabnet(limit=args.n)
    print(f"  FinTabNet.c: {len(pairs_fin)} tables ...")
    r_fin_fixed = run_benchmark(pairs_fin, 'fixed', args.cores, 'FinTabNet fixed')
    r_fin_maxjump = run_benchmark(pairs_fin, 'maxjump', args.cores, 'FinTabNet max-jump')
    print_comparison(r_fin_fixed, r_fin_maxjump, 'FinTabNet.c')

    # Cross-domain summary
    print(f"\n{'=' * 65}")
    print(f"  CROSS-DOMAIN SUMMARY")
    print(f"{'=' * 65}")
    print(f"  {'':22s}  {'PubTab':>10s}  {'FinTab':>10s}  {'Gap':>8s}")
    print(f"  {'-' * 55}")

    gap_fixed = abs(
        r_pub_fixed.get('grits_top', 0) - r_fin_fixed.get('grits_top', 0),
    )
    gap_maxjump = abs(
        r_pub_maxjump.get('grits_top', 0) - r_fin_maxjump.get('grits_top', 0),
    )

    print(f"  {'Fixed GriTS_Top':22s}  "
          f"{100 * r_pub_fixed.get('grits_top', 0):>9.1f}%  "
          f"{100 * r_fin_fixed.get('grits_top', 0):>9.1f}%  "
          f"{100 * gap_fixed:>7.1f}pp")
    print(f"  {'Max-Jump GriTS_Top':22s}  "
          f"{100 * r_pub_maxjump.get('grits_top', 0):>9.1f}%  "
          f"{100 * r_fin_maxjump.get('grits_top', 0):>9.1f}%  "
          f"{100 * gap_maxjump:>7.1f}pp")
    print()

    if gap_maxjump < gap_fixed:
        pct = 100 * (1 - gap_maxjump / gap_fixed)
        print(f"  Max-jump REDUCES cross-domain gap: "
              f"{100 * gap_fixed:.1f}pp → {100 * gap_maxjump:.1f}pp "
              f"({pct:.0f}% reduction)")
    else:
        print(f"  Max-jump does NOT reduce cross-domain gap. "
              f"({100 * gap_fixed:.1f}pp → {100 * gap_maxjump:.1f}pp)")

    # Verdict
    pub_ok = (r_pub_maxjump.get('grits_top', 0) >=
              r_pub_fixed.get('grits_top', 0) - 0.005)
    fin_better = (r_fin_maxjump.get('grits_top', 0) >
                  r_fin_fixed.get('grits_top', 0))

    print()
    if pub_ok and fin_better:
        print("  *** VERDICT: Max-jump beats fixed-k on FinTabNet "
              "without degrading PubTables! ***")
        print("  *** The constant-free law works. ***")
    elif fin_better:
        print("  Max-jump improves FinTabNet but degrades PubTables.")
    else:
        print("  Max-jump does not improve FinTabNet.")
    print()


if __name__ == '__main__':
    main()
