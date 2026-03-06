#!/usr/bin/env python3
"""
morph.bench.pubtables — PubTables-1M Benchmark Adapter
=======================================================

Converts PubTables-1M JSON word annotations into Morph particles and
evaluates column / row detection accuracy against PASCAL-VOC XML
ground truth.

Dataset structure expected::

    <DATASET_ROOT>/
        <table_id>_words.json   — word bounding boxes + text
        <table_id>.xml          — PASCAL-VOC ground truth

Usage::

    python -m morph.bench.pubtables --n 1000 --cores 4

Author: Eugeniu Tacu, 2026
"""

import json
import os
import random
import time
import xml.etree.ElementTree as ET
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from morph.core.typify import typify_word
from morph.core.sense import sense_page
from morph.bench.grid import count_columns_universal, count_rows_universal
from morph.core.field import extract_page

# Default dataset path — override with PUBTABLES_ROOT env var
DATASET = Path(
    os.environ.get(
        'PUBTABLES_ROOT',
        '/mnt/dati/home/Progetti/dataset/pubtables-1m',
    )
)


# ---------------------------------------------------------------------------
# Adapter: JSON words → Morph particles
# ---------------------------------------------------------------------------

def json_to_particles(
    words: list[dict],
    domain: bool = False,
) -> list[dict]:
    """Convert PubTables-1M word annotations to Morph particles.

    Each word is typed through :func:`~morph.core.typify.typify_word`
    and positioned using the bounding box centre.

    Args:
        words: List of dicts with ``text`` and ``bbox`` keys.
        domain: If True, activate HVAC domain vocabulary.

    Returns:
        List of particle dicts compatible with sense/field layers.
    """
    particles = []
    for w in words:
        text = w.get('text', '').strip()
        if not text:
            continue
        x0, y0, x1, y1 = w['bbox']
        ptype = typify_word(text, domain=domain)
        particles.append({
            'text': text[:80],
            'x': (x0 + x1) / 2,
            'y': (y0 + y1) / 2,
            'x0': x0, 'x1': x1,
            'y0': y0, 'y1': y1,
            'type': ptype,
            'size': 10.0,  # not available in the dataset
        })
    return particles


# ---------------------------------------------------------------------------
# PASCAL-VOC XML ground-truth parser
# ---------------------------------------------------------------------------

def parse_gt(xml_path: str) -> dict:
    """Parse PASCAL-VOC XML ground truth for a table.

    Extracts rows, columns, optional column header, and spanning cells.

    Args:
        xml_path: Path to the XML annotation file.

    Returns:
        Dict with ``width``, ``height``, ``rows``, ``columns``,
        ``header``, ``spanning_cells``.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    size = root.find('size')
    width = float(size.find('width').text)
    height = float(size.find('height').text)

    gt: dict = {
        'width': width,
        'height': height,
        'rows': [],
        'columns': [],
        'header': None,
        'spanning_cells': [],
    }

    for obj in root.findall('object'):
        name = obj.find('name').text
        bb = obj.find('bndbox')
        bbox = {
            'xmin': float(bb.find('xmin').text),
            'ymin': float(bb.find('ymin').text),
            'xmax': float(bb.find('xmax').text),
            'ymax': float(bb.find('ymax').text),
        }

        if name == 'table row':
            gt['rows'].append(bbox)
        elif name == 'table column':
            gt['columns'].append(bbox)
        elif name == 'table column header':
            gt['header'] = bbox
        elif name == 'table spanning cell':
            gt['spanning_cells'].append(bbox)

    gt['rows'].sort(key=lambda b: b['ymin'])
    gt['columns'].sort(key=lambda b: b['xmin'])

    return gt


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def count_columns_detected(particles: list[dict]) -> int:
    """Count detected columns by clustering structural particles on X.

    Structural types: NUMERIC, SPEC_LABEL, MODEL, MODEL_CODE,
    SIZE_HEADER, KW_HEADER, UNIT.

    Args:
        particles: Typed particle list (post-sensing).

    Returns:
        Number of detected columns (clusters with >= 2 particles).
    """
    structural_types = {
        'NUMERIC', 'SPEC_LABEL', 'MODEL', 'MODEL_CODE',
        'SIZE_HEADER', 'KW_HEADER', 'UNIT',
    }
    structural = sorted(
        [p for p in particles if p['type'] in structural_types],
        key=lambda p: p['x'],
    )
    if not structural:
        return 0

    clusters = [[structural[0]]]
    for p in structural[1:]:
        if abs(p['x'] - clusters[-1][-1]['x']) < 20:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    return sum(1 for c in clusters if len(c) >= 2)


def count_rows_from_particles(
    particles: list[dict],
    y_tol: float = 8.0,
) -> int:
    """Count rows by grouping particles on Y.

    Args:
        particles: Typed particle list.
        y_tol: Maximum Y-gap within the same row.

    Returns:
        Number of detected rows.
    """
    ys = sorted(set(round(p['y'], 1) for p in particles))
    if not ys:
        return 0
    rows = [[ys[0]]]
    for y in ys[1:]:
        if y - rows[-1][-1] < y_tol:
            rows[-1].append(y)
        else:
            rows.append([y])
    return len(rows)


def evaluate_table(
    json_path: str,
    xml_path: str,
    domain: bool = False,
    verbose: bool = False,
) -> dict:
    """Evaluate Morph on a single PubTables-1M table.

    Runs the full pipeline (typify → sense → field) and compares
    detected structure against ground truth.

    Args:
        json_path: Path to ``_words.json`` file.
        xml_path: Path to corresponding ``.xml`` file.
        domain: Activate HVAC domain vocabulary.
        verbose: Print per-table results.

    Returns:
        Dict with accuracy metrics, or ``{'skip': True}`` if invalid.
    """
    with open(json_path) as f:
        words = json.load(f)

    gt = parse_gt(xml_path)

    particles = json_to_particles(words, domain=domain)
    if len(particles) < 3:
        return {'skip': True, 'reason': 'too_few_particles'}

    sense_result = sense_page(particles)
    sensed = sense_result['particles']

    field_result = extract_page(sensed)

    gt_cols = len(gt['columns'])
    gt_rows = len(gt['rows'])
    det_cols = count_columns_universal(sensed)
    det_cols_grid = count_columns_detected(sensed)
    det_rows = count_rows_universal(sensed)
    det_entities = field_result['stats']['entities']
    det_specs = field_result['stats']['total_specs']
    det_mapped = field_result['stats']['mapped']
    det_unmapped = field_result['stats']['unmapped']

    type_dist = Counter(p['type'] for p in sensed)

    result = {
        'skip': False,
        'gt_cols': gt_cols,
        'gt_rows': gt_rows,
        'det_cols': det_cols,
        'det_cols_grid': det_cols_grid,
        'det_rows': det_rows,
        'col_exact': 1 if det_cols == gt_cols else 0,
        'col_exact_grid': 1 if det_cols_grid == gt_cols else 0,
        'col_delta': det_cols - gt_cols,
        'row_exact': 1 if det_rows == gt_rows else 0,
        'row_delta': det_rows - gt_rows,
        'det_entities': det_entities,
        'det_specs': det_specs,
        'det_mapped': det_mapped,
        'det_unmapped': det_unmapped,
        'n_words': len(words),
        'n_particles': len(sensed),
        'types': dict(type_dist),
        'has_spanning': len(gt['spanning_cells']) > 0,
    }

    if verbose:
        name = Path(json_path).stem.replace('_words', '')
        print(f"  {name}: cols={gt_cols}→{det_cols} "
              f"rows={gt_rows}→{det_rows} "
              f"mapped={det_mapped} entities={det_entities}")

    return result


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def find_pairs(limit: int | None = None) -> list[tuple]:
    """Discover (JSON, XML) pairs in the PubTables-1M dataset.

    Args:
        limit: Maximum number of pairs to return (random sample).

    Returns:
        List of ``(json_path, xml_path)`` tuples.
    """
    xmls = {}
    for f in os.scandir(DATASET):
        if f.name.endswith('.xml'):
            key = f.name.replace('.xml', '')
            xmls[key] = f.path

    pairs = []
    for f in os.scandir(DATASET):
        if f.name.endswith('_words.json'):
            key = f.name.replace('_words.json', '')
            if key in xmls:
                pairs.append((f.path, xmls[key]))

    random.shuffle(pairs)
    if limit:
        pairs = pairs[:limit]
    return pairs


# ---------------------------------------------------------------------------
# Multiprocessing worker
# ---------------------------------------------------------------------------

def _eval_worker(args_tuple):
    """Worker function for :class:`multiprocessing.Pool`."""
    json_path, xml_path, domain = args_tuple
    return evaluate_table(json_path, xml_path, domain=domain)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run the PubTables-1M benchmark from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Morph benchmark on PubTables-1M',
    )
    parser.add_argument('--n', type=int, default=100,
                        help='Number of tables to test')
    parser.add_argument('--domain', action='store_true',
                        help='Activate HVAC domain vocabulary')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cores', type=int, default=1,
                        help='Parallel cores (4 = sweet spot)')
    args = parser.parse_args()

    random.seed(args.seed)
    pairs = find_pairs(limit=args.n)
    mode = 'engine+HVAC' if args.domain else 'engine-only'

    print(f"\n{'=' * 60}")
    print(f"  Morph Benchmark — PubTables-1M")
    print(f"  Mode: {mode}  |  N={len(pairs)}  |  "
          f"seed={args.seed}  |  cores={args.cores}")
    print(f"{'=' * 60}\n")

    results = []
    skipped = 0
    t0 = time.time()

    if args.cores > 1:
        work = [(j, x, args.domain) for j, x in pairs]
        with Pool(args.cores) as pool:
            for i, r in enumerate(
                pool.imap_unordered(_eval_worker, work, chunksize=64),
            ):
                if r.get('skip'):
                    skipped += 1
                    continue
                results.append(r)
                done = i + 1
                if done % 2000 == 0:
                    elapsed = time.time() - t0
                    print(f"  [{done}/{len(pairs)}] "
                          f"{done / elapsed:.0f} tab/s ...")
    else:
        for i, (json_path, xml_path) in enumerate(pairs):
            r = evaluate_table(
                json_path, xml_path,
                domain=args.domain, verbose=args.verbose,
            )
            if r.get('skip'):
                skipped += 1
                continue
            results.append(r)

            if (i + 1) % 50 == 0 and not args.verbose:
                elapsed = time.time() - t0
                print(f"  [{i + 1}/{len(pairs)}] "
                      f"{(i + 1) / elapsed:.0f} tab/s ...")

    elapsed = time.time() - t0
    n = len(results)

    print(f"\n{'=' * 60}")
    print(f"  RESULTS — {mode}")
    print(f"{'=' * 60}")
    print(f"  Tables: {n} evaluated, {skipped} skipped")
    print(f"  Time: {elapsed:.1f}s ({n / elapsed:.0f} tab/s)")
    print()

    col_exact = sum(r['col_exact'] for r in results)
    col_exact_grid = sum(r.get('col_exact_grid', 0) for r in results)
    col_deltas = Counter(r['col_delta'] for r in results)
    print(f"  COLUMNS:")
    print(f"    Universal (ratio k=0.3): "
          f"{col_exact}/{n} = {100 * col_exact / n:.1f}%")
    print(f"    Grid (legacy):           "
          f"{col_exact_grid}/{n} = {100 * col_exact_grid / n:.1f}%")
    print(f"    Delta distribution: {dict(sorted(col_deltas.items()))}")
    print()

    row_exact = sum(r['row_exact'] for r in results)
    print(f"  ROWS:")
    print(f"    Exact match: {row_exact}/{n} = {100 * row_exact / n:.1f}%")
    print()

    avg_mapped = sum(r['det_mapped'] for r in results) / n
    avg_unmapped = sum(r['det_unmapped'] for r in results) / n
    avg_entities = sum(r['det_entities'] for r in results) / n
    print(f"  FIELD PHI:")
    print(f"    Mean mapped={avg_mapped:.1f}  unmapped={avg_unmapped:.1f}")
    print(f"    Mean entities={avg_entities:.1f}")
    print()

    type_totals = Counter()
    for r in results:
        for t, c in r['types'].items():
            type_totals[t] += c
    total_particles = sum(type_totals.values())
    print(f"  PARTICLE TYPES ({total_particles} total):")
    for t, c in type_totals.most_common():
        print(f"    {t:15s}: {c:>8d} ({100 * c / total_particles:.1f}%)")
    print()

    has_span = [r for r in results if r['has_spanning']]
    no_span = [r for r in results if not r['has_spanning']]
    if has_span and no_span:
        span_acc = sum(r['col_exact'] for r in has_span) / len(has_span)
        nospan_acc = sum(r['col_exact'] for r in no_span) / len(no_span)
        print(f"  SPANNING CELLS:")
        print(f"    With ({len(has_span)}): col_exact={100 * span_acc:.1f}%")
        print(f"    Without ({len(no_span)}): "
              f"col_exact={100 * nospan_acc:.1f}%")


if __name__ == '__main__':
    main()
