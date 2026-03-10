#!/usr/bin/env python3
"""Distribuzione tipi DOPO sensing su benchmark accademici.

Domanda: quante particelle COL_TYPES (MODEL, SIZE_HEADER, KW_HEADER)
produce il sensing sui dati accademici? Se sono poche, il campo ha
pochi magneti → errori sistematici inevitabili.
"""

import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from morph.core import typify_word, sense_page
from morph.bench.pubtables import json_to_particles, find_pairs


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--n', type=int, default=1000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--dataset', default='pubtables')
    args = parser.parse_args()

    pairs = find_pairs(dataset=args.dataset)
    random.seed(args.seed)
    if args.n > 0 and args.n < len(pairs):
        pairs = random.sample(pairs, args.n)

    print(f"Distribuzione tipi su {len(pairs)} tabelle ({args.dataset})")
    print("=" * 60)

    pre_sense = Counter()
    post_sense = Counter()
    promotions = Counter()  # TEXT→MODEL, TEXT→SPEC_LABEL, etc.
    tables_with_col_types = 0
    tables_with_specs = 0
    total_tables = 0

    for json_path, xml_path in pairs:
        with open(json_path) as f:
            words = json.load(f)

        particles = json_to_particles(words, domain=False)
        if len(particles) < 3:
            continue

        total_tables += 1

        # Pre-sensing
        for p in particles:
            pre_sense[p['type']] += 1

        # Post-sensing
        result = sense_page(particles)
        sensed = result['particles']

        has_col = False
        has_spec = False
        for p in sensed:
            post_sense[p['type']] += 1
            if p['type'] in ('MODEL', 'SIZE_HEADER', 'KW_HEADER'):
                has_col = True
            if p['type'] == 'SPEC_LABEL':
                has_spec = True

        if has_col:
            tables_with_col_types += 1
        if has_spec:
            tables_with_specs += 1

        # Conta promozioni
        for pre, post in zip(particles, sensed):
            if pre['type'] != post['type']:
                promotions[(pre['type'], post['type'])] += 1

    print(f"\nTabelle analizzate: {total_tables}")
    print()

    print("PRE-SENSING (tipi da typify)")
    print("-" * 40)
    for t, c in pre_sense.most_common():
        pct = c / sum(pre_sense.values()) * 100
        print(f"  {t:20s} {c:>8}  ({pct:.1f}%)")

    print()
    print("POST-SENSING (tipi dopo sense)")
    print("-" * 40)
    for t, c in post_sense.most_common():
        pct = c / sum(post_sense.values()) * 100
        print(f"  {t:20s} {c:>8}  ({pct:.1f}%)")

    print()
    print("PROMOZIONI (cambi tipo)")
    print("-" * 40)
    for (pre, post), c in promotions.most_common():
        print(f"  {pre:15s} → {post:15s} {c:>6}")

    print()
    print("COPERTURA STRUTTURALE")
    print("-" * 40)
    n_col = sum(post_sense[t] for t in ('MODEL', 'SIZE_HEADER', 'KW_HEADER'))
    n_spec = post_sense['SPEC_LABEL']
    n_num = post_sense['NUMERIC']
    total = sum(post_sense.values())
    print(f"  COL_TYPES (magneti colonna): {n_col:>6} "
          f"({n_col/total*100:.1f}%)")
    print(f"  SPEC_LABEL (magneti riga):   {n_spec:>6} "
          f"({n_spec/total*100:.1f}%)")
    print(f"  NUMERIC (da assegnare):      {n_num:>6} "
          f"({n_num/total*100:.1f}%)")
    print(f"  Rapporto NUMERIC/COL_TYPES:  "
          f"{n_num/n_col:.1f}:1" if n_col > 0 else "  Rapporto: ∞ (ZERO COL_TYPES!)")
    print(f"  Rapporto NUMERIC/SPEC_LABEL: "
          f"{n_num/n_spec:.1f}:1" if n_spec > 0 else "  Rapporto: ∞ (ZERO SPEC_LABEL!)")
    print()
    print(f"  Tabelle CON col_types: {tables_with_col_types}/{total_tables} "
          f"({tables_with_col_types/total_tables*100:.1f}%)")
    print(f"  Tabelle CON spec_label: {tables_with_specs}/{total_tables} "
          f"({tables_with_specs/total_tables*100:.1f}%)")


if __name__ == '__main__':
    main()
