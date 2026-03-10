#!/usr/bin/env python3
"""
Test v0.1 vs v2.0 — Comparative Analysis

Testa Phase 1-3 improvements su tutti i dataset:
- HVAC (Hitachi + Daikin)
- PubTables-1M (100 tabelle sample)

Output:
- Confronto side-by-side v0.1 vs v2.0
- Delta mapped/unmapped/entities
- Timing comparison

Usage:
    python scripts/test_v2.0.py
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

# Paths
BASE_DIR = Path(__file__).parent.parent
DATASET_DIR = Path('/mnt/dati/home/Progetti/dataset')
DATA_DIR = BASE_DIR / 'data'

# HVAC test set
HVAC_TEST_SET = [
    ('/mnt/dati/home/Progetti/dots.ocr/brands/hitachi/input/Brochure airH20_800.pdf', 7, 'hitachi', 'RWM series'),
    ('/mnt/dati/home/Progetti/dots.ocr/brands/daikin/input/20220412 VRV 5 HR.pdf', 20, 'daikin', 'FXFA series'),
]

# v2.0 sigma values (experimental)
SIGMA_FONT = 50.0
SIGMA_HIERARCHY = 30.0
SIGMA_COLOR = 100.0


def test_hvac_comparison():
    """Compare v0.1 vs v2.0 on HVAC pages."""
    print("\n=== HVAC COMPARISON ===\n")

    results = []

    for pdf_path, page_num, brand, desc in HVAC_TEST_SET:
        print(f"{brand.upper()} - {desc} (p.{page_num+1})...")

        try:
            # Open PDF
            pdf = open_pdf(pdf_path)
            page = pdf[page_num]

            # v0.1 mode (full_features=False)
            t0 = time.time()
            particles_v01 = extract_particles(page, full_features=False)
            result_v01 = extract_page(particles_v01)
            t_v01 = time.time() - t0

            # v2.0 mode (full_features=True, multi-dim enabled)
            t0 = time.time()
            particles_v20 = extract_particles(page, full_features=True)
            result_v20 = extract_page(
                particles_v20,
                sigma_font=SIGMA_FONT,
                sigma_hierarchy=SIGMA_HIERARCHY,
                sigma_color=SIGMA_COLOR
            )
            t_v20 = time.time() - t0

            # Compare
            result = {
                'dataset': 'hvac',
                'brand': brand,
                'file': pdf_path,
                'page': page_num,
                'description': desc,

                'v01': {
                    'particles': len(particles_v01),
                    'entities': result_v01['stats']['entities'],
                    'mapped': result_v01['stats']['mapped'],
                    'unmapped': result_v01['stats']['unmapped'],
                    'time_ms': round(t_v01 * 1000, 2),
                },

                'v20': {
                    'particles': len(particles_v20),
                    'entities': result_v20['stats']['entities'],
                    'mapped': result_v20['stats']['mapped'],
                    'unmapped': result_v20['stats']['unmapped'],
                    'time_ms': round(t_v20 * 1000, 2),
                },

                'delta': {
                    'particles': len(particles_v20) - len(particles_v01),
                    'entities': result_v20['stats']['entities'] - result_v01['stats']['entities'],
                    'mapped': result_v20['stats']['mapped'] - result_v01['stats']['mapped'],
                    'unmapped': result_v20['stats']['unmapped'] - result_v01['stats']['unmapped'],
                },
            }

            results.append(result)

            # Print summary
            print(f"  v0.1: {result['v01']['entities']} entities, {result['v01']['mapped']} mapped, {result['v01']['unmapped']} unmapped")
            print(f"  v2.0: {result['v20']['entities']} entities, {result['v20']['mapped']} mapped, {result['v20']['unmapped']} unmapped")
            print(f"  Δ:    +{result['delta']['entities']} entities, +{result['delta']['mapped']} mapped, {result['delta']['unmapped']:+d} unmapped")
            print(f"  Time: {result['v01']['time_ms']:.0f}ms (v0.1) vs {result['v20']['time_ms']:.0f}ms (v2.0)")

            pdf.close()

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


def test_pubtables_comparison(n_sample=100):
    """Compare v0.1 vs v2.0 on PubTables-1M (100 tables)."""
    print(f"\n=== PUBTABLES-1M COMPARISON ({n_sample} tables) ===\n")

    # Find all XML files
    pubtables_dir = DATASET_DIR / 'pubtables-1m'
    xml_files = list(pubtables_dir.glob('*.xml'))

    # Filter valid files
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

    print(f"Testing {len(sample_files)} tables...\n")

    results_v01 = []
    results_v20 = []

    for i, xml_path in enumerate(sample_files, 1):
        if i % 25 == 0:
            print(f"  Progress: {i}/{len(sample_files)}...")

        try:
            table_id = xml_path.stem
            json_path = xml_path.parent / f'{table_id}_words.json'

            # v0.1 mode
            metrics_v01 = evaluate_grits(
                str(json_path),
                str(xml_path),
                top_only=False,
                method='max+crystal',
                full_features=False,  # v0.1
            )

            # v2.0 mode
            metrics_v20 = evaluate_grits(
                str(json_path),
                str(xml_path),
                top_only=False,
                method='max+crystal',
                full_features=True,  # v2.0
                sigma_font=SIGMA_FONT,
                sigma_hierarchy=SIGMA_HIERARCHY,
                sigma_color=SIGMA_COLOR,
            )

            if metrics_v01:
                results_v01.append(metrics_v01)
            if metrics_v20:
                results_v20.append(metrics_v20)

        except Exception as e:
            pass

    # Summary
    if results_v01 and results_v20:
        avg_v01 = {
            'grits_top': sum(r['grits_top'] for r in results_v01) / len(results_v01),
            'row_exact': sum(r['row_exact'] for r in results_v01) / len(results_v01),
            'col_exact': sum(r['col_exact'] for r in results_v01) / len(results_v01),
        }

        avg_v20 = {
            'grits_top': sum(r['grits_top'] for r in results_v20) / len(results_v20),
            'row_exact': sum(r['row_exact'] for r in results_v20) / len(results_v20),
            'col_exact': sum(r['col_exact'] for r in results_v20) / len(results_v20),
        }

        print(f"\n  Tested: {len(results_v01)} tables")
        print(f"\n  v0.1:")
        print(f"    GriTS_Top: {avg_v01['grits_top']:.1%}")
        print(f"    Row exact: {avg_v01['row_exact']:.1%}")
        print(f"    Col exact: {avg_v01['col_exact']:.1%}")

        print(f"\n  v2.0:")
        print(f"    GriTS_Top: {avg_v20['grits_top']:.1%}")
        print(f"    Row exact: {avg_v20['row_exact']:.1%}")
        print(f"    Col exact: {avg_v20['col_exact']:.1%}")

        print(f"\n  Δ:")
        print(f"    GriTS_Top: {(avg_v20['grits_top'] - avg_v01['grits_top'])*100:+.2f}pp")
        print(f"    Row exact: {(avg_v20['row_exact'] - avg_v01['row_exact'])*100:+.2f}pp")
        print(f"    Col exact: {(avg_v20['col_exact'] - avg_v01['col_exact'])*100:+.2f}pp")

    return {
        'v01': results_v01,
        'v20': results_v20,
    }


def main():
    """Run comparative test v0.1 vs v2.0."""
    print("=" * 70)
    print("MORPH v0.1 vs v2.0 — COMPARATIVE TEST")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nv2.0 settings:")
    print(f"  sigma_font = {SIGMA_FONT}")
    print(f"  sigma_hierarchy = {SIGMA_HIERARCHY}")
    print(f"  sigma_color = {SIGMA_COLOR}")

    # Set random seed
    random.seed(42)

    # HVAC comparison
    hvac_results = test_hvac_comparison()

    # PubTables comparison
    pubtables_results = test_pubtables_comparison(n_sample=100)

    # Save results
    output = {
        'date': datetime.now().isoformat(),
        'v20_settings': {
            'sigma_font': SIGMA_FONT,
            'sigma_hierarchy': SIGMA_HIERARCHY,
            'sigma_color': SIGMA_COLOR,
        },
        'hvac': hvac_results,
        'pubtables': {
            'v01_count': len(pubtables_results['v01']),
            'v20_count': len(pubtables_results['v20']),
        },
    }

    output_path = DATA_DIR / 'test_v2.0_results.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\n✓ Results saved to: {output_path}")
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
