#!/usr/bin/env python3
"""
morph.bench.funsd — FUNSD Form Understanding Benchmark Adapter
===============================================================

Converts FUNSD (Form Understanding in Noisy Scanned Documents) annotations
into Morph particles and evaluates entity-linking F1 using field bonds.

FUNSD structure: each form has ``entities`` with label (question/answer/
header/other), words with bboxes, and ``linking`` pairs ``[from_id, to_id]``
that connect question entities to answer entities.

The key challenge: FUNSD bonds are TEXT→TEXT (question→answer).
Morph's field only bonds NUMERIC→SPEC_LABEL/MODEL.  This benchmark
measures the baseline — how much the field sees without extending W.

Dataset::

    <FUNSD_ROOT>/
        dataset/
            testing_data/annotations/*.json   (50 forms)
            training_data/annotations/*.json  (149 forms)

Usage::

    python -m morph.bench.funsd --split test
    python -m morph.bench.funsd --split train

Author: Eugeniu Tacu, 2026
"""

import json
import os
import time
from collections import defaultdict
from pathlib import Path

from morph.core import typify_word, sense_page, extract_page

# Default dataset path — override with FUNSD_ROOT env var
DATASET = Path(
    os.environ.get(
        'FUNSD_ROOT',
        '/mnt/dati/home/Progetti/dataset/funsd',
    )
)


# ---------------------------------------------------------------------------
# Adapter: FUNSD JSON → Morph particles
# ---------------------------------------------------------------------------

def funsd_to_particles(form_data: dict) -> list[dict]:
    """Converte annotazioni FUNSD in particelle Morph.

    Ogni word in ogni entita' diventa una particella.
    Box FUNSD: [x0, y0, x1, y1] (gia' rettangolare).

    Returns:
        Lista di particelle con chiavi: text, x, y, x0, y0, x1, y1,
        type, size, _funsd_entity_id, _funsd_label.
    """
    particles = []

    for entity in form_data.get('form', []):
        entity_id = entity['id']
        label = entity.get('label', 'other')

        for word in entity.get('words', []):
            text = word.get('text', '').strip()
            if not text:
                continue

            box = word['box']  # [x0, y0, x1, y1]
            x0, y0, x1, y1 = box

            # Scarta bbox degeneri
            if x1 <= x0 or y1 <= y0:
                continue

            ptype = typify_word(text, domain=False)

            particles.append({
                'text': text[:80],
                'x': (x0 + x1) / 2,
                'y': (y0 + y1) / 2,
                'x0': x0, 'x1': x1,
                'y0': y0, 'y1': y1,
                'type': ptype,
                'size': max(1.0, y1 - y0),
                # Metadati FUNSD per valutazione
                '_funsd_entity_id': entity_id,
                '_funsd_label': label,
            })

    return particles


# ---------------------------------------------------------------------------
# Ground truth parser
# ---------------------------------------------------------------------------

def parse_funsd_gt(form_data: dict) -> list[dict]:
    """Estrae i link GT dal JSON FUNSD.

    Un link GT e' una coppia [from_id, to_id] nel campo ``linking``.
    Ogni link appare in entrambe le entita' coinvolte — deduplicazione
    per (min_id, max_id).

    Returns:
        Lista di dict: {from_id, to_id, from_label, to_label,
        from_text, to_text}
    """
    entities = form_data.get('form', [])

    # Indice entita' per id
    id_to_entity = {}
    for e in entities:
        id_to_entity[e['id']] = e

    # Raccogli link unici
    seen = set()
    links = []

    for e in entities:
        for link in e.get('linking', []):
            from_id, to_id = link
            key = (min(from_id, to_id), max(from_id, to_id))
            if key in seen:
                continue
            seen.add(key)

            from_e = id_to_entity.get(from_id)
            to_e = id_to_entity.get(to_id)
            if not from_e or not to_e:
                continue

            links.append({
                'from_id': from_id,
                'to_id': to_id,
                'from_label': from_e.get('label', 'other'),
                'to_label': to_e.get('label', 'other'),
                'from_text': from_e.get('text', ''),
                'to_text': to_e.get('text', ''),
            })

    return links


# ---------------------------------------------------------------------------
# Evaluator: bonds Morph → F1 vs GT links
# ---------------------------------------------------------------------------

def evaluate_form(form_data: dict) -> dict:
    """Valuta Morph su un singolo form FUNSD.

    Pipeline: funsd_to_particles → sense → field → match links.

    Tre livelli di valutazione:
    0. **Spatial (campo puro)**: il campo ha bondato una particella di
       un'entita' answer a una particella di UNA QUALSIASI entita' question.
       (il campo vede la struttura question/answer?)
    1. **Bond (link match)**: il campo ha bondato una particella dell'entita'
       answer alla CORRETTA entita' question (link esatto GT).
    2. **Type distribution**: quante particelle per tipo typify.
       (diagnostica — non e' un livello F1)

    Il gap tra spatial e bond = costo di traduzione.

    Returns:
        Dict con metriche per i livelli.
    """
    particles = funsd_to_particles(form_data)
    if len(particles) < 2:
        return {'skip': True, 'reason': 'too_few_particles'}

    # Mappa posizioni → metadata FUNSD (prima del sensing)
    funsd_meta = {}
    for p in particles:
        key = (round(p['x'], 1), round(p['y'], 1))
        funsd_meta[key] = {
            'entity_id': p['_funsd_entity_id'],
            'label': p['_funsd_label'],
        }

    # Distribuzione tipi per diagnostica
    type_counts = defaultdict(int)
    label_type_counts = defaultdict(lambda: defaultdict(int))
    for p in particles:
        type_counts[p['type']] += 1
        label_type_counts[p['_funsd_label']][p['type']] += 1

    # Pipeline Morph
    sense_result = sense_page(particles)
    sensed = sense_result['particles']
    field_result = extract_page(sensed)

    # GT links
    gt_links = parse_funsd_gt(form_data)

    # Set di entita' question (per spatial test)
    question_ids = set()
    for e in form_data.get('form', []):
        if e.get('label') == 'question':
            question_ids.add(e['id'])

    # Mappa particelle sensed → entity_id (dopo sensing)
    pos_to_entity = {}
    for p in sensed:
        pkey = (round(p['x'], 1), round(p['y'], 1))
        if pkey in funsd_meta:
            pos_to_entity[pkey] = funsd_meta[pkey]['entity_id']

    # Bonds Morph: per ogni NUMERIC mappato → posizioni dell'entity e spec
    morph_bonds = {}  # (x, y) del NUMERIC → {entity_text, spec_text, entity_pos, spec_pos}
    for entity_text, specs in field_result['data'].items():
        for spec_text, info in specs.items():
            val_key = (round(info['x'], 1), round(info['y'], 1))
            morph_bonds[val_key] = {
                'entity': entity_text,
                'spec': spec_text,
            }

    # Trova entity_id del testo entity/spec nel campo
    # Per ogni particella sensed, mappa testo → set di entity_id
    text_to_entity_ids = defaultdict(set)
    for p in sensed:
        pkey = (round(p['x'], 1), round(p['y'], 1))
        if pkey in funsd_meta:
            text_to_entity_ids[p['text'].lower()].add(
                funsd_meta[pkey]['entity_id']
            )

    # Valutazione per link GT
    spatial_tp = spatial_fn = 0
    bond_tp = bond_fn = 0
    unreachable = 0  # link dove answer non ha NUMERIC → impossibile per il campo

    detail = defaultdict(lambda: {
        'spatial_tp': 0, 'spatial_fn': 0,
        'bond_tp': 0, 'bond_fn': 0,
        'unreachable': 0,
    })

    for gt_link in gt_links:
        from_id = gt_link['from_id']
        to_id = gt_link['to_id']
        link_type = f"{gt_link['from_label']}->{gt_link['to_label']}"

        # Trova particelle dell'entita' "to" (tipicamente answer)
        to_positions = []
        for p in particles:
            if p['_funsd_entity_id'] == to_id:
                to_positions.append((round(p['x'], 1), round(p['y'], 1)))

        # Cerca se almeno una particella di "to" e' stata bondata dal campo
        found_morph = None
        for pos in to_positions:
            if pos in morph_bonds:
                found_morph = morph_bonds[pos]
                break

        if found_morph is None:
            # Nessuna particella dell'entita' answer bondata
            # Distingui: ha NUMERIC? Se no, e' unreachable per il campo attuale
            has_numeric = any(
                p['type'] == 'NUMERIC'
                for p in particles
                if p['_funsd_entity_id'] == to_id
            )
            if not has_numeric:
                unreachable += 1
                detail[link_type]['unreachable'] += 1

            spatial_fn += 1
            bond_fn += 1
            detail[link_type]['spatial_fn'] += 1
            detail[link_type]['bond_fn'] += 1
            continue

        # Particella answer bondata. Verifica entity/spec del campo.

        # Spatial: il campo ha puntato a UNA QUALSIASI question entity?
        entity_ids = text_to_entity_ids.get(found_morph['entity'].lower(), set())
        spec_ids = text_to_entity_ids.get(found_morph['spec'].lower(), set())
        pointed_ids = entity_ids | spec_ids

        spatial_match = bool(pointed_ids & question_ids)
        if spatial_match:
            spatial_tp += 1
            detail[link_type]['spatial_tp'] += 1
        else:
            spatial_fn += 1
            detail[link_type]['spatial_fn'] += 1

        # Bond: il campo ha puntato all'entita' from_id specifica?
        bond_match = from_id in pointed_ids
        if bond_match:
            bond_tp += 1
            detail[link_type]['bond_tp'] += 1
        else:
            bond_fn += 1
            detail[link_type]['bond_fn'] += 1

    # FP: bonds Morph che non corrispondono a nessun link GT
    gt_to_positions = set()
    for gt_link in gt_links:
        for p in particles:
            if p['_funsd_entity_id'] == gt_link['to_id']:
                gt_to_positions.add((round(p['x'], 1), round(p['y'], 1)))

    fp = sum(1 for pos in morph_bonds if pos not in gt_to_positions)

    def _f1(tp, fp_, fn):
        p = tp / (tp + fp_) if (tp + fp_) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f

    p_spat, r_spat, f1_spat = _f1(spatial_tp, fp, spatial_fn)
    p_bond, r_bond, f1_bond = _f1(bond_tp, fp, bond_fn)

    return {
        'skip': False,
        'spatial_tp': spatial_tp, 'spatial_fn': spatial_fn,
        'spatial_p': p_spat, 'spatial_r': r_spat, 'spatial_f1': f1_spat,
        'bond_tp': bond_tp, 'bond_fn': bond_fn,
        'bond_p': p_bond, 'bond_r': r_bond, 'bond_f1': f1_bond,
        'fp': fp,
        'unreachable': unreachable,
        'n_particles': len(particles),
        'n_gt_links': len(gt_links),
        'n_morph_bonds': len(morph_bonds),
        'type_counts': dict(type_counts),
        'label_type_counts': {k: dict(v) for k, v in label_type_counts.items()},
        'detail': dict(detail),
    }


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def find_forms(split: str = 'test') -> list[Path]:
    """Trova tutti i JSON in uno split FUNSD.

    Args:
        split: ``'train'`` o ``'test'``.

    Returns:
        Lista di Path ai file JSON.
    """
    split_map = {
        'test': 'testing_data',
        'train': 'training_data',
    }
    split_name = split_map.get(split, split)
    ann_dir = DATASET / 'dataset' / split_name / 'annotations'

    if not ann_dir.exists():
        raise FileNotFoundError(f"FUNSD split not found: {ann_dir}")

    return sorted(ann_dir.glob('*.json'))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run FUNSD benchmark."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Morph benchmark on FUNSD forms',
    )
    parser.add_argument(
        '--split', default='test',
        choices=['train', 'test'],
        help='Dataset split (default: test)',
    )
    parser.add_argument(
        '--n', type=int, default=0,
        help='Max form (0 = tutti)',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Stampa dettagli per form',
    )
    args = parser.parse_args()

    paths = find_forms(args.split)
    if args.n > 0:
        paths = paths[:args.n]

    print(f"FUNSD Benchmark — {len(paths)} form ({args.split})")
    print("=" * 60)

    t0 = time.time()
    skipped = 0
    results = []
    totals = {
        'spatial_tp': 0, 'spatial_fn': 0,
        'bond_tp': 0, 'bond_fn': 0,
        'fp': 0, 'unreachable': 0,
    }
    link_detail = defaultdict(lambda: {
        'spatial_tp': 0, 'spatial_fn': 0,
        'bond_tp': 0, 'bond_fn': 0,
        'unreachable': 0,
    })
    # Accumulatori tipi
    total_type_counts = defaultdict(int)
    total_label_type = defaultdict(lambda: defaultdict(int))

    for path in paths:
        with open(path) as f:
            data = json.load(f)

        r = evaluate_form(data)
        if r.get('skip'):
            skipped += 1
            continue

        results.append(r)
        for k in ['spatial_tp', 'spatial_fn', 'bond_tp', 'bond_fn',
                   'fp', 'unreachable']:
            totals[k] += r.get(k, 0)

        for lt, d in r['detail'].items():
            for k in link_detail[lt]:
                link_detail[lt][k] += d.get(k, 0)

        for t, c in r['type_counts'].items():
            total_type_counts[t] += c

        for label, types in r['label_type_counts'].items():
            for t, c in types.items():
                total_label_type[label][t] += c

        if args.verbose:
            print(f"  {path.name}: "
                  f"Spatial={r['spatial_f1']:.0%} "
                  f"Bond={r['bond_f1']:.0%} "
                  f"bonds={r['n_morph_bonds']}/{r['n_gt_links']} "
                  f"(FP={r['fp']}, unreach={r['unreachable']})")

    elapsed = time.time() - t0

    if not results:
        print("Nessun risultato!")
        return

    def _f1(tp, fp_, fn):
        p = tp / (tp + fp_) if (tp + fp_) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f

    fp = totals['fp']

    print(f"\nCompletato: {len(results)} form, {skipped} skipped, {elapsed:.1f}s")
    print(f"Velocita': {len(results)/elapsed:.0f} form/s")
    print()

    # --- Risultati ---
    print("=" * 70)
    print("RISULTATI — entity linking (micro-average)")
    print("=" * 70)
    print(f"  {'Livello':>25} {'TP':>6} {'FP':>6} {'FN':>6} "
          f"{'Prec':>8} {'Recall':>8} {'F1':>8}")
    print(f"  {'-'*70}")

    for level, label in [('spatial', 'Spatial (any question)'),
                         ('bond', 'Bond (correct link)')]:
        tp = totals[f'{level}_tp']
        fn = totals[f'{level}_fn']
        p, r, f = _f1(tp, fp, fn)
        print(f"  {label:>25} {tp:>6} {fp:>6} {fn:>6} "
              f"{p:>7.1%} {r:>7.1%} {f:>7.1%}")

    _, r_spat, _ = _f1(totals['spatial_tp'], fp, totals['spatial_fn'])
    _, r_bond, _ = _f1(totals['bond_tp'], fp, totals['bond_fn'])
    print()
    print(f"  Costo traduzione (Spatial→Bond): "
          f"{(r_spat - r_bond)*100:+.1f}pp recall")
    print(f"  Link irraggiungibili (answer senza NUMERIC): "
          f"{totals['unreachable']}")

    total_gt = sum(r['n_gt_links'] for r in results)
    print(f"  Link GT totali: {total_gt}")
    print(f"  Unreachable / GT: "
          f"{totals['unreachable']/total_gt*100:.1f}%")

    # --- Breakdown per tipo link ---
    print()
    print("=" * 70)
    print("RECALL PER TIPO LINK")
    print("=" * 70)
    print(f"  {'Tipo link':>30} {'TP':>6} {'FN':>6} "
          f"{'Unreach':>8} {'Recall':>10}")
    print(f"  {'-'*60}")

    for lt in sorted(link_detail.keys()):
        d = link_detail[lt]
        lt_r = d['bond_tp'] / (d['bond_tp'] + d['bond_fn']) \
            if (d['bond_tp'] + d['bond_fn']) > 0 else 0.0
        print(f"  {lt:>30} {d['bond_tp']:>6} {d['bond_fn']:>6} "
              f"{d['unreachable']:>8} {lt_r:>9.1%}")

    # --- Distribuzione tipi (diagnostica) ---
    print()
    print("=" * 70)
    print("DISTRIBUZIONE TIPI PARTICELLA")
    print("=" * 70)
    total_p = sum(total_type_counts.values())
    for t in sorted(total_type_counts.keys()):
        c = total_type_counts[t]
        print(f"  {t:>15}: {c:>6} ({c/total_p*100:>5.1f}%)")

    print()
    print("  Per label FUNSD:")
    for label in ['question', 'answer', 'header', 'other']:
        if label not in total_label_type:
            continue
        types = total_label_type[label]
        tot = sum(types.values())
        parts = ', '.join(f"{t}={c}" for t, c in sorted(types.items()))
        numeric_pct = types.get('NUMERIC', 0) / tot * 100 if tot else 0
        print(f"    {label:>10} ({tot:>5} words): {parts}")
        print(f"              → {numeric_pct:.1f}% NUMERIC")

    # --- Statistiche ---
    avg_particles = sum(r['n_particles'] for r in results) / len(results)
    avg_gt = sum(r['n_gt_links'] for r in results) / len(results)
    avg_morph = sum(r['n_morph_bonds'] for r in results) / len(results)

    print()
    print("=" * 70)
    print("STATISTICHE")
    print("=" * 70)
    print(f"  Particelle/form (media): {avg_particles:.1f}")
    print(f"  Link GT/form (media):    {avg_gt:.1f}")
    print(f"  Bond Morph/form (media): {avg_morph:.1f}")


if __name__ == '__main__':
    main()
