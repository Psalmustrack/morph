#!/usr/bin/env python3
"""
morph.bench.grits — GriTS Benchmark (Grid Table Similarity)
=============================================================

Official PubTables-1M metric applied to Morph's structure detection.
Adapted from the Microsoft table-transformer repository (MIT License):
https://github.com/microsoft/table-transformer

GriTS uses optimal 2D dynamic-programming alignment between ground-truth
and predicted grids.  Unlike simple row/column exact match, it is robust
to off-by-one errors and partial matches.

Metrics computed:

* **GriTS_Top** — structural topology (relative-span cells)
* **GriTS_Con** — cell content (LCS text similarity)

The factored 2D MSS algorithm decomposes the NP-hard 2D alignment into
row-first and column-first passes, then intersects them.

Usage::

    python -m morph.bench.grits --n 1000 --cores 4
    python -m morph.bench.grits --dataset fintabnet --n 1000
    python -m morph.bench.grits --top-only    # topology only (faster)

Author: Eugeniu Tacu, 2026
"""

import itertools
import json
import os
import random
import time
from collections import Counter
from difflib import SequenceMatcher
from multiprocessing import Pool

import numpy as np

from morph.bench.grid import _group_into_rows, _count_cols_ratio
from morph.bench.pubtables import (
    find_pairs as find_pairs_pubtables,
    json_to_particles,
    parse_gt,
)


def find_pairs_fintabnet(limit: int | None = None) -> list[tuple]:
    """Discover (JSON, XML) pairs for the FinTabNet.c-Structure dataset.

    Args:
        limit: Maximum number of pairs to return (random sample).

    Returns:
        List of ``(json_path, xml_path)`` tuples.
    """
    root = os.environ.get(
        'FINTABNET_ROOT',
        '/mnt/dati/home/Progetti/dataset/fintabnet/FinTabNet.c-Structure',
    )
    test_dir = os.path.join(root, 'test')
    words_dir = os.path.join(root, 'words')

    xmls = {}
    for f in os.scandir(test_dir):
        if f.name.endswith('.xml'):
            xmls[f.name.replace('.xml', '')] = f.path

    pairs = []
    for f in os.scandir(words_dir):
        if f.name.endswith('_words.json'):
            key = f.name.replace('_words.json', '')
            if key in xmls:
                pairs.append((f.path, xmls[key]))

    random.shuffle(pairs)
    if limit:
        pairs = pairs[:limit]
    return pairs


# ---------------------------------------------------------------------------
# GriTS core — adapted from Microsoft (MIT License)
# ---------------------------------------------------------------------------

def bbox_iou(bbox1, bbox2) -> float:
    """Intersection-over-Union between two ``[x0, y0, x1, y1]`` boxes.

    Handles empty cells (represented as ``0`` from numpy init):
    two empty cells match perfectly (IoU = 1.0).

    Args:
        bbox1: First bounding box or scalar 0 (empty cell).
        bbox2: Second bounding box or scalar 0.

    Returns:
        IoU score in [0, 1].
    """
    if not isinstance(bbox1, (list, tuple)) or not isinstance(bbox2, (list, tuple)):
        if not isinstance(bbox1, (list, tuple)) and not isinstance(bbox2, (list, tuple)):
            return 1.0  # both empty = perfect match
        return 0.0
    x0 = max(bbox1[0], bbox2[0])
    y0 = max(bbox1[1], bbox2[1])
    x1 = min(bbox1[2], bbox2[2])
    y1 = min(bbox1[3], bbox2[3])
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    area1 = max(0, bbox1[2] - bbox1[0]) * max(0, bbox1[3] - bbox1[1])
    area2 = max(0, bbox2[2] - bbox2[0]) * max(0, bbox2[3] - bbox2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def lcs_similarity(s1, s2) -> float:
    """Normalised LCS (Longest Common Subsequence) similarity.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Similarity in [0, 1].
    """
    s1, s2 = str(s1), str(s2)
    if len(s1) == 0 and len(s2) == 0:
        return 1.0
    if len(s1) == 0 or len(s2) == 0:
        return 0.0
    sm = SequenceMatcher(None, s1, s2)
    lcs = ''.join([s1[b.a:b.a + b.size] for b in sm.get_matching_blocks()])
    return 2 * len(lcs) / (len(s1) + len(s2))


def compute_fscore(
    tp: float,
    n_true: int,
    n_pos: int,
) -> tuple[float, float, float]:
    """Compute F-score with GriTS conventions.

    Args:
        tp: True positive sum (may be fractional from similarity).
        n_true: Total ground-truth cells.
        n_pos: Total predicted cells.

    Returns:
        Tuple ``(f_score, precision, recall)``.
    """
    prec = tp / n_pos if n_pos > 0 else 1.0
    recall = tp / n_true if n_true > 0 else 1.0
    if prec + recall > 0:
        f = 2 * prec * recall / (prec + recall)
    else:
        f = 0.0
    return f, prec, recall


def _init_dp(len1: int, len2: int):
    """Initialise DP score and pointer matrices."""
    scores = np.zeros((len1 + 1, len2 + 1))
    pointers = np.zeros((len1 + 1, len2 + 1))
    for i in range(1, len1 + 1):
        pointers[i, 0] = -1
    for j in range(1, len2 + 1):
        pointers[0, j] = 1
    return scores, pointers


def _traceback(pointers):
    """Trace back through pointer matrix to recover alignment."""
    i, j = pointers.shape[0] - 1, pointers.shape[1] - 1
    ai, aj = [], []
    while i > 0 or j > 0:
        if pointers[i, j] == -1:
            i -= 1
        elif pointers[i, j] == 1:
            j -= 1
        else:
            i -= 1; j -= 1
            ai.append(i); aj.append(j)
    return ai[::-1], aj[::-1]


def _align_1d(seq1, seq2, rewards):
    """1D DP alignment with pre-computed rewards."""
    n1, n2 = len(seq1), len(seq2)
    scores, ptrs = _init_dp(n1, n2)
    for i in range(1, n1 + 1):
        for j in range(1, n2 + 1):
            r = rewards[seq1[i - 1] + seq2[j - 1]]
            diag = scores[i - 1, j - 1] + r
            skip_j = scores[i, j - 1]
            skip_i = scores[i - 1, j]
            m = max(diag, skip_i, skip_j)
            scores[i, j] = m
            if diag == m:
                ptrs[i, j] = 0
            elif skip_i == m:
                ptrs[i, j] = -1
            else:
                ptrs[i, j] = 1
    return scores[-1, -1]


def _align_2d_outer(shape1, shape2, rewards):
    """Outer 2D DP: align rows with 1D column alignment inside."""
    scores, ptrs = _init_dp(shape1[0], shape2[0])
    for i in range(1, shape1[0] + 1):
        for j in range(1, shape2[0] + 1):
            r = _align_1d(
                [(i - 1, c) for c in range(shape1[1])],
                [(j - 1, c) for c in range(shape2[1])],
                rewards,
            )
            diag = scores[i - 1, j - 1] + r
            skip_j = scores[i, j - 1]
            skip_i = scores[i - 1, j]
            m = max(diag, skip_i, skip_j)
            scores[i, j] = m
            if diag == m:
                ptrs[i, j] = 0
            elif skip_i == m:
                ptrs[i, j] = -1
            else:
                ptrs[i, j] = 1
    ai, aj = _traceback(ptrs)
    return ai, aj, scores[-1, -1]


def factored_2dmss(gt_grid, pred_grid, reward_fn):
    """Factored 2D Most-Similar-Substructures — the heart of GriTS.

    Decomposes the 2D grid alignment into row-first and column-first
    passes, then intersects them for the final score.

    Copyright (C) 2021 Microsoft Corporation (MIT License).

    Args:
        gt_grid: Ground-truth grid (numpy object array).
        pred_grid: Predicted grid (numpy object array).
        reward_fn: Similarity function for cell pairs.

    Returns:
        Tuple ``(f_score, precision, recall)``.
    """
    rewards = {}
    t_rewards = {}
    for tr, tc, pr, pc in itertools.product(
        range(gt_grid.shape[0]), range(gt_grid.shape[1]),
        range(pred_grid.shape[0]), range(pred_grid.shape[1]),
    ):
        r = reward_fn(gt_grid[tr, tc], pred_grid[pr, pc])
        rewards[(tr, tc, pr, pc)] = r
        t_rewards[(tc, tr, pc, pr)] = r

    n_true = gt_grid.shape[0] * gt_grid.shape[1]
    n_pos = pred_grid.shape[0] * pred_grid.shape[1]

    true_rows, pred_rows, _ = _align_2d_outer(
        gt_grid.shape[:2], pred_grid.shape[:2], rewards,
    )
    true_cols, pred_cols, _ = _align_2d_outer(
        gt_grid.shape[:2][::-1], pred_grid.shape[:2][::-1], t_rewards,
    )

    match = 0
    for tr, pr in zip(true_rows, pred_rows):
        for tc, pc in zip(true_cols, pred_cols):
            match += rewards[(tr, tc, pr, pc)]

    return compute_fscore(match, n_true, n_pos)


# ---------------------------------------------------------------------------
# Grid construction
# ---------------------------------------------------------------------------

def cells_to_relspan_grid(cells: list[dict]):
    """Convert cells to a relative-span grid for GriTS_Top.

    Each cell occupies one or more (row, col) positions.  The grid
    stores ``[col_offset, row_offset, col_end, row_end]`` relative
    spans at each position.

    Args:
        cells: List of cell dicts with ``row_nums``, ``column_nums``.

    Returns:
        Numpy object array of shape ``(n_rows, n_cols)``.
    """
    if not cells:
        return np.zeros((1, 1), dtype=object)
    n_rows = max(max(c['row_nums']) for c in cells) + 1
    n_cols = max(max(c['column_nums']) for c in cells) + 1
    grid = np.zeros((n_rows, n_cols), dtype=object)
    for cell in cells:
        r_min = min(cell['row_nums'])
        c_min = min(cell['column_nums'])
        r_max = max(cell['row_nums']) + 1
        c_max = max(cell['column_nums']) + 1
        for r in cell['row_nums']:
            for c in cell['column_nums']:
                grid[r, c] = [c_min - c, r_min - r, c_max - c, r_max - r]
    return grid


def cells_to_text_grid(cells: list[dict]):
    """Convert cells to a text grid for GriTS_Con.

    Args:
        cells: List of cell dicts with ``row_nums``, ``column_nums``,
            ``cell_text``.

    Returns:
        Numpy object array of strings.
    """
    if not cells:
        return np.array([['']], dtype=object)
    n_rows = max(max(c['row_nums']) for c in cells) + 1
    n_cols = max(max(c['column_nums']) for c in cells) + 1
    grid = np.empty((n_rows, n_cols), dtype=object)
    grid[:] = ''
    for cell in cells:
        for r in cell['row_nums']:
            for c in cell['column_nums']:
                grid[r, c] = cell.get('cell_text', '')
    return grid


def build_gt_cells(
    gt: dict,
    words: list[dict] | None = None,
) -> list[dict]:
    """Build ground-truth cells from rows, columns, and spanning cells.

    Handles both simple tables (one cell per grid position) and complex
    tables with spanning cells that occupy multiple rows/columns.

    Args:
        gt: Parsed ground truth from :func:`parse_gt`.
        words: Optional word annotations for text assignment.

    Returns:
        List of cell dicts with ``row_nums``, ``column_nums``,
        ``cell_text``.
    """
    rows = gt['rows']
    cols = gt['columns']
    n_rows, n_cols = len(rows), len(cols)
    if n_rows == 0 or n_cols == 0:
        return []

    cell_spans = {}
    for r in range(n_rows):
        for c in range(n_cols):
            cell_spans[(r, c)] = ([r], [c])

    occupied = set()
    for sc in gt.get('spanning_cells', []):
        sc_rows = []
        for r, row in enumerate(rows):
            h = row['ymax'] - row['ymin']
            ov = min(sc['ymax'], row['ymax']) - max(sc['ymin'], row['ymin'])
            if h > 0 and ov / h >= 0.5:
                sc_rows.append(r)
        sc_cols = []
        for c, col in enumerate(cols):
            w = col['xmax'] - col['xmin']
            ov = min(sc['xmax'], col['xmax']) - max(sc['xmin'], col['xmin'])
            if w > 0 and ov / w >= 0.5:
                sc_cols.append(c)
        if not sc_rows or not sc_cols:
            continue
        if any((r, c) in occupied for r in sc_rows for c in sc_cols):
            continue
        for r in sc_rows:
            for c in sc_cols:
                occupied.add((r, c))
                cell_spans[(r, c)] = (sc_rows, sc_cols)

    seen = set()
    cells = []
    for r in range(n_rows):
        for c in range(n_cols):
            rn, cn = cell_spans[(r, c)]
            key = (tuple(rn), tuple(cn))
            if key not in seen:
                seen.add(key)
                cells.append({
                    'row_nums': list(rn),
                    'column_nums': list(cn),
                    'cell_text': '',
                })

    if words:
        cell_lookup = {}
        for cell in cells:
            for r in cell['row_nums']:
                for c in cell['column_nums']:
                    cell_lookup[(r, c)] = cell

        row_centers = [(row['ymin'] + row['ymax']) / 2 for row in rows]
        col_centers = [(col['xmin'] + col['xmax']) / 2 for col in cols]

        for w in words:
            text = w.get('text', '').strip()
            if not text:
                continue
            x0, y0, x1, y1 = w['bbox']
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            r_idx = min(range(n_rows), key=lambda i: abs(cy - row_centers[i]))
            c_idx = min(range(n_cols), key=lambda i: abs(cx - col_centers[i]))
            cell = cell_lookup.get((r_idx, c_idx))
            if cell:
                cell['cell_text'] = (cell['cell_text'] + ' ' + text).strip()

    return cells


def build_pred_cells(
    col_splits: list[float],
    row_groups: list[list[dict]],
) -> list[dict]:
    """Build predicted cells from column splits and row groups.

    Args:
        col_splits: X-positions of column boundaries.
        row_groups: Grouped particles per row.

    Returns:
        List of cell dicts with ``row_nums``, ``column_nums``,
        ``cell_text``.
    """
    n_rows = len(row_groups)
    n_cols = len(col_splits) + 1
    if n_rows == 0 or n_cols == 0:
        return []

    cell_texts: dict[tuple, list[str]] = {}
    for r, row in enumerate(row_groups):
        for p in row:
            c = sum(1 for sx in col_splits if p['x'] > sx)
            c = min(c, n_cols - 1)
            if (r, c) not in cell_texts:
                cell_texts[(r, c)] = []
            cell_texts[(r, c)].append(p.get('text', ''))

    cells = []
    for r in range(n_rows):
        for c in range(n_cols):
            texts = cell_texts.get((r, c), [])
            cells.append({
                'row_nums': [r],
                'column_nums': [c],
                'cell_text': ' '.join(texts),
            })
    return cells


# ---------------------------------------------------------------------------
# Per-column row detection (universal boundary law: k_y = 0.05)
# ---------------------------------------------------------------------------

def _count_rows_per_column(
    col_particles: list[dict],
    k_y: float = 0.1,
) -> int:
    """Count rows in a column using the universal boundary law on Y.

    Boundary condition: ``gap_y > avg_particle_height * k_y``.
    Symmetric with :func:`_count_cols_ratio` (per-row).

    Args:
        col_particles: Particles assigned to one column.
        k_y: Boundary constant (default 0.1).

    Returns:
        Number of detected rows.
    """
    if len(col_particles) < 2:
        return max(1, len(col_particles))
    sorted_ps = sorted(col_particles, key=lambda p: p['y0'])
    heights = [p['y1'] - p['y0'] for p in sorted_ps if p['y1'] > p['y0']]
    if not heights:
        return 1
    avg_h = max(3.0, min(30.0, sum(heights) / len(heights)))
    threshold = avg_h * k_y
    n_rows = 1
    for i in range(1, len(sorted_ps)):
        gap = sorted_ps[i]['y0'] - sorted_ps[i - 1]['y1']
        if gap > threshold:
            n_rows += 1
    return n_rows


def find_row_splits_per_column(
    particles: list[dict],
    col_splits: list[float],
    k_y: float = 0.1,
) -> tuple[list[float], int]:
    """Find Y row boundaries using per-column mode voting.

    Symmetric with :func:`find_col_splits_ratio`:

    * Columns: per row, count cols with ``gap_x > avg_w * k_x`` → vote
    * Rows: per column, count rows with ``gap_y > avg_h * k_y`` → vote

    Args:
        particles: All particles on the page.
        col_splits: Column boundary X-positions.
        k_y: Boundary constant.

    Returns:
        Tuple ``(row_split_positions, mode_row_count)``.
    """
    n_cols = len(col_splits) + 1

    columns: list[list[dict]] = [[] for _ in range(n_cols)]
    for p in particles:
        c = sum(1 for sx in col_splits if p['x'] > sx)
        columns[min(c, n_cols - 1)].append(p)

    votes = []
    col_data = []
    for col_ps in columns:
        if len(col_ps) < 2:
            continue
        n = _count_rows_per_column(col_ps, k_y=k_y)
        votes.append(n)
        col_data.append((col_ps, n))

    if not votes:
        return [], 1

    mode_rows = Counter(votes).most_common(1)[0][0]
    if mode_rows <= 1:
        return [], 1

    best_boundaries: list[float] = []
    best_size = 0
    for col_ps, n in col_data:
        if n == mode_rows and len(col_ps) > best_size:
            sorted_ps = sorted(col_ps, key=lambda p: p['y0'])
            heights = [p['y1'] - p['y0'] for p in sorted_ps
                       if p['y1'] > p['y0']]
            avg_h = (max(3.0, min(30.0, sum(heights) / len(heights)))
                     if heights else 10)
            threshold = avg_h * k_y
            boundaries = []
            for i in range(1, len(sorted_ps)):
                gap = sorted_ps[i]['y0'] - sorted_ps[i - 1]['y1']
                if gap > threshold:
                    boundaries.append(
                        (sorted_ps[i - 1]['y1'] + sorted_ps[i]['y0']) / 2,
                    )
            if len(boundaries) == mode_rows - 1:
                best_boundaries = boundaries
                best_size = len(col_ps)

    return best_boundaries, mode_rows


def group_rows_per_column(
    particles: list[dict],
    col_splits: list[float],
    k_y: float = 0.1,
) -> list[list[dict]]:
    """Group particles into rows using per-column row splits.

    Falls back to proximity-based grouping if no row splits are found.

    Args:
        particles: All particles on the page.
        col_splits: Column boundary X-positions.
        k_y: Boundary constant.

    Returns:
        List of row groups (each a list of particles).
    """
    row_splits, mode_rows = find_row_splits_per_column(
        particles, col_splits, k_y,
    )
    if not row_splits:
        return _group_into_rows(particles)

    rows: list[list[dict]] = [[] for _ in range(mode_rows)]
    for p in particles:
        r = sum(1 for sy in row_splits if p['y0'] > sy)
        rows[min(r, mode_rows - 1)].append(p)
    return [r for r in rows if r]


# ---------------------------------------------------------------------------
# Column splits from mode-row (universal boundary law)
# ---------------------------------------------------------------------------

def find_col_splits_ratio(
    particles: list[dict],
    k: float = 0.3,
) -> list[float]:
    """Find column boundary X-positions using ratio k.

    For each row: count columns where ``gap_x > avg_width * k``.
    Mode-vote across rows, then extract boundaries from the best row.

    Args:
        particles: All particles.
        k: Boundary constant (default 0.3).

    Returns:
        Sorted list of column split X-positions.
    """
    if len(particles) < 2:
        return []
    rows = _group_into_rows(particles)
    votes, row_data = [], []
    for row in rows:
        if len(row) < 2:
            continue
        n = _count_cols_ratio(row, k=k)
        votes.append(n)
        row_data.append((row, n))
    if not votes:
        return []
    mode_cols = Counter(votes).most_common(1)[0][0]
    if mode_cols <= 1:
        return []

    best_boundaries: list[float] = []
    best_size = 0
    for row, n in row_data:
        if n == mode_cols and len(row) > best_size:
            ps = sorted(row, key=lambda p: p['x0'])
            widths = [p['x1'] - p['x0'] for p in ps]
            gaps = [ps[i + 1]['x0'] - ps[i]['x1']
                    for i in range(len(ps) - 1)]
            avg_w = sum(widths) / len(widths) if widths else 10
            if avg_w <= 0:
                avg_w = 10
            threshold = avg_w * k
            boundaries = [
                (ps[i]['x1'] + ps[i + 1]['x0']) / 2
                for i, g in enumerate(gaps)
                if g > threshold
            ]
            if len(boundaries) == mode_cols - 1:
                best_boundaries = boundaries
                best_size = len(row)
    return best_boundaries


# ---------------------------------------------------------------------------
# Single-table evaluation
# ---------------------------------------------------------------------------

def evaluate_grits(
    json_path: str,
    xml_path: str,
    top_only: bool = False,
    k_y: float = 0.1,
) -> dict | None:
    """Compute GriTS_Top (and optionally GriTS_Con) for one table.

    Args:
        json_path: Path to ``_words.json`` file.
        xml_path: Path to ``.xml`` ground truth.
        top_only: Skip GriTS_Con (faster).
        k_y: Row detection boundary constant.

    Returns:
        Dict with metrics, or ``None`` if the table is invalid/too large.
    """
    with open(json_path) as f:
        words = json.load(f)
    gt = parse_gt(xml_path)

    if not gt['columns'] or not gt['rows']:
        return None

    n_gt_rows = len(gt['rows'])
    n_gt_cols = len(gt['columns'])
    has_spanning = len(gt.get('spanning_cells', [])) > 0

    # Cap very large tables (DP is O(R1*C1*R2*C2))
    if n_gt_rows > 50 or n_gt_cols > 30:
        return None

    particles = json_to_particles(words, domain=False)
    if len(particles) < 3:
        return None

    # Predicted structure
    col_splits = find_col_splits_ratio(particles)
    rows_pred = group_rows_per_column(particles, col_splits, k_y=k_y)
    n_pred_rows = len(rows_pred)
    n_pred_cols = len(col_splits) + 1

    if n_pred_rows > 60 or n_pred_cols > 35:
        return None

    # --- GriTS_Top ---
    if not has_spanning:
        # Fast path: all cells have relspan [0,0,1,1]
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

    result = {
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
        'n_words': len(words),
    }

    # --- GriTS_Con (optional, slower) ---
    if not top_only:
        gt_cells_con = build_gt_cells(gt, words=words)
        pred_cells_con = build_pred_cells(col_splits, rows_pred)
        gt_text = cells_to_text_grid(gt_cells_con)
        pred_text = cells_to_text_grid(pred_cells_con)
        con_f, con_p, con_r = factored_2dmss(
            gt_text, pred_text, lcs_similarity,
        )
        result['grits_con'] = con_f
        result['grits_con_prec'] = con_p
        result['grits_con_recall'] = con_r

    return result


# ---------------------------------------------------------------------------
# Multiprocessing support
# ---------------------------------------------------------------------------

_WORKER_TOP_ONLY = False
_WORKER_KY = 0.1


def _eval_worker(args):
    """Worker for :class:`multiprocessing.Pool`."""
    json_path, xml_path = args
    return evaluate_grits(
        json_path, xml_path,
        top_only=_WORKER_TOP_ONLY, k_y=_WORKER_KY,
    )


def _init_worker(top_only, k_y):
    """Initialiser for worker processes."""
    global _WORKER_TOP_ONLY, _WORKER_KY
    _WORKER_TOP_ONLY = top_only
    _WORKER_KY = k_y


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run the GriTS benchmark from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description='GriTS benchmark on PubTables-1M / FinTabNet',
    )
    parser.add_argument('--n', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cores', type=int, default=1)
    parser.add_argument('--ky', type=float, default=0.1,
                        help='k_y for per-column row detection')
    parser.add_argument('--top-only', action='store_true',
                        help='Topology only (skip GriTS_Con)')
    parser.add_argument('--dataset', choices=['pubtables', 'fintabnet'],
                        default='pubtables')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    random.seed(args.seed)
    if args.dataset == 'fintabnet':
        pairs = find_pairs_fintabnet(limit=args.n)
        ds_name = 'FinTabNet.c'
    else:
        pairs = find_pairs_pubtables(limit=args.n)
        ds_name = 'PubTables-1M'

    print(f"\n{'=' * 65}")
    print(f"  GriTS Benchmark — k_x=0.3  k_y={args.ky}  on {ds_name}")
    print(f"  N={len(pairs)}  seed={args.seed}  cores={args.cores}"
          f"  {'top-only' if args.top_only else 'top+con'}")
    print(f"{'=' * 65}\n")

    results = []
    skipped = 0
    t0 = time.time()

    if args.cores > 1:
        work = [(j, x) for j, x in pairs]
        with Pool(
            args.cores,
            initializer=_init_worker,
            initargs=(args.top_only, args.ky),
        ) as pool:
            for i, r in enumerate(
                pool.imap_unordered(_eval_worker, work, chunksize=32),
            ):
                if r is None:
                    skipped += 1
                    continue
                results.append(r)
                if (i + 1) % 200 == 0:
                    elapsed = time.time() - t0
                    print(f"  [{i + 1}/{len(pairs)}] "
                          f"{(i + 1) / elapsed:.0f} tab/s ...")
    else:
        for i, (json_path, xml_path) in enumerate(pairs):
            r = evaluate_grits(
                json_path, xml_path,
                top_only=args.top_only, k_y=args.ky,
            )
            if r is None:
                skipped += 1
                continue
            results.append(r)
            if args.verbose:
                print(f"  {os.path.basename(json_path)}: "
                      f"Top={r['grits_top']:.3f} "
                      f"cols={r['gt_cols']}→{r['pred_cols']} "
                      f"rows={r['gt_rows']}→{r['pred_rows']}")
            if (i + 1) % 100 == 0 and not args.verbose:
                elapsed = time.time() - t0
                print(f"  [{i + 1}/{len(pairs)}] "
                      f"{(i + 1) / elapsed:.0f} tab/s ...")

    elapsed = time.time() - t0
    n = len(results)
    if n == 0:
        print("  No valid results!")
        return

    # --- Report ---
    print(f"\n{'=' * 65}")
    print(f"  GriTS RESULTS — k_x=0.3  k_y={args.ky}  [{ds_name}]")
    print(f"{'=' * 65}")
    print(f"  Tables: {n} evaluated, {skipped} skipped")
    print(f"  Time: {elapsed:.1f}s ({n / elapsed:.0f} tab/s)\n")

    avg_top = sum(r['grits_top'] for r in results) / n
    avg_top_p = sum(r['grits_top_prec'] for r in results) / n
    avg_top_r = sum(r['grits_top_recall'] for r in results) / n
    print(f"  GriTS_Top (structural topology):")
    print(f"    F-score:   {avg_top:.4f}")
    print(f"    Precision: {avg_top_p:.4f}")
    print(f"    Recall:    {avg_top_r:.4f}\n")

    if not args.top_only:
        avg_con = sum(r['grits_con'] for r in results) / n
        print(f"  GriTS_Con (cell content):")
        print(f"    F-score:   {avg_con:.4f}\n")

    col_exact = sum(r['col_exact'] for r in results)
    row_exact = sum(r['row_exact'] for r in results)
    print(f"  COMPARISON:")
    print(f"    Col exact: {100 * col_exact / n:.1f}%")
    print(f"    Row exact: {100 * row_exact / n:.1f}%")
    print(f"    GriTS_Top: {100 * avg_top:.1f}%\n")

    # Breakdown by table size
    small = [r for r in results if r['gt_cols'] <= 3]
    medium = [r for r in results if 4 <= r['gt_cols'] <= 6]
    large = [r for r in results if r['gt_cols'] >= 7]
    print(f"  BY GT COLUMNS:")
    for label, subset in [('1-3', small), ('4-6', medium), ('7+', large)]:
        if subset:
            avg = sum(r['grits_top'] for r in subset) / len(subset)
            ce = sum(r['col_exact'] for r in subset) / len(subset)
            print(f"    {label:5s}: GriTS_Top={avg:.3f}  "
                  f"col_exact={100 * ce:.1f}%  N={len(subset)}")
    print()

    # Distribution
    perfect = sum(1 for r in results if r['grits_top'] >= 0.999)
    high = sum(1 for r in results if 0.9 <= r['grits_top'] < 0.999)
    mid = sum(1 for r in results if 0.7 <= r['grits_top'] < 0.9)
    low = sum(1 for r in results if r['grits_top'] < 0.7)
    print(f"  DISTRIBUTION:")
    print(f"    =1.000 (perfect): {perfect:>5d} ({100 * perfect / n:.1f}%)")
    print(f"    0.9-1.0 (good):   {high:>5d} ({100 * high / n:.1f}%)")
    print(f"    0.7-0.9 (medium): {mid:>5d} ({100 * mid / n:.1f}%)")
    print(f"    <0.7    (low):    {low:>5d} ({100 * low / n:.1f}%)")
    print()


if __name__ == '__main__':
    main()
