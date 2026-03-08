#!/usr/bin/env python3
"""
morph.bench.boundaries — Test diretto del principio percettivo
===============================================================

NON conta righe o colonne. NON traduce in griglia.

Per ogni gap tra particelle consecutive in una riga, classifica:
- Il principio dice: confine o non-confine?
- Il ground truth dice: confine o non-confine?

Misura: precision, recall, F1, accuracy della classificazione binaria.
Questo testa il PRINCIPIO (_natural_threshold), non il TRADUTTORE (count_*).

Uso::

    python -m morph.bench.boundaries --n 1000 --cores 4
    python -m morph.bench.boundaries --n 1000 --axis both
    python -m morph.bench.boundaries --dataset fintabnet --n 1000

Author: Eugeniu Tacu, 2026
"""

import json
import random
import time
from multiprocessing import Pool

from morph.core.sense import (
    _natural_threshold, _group_into_rows, _nn_column_evidence,
    _crystallize_columns,
)
from morph.bench.grid import _group_into_columns
from morph.bench.pubtables import (
    find_pairs as find_pairs_pubtables,
    json_to_particles,
    parse_gt,
)
from morph.bench.grits import find_pairs_fintabnet


# ---------------------------------------------------------------------------
# Dataset HVAC (terzo dominio)
# ---------------------------------------------------------------------------

def find_pairs_hvac(limit: int | None = None) -> list[tuple]:
    """Scopre coppie (JSON, XML) nel dataset HVAC annotato a mano.

    Il dataset vive in /mnt/dati/home/Progetti/dataset/hvac/ con:
      - words/<name>_words.json (particelle PyMuPDF)
      - test/<name>.xml (GT colonne/righe in formato PASCAL-VOC)
    """
    import os
    root = os.environ.get(
        'HVAC_ROOT',
        '/mnt/dati/home/Progetti/dataset/hvac',
    )
    words_dir = os.path.join(root, 'words')
    test_dir = os.path.join(root, 'test')

    if not os.path.isdir(words_dir) or not os.path.isdir(test_dir):
        return []

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

    if limit and limit > 0:
        pairs = pairs[:limit]
    return pairs


# ---------------------------------------------------------------------------
# Classificazione gap: ground truth
# ---------------------------------------------------------------------------

def _assign_gt_column(x: float, gt_columns: list[dict]) -> int:
    """Assegna una particella alla colonna GT piu' vicina (per centro X)."""
    best_col = 0
    best_dist = float('inf')
    for i, col in enumerate(gt_columns):
        cx = (col['xmin'] + col['xmax']) / 2
        d = abs(x - cx)
        if d < best_dist:
            best_dist = d
            best_col = i
    return best_col


def _assign_gt_row(y: float, gt_rows: list[dict]) -> int:
    """Assegna una particella alla riga GT piu' vicina (per centro Y)."""
    best_row = 0
    best_dist = float('inf')
    for i, row in enumerate(gt_rows):
        cy = (row['ymin'] + row['ymax']) / 2
        d = abs(y - cy)
        if d < best_dist:
            best_dist = d
            best_row = i
    return best_row


# ---------------------------------------------------------------------------
# Valutazione singola tabella — asse X (colonne)
# ---------------------------------------------------------------------------

def evaluate_x_boundaries(particles: list[dict],
                          gt: dict,
                          method: str = 'gap') -> dict | None:
    """Testa il principio sui confini colonna (asse X).

    Per ogni riga di particelle:
    1. Calcola i gap tra particelle consecutive
    2. Lancia _natural_threshold → soglia
    3. Per ogni gap: principio dice confine (gap > soglia) o no?
    4. GT dice confine (particelle in colonne diverse) o no?
    5. Conta TP, FP, TN, FN

    Metodi:
    - 'gap': solo gap bimodality (_natural_threshold)
    - 'gap+nn': gap + NN-direction rescue (Docstrum)
    - 'gap+crystal': gap + cristallizzazione verticale (fallback globale)
    """
    gt_cols = gt['columns']
    if len(gt_cols) < 2:
        return None

    rows = _group_into_rows(particles)
    if not rows:
        return None

    use_nn = method == 'gap+nn'
    use_crystal = method == 'gap+crystal'

    # Cristallizzazione: calcola una volta per tutta la tabella
    crystal_bounds = None
    if use_crystal:
        crystal_bounds = _crystallize_columns(particles)

    tp = fp = tn = fn = 0
    total_gaps = 0

    for row in rows:
        if len(row) < 2:
            continue

        ps = sorted(row, key=lambda p: p['x0'])
        gaps = []
        gap_meta = []  # (gap_value, particle_left, particle_right)

        for i in range(len(ps) - 1):
            g = ps[i + 1]['x0'] - ps[i]['x1']
            gaps.append(g)
            gap_meta.append((g, ps[i], ps[i + 1]))

        pos_gaps = [g for g in gaps if g > 0]

        # Il principio: trova la soglia naturale
        if len(pos_gaps) >= 3:
            threshold = _natural_threshold(pos_gaps)
            # Se nessun break bimodale, il principio dice "nessun confine"
            no_bimodality = threshold > max(pos_gaps)
            if no_bimodality:
                threshold = float('inf')
        elif len(pos_gaps) >= 1:
            # Troppo pochi gap: il principio non puo' decidere
            # → skip questa riga (non penalizzare ne' premiare)
            continue
        else:
            continue

        # NN evidence (solo se richiesto e soglia non ha trovato break)
        nn_ev = None
        if use_nn and no_bimodality and len(ps) >= 2:
            nn_ev = _nn_column_evidence(ps, particles)
            # Lateral inhibition: NN rescue solo se almeno meta'
            # dei gap mostra evidenza (segnale isolato = rumore)
            if nn_ev and sum(nn_ev) < len(nn_ev) * 0.5:
                nn_ev = None

        # Classifica ogni gap
        for idx, (g, p_left, p_right) in enumerate(gap_meta):
            total_gaps += 1

            # GT: particelle in colonne diverse?
            col_left = _assign_gt_column(p_left['x'], gt_cols)
            col_right = _assign_gt_column(p_right['x'], gt_cols)
            gt_boundary = col_left != col_right

            # Principio primario: gap sopra soglia?
            pred_boundary = g > threshold

            # NN rescue: quando gap-threshold non trova break,
            # NN-direction puo' salvare i FN (tabelle equispaziate)
            if not pred_boundary and nn_ev is not None and g > 1.0:
                if idx < len(nn_ev) and nn_ev[idx]:
                    pred_boundary = True

            # Crystal rescue: quando gap-threshold non trova break,
            # l'allineamento verticale globale rivela le colonne
            if not pred_boundary and crystal_bounds and no_bimodality:
                for cb in crystal_bounds:
                    if p_left['x1'] < cb < p_right['x0']:
                        pred_boundary = True
                        break

            if gt_boundary and pred_boundary:
                tp += 1
            elif gt_boundary and not pred_boundary:
                fn += 1
            elif not gt_boundary and pred_boundary:
                fp += 1
            else:
                tn += 1

    if total_gaps == 0:
        return None

    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn, 'total': total_gaps}


# ---------------------------------------------------------------------------
# Valutazione singola tabella — asse Y (righe)
# ---------------------------------------------------------------------------

def evaluate_y_boundaries(particles: list[dict],
                          gt: dict) -> dict | None:
    """Testa il principio sui confini riga (asse Y).

    Simmetrico a evaluate_x_boundaries ma sull'asse verticale.
    Per ogni colonna di particelle, classifica i gap Y.
    """
    gt_rows = gt['rows']
    if len(gt_rows) < 2:
        return None

    cols = _group_into_columns(particles)
    if not cols:
        return None

    tp = fp = tn = fn = 0
    total_gaps = 0

    for col in cols:
        if len(col) < 2:
            continue

        ps = sorted(col, key=lambda p: p['y0'])
        gaps = []
        gap_meta = []

        for i in range(len(ps) - 1):
            g = ps[i + 1]['y0'] - ps[i]['y1']
            gaps.append(g)
            gap_meta.append((g, ps[i], ps[i + 1]))

        pos_gaps = [g for g in gaps if g > 0]

        if len(pos_gaps) >= 3:
            threshold = _natural_threshold(pos_gaps)
            if threshold > max(pos_gaps):
                threshold = float('inf')
        elif len(pos_gaps) >= 1:
            continue
        else:
            continue

        for g, p_top, p_bottom in gap_meta:
            total_gaps += 1

            row_top = _assign_gt_row(p_top['y'], gt_rows)
            row_bottom = _assign_gt_row(p_bottom['y'], gt_rows)
            gt_boundary = row_top != row_bottom

            pred_boundary = g > threshold

            if gt_boundary and pred_boundary:
                tp += 1
            elif gt_boundary and not pred_boundary:
                fn += 1
            elif not gt_boundary and pred_boundary:
                fp += 1
            else:
                tn += 1

    if total_gaps == 0:
        return None

    return {'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn, 'total': total_gaps}


# ---------------------------------------------------------------------------
# Worker per una tabella
# ---------------------------------------------------------------------------

_WORKER_AXIS = 'x'
_WORKER_METHOD = 'gap'


def evaluate_table(json_path: str, xml_path: str,
                   axis: str = 'x',
                   method: str = 'gap') -> dict | None:
    """Pipeline: particelle → principio → classificazione gap."""
    with open(json_path) as f:
        words = json.load(f)

    gt = parse_gt(xml_path)
    if not gt['columns'] or not gt['rows']:
        return None

    if len(gt['rows']) > 50 or len(gt['columns']) > 30:
        return None

    particles = json_to_particles(words, domain=False)
    if len(particles) < 3:
        return None

    if axis == 'x':
        return evaluate_x_boundaries(particles, gt, method=method)
    elif axis == 'y':
        return evaluate_y_boundaries(particles, gt)
    else:
        # both: combina i conteggi
        rx = evaluate_x_boundaries(particles, gt, method=method)
        ry = evaluate_y_boundaries(particles, gt)
        if rx is None and ry is None:
            return None
        result = {'tp': 0, 'fp': 0, 'tn': 0, 'fn': 0, 'total': 0}
        for r in (rx, ry):
            if r:
                for k in result:
                    result[k] += r[k]
        return result if result['total'] > 0 else None


def _eval_worker(args):
    json_path, xml_path = args
    return evaluate_table(json_path, xml_path,
                          axis=_WORKER_AXIS, method=_WORKER_METHOD)


def _init_worker(axis, method='gap'):
    global _WORKER_AXIS, _WORKER_METHOD
    _WORKER_AXIS = axis
    _WORKER_METHOD = method


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def print_report(results: list[dict], label: str, axis: str):
    """Stampa metriche di classificazione binaria dei confini."""
    tp = sum(r['tp'] for r in results)
    fp = sum(r['fp'] for r in results)
    tn = sum(r['tn'] for r in results)
    fn = sum(r['fn'] for r in results)
    total = sum(r['total'] for r in results)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / total if total > 0 else 0.0

    axis_label = {'x': 'colonne (X)', 'y': 'righe (Y)', 'both': 'entrambi'}

    print(f"\n{'=' * 65}")
    print(f"  TEST DEL PRINCIPIO — {label}")
    print(f"  Asse: {axis_label.get(axis, axis)}")
    print(f"  Domanda: per ogni gap, il principio lo classifica correttamente?")
    print(f"{'=' * 65}")
    print(f"  Tabelle valutate: {len(results)}")
    print(f"  Gap totali classificati: {total:,}")
    print()
    print(f"  MATRICE DI CONFUSIONE:")
    print(f"                        Principio: SI    Principio: NO")
    print(f"    GT confine:       TP={tp:>7,}        FN={fn:>7,}")
    print(f"    GT non-confine:   FP={fp:>7,}        TN={tn:>7,}")
    print()
    print(f"  METRICHE:")
    print(f"    Precision:  {precision:.4f}  (dei confini trovati, quanti sono veri?)")
    print(f"    Recall:     {recall:.4f}  (dei confini veri, quanti trovati?)")
    print(f"    F1:         {f1:.4f}")
    print(f"    Accuracy:   {accuracy:.4f}  (gap classificati correttamente)")
    print()

    # Breakdown: quanti errori sono "troppi confini" vs "pochi confini"?
    if fp + fn > 0:
        print(f"  ERRORI:")
        print(f"    Troppi confini (FP):  {fp:>7,}  ({100*fp/(fp+fn):.1f}% degli errori)")
        print(f"    Pochi confini (FN):   {fn:>7,}  ({100*fn/(fp+fn):.1f}% degli errori)")
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Test diretto del principio percettivo sui confini',
    )
    parser.add_argument('--n', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cores', type=int, default=4)
    parser.add_argument('--axis', choices=['x', 'y', 'both'], default='x',
                        help='Asse da testare: x (colonne), y (righe), both')
    parser.add_argument('--dataset',
                        choices=['pubtables', 'fintabnet', 'hvac', 'both', 'all'],
                        default='pubtables')
    parser.add_argument('--method',
                        choices=['gap', 'gap+nn', 'gap+crystal'],
                        default='gap',
                        help='Metodo: gap (solo soglia), gap+nn (soglia + NN direction)')
    args = parser.parse_args()

    random.seed(args.seed)

    axis_label = {'x': 'colonne (X)', 'y': 'righe (Y)', 'both': 'entrambi'}
    print(f"\n{'=' * 65}")
    print(f"  Test del Principio Percettivo (_natural_threshold)")
    print(f"  Ogni gap → confine si/no → confronto con ground truth")
    method_label = {'gap': 'gap-only', 'gap+nn': 'gap + NN direction',
                        'gap+crystal': 'gap + crystallization'}
    print(f"  Asse: {axis_label[args.axis]}  N={args.n}  seed={args.seed}  cores={args.cores}")
    print(f"  Metodo: {method_label[args.method]}")
    print(f"{'=' * 65}")

    datasets = []
    if args.dataset in ('pubtables', 'both', 'all'):
        datasets.append(('PubTables-1M', find_pairs_pubtables))
    if args.dataset in ('fintabnet', 'both', 'all'):
        datasets.append(('FinTabNet', find_pairs_fintabnet))
    if args.dataset in ('hvac', 'all'):
        datasets.append(('HVAC', find_pairs_hvac))

    for ds_name, find_fn in datasets:
        random.seed(args.seed)
        pairs = find_fn(limit=args.n)
        print(f"\n  {ds_name}: {len(pairs)} tabelle ...")

        results = []
        skipped = 0
        t0 = time.time()

        if args.cores > 1:
            work = [(j, x) for j, x in pairs]
            with Pool(
                args.cores,
                initializer=_init_worker,
                initargs=(args.axis, args.method),
            ) as pool:
                for r in pool.imap_unordered(_eval_worker, work, chunksize=64):
                    if r is None:
                        skipped += 1
                    else:
                        results.append(r)
        else:
            for json_path, xml_path in pairs:
                r = evaluate_table(json_path, xml_path,
                                   axis=args.axis, method=args.method)
                if r is None:
                    skipped += 1
                else:
                    results.append(r)

        elapsed = time.time() - t0
        print(f"  Tempo: {elapsed:.1f}s ({len(results)/elapsed:.0f} tab/s), "
              f"{skipped} skipped")

        if results:
            print_report(results, ds_name, args.axis)

    # Cross-domain se entrambi
    if args.dataset == 'both' and len(datasets) == 2:
        print(f"\n{'=' * 65}")
        print(f"  Il principio e' universale? Stesse metriche su domini diversi = SI")
        print(f"{'=' * 65}\n")


if __name__ == '__main__':
    main()
