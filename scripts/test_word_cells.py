#!/usr/bin/env python3
"""
Livello 2: test contenuto celle — ogni parola nella cella giusta?

Per ogni tabella HVAC:
1. Carica words (text + bbox) e GT (colonne + righe)
2. Assegna ogni parola alla cella GT (row, col) per posizione centro
3. Raggruppa in righe Morph, applica _natural_threshold per colonne
4. Per ogni coppia di parole adiacenti sulla stessa riga:
   - GT dice: stessa cella o cella diversa?
   - Morph dice: stessa cella o cella diversa?
   → TP/FP/TN/FN

Questo è il test definitivo: "bianco" e "52" finiscono separati o uniti?

Uso:
    python -m scripts.test_word_cells [--n 100] [--show 5] [--verbose]
"""

import json
import sys
import os
import argparse
from pathlib import Path

# Assicurati che morph sia importabile
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morph.core.sense import _natural_threshold, _group_into_rows
from morph.bench.boundaries import (
    find_pairs_hvac,
    _assign_gt_column,
    _assign_gt_row,
)
from morph.bench.pubtables import parse_gt


def load_hvac_words(json_path: str) -> list[dict]:
    """Carica parole dal JSON HVAC e converte in formato particella."""
    with open(json_path) as f:
        raw = json.load(f)
    particles = []
    for w in raw:
        b = w['bbox']
        particles.append({
            'text': w['text'],
            'x0': b[0], 'y0': b[1], 'x1': b[2], 'y1': b[3],
            'x': (b[0] + b[2]) / 2,
            'y': (b[1] + b[3]) / 2,
            'w': b[2] - b[0],
            'h': b[3] - b[1],
            'size': 10.0,
            'type': 'UNKNOWN',
        })
    return particles


def evaluate_word_placement(particles: list[dict], gt: dict,
                            verbose: bool = False) -> dict | None:
    """Test Livello 2: per ogni parola, la cella e' corretta?

    Approccio: per ogni coppia adiacente sulla stessa riga Morph,
    confronta se GT e Morph concordano su "stessa cella / cella diversa".

    Return dict con TP/FP/TN/FN + lista errori dettagliati.
    """
    gt_cols = gt.get('columns', [])
    gt_rows = gt.get('rows', [])

    if len(gt_cols) < 2:
        return None

    # Step 1: assegna GT column a ogni particella
    for p in particles:
        p['_gt_col'] = _assign_gt_column(p['x'], gt_cols)
        p['_gt_row'] = _assign_gt_row(p['y'], gt_rows) if gt_rows else 0

    # Step 2: raggruppa in righe Morph
    rows = _group_into_rows(particles)
    if not rows:
        return None

    tp = fp = tn = fn = 0
    errors = []
    total_words = sum(len(r) for r in rows)

    for row in rows:
        if len(row) < 2:
            continue

        ps = sorted(row, key=lambda p: p['x0'])

        # Calcola gaps
        gaps = []
        for i in range(len(ps) - 1):
            gaps.append(ps[i + 1]['x0'] - ps[i]['x1'])

        pos_gaps = [g for g in gaps if g > 0]

        # Soglia naturale
        if len(pos_gaps) >= 3:
            threshold = _natural_threshold(pos_gaps)
            if threshold > max(pos_gaps):
                threshold = float('inf')
        else:
            threshold = float('inf')

        # Per ogni coppia adiacente
        for i in range(len(ps) - 1):
            left = ps[i]
            right = ps[i + 1]
            g = gaps[i]

            gt_boundary = left['_gt_col'] != right['_gt_col']
            morph_boundary = g > threshold

            if gt_boundary and morph_boundary:
                tp += 1
            elif gt_boundary and not morph_boundary:
                fn += 1
                if verbose:
                    errors.append({
                        'type': 'FN',
                        'left': left['text'],
                        'right': right['text'],
                        'gap': round(g, 1),
                        'threshold': round(threshold, 1) if threshold != float('inf') else 'inf',
                        'gt_cols': (left['_gt_col'], right['_gt_col']),
                    })
            elif not gt_boundary and morph_boundary:
                fp += 1
                if verbose:
                    errors.append({
                        'type': 'FP',
                        'left': left['text'],
                        'right': right['text'],
                        'gap': round(g, 1),
                        'threshold': round(threshold, 1) if threshold != float('inf') else 'inf',
                        'gt_cols': (left['_gt_col'], right['_gt_col']),
                    })
            else:
                tn += 1

    total = tp + fp + tn + fn
    if total == 0:
        return None

    return {
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'total_pairs': total,
        'total_words': total_words,
        'errors': errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Livello 2: ogni parola nella cella giusta?')
    parser.add_argument('--n', type=int, default=0,
                        help='Numero tabelle (0=tutte)')
    parser.add_argument('--show', type=int, default=3,
                        help='Mostra dettaglio per N tabelle con errori')
    parser.add_argument('--verbose', action='store_true',
                        help='Stampa ogni errore')
    args = parser.parse_args()

    pairs = find_pairs_hvac(args.n if args.n > 0 else None)
    if not pairs:
        print("ERRORE: dataset HVAC non trovato")
        sys.exit(1)

    print(f"{'='*70}")
    print(f"  LIVELLO 2: Ogni parola nella cella giusta?")
    print(f"  Dataset HVAC — {len(pairs)} tabelle")
    print(f"{'='*70}\n")

    # Accumula metriche globali
    g_tp = g_fp = g_tn = g_fn = 0
    g_words = 0
    n_ok = 0
    n_err = 0
    n_skip = 0
    worst_tables = []  # (accuracy, name, errors)

    for json_path, xml_path in pairs:
        name = Path(json_path).stem.replace('_words', '')
        particles = load_hvac_words(json_path)
        gt = parse_gt(xml_path)

        result = evaluate_word_placement(particles, gt, verbose=args.show > 0)

        if result is None:
            n_skip += 1
            continue

        g_tp += result['tp']
        g_fp += result['fp']
        g_tn += result['tn']
        g_fn += result['fn']
        g_words += result['total_words']

        total = result['total_pairs']
        correct = result['tp'] + result['tn']
        acc = correct / total if total > 0 else 1.0

        if result['fp'] + result['fn'] > 0:
            n_err += 1
            worst_tables.append((acc, name, result.get('errors', []),
                                 result['fp'], result['fn'], total))
        else:
            n_ok += 1

    # Metriche globali
    total_pairs = g_tp + g_fp + g_tn + g_fn
    if total_pairs == 0:
        print("Nessun dato da valutare!")
        return

    precision = g_tp / (g_tp + g_fp) if (g_tp + g_fp) > 0 else 0
    recall = g_tp / (g_tp + g_fn) if (g_tp + g_fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (g_tp + g_tn) / total_pairs

    print(f"{'='*70}")
    print(f"  RISULTATO — LIVELLO 2: Parola nella cella giusta?")
    print(f"{'='*70}")
    print(f"  Tabelle valutate: {n_ok + n_err} ({n_skip} skipped)")
    print(f"  Tabelle perfette (0 errori): {n_ok} ({100*n_ok/(n_ok+n_err):.1f}%)")
    print(f"  Tabelle con errori: {n_err}")
    print(f"  Parole totali: {g_words:,}")
    print(f"  Coppie adiacenti valutate: {total_pairs:,}")
    print()
    print(f"  MATRICE DI CONFUSIONE:")
    print(f"  {'':20s} Morph: cella diversa  Morph: stessa cella")
    print(f"  GT cella diversa:  TP={g_tp:>8,}          FN={g_fn:>8,}")
    print(f"  GT stessa cella:   FP={g_fp:>8,}          TN={g_tn:>8,}")
    print()
    print(f"  METRICHE:")
    print(f"    Precision:  {precision:.4f}  (quando Morph separa, ha ragione?)")
    print(f"    Recall:     {recall:.4f}  (dei confini veri, quanti trovati?)")
    print(f"    F1:         {f1:.4f}")
    print(f"    Accuracy:   {accuracy:.4f}  (coppie classificate correttamente)")
    print()
    print(f"  IN PAROLE SEMPLICI:")
    print(f"    Su {total_pairs:,} coppie di parole adiacenti:")
    print(f"    - {g_tp+g_tn:,} ({100*accuracy:.1f}%) → Morph concorda con GT")
    print(f"    - {g_fp:,} ({100*g_fp/total_pairs:.1f}%) → Morph separa ma non dovrebbe (FP)")
    print(f"    - {g_fn:,} ({100*g_fn/total_pairs:.1f}%) → Morph non separa ma dovrebbe (FN)")
    print()

    # Mostra tabelle peggiori
    if args.show > 0 and worst_tables:
        worst_tables.sort(key=lambda t: t[0])
        print(f"\n  {'='*70}")
        print(f"  TABELLE CON PIU' ERRORI (top {min(args.show, len(worst_tables))})")
        print(f"  {'='*70}")
        for acc, name, errs, n_fp, n_fn, total in worst_tables[:args.show]:
            print(f"\n  {name}")
            print(f"  Accuracy: {100*acc:.1f}% | FP={n_fp} FN={n_fn} / {total} coppie")
            if errs:
                for e in errs[:10]:  # max 10 errori per tabella
                    tag = "SEPARA-TROPPO" if e['type'] == 'FP' else "NON-SEPARA"
                    print(f"    [{tag}] '{e['left']}' | '{e['right']}' "
                          f"gap={e['gap']}px thr={e['threshold']} "
                          f"GT-col=({e['gt_cols'][0]},{e['gt_cols'][1]})")


if __name__ == '__main__':
    main()
