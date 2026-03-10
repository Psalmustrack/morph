#!/usr/bin/env python3
"""
morph.bench.docbank — DocBank Document Layout Benchmark Adapter
===============================================================

Evaluates the Morph field equation on DocBank (500K scientific document
pages with 13 token-level layout labels).

DocBank tests the *dragon weakness*: most tokens are TEXT (70-90%) and the
field has W(TEXT, TEXT) = 0.  The key question is: on pages with equations,
tables, and dates, can the field still bond the NUMERIC tokens correctly?

Labels (13 types)::

    abstract, author, caption, date, equation, figure, footer,
    header, list, paragraph, reference, section, table, title

For each page, we measure:

1. **Type reachability**: per GT label, what % of tokens are NUMERIC?
2. **Bond recall**: per GT label, are any tokens bonded by the field?
3. **Bond purity**: when bonded, do bonded tokens share the same GT label?
4. **Overall coverage**: what fraction of NUMERIC tokens are bonded?

Dataset::

    <DOCBANK_ROOT>/
        DocBank_500K_txt/
            *.txt  — one file per page, tab-separated:
                    token  x0  y0  x1  y1  R  G  B  font  label

Usage::

    python -m morph.bench.docbank --n 1000
    python -m morph.bench.docbank --n 100 --verbose

Author: Eugeniu Tacu, 2026
"""

import os
import time
from collections import defaultdict
from pathlib import Path

from morph.core import typify_word, sense_page, extract_page

# Default dataset path — override with DOCBANK_ROOT env var
DATASET = Path(
    os.environ.get(
        'DOCBANK_ROOT',
        '/mnt/dati/home/Progetti/dataset/docbank',
    )
)

# DocBank label types
LABELS = [
    'abstract', 'author', 'caption', 'date', 'equation', 'figure',
    'footer', 'header', 'list', 'paragraph', 'reference', 'section',
    'table', 'title',
]

# Labels where NUMERIC tokens are expected (field-relevant)
NUMERIC_LABELS = {'equation', 'table', 'date', 'caption', 'reference'}


# ---------------------------------------------------------------------------
# Parser: DocBank txt → tokens
# ---------------------------------------------------------------------------

def _parse_docbank_txt(path: Path) -> list[dict]:
    """Parsa un file DocBank .txt.

    Formato: token\\tx0\\ty0\\tx1\\ty1\\tR\\tG\\tB\\tfont\\tlabel
    (tab-separated, 10 colonne).

    Returns:
        Lista di dict: {text, x0, y0, x1, y1, label, font}.
    """
    tokens = []
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            parts = line.rstrip('\n').split('\t')
            if len(parts) < 10:
                continue

            text = parts[0]
            if not text.strip():
                continue

            try:
                x0, y0, x1, y1 = int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
            except ValueError:
                continue

            if x1 <= x0 or y1 <= y0:
                continue

            label = parts[9].strip()
            tokens.append({
                'text': text,
                'x0': x0, 'y0': y0,
                'x1': x1, 'y1': y1,
                'label': label,
                'font': parts[8],
            })

    return tokens


# ---------------------------------------------------------------------------
# Adapter: DocBank tokens → Morph particles
# ---------------------------------------------------------------------------

def docbank_to_particles(tokens: list[dict]) -> list[dict]:
    """Converte token DocBank in particelle Morph.

    Returns:
        Lista di particelle con chiavi standard Morph + _gt_label.
    """
    particles = []
    for t in tokens:
        ptype = typify_word(t['text'], domain=False)
        particles.append({
            'text': t['text'][:80],
            'x': (t['x0'] + t['x1']) / 2,
            'y': (t['y0'] + t['y1']) / 2,
            'x0': t['x0'], 'x1': t['x1'],
            'y0': t['y0'], 'y1': t['y1'],
            'type': ptype,
            'size': max(1.0, t['y1'] - t['y0']),
            '_gt_label': t['label'],
        })
    return particles


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

def evaluate_page(tokens: list[dict]) -> dict:
    """Valuta Morph su una singola pagina DocBank.

    Metriche:
    1. Per-label: quanti token sono NUMERIC (reachable)?
    2. Per-label: quanti token sono bonded dal campo?
    3. Bond purity: i token bonded condividono lo stesso GT label?
    4. Overall coverage: fraction of NUMERIC tokens that are bonded.

    Returns:
        Dict con metriche dettagliate.
    """
    particles = docbank_to_particles(tokens)
    if len(particles) < 2:
        return {'skip': True, 'reason': 'too_few_particles'}

    # --- Pipeline Morph ---
    sense_result = sense_page(particles)
    sensed = sense_result['particles']
    # v2.0 parameters: sigma_font=50, sigma_hierarchy=30, sigma_color=100, R=0
    field_result = extract_page(sensed, sigma_font=50, sigma_hierarchy=30, sigma_color=100, R=0)

    # --- Mappa posizioni bonded ---
    bonded_positions = set()
    for entity_text, specs in field_result['data'].items():
        for spec_text, info in specs.items():
            bonded_positions.add((round(info['x'], 1), round(info['y'], 1)))

    # --- Per-label statistics ---
    label_stats = defaultdict(lambda: {
        'total': 0, 'numeric': 0, 'bonded': 0,
    })

    # Conta tipi Morph per diagnostica
    type_counts = defaultdict(int)

    for p in particles:
        gt_label = p['_gt_label']
        label_stats[gt_label]['total'] += 1
        type_counts[p['type']] += 1

        if p['type'] == 'NUMERIC':
            label_stats[gt_label]['numeric'] += 1

        pkey = (round(p['x'], 1), round(p['y'], 1))
        if pkey in bonded_positions:
            label_stats[gt_label]['bonded'] += 1

    # --- Bond purity ---
    # Per ogni cluster di bond (entity), qual e' il label GT dominante?
    cluster_labels = defaultdict(list)
    for p in particles:
        pkey = (round(p['x'], 1), round(p['y'], 1))
        if pkey in bonded_positions:
            # Trova a quale entity appartiene
            for ent_text, specs in field_result['data'].items():
                for spec_text, info in specs.items():
                    if (round(info['x'], 1), round(info['y'], 1)) == pkey:
                        cluster_labels[ent_text].append(p['_gt_label'])

    # Purity = fraction of bonded tokens that match cluster majority label
    purity_correct = 0
    purity_total = 0
    for ent, labels in cluster_labels.items():
        if not labels:
            continue
        from collections import Counter
        mc = Counter(labels).most_common(1)[0]
        purity_correct += mc[1]
        purity_total += len(labels)

    purity = purity_correct / purity_total if purity_total > 0 else 0.0

    # --- Overall coverage ---
    total_numeric = sum(s['numeric'] for s in label_stats.values())
    total_bonded_numeric = 0
    for p in particles:
        if p['type'] == 'NUMERIC':
            pkey = (round(p['x'], 1), round(p['y'], 1))
            if pkey in bonded_positions:
                total_bonded_numeric += 1

    coverage = total_bonded_numeric / total_numeric if total_numeric > 0 else 0.0

    return {
        'skip': False,
        'n_particles': len(particles),
        'n_bonds': len(bonded_positions),
        'n_entities': field_result['stats']['entities'],
        'label_stats': dict(label_stats),
        'type_counts': dict(type_counts),
        'purity': purity,
        'purity_correct': purity_correct,
        'purity_total': purity_total,
        'coverage': coverage,
        'total_numeric': total_numeric,
        'total_bonded_numeric': total_bonded_numeric,
    }


# ---------------------------------------------------------------------------
# Dataset discovery
# ---------------------------------------------------------------------------

def find_pages(n: int = 0) -> list[Path]:
    """Trova file .txt in DocBank.

    Args:
        n: Max pagine (0 = tutte).

    Returns:
        Lista di Path ordinati.
    """
    txt_dir = DATASET / 'DocBank_500K_txt'
    if not txt_dir.exists():
        raise FileNotFoundError(f"DocBank txt not found: {txt_dir}")

    pages = sorted(txt_dir.glob('*.txt'))
    if n > 0:
        pages = pages[:n]

    return pages


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    """Run DocBank benchmark."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Morph benchmark on DocBank document pages',
    )
    parser.add_argument(
        '--n', type=int, default=1000,
        help='Max pagine (0 = tutte, default 1000)',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Stampa dettagli per pagina',
    )
    args = parser.parse_args()

    pages = find_pages(args.n)
    print(f"DocBank Benchmark — {len(pages)} pagine di paper scientifici")
    print("=" * 70)

    t0 = time.time()
    skipped = 0
    results = []

    # Aggregati
    agg_label_stats = defaultdict(lambda: {'total': 0, 'numeric': 0, 'bonded': 0})
    agg_type_counts = defaultdict(int)
    total_purity_correct = 0
    total_purity_total = 0
    total_numeric_all = 0
    total_bonded_numeric_all = 0

    for page_path in pages:
        tokens = _parse_docbank_txt(page_path)
        r = evaluate_page(tokens)

        if r.get('skip'):
            skipped += 1
            continue

        results.append(r)

        for label, stats in r['label_stats'].items():
            agg_label_stats[label]['total'] += stats['total']
            agg_label_stats[label]['numeric'] += stats['numeric']
            agg_label_stats[label]['bonded'] += stats['bonded']

        for t, c in r['type_counts'].items():
            agg_type_counts[t] += c

        total_purity_correct += r['purity_correct']
        total_purity_total += r['purity_total']
        total_numeric_all += r['total_numeric']
        total_bonded_numeric_all += r['total_bonded_numeric']

        if args.verbose:
            print(f"  {page_path.stem[:50]}: "
                  f"particles={r['n_particles']} bonds={r['n_bonds']} "
                  f"entities={r['n_entities']} purity={r['purity']:.1%} "
                  f"coverage={r['coverage']:.1%}")

    elapsed = time.time() - t0

    if not results:
        print("Nessun risultato!")
        return

    print(f"\nCompletato: {len(results)} pagine, {skipped} skipped, {elapsed:.1f}s")
    print(f"Velocita': {len(results)/elapsed:.0f} pagine/s")

    # --- Risultati per label GT ---
    print()
    print("=" * 80)
    print("RISULTATI PER LABEL GT")
    print("=" * 80)
    print(f"  {'Label':>12} {'Tokens':>8} {'NUMERIC':>8} {'%NUM':>7} "
          f"{'Bonded':>8} {'%Bond':>7} {'Reach':>7}")
    print(f"  {'-'*72}")

    for label in LABELS:
        s = agg_label_stats.get(label)
        if not s or s['total'] == 0:
            continue
        pct_num = s['numeric'] / s['total'] * 100
        pct_bond = s['bonded'] / s['total'] * 100
        reach = s['numeric'] / s['total'] * 100
        print(f"  {label:>12} {s['total']:>8} {s['numeric']:>8} {pct_num:>6.1f}% "
              f"{s['bonded']:>8} {pct_bond:>6.1f}% {reach:>6.1f}%")

    # --- Metriche aggregate ---
    print()
    print("=" * 80)
    print("METRICHE AGGREGATE")
    print("=" * 80)

    global_purity = total_purity_correct / total_purity_total if total_purity_total > 0 else 0
    global_coverage = total_bonded_numeric_all / total_numeric_all if total_numeric_all > 0 else 0

    total_tokens = sum(s['total'] for s in agg_label_stats.values())
    total_numeric = sum(s['numeric'] for s in agg_label_stats.values())
    total_bonded = sum(s['bonded'] for s in agg_label_stats.values())

    print(f"  Token totali:      {total_tokens:>10}")
    print(f"  Token NUMERIC:     {total_numeric:>10} ({total_numeric/total_tokens*100:.1f}%)")
    print(f"  Token bonded:      {total_bonded:>10} ({total_bonded/total_tokens*100:.1f}%)")
    print()
    print(f"  Bond purity:       {global_purity:>10.1%}  (bonded tokens con stesso label GT)")
    print(f"  NUMERIC coverage:  {global_coverage:>10.1%}  (NUMERIC tokens che sono bonded)")
    print()

    # Confronto con altri benchmark
    print(f"  --- Il muro W ---")
    pct_text = agg_type_counts.get('TEXT', 0) / total_tokens * 100
    print(f"  TEXT tokens: {pct_text:.1f}% del totale (invisibili al campo)")
    print(f"  Il campo puo' al massimo bondare {total_numeric/total_tokens*100:.1f}% dei token")

    # --- Per-tipo Morph reach into GT labels ---
    print()
    print("=" * 80)
    print("REACHABILITY: TIPI NUMERIC-RICH NEL GT")
    print("=" * 80)
    for label in ['equation', 'table', 'date', 'caption', 'figure']:
        s = agg_label_stats.get(label)
        if not s or s['total'] == 0:
            continue
        reach = s['numeric'] / s['total'] * 100
        bond_of_num = s['bonded'] / s['numeric'] * 100 if s['numeric'] > 0 else 0
        print(f"  {label:>12}: {s['total']:>6} token, {reach:.1f}% NUMERIC, "
              f"{bond_of_num:.1f}% dei NUMERIC bonded")

    # --- Distribuzione tipi Morph ---
    print()
    print("=" * 80)
    print("DISTRIBUZIONE TIPI PARTICELLA")
    print("=" * 80)
    for t in sorted(agg_type_counts.keys()):
        c = agg_type_counts[t]
        print(f"  {t:>15}: {c:>8} ({c/total_tokens*100:>5.1f}%)")

    # --- Statistiche ---
    avg_particles = sum(r['n_particles'] for r in results) / len(results)
    avg_bonds = sum(r['n_bonds'] for r in results) / len(results)
    avg_entities = sum(r['n_entities'] for r in results) / len(results)

    print()
    print("=" * 80)
    print("STATISTICHE")
    print("=" * 80)
    print(f"  Particelle/pagina (media): {avg_particles:.1f}")
    print(f"  Bond/pagina (media):       {avg_bonds:.1f}")
    print(f"  Entita'/pagina (media):    {avg_entities:.1f}")


if __name__ == '__main__':
    main()
