#!/usr/bin/env python3
"""
morph.bench.sroie — SROIE Receipt Benchmark Adapter
=====================================================

Converts SROIE (ICDAR 2019 Scanned Receipts) annotations into
Morph particles and evaluates key information extraction.

SROIE structure: each receipt has a box CSV (word bboxes + transcripts)
and a key JSON with 4 GT fields: company, address, date, total.

Unlike CORD (digital receipts) SROIE uses scanned images with noisy
OCR coordinates.  This tests whether the field principle degrades
with coordinate noise.

The most comparable metric to CORD is ``total`` recall: can the field
bond the total amount to a label?

Dataset::

    <SROIE_ROOT>/
        repo/data/
            box/*.csv    — word-level OCR (x1,y1,...,x4,y4,transcript)
            key/*.json   — GT: {company, address, date, total}
            img/*.jpg    — scanned images (not used)

Usage::

    python -m morph.bench.sroie
    python -m morph.bench.sroie --n 100 --verbose

Author: Eugeniu Tacu, 2026
"""

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

from morph.core import typify_word, sense_page, extract_page

# Default dataset path — override with SROIE_ROOT env var
DATASET = Path(
    os.environ.get(
        'SROIE_ROOT',
        '/mnt/dati/home/Progetti/dataset/sroie',
    )
)


# ---------------------------------------------------------------------------
# Parser: SROIE box CSV → words
# ---------------------------------------------------------------------------

def _parse_box_csv(path: Path) -> list[dict]:
    """Parsa un file box CSV SROIE.

    Formato: x1,y1,x2,y2,x3,y3,x4,y4,transcript
    (4 vertici clockwise dal top-left, poi testo).

    Returns:
        Lista di dict: {text, x0, y0, x1, y1} (bbox rettangolare).
    """
    words = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # 8 coordinate separate da virgola, poi il testo (che puo' contenere virgole)
            parts = line.split(',', 8)
            if len(parts) < 9:
                continue

            try:
                coords = [int(p) for p in parts[:8]]
            except ValueError:
                continue

            text = parts[8].strip()
            if not text:
                continue

            # Quad → bbox rettangolare
            xs = coords[0::2]  # x1, x2, x3, x4
            ys = coords[1::2]  # y1, y2, y3, y4
            x0, x1 = min(xs), max(xs)
            y0, y1 = min(ys), max(ys)

            if x1 <= x0 or y1 <= y0:
                continue

            words.append({
                'text': text,
                'x0': x0, 'y0': y0,
                'x1': x1, 'y1': y1,
            })

    return words


# ---------------------------------------------------------------------------
# Adapter: SROIE words → Morph particles
# ---------------------------------------------------------------------------

def sroie_to_particles(words: list[dict]) -> list[dict]:
    """Converte words SROIE in particelle Morph.

    Returns:
        Lista di particelle con chiavi standard Morph.
    """
    particles = []
    for w in words:
        ptype = typify_word(w['text'], domain=False)
        particles.append({
            'text': w['text'][:80],
            'x': (w['x0'] + w['x1']) / 2,
            'y': (w['y0'] + w['y1']) / 2,
            'x0': w['x0'], 'x1': w['x1'],
            'y0': w['y0'], 'y1': w['y1'],
            'type': ptype,
            'size': max(1.0, w['y1'] - w['y0']),
        })
    return particles


# ---------------------------------------------------------------------------
# GT matching: trova le parole che corrispondono ai campi GT
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalizza testo per matching (lowercase, strip punteggiatura ai bordi)."""
    return re.sub(r'[^\w\s.]', '', text.lower()).strip()


def _find_total_words(words: list[dict], gt_total: str) -> list[int]:
    """Trova gli indici delle parole che contengono il valore total GT.

    Strategia: cerca match esatto numerico nel testo della parola.
    """
    if not gt_total:
        return []

    gt_num = _normalize(gt_total)
    indices = []

    for i, w in enumerate(words):
        w_text = _normalize(w['text'])
        if w_text == gt_num:
            indices.append(i)

    return indices


def _find_date_words(words: list[dict], gt_date: str) -> list[int]:
    """Trova le parole che contengono la data GT.

    La data puo' essere in una sola parola o spezzata (es. "25/12/2018").
    """
    if not gt_date:
        return []

    gt_norm = _normalize(gt_date)
    indices = []

    for i, w in enumerate(words):
        w_norm = _normalize(w['text'])
        # Match esatto o contenuto
        if w_norm == gt_norm or gt_norm in w_norm or w_norm in gt_norm:
            if len(w_norm) >= 4:  # evita match su "1" singoli
                indices.append(i)

    return indices


def _find_text_words(words: list[dict], gt_text: str) -> list[int]:
    """Trova le parole che compongono un campo testuale GT (company/address).

    Strategia: ogni parola GT di 3+ caratteri viene cercata nelle parole
    della ricevuta.
    """
    if not gt_text:
        return []

    gt_tokens = set()
    for token in gt_text.split():
        norm = _normalize(token)
        if len(norm) >= 3:
            gt_tokens.add(norm)

    if not gt_tokens:
        return []

    indices = []
    for i, w in enumerate(words):
        w_norm = _normalize(w['text'])
        if w_norm in gt_tokens and len(w_norm) >= 3:
            indices.append(i)

    return indices


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_receipt(words: list[dict], gt_keys: dict) -> dict:
    """Valuta Morph su una singola ricevuta SROIE.

    Per ogni campo GT (company, address, date, total):
    1. Trova le parole corrispondenti nella ricevuta
    2. Controlla se il campo Morph le ha bondate

    Livelli:
    - **Presence**: almeno una parola del campo GT e' bondata dal campo
    - **Reachable**: almeno una parola del campo GT e' NUMERIC (il campo
      puo' vederla)

    Returns:
        Dict con metriche per campo.
    """
    particles = sroie_to_particles(words)
    if len(particles) < 2:
        return {'skip': True, 'reason': 'too_few_particles'}

    # Pipeline Morph
    sense_result = sense_page(particles)
    sensed = sense_result['particles']
    field_result = extract_page(sensed)

    # Positions of bonded particles
    bonded_positions = set()
    for entity_text, specs in field_result['data'].items():
        for spec_text, info in specs.items():
            bonded_positions.add((round(info['x'], 1), round(info['y'], 1)))

    # Mappa posizione → tipo (per diagnostica)
    pos_to_type = {}
    for p in particles:
        pos_to_type[(round(p['x'], 1), round(p['y'], 1))] = p['type']

    # Per ogni campo GT, trova words e valuta
    results = {}
    total_tp = total_fn = total_fp = 0
    total_bonded = len(bonded_positions)

    finders = {
        'total': _find_total_words,
        'date': _find_date_words,
        'company': _find_text_words,
        'address': _find_text_words,
    }

    for field in ['company', 'date', 'address', 'total']:
        gt_value = gt_keys.get(field, '')
        if not gt_value:
            results[field] = {'gt': '', 'matched_words': 0, 'present': False,
                              'reachable': False, 'has_numeric': False}
            continue

        # Trova indici parole corrispondenti
        finder = finders[field]
        word_indices = finder(words, gt_value)

        if not word_indices:
            results[field] = {
                'gt': gt_value[:50], 'matched_words': 0,
                'present': False, 'reachable': False, 'has_numeric': False,
            }
            total_fn += 1
            continue

        # Controlla se almeno una parola ha tipo NUMERIC
        has_numeric = any(
            particles[i]['type'] == 'NUMERIC' for i in word_indices
        )

        # Controlla se almeno una parola e' bondata
        present = False
        for i in word_indices:
            p = particles[i]
            pkey = (round(p['x'], 1), round(p['y'], 1))
            if pkey in bonded_positions:
                present = True
                break

        if present:
            total_tp += 1
        else:
            total_fn += 1

        results[field] = {
            'gt': gt_value[:50],
            'matched_words': len(word_indices),
            'present': present,
            'reachable': has_numeric,
            'has_numeric': has_numeric,
        }

    # FP: bonds che non corrispondono a nessun campo GT
    gt_positions = set()
    for field in ['company', 'date', 'address', 'total']:
        gt_value = gt_keys.get(field, '')
        if not gt_value:
            continue
        finder = finders[field]
        for i in finder(words, gt_value):
            p = particles[i]
            gt_positions.add((round(p['x'], 1), round(p['y'], 1)))

    fp = sum(1 for pos in bonded_positions if pos not in gt_positions)

    # Distribuzione tipi
    type_counts = defaultdict(int)
    for p in particles:
        type_counts[p['type']] += 1

    return {
        'skip': False,
        'fields': results,
        'tp': total_tp, 'fn': total_fn, 'fp': fp,
        'n_particles': len(particles),
        'n_morph_bonds': total_bonded,
        'type_counts': dict(type_counts),
    }


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def find_receipts() -> list[tuple[Path, Path]]:
    """Trova tutte le coppie (box, key) in SROIE.

    Returns:
        Lista di (box_path, key_path).
    """
    box_dir = DATASET / 'repo' / 'data' / 'box'
    key_dir = DATASET / 'repo' / 'data' / 'key'

    if not box_dir.exists():
        raise FileNotFoundError(f"SROIE box not found: {box_dir}")

    pairs = []
    for box_path in sorted(box_dir.glob('*.csv')):
        key_path = key_dir / (box_path.stem + '.json')
        if key_path.exists():
            pairs.append((box_path, key_path))

    return pairs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run SROIE benchmark."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Morph benchmark on SROIE scanned receipts',
    )
    parser.add_argument(
        '--n', type=int, default=0,
        help='Max ricevute (0 = tutte)',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Stampa dettagli per ricevuta',
    )
    args = parser.parse_args()

    pairs = find_receipts()
    if args.n > 0:
        pairs = pairs[:args.n]

    print(f"SROIE Benchmark — {len(pairs)} ricevute scansionate")
    print("=" * 60)

    t0 = time.time()
    skipped = 0
    results = []
    totals = {'tp': 0, 'fn': 0, 'fp': 0}
    field_stats = defaultdict(lambda: {
        'present': 0, 'absent': 0, 'reachable': 0,
        'unreachable': 0, 'no_match': 0,
    })
    total_type_counts = defaultdict(int)

    for box_path, key_path in pairs:
        words = _parse_box_csv(box_path)
        with open(key_path) as f:
            gt_keys = json.load(f)

        r = evaluate_receipt(words, gt_keys)
        if r.get('skip'):
            skipped += 1
            continue

        results.append(r)
        totals['tp'] += r['tp']
        totals['fn'] += r['fn']
        totals['fp'] += r['fp']

        for field, info in r['fields'].items():
            gt_value = gt_keys.get(field, '')
            if not gt_value:
                continue

            if info['matched_words'] == 0:
                field_stats[field]['no_match'] += 1
                field_stats[field]['absent'] += 1
            elif info['present']:
                field_stats[field]['present'] += 1
            else:
                field_stats[field]['absent'] += 1

            if info.get('has_numeric'):
                field_stats[field]['reachable'] += 1
            else:
                field_stats[field]['unreachable'] += 1

        for t, c in r['type_counts'].items():
            total_type_counts[t] += c

        if args.verbose:
            fields_str = ' '.join(
                f"{k}={'OK' if v['present'] else 'NO'}"
                for k, v in r['fields'].items()
                if gt_keys.get(k, '')
            )
            print(f"  {box_path.stem}: {fields_str} "
                  f"bonds={r['n_morph_bonds']}")

    elapsed = time.time() - t0

    if not results:
        print("Nessun risultato!")
        return

    def _f1(tp, fp_, fn):
        p = tp / (tp + fp_) if (tp + fp_) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f

    print(f"\nCompletato: {len(results)} ricevute, {skipped} skipped, {elapsed:.1f}s")
    print(f"Velocita': {len(results)/elapsed:.0f} ricevute/s")
    print()

    # --- Risultati per campo ---
    print("=" * 70)
    print("RISULTATI PER CAMPO")
    print("=" * 70)
    print(f"  {'Campo':>10} {'Present':>8} {'Absent':>8} {'NoMatch':>8} "
          f"{'Reach':>8} {'Unreach':>8} {'Recall':>8}")
    print(f"  {'-'*65}")

    for field in ['company', 'date', 'address', 'total']:
        s = field_stats[field]
        total_f = s['present'] + s['absent']
        recall = s['present'] / total_f if total_f > 0 else 0.0
        print(f"  {field:>10} {s['present']:>8} {s['absent']:>8} "
              f"{s['no_match']:>8} {s['reachable']:>8} "
              f"{s['unreachable']:>8} {recall:>7.1%}")

    # --- Macro F1 ---
    print()
    tp, fn, fp = totals['tp'], totals['fn'], totals['fp']
    p, r, f = _f1(tp, fp, fn)
    print(f"  Macro (tutti i campi): P={p:.1%}  R={r:.1%}  F1={f:.1%}")
    print(f"  TP={tp}  FP={fp}  FN={fn}")

    # Confronto con CORD
    print()
    total_s = field_stats['total']
    total_total = total_s['present'] + total_s['absent']
    total_recall = total_s['present'] / total_total if total_total > 0 else 0
    print(f"  --- Confronto con CORD ---")
    print(f"  SROIE total recall: {total_recall:.1%} "
          f"(vs CORD total: 61.0%)")

    # --- Distribuzione tipi ---
    print()
    print("=" * 70)
    print("DISTRIBUZIONE TIPI PARTICELLA")
    print("=" * 70)
    total_p = sum(total_type_counts.values())
    for t in sorted(total_type_counts.keys()):
        c = total_type_counts[t]
        print(f"  {t:>15}: {c:>6} ({c/total_p*100:>5.1f}%)")

    # --- Statistiche ---
    avg_particles = sum(r['n_particles'] for r in results) / len(results)
    avg_morph = sum(r['n_morph_bonds'] for r in results) / len(results)

    print()
    print("=" * 70)
    print("STATISTICHE")
    print("=" * 70)
    print(f"  Particelle/ricevuta (media): {avg_particles:.1f}")
    print(f"  Bond Morph/ricevuta (media): {avg_morph:.1f}")


if __name__ == '__main__':
    main()
