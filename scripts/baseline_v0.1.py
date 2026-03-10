#!/usr/bin/env python3
"""
Phase 0: Baseline v0.1.0 - PUNTO ZERO

Raccoglie metriche complete su TUTTI i dataset disponibili:
- HVAC (5 cataloghi)
- PubTables-1M (500 tabelle random)
- FinTabNet (sample)
- SROIE (sample)
- FUNSD (sample)
- DocBank (sample)
- CORD (sample)

Output:
- data/baseline_v0.1.json (dati completi)
- data/baseline_v0.1_summary.txt (sommario leggibile)

Usage:
    python scripts/baseline_v0.1.py
"""

import json
import random
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Morph imports
from morph.io.reader import open_pdf
from morph.core import extract_particles, extract_page
from morph.bench.grits import evaluate_grits
from morph.bench.pubtables import parse_gt

# Paths
BASE_DIR = Path(__file__).parent.parent
DATASET_DIR = Path('/mnt/dati/home/Progetti/dataset')
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

# ============================================================================
# HVAC BASELINE
# ============================================================================

HVAC_TEST_SET = [
    # (pdf_path, page_num, brand, description)
    ('/mnt/dati/home/Progetti/dots.ocr/brands/hitachi/input/Brochure airH20_800.pdf', 7, 'hitachi', 'RWM series'),
    ('/mnt/dati/home/Progetti/dots.ocr/brands/daikin/input/20220412 VRV 5 HR.pdf', 20, 'daikin', 'FXFA series'),
    # TBD: Toshiba, Mitsubishi, Midea quando disponibili
]


def run_baseline_hvac():
    """Baseline su cataloghi HVAC"""
    print("\n=== HVAC BASELINE ===")
    results = []

    for pdf_path, page_num, brand, desc in HVAC_TEST_SET:
        print(f"\n{brand.upper()} - {desc} (p.{page_num+1})...")

        try:
            # Timer
            t0 = time.time()

            # Reader
            pdf = open_pdf(pdf_path)
            page = pdf[page_num]

            t_reader = time.time()

            # Typify
            particles = extract_particles(page)

            t_typify = time.time()

            # Field
            field_result = extract_page(particles)

            t_field = time.time()

            # Analizza types
            types_breakdown = defaultdict(int)
            for p in particles:
                types_breakdown[p.get('type', 'UNKNOWN')] += 1

            # Result
            result = {
                'dataset': 'hvac',
                'brand': brand,
                'file': pdf_path,
                'page': page_num,
                'description': desc,

                # Reader
                'reader': {
                    'words_extracted': len(particles),
                    'features': ['text', 'bbox', 'size'],  # v0.1 basic
                },

                # Typify
                'typify': {
                    'particles_total': len(particles),
                    'types_breakdown': dict(types_breakdown),
                },

                # Field
                'field': field_result.get('stats', {}),
                'entities': field_result.get('data', {}).keys(),

                # Timing (ms)
                'timing': {
                    'reader_ms': round((t_reader - t0) * 1000, 2),
                    'typify_ms': round((t_typify - t_reader) * 1000, 2),
                    'field_ms': round((t_field - t_typify) * 1000, 2),
                    'total_ms': round((t_field - t0) * 1000, 2),
                },
            }

            results.append(result)

            print(f"  Particles: {len(particles)}")
            print(f"  Entities: {field_result['stats']['entities']}")
            print(f"  Mapped: {field_result['stats']['mapped']}/{field_result['stats']['mapped'] + field_result['stats']['unmapped']}")
            print(f"  Time: {result['timing']['total_ms']:.0f}ms")

        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                'dataset': 'hvac',
                'brand': brand,
                'file': pdf_path,
                'page': page_num,
                'error': str(e),
            })

    return results


# ============================================================================
# PUBTABLES BASELINE
# ============================================================================

def run_baseline_pubtables(n_sample=500):
    """Baseline su PubTables-1M (500 tabelle random)"""
    print(f"\n=== PUBTABLES-1M BASELINE ({n_sample} tables) ===")

    # Trova tutti i file XML nel test set
    pubtables_dir = DATASET_DIR / 'pubtables-1m'
    xml_files = list(pubtables_dir.glob('*.xml'))

    # Filtra solo quelli con _words.json
    valid_files = [
        f for f in xml_files
        if (pubtables_dir / f.name.replace('.xml', '_words.json')).exists()
    ]

    print(f"Found {len(valid_files)} valid tables")

    # Sample random
    if len(valid_files) > n_sample:
        sample_files = random.sample(valid_files, n_sample)
    else:
        sample_files = valid_files

    print(f"Testing {len(sample_files)} tables...")

    results = []

    for i, xml_path in enumerate(sample_files, 1):
        if i % 50 == 0:
            print(f"  Progress: {i}/{len(sample_files)}...")

        try:
            table_id = xml_path.stem
            json_path = xml_path.parent / f'{table_id}_words.json'

            # Timer
            t0 = time.time()

            # Evaluate
            metrics = evaluate_grits(
                str(json_path),
                str(xml_path),
                top_only=False,  # GriTS_Top + GriTS_Con
                method='max+crystal',  # v0.1 best method
            )

            t_total = time.time()

            if metrics:
                result = {
                    'dataset': 'pubtables',
                    'table_id': table_id,
                    'metrics': metrics,
                    'timing': {
                        'total_ms': round((t_total - t0) * 1000, 2),
                    },
                }
                results.append(result)

        except Exception as e:
            results.append({
                'dataset': 'pubtables',
                'table_id': xml_path.stem,
                'error': str(e),
            })

    # Summary stats
    valid_results = [r for r in results if 'metrics' in r]

    if valid_results:
        avg_grits_top = sum(r['metrics']['grits_top'] for r in valid_results) / len(valid_results)
        avg_row_exact = sum(r['metrics']['row_exact'] for r in valid_results) / len(valid_results)
        avg_col_exact = sum(r['metrics']['col_exact'] for r in valid_results) / len(valid_results)

        print(f"\n  Tested: {len(valid_results)}/{len(sample_files)}")
        print(f"  GriTS_Top: {avg_grits_top:.1%}")
        print(f"  Row exact: {avg_row_exact:.1%}")
        print(f"  Col exact: {avg_col_exact:.1%}")

    return results


# ============================================================================
# FINTABNET BASELINE
# ============================================================================

def run_baseline_fintabnet(n_sample=100):
    """Baseline su FinTabNet (100 tabelle)"""
    print(f"\n=== FINTABNET BASELINE ({n_sample} tables) ===")

    # TBD: implementare quando necesario
    # Struttura simile a PubTables

    print("  SKIPPED (TBD)")
    return []


# ============================================================================
# OTHER DATASETS
# ============================================================================

def run_baseline_sroie(n_sample=50):
    """Baseline su SROIE (scanned receipts)"""
    print(f"\n=== SROIE BASELINE ({n_sample} receipts) ===")
    print("  SKIPPED (TBD)")
    return []


def run_baseline_funsd(n_sample=50):
    """Baseline su FUNSD (forms)"""
    print(f"\n=== FUNSD BASELINE ({n_sample} forms) ===")
    print("  SKIPPED (TBD)")
    return []


def run_baseline_docbank(n_sample=50):
    """Baseline su DocBank"""
    print(f"\n=== DOCBANK BASELINE ({n_sample} docs) ===")
    print("  SKIPPED (TBD)")
    return []


def run_baseline_cord(n_sample=50):
    """Baseline su CORD"""
    print(f"\n=== CORD BASELINE ({n_sample} docs) ===")
    print("  SKIPPED (TBD)")
    return []


# ============================================================================
# MAIN
# ============================================================================

def run_baseline_all():
    """Raccoglie baseline completa su tutti i dataset"""

    print("=" * 60)
    print("MORPH v0.1.0 - BASELINE COLLECTION")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Output: {DATA_DIR / 'baseline_v0.1.json'}")

    # Raccolta dati
    baseline = {
        'version': 'v0.1.0',
        'date': datetime.now().isoformat(),
        'datasets': {},
    }

    # HVAC
    baseline['datasets']['hvac'] = run_baseline_hvac()

    # PubTables (500 tabelle)
    baseline['datasets']['pubtables'] = run_baseline_pubtables(n_sample=500)

    # Altri dataset (TBD)
    baseline['datasets']['fintabnet'] = run_baseline_fintabnet(n_sample=100)
    baseline['datasets']['sroie'] = run_baseline_sroie(n_sample=50)
    baseline['datasets']['funsd'] = run_baseline_funsd(n_sample=50)
    baseline['datasets']['docbank'] = run_baseline_docbank(n_sample=50)
    baseline['datasets']['cord'] = run_baseline_cord(n_sample=50)

    # Salva JSON completo
    json_path = DATA_DIR / 'baseline_v0.1.json'
    with open(json_path, 'w') as f:
        json.dump(baseline, f, indent=2, default=str)

    print(f"\n✓ Baseline saved to: {json_path}")

    # Genera summary
    generate_summary(baseline)

    return baseline


def generate_summary(baseline):
    """Genera summary leggibile"""

    summary_path = DATA_DIR / 'baseline_v0.1_summary.txt'

    with open(summary_path, 'w') as f:
        f.write("=" * 70 + "\n")
        f.write("MORPH v0.1.0 - BASELINE SUMMARY\n")
        f.write("=" * 70 + "\n")
        f.write(f"Date: {baseline['date']}\n")
        f.write(f"Version: {baseline['version']}\n\n")

        # HVAC
        hvac_results = baseline['datasets']['hvac']
        if hvac_results:
            f.write("HVAC (cataloghi borderless, domain-specific):\n")
            f.write("-" * 70 + "\n")

            for r in hvac_results:
                if 'error' not in r:
                    f.write(f"  {r['brand'].upper()} - {r['description']}\n")
                    f.write(f"    Particles: {r['typify']['particles_total']}\n")
                    f.write(f"    Entities: {r['field'].get('entities', 0)}\n")
                    f.write(f"    Mapped: {r['field'].get('mapped', 0)}/{r['field'].get('mapped', 0) + r['field'].get('unmapped', 0)}\n")
                    f.write(f"    Time: {r['timing']['total_ms']:.0f}ms\n\n")

            # Avg
            valid = [r for r in hvac_results if 'error' not in r]
            if valid:
                avg_particles = sum(r['typify']['particles_total'] for r in valid) / len(valid)
                avg_mapped = sum(r['field'].get('mapped', 0) for r in valid) / len(valid)
                avg_time = sum(r['timing']['total_ms'] for r in valid) / len(valid)

                f.write(f"  AVERAGE:\n")
                f.write(f"    Particles: {avg_particles:.0f}\n")
                f.write(f"    Mapped: {avg_mapped:.0f}\n")
                f.write(f"    Time: {avg_time:.0f}ms\n\n")

        # PubTables
        pubtables_results = baseline['datasets']['pubtables']
        if pubtables_results:
            valid = [r for r in pubtables_results if 'metrics' in r]

            f.write("\nPubTables-1M (bordered, scientific papers):\n")
            f.write("-" * 70 + "\n")
            f.write(f"  Tables tested: {len(valid)}\n")

            if valid:
                avg_grits_top = sum(r['metrics']['grits_top'] for r in valid) / len(valid)
                avg_grits_con = sum(r['metrics'].get('grits_con', 0) for r in valid if r['metrics'].get('grits_con')) / len([r for r in valid if r['metrics'].get('grits_con')])
                avg_row = sum(r['metrics']['row_exact'] for r in valid) / len(valid)
                avg_col = sum(r['metrics']['col_exact'] for r in valid) / len(valid)
                avg_time = sum(r['timing']['total_ms'] for r in valid) / len(valid)

                f.write(f"  GriTS_Top: {avg_grits_top:.1%}\n")
                if avg_grits_con > 0:
                    f.write(f"  GriTS_Con: {avg_grits_con:.1%}\n")
                f.write(f"  Row exact: {avg_row:.1%}\n")
                f.write(f"  Col exact: {avg_col:.1%}\n")
                f.write(f"  Avg time: {avg_time:.0f}ms\n\n")

        # Altri dataset (TBD)
        for ds_name in ['fintabnet', 'sroie', 'funsd', 'docbank', 'cord']:
            ds_results = baseline['datasets'].get(ds_name, [])
            if ds_results:
                f.write(f"\n{ds_name.upper()}:\n")
                f.write(f"  Tables: {len(ds_results)}\n")
                f.write(f"  Status: TBD\n\n")

        f.write("=" * 70 + "\n")
        f.write("BASELINE COMPLETE - PUNTO ZERO ESTABLISHED\n")
        f.write("=" * 70 + "\n")

    print(f"✓ Summary saved to: {summary_path}")

    # Stampa anche a video
    with open(summary_path) as f:
        print(f.read())


if __name__ == '__main__':
    # Set random seed per reproducibilità
    random.seed(42)

    # Run baseline
    baseline = run_baseline_all()

    print("\n✅ PHASE 0 COMPLETE!")
    print(f"   Baseline data: data/baseline_v0.1.json")
    print(f"   Summary: data/baseline_v0.1_summary.txt")
    print("\n   Next: Phase 1 (Reader++)")
