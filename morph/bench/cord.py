#!/usr/bin/env python3
"""
morph.bench.cord — CORD Receipt Benchmark Adapter
==================================================

Converts CORD (Consolidated Receipt Dataset) JSON annotations into
Morph particles and evaluates entity-level F1 using field bonds.

CORD structure: each receipt has ``valid_line`` entries with words
(``is_key=1`` for labels, ``is_key=0`` for values) and a ``category``
like ``total.total_price``, ``menu.price``, ``sub_total.tax_price``.

Morph's field creates bonds SPEC_LABEL → NUMERIC. The evaluation
checks whether each bond matches the GT category: if a NUMERIC is
bonded to a SPEC_LABEL that belongs to the same ``valid_line``,
the entity is correctly extracted.

Dataset::

    <CORD_ROOT>/
        train/0000.json ... 0799.json
        val/0000.json   ... 0099.json
        test/0000.json  ... 0099.json

Usage::

    python -m morph.bench.cord --split test

Author: Eugeniu Tacu, 2026
"""

import json
import os
import time
from collections import defaultdict
from pathlib import Path

from morph.core import typify_word, sense_page, extract_page

# Default dataset path — override with CORD_ROOT env var
DATASET = Path(
    os.environ.get(
        'CORD_ROOT',
        '/mnt/dati/home/Progetti/dataset/cord',
    )
)


# ---------------------------------------------------------------------------
# Adapter: CORD JSON → Morph particles
# ---------------------------------------------------------------------------

def cord_to_particles(gt: dict) -> list[dict]:
    """Converte annotazioni CORD in particelle Morph.

    Ogni word in valid_line diventa una particella. Il quad (x1,y1...x4,y4)
    viene convertito in bbox rettangolare (x0, y0, x1, y1).

    Returns:
        Lista di particelle con chiavi: text, x, y, x0, y0, x1, y1,
        type, size, _cord_line_idx, _cord_is_key, _cord_category.
    """
    particles = []

    for line_idx, line in enumerate(gt.get('valid_line', [])):
        category = line.get('category', '')

        for word in line.get('words', []):
            text = word.get('text', '').strip()
            if not text:
                continue

            q = word['quad']
            # quad → bbox rettangolare
            x0 = min(q['x1'], q['x4'])
            x1 = max(q['x2'], q['x3'])
            y0 = min(q['y1'], q['y2'])
            y1 = max(q['y3'], q['y4'])

            ptype = typify_word(text, domain=False)

            particles.append({
                'text': text[:80],
                'x': (x0 + x1) / 2,
                'y': (y0 + y1) / 2,
                'x0': x0, 'x1': x1,
                'y0': y0, 'y1': y1,
                'type': ptype,
                'size': max(1.0, y1 - y0),
                # Metadati CORD per valutazione
                '_cord_line_idx': line_idx,
                '_cord_is_key': word.get('is_key', 0),
                '_cord_category': category,
                '_cord_group_id': line.get('group_id', -1),
            })

    return particles


# ---------------------------------------------------------------------------
# Ground truth parser
# ---------------------------------------------------------------------------

def parse_cord_gt(gt: dict) -> list[dict]:
    """Estrae i bond GT dal JSON CORD.

    Un bond GT esiste quando una valid_line ha sia parole is_key=1 (label)
    sia parole is_key=0 (valore). Il bond e':
      key_text (concatenato) → value_text (concatenato) → category

    Returns:
        Lista di dict: {category, key_text, value_text, key_positions,
        value_positions, group_id}
    """
    bonds = []

    for line in gt.get('valid_line', []):
        category = line.get('category', '')
        group_id = line.get('group_id', -1)
        words = line.get('words', [])

        key_words = []
        value_words = []

        for w in words:
            text = w.get('text', '').strip()
            if not text:
                continue
            q = w['quad']
            x = (min(q['x1'], q['x4']) + max(q['x2'], q['x3'])) / 2
            y = (min(q['y1'], q['y2']) + max(q['y3'], q['y4'])) / 2

            if w.get('is_key', 0) == 1:
                key_words.append({'text': text, 'x': x, 'y': y})
            else:
                value_words.append({'text': text, 'x': x, 'y': y})

        if value_words:
            # Concatena testi
            key_text = ' '.join(w['text'] for w in key_words)
            value_text = ' '.join(w['text'] for w in value_words)

            bonds.append({
                'category': category,
                'key_text': key_text,
                'value_text': value_text,
                'key_positions': [(w['x'], w['y']) for w in key_words],
                'value_positions': [(w['x'], w['y']) for w in value_words],
                'group_id': group_id,
            })

    return bonds


# ---------------------------------------------------------------------------
# Evaluator: bonds Morph → F1 vs GT
# ---------------------------------------------------------------------------

def evaluate_receipt(gt: dict) -> dict:
    """Valuta Morph su una singola ricevuta CORD.

    Pipeline: cord_to_particles → sense → field → match bonds.

    Quattro livelli di valutazione:
    0. **Spatial bond**: il campo Φ ha bondato il NUMERIC a una particella
       della stessa valid_line GT? (campo puro — nessuna traduzione)
    1. **Presence F1**: il NUMERIC e' stato mappato dal campo? (loose)
    2. **Bond F1**: il NUMERIC e' bondato a un key della stessa valid_line?
       (match testuale — traduzione)
    3. **Value F1**: il valore estratto corrisponde al GT? (entity-level)

    Il gap tra livello 0 e livello 2 = costo di traduzione.
    Come su PubTables: Boundary Precision (93.3%) vs GriTS (79.9%).

    Returns:
        Dict con metriche per i 4 livelli.
    """
    particles = cord_to_particles(gt)
    if len(particles) < 2:
        return {'skip': True, 'reason': 'too_few_particles'}

    # Mappa posizioni → metadata CORD (prima del sensing che puo' copiare)
    cord_meta = {}
    for p in particles:
        key = (round(p['x'], 1), round(p['y'], 1))
        cord_meta[key] = {
            'line_idx': p['_cord_line_idx'],
            'is_key': p['_cord_is_key'],
            'category': p['_cord_category'],
            'group_id': p['_cord_group_id'],
        }

    # Pipeline Morph
    sense_result = sense_page(particles)
    sensed = sense_result['particles']
    field_result = extract_page(sensed)

    # Bonds GT
    gt_bonds = parse_cord_gt(gt)

    # Mappa bonds Morph: per ogni NUMERIC mappato → (entity_text, spec_text, x, y)
    morph_bonds = {}  # (x, y) → {entity, spec}
    for entity, specs in field_result['data'].items():
        for spec, info in specs.items():
            key = (round(info['x'], 1), round(info['y'], 1))
            morph_bonds[key] = {
                'entity': entity,
                'spec': spec,
            }

    # Mappa testo → line_idx per il test campo puro (livello 0)
    # Per ogni particella sensed, cerca il cord_meta per posizione
    text_to_lines = defaultdict(set)  # testo → set di line_idx
    for p in sensed:
        pkey = (round(p['x'], 1), round(p['y'], 1))
        if pkey in cord_meta:
            text_to_lines[p['text'].lower()].add(cord_meta[pkey]['line_idx'])

    # Per ogni GT bond, costruisci set di key texts per matching
    spatial_tp = spatial_fn = 0
    presence_tp = presence_fn = 0
    bond_tp = bond_fn = 0
    value_tp = value_fn = 0
    detail = defaultdict(lambda: {'spatial_tp': 0, 'spatial_fn': 0,
                                  'presence_tp': 0, 'presence_fn': 0,
                                  'bond_tp': 0, 'bond_fn': 0,
                                  'value_tp': 0, 'value_fn': 0})

    for gt_bond in gt_bonds:
        cat = gt_bond['category']
        gt_key_texts = set(gt_bond['key_text'].lower().split())
        gt_value_text = gt_bond['value_text'].strip()

        # Cerca il value word nell'output Morph
        found_morph = None
        for vx, vy in gt_bond['value_positions']:
            vkey = (round(vx, 1), round(vy, 1))
            if vkey in morph_bonds:
                found_morph = morph_bonds[vkey]
                break

        if found_morph is None:
            # NUMERIC non trovato dal campo
            spatial_fn += 1
            presence_fn += 1
            bond_fn += 1
            value_fn += 1
            detail[cat]['spatial_fn'] += 1
            detail[cat]['presence_fn'] += 1
            detail[cat]['bond_fn'] += 1
            detail[cat]['value_fn'] += 1
            continue

        # Livello 1: Presence — il NUMERIC e' stato mappato
        presence_tp += 1
        detail[cat]['presence_tp'] += 1

        # Livello 0: Campo puro — Φ ha puntato alla stessa valid_line?
        # Il campo assegna entity (colonna) e spec (riga).
        # Verifica se entity O spec appartengono alla stessa valid_line
        # del value word, usando le posizioni originali CORD.
        gt_line_idx = gt_bond.get('_line_idx', -1)
        if gt_line_idx < 0:
            # Fallback: trova line_idx dal value position
            for vx, vy in gt_bond['value_positions']:
                vk = (round(vx, 1), round(vy, 1))
                if vk in cord_meta:
                    gt_line_idx = cord_meta[vk]['line_idx']
                    break

        # L'entity e lo spec del campo sono testi di particelle.
        # Cerco se quei testi hanno almeno un'occorrenza nella stessa line.
        entity_lines = text_to_lines.get(found_morph['entity'].lower(), set())
        spec_lines = text_to_lines.get(found_morph['spec'].lower(), set())
        spatial_match = (gt_line_idx in entity_lines or
                         gt_line_idx in spec_lines)

        if spatial_match:
            spatial_tp += 1
            detail[cat]['spatial_tp'] += 1
        else:
            spatial_fn += 1
            detail[cat]['spatial_fn'] += 1

        # Livello 2: Bond — match testuale con key words GT
        morph_entity = found_morph['entity'].lower()
        morph_spec = found_morph['spec'].lower()
        morph_texts = set(morph_entity.split()) | set(morph_spec.split())

        bond_match = bool(gt_key_texts & morph_texts)

        if bond_match:
            bond_tp += 1
            detail[cat]['bond_tp'] += 1
        else:
            bond_fn += 1
            detail[cat]['bond_fn'] += 1

        # Livello 3: Value — valore estratto = GT?
        morph_value = field_result['data'].get(
            found_morph['entity'], {}
        ).get(found_morph['spec'], {}).get('value', '')

        value_match = morph_value.strip() == gt_value_text
        if value_match and bond_match:
            value_tp += 1
            detail[cat]['value_tp'] += 1
        else:
            value_fn += 1
            detail[cat]['value_fn'] += 1

    # FP: bonds Morph su NUMERIC non presenti in nessun bond GT
    gt_value_positions = set()
    for gt_bond in gt_bonds:
        for vx, vy in gt_bond['value_positions']:
            gt_value_positions.add((round(vx, 1), round(vy, 1)))

    fp = sum(1 for pos in morph_bonds if pos not in gt_value_positions)

    def _f1(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f

    p_spat, r_spat, f1_spat = _f1(spatial_tp, fp, spatial_fn)
    p_pres, r_pres, f1_pres = _f1(presence_tp, fp, presence_fn)
    p_bond, r_bond, f1_bond = _f1(bond_tp, fp, bond_fn)
    p_val, r_val, f1_val = _f1(value_tp, fp, value_fn)

    return {
        'skip': False,
        # Spatial (campo puro — nessuna traduzione)
        'spatial_tp': spatial_tp, 'spatial_fn': spatial_fn,
        'spatial_p': p_spat, 'spatial_r': r_spat, 'spatial_f1': f1_spat,
        # Presence (loose)
        'presence_tp': presence_tp, 'presence_fn': presence_fn,
        'presence_p': p_pres, 'presence_r': r_pres, 'presence_f1': f1_pres,
        # Bond (strict — key corretto)
        'bond_tp': bond_tp, 'bond_fn': bond_fn,
        'bond_p': p_bond, 'bond_r': r_bond, 'bond_f1': f1_bond,
        # Value (entity-level — key + valore corretti)
        'value_tp': value_tp, 'value_fn': value_fn,
        'value_p': p_val, 'value_r': r_val, 'value_f1': f1_val,
        # Comuni
        'fp': fp,
        'n_particles': len(particles),
        'n_gt_bonds': len(gt_bonds),
        'n_morph_bonds': len(morph_bonds),
        'detail': dict(detail),
    }


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def find_receipts(split: str = 'test') -> list[Path]:
    """Trova tutti i JSON in uno split CORD.

    Args:
        split: ``'train'``, ``'val'``, o ``'test'``.

    Returns:
        Lista di Path ai file JSON.
    """
    split_dir = DATASET / split
    if not split_dir.exists():
        raise FileNotFoundError(f"CORD split not found: {split_dir}")

    paths = sorted(split_dir.glob('*.json'))
    return paths


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run CORD benchmark."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Morph benchmark on CORD receipts',
    )
    parser.add_argument(
        '--split', default='test',
        choices=['train', 'val', 'test'],
        help='Dataset split (default: test)',
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

    paths = find_receipts(args.split)
    if args.n > 0:
        paths = paths[:args.n]

    print(f"CORD Benchmark — {len(paths)} ricevute ({args.split})")
    print("=" * 60)

    t0 = time.time()
    skipped = 0
    results = []
    # Accumulatori per i 4 livelli
    totals = {
        'spatial_tp': 0, 'spatial_fn': 0,
        'presence_tp': 0, 'presence_fn': 0,
        'bond_tp': 0, 'bond_fn': 0,
        'value_tp': 0, 'value_fn': 0,
        'fp': 0,
    }
    cat_detail = defaultdict(lambda: {
        'spatial_tp': 0, 'spatial_fn': 0,
        'presence_tp': 0, 'presence_fn': 0,
        'bond_tp': 0, 'bond_fn': 0,
        'value_tp': 0, 'value_fn': 0,
    })

    for i, path in enumerate(paths):
        with open(path) as f:
            gt = json.load(f)

        r = evaluate_receipt(gt)
        if r.get('skip'):
            skipped += 1
            continue

        results.append(r)
        for k in totals:
            totals[k] += r.get(k, 0)

        for cat, d in r['detail'].items():
            for k in cat_detail[cat]:
                cat_detail[cat][k] += d.get(k, 0)

        if args.verbose:
            print(f"  {path.name}: "
                  f"Spatial={r['spatial_f1']:.0%} "
                  f"Presence={r['presence_f1']:.0%} "
                  f"Bond={r['bond_f1']:.0%} "
                  f"Value={r['value_f1']:.0%} "
                  f"(FP={r['fp']})")

    elapsed = time.time() - t0

    if not results:
        print("Nessun risultato!")
        return

    def _f1(tp, fp, fn):
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        return p, r, f

    fp = totals['fp']

    print(f"\nCompletato: {len(results)} ricevute, {skipped} skipped, {elapsed:.1f}s")
    print(f"Velocita': {len(results)/elapsed:.0f} ricevute/s")
    print()

    # --- 4 livelli ---
    print("=" * 70)
    print("RISULTATI — 4 livelli (micro-average)")
    print("=" * 70)
    print(f"  {'Livello':>25} {'TP':>6} {'FP':>6} {'FN':>6} "
          f"{'Prec':>8} {'Recall':>8} {'F1':>8}")
    print(f"  {'-'*70}")

    for level, label in [('spatial', 'Spatial (campo puro)'),
                         ('presence', 'Presence (mapped)'),
                         ('bond', 'Bond (key match)'),
                         ('value', 'Value (entity)')]:
        tp = totals[f'{level}_tp']
        fn = totals[f'{level}_fn']
        p, r, f = _f1(tp, fp, fn)
        print(f"  {label:>25} {tp:>6} {fp:>6} {fn:>6} "
              f"{p:>7.1%} {r:>7.1%} {f:>7.1%}")

    # Gap campo puro vs traduzione
    _, r_spat, _ = _f1(totals['spatial_tp'], fp, totals['spatial_fn'])
    _, r_bond, _ = _f1(totals['bond_tp'], fp, totals['bond_fn'])
    print()
    print(f"  Costo traduzione (Spatial→Bond): "
          f"{(r_spat - r_bond)*100:+.1f}pp recall")

    # Breakdown per superclasse (Bond F1)
    print()
    print("=" * 70)
    print("BOND F1 PER CATEGORIA")
    print("=" * 70)
    print(f"  {'Categoria':>30} {'TP':>6} {'FN':>6} {'Recall':>10}")
    print(f"  {'-'*55}")

    super_cats = defaultdict(lambda: {'tp': 0, 'fn': 0})
    for cat, d in sorted(cat_detail.items()):
        super_cat = cat.split('.')[0] if '.' in cat else cat
        super_cats[super_cat]['tp'] += d['bond_tp']
        super_cats[super_cat]['fn'] += d['bond_fn']

        cat_r = d['bond_tp'] / (d['bond_tp'] + d['bond_fn']) \
            if (d['bond_tp'] + d['bond_fn']) > 0 else 0.0
        print(f"  {cat:>30} {d['bond_tp']:>6} {d['bond_fn']:>6} {cat_r:>9.1%}")

    print(f"  {'-'*55}")
    for sc, d in sorted(super_cats.items()):
        sc_r = d['tp'] / (d['tp'] + d['fn']) if (d['tp'] + d['fn']) > 0 else 0.0
        print(f"  {sc + ' (totale)':>30} {d['tp']:>6} {d['fn']:>6} {sc_r:>9.1%}")

    # Statistiche
    avg_particles = sum(r['n_particles'] for r in results) / len(results)
    avg_gt = sum(r['n_gt_bonds'] for r in results) / len(results)
    avg_morph = sum(r['n_morph_bonds'] for r in results) / len(results)

    print()
    print("=" * 70)
    print("STATISTICHE")
    print("=" * 70)
    print(f"  Particelle/ricevuta (media): {avg_particles:.1f}")
    print(f"  Bond GT/ricevuta (media):    {avg_gt:.1f}")
    print(f"  Bond Morph/ricevuta (media): {avg_morph:.1f}")


if __name__ == '__main__':
    main()
