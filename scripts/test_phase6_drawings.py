#!/usr/bin/env python3
"""
Test Phase 6: Hybrid Boundary Detection

Verifies that drawing-based column detection works on bordered tables.
Uses Daikin VRV catalog p.20 which has 923 vertical/horizontal lines.

Expected:
- Without drawings: geometric clustering
- With drawings: exact boundary detection from vertical lines
"""

from pathlib import Path

# Morph imports
from morph.io.reader import open_pdf
from morph.core.typify import extract_particles
from morph.core.sense import detect_columns, _extract_vertical_lines

# Test file
PDF_PATH = '/mnt/dati/home/Progetti/dots.ocr/brands/daikin/input/20220412 VRV 5 HR.pdf'
PAGE_NUM = 20  # FXFA series table


def test_drawing_based_detection():
    """Compare column detection with/without drawings."""
    print("=" * 70)
    print("PHASE 6: HYBRID BOUNDARY DETECTION TEST")
    print("=" * 70)
    print(f"\nFile: {Path(PDF_PATH).name}")
    print(f"Page: {PAGE_NUM + 1}")

    # Open PDF
    pdf = open_pdf(PDF_PATH)
    page = pdf[PAGE_NUM]

    print(f"\nPage size: {page.width:.0f} x {page.height:.0f} px")

    # Extract drawings
    drawings = page.extract_drawings()
    print(f"Drawings: {len(drawings)} elements")

    # Extract vertical lines
    vertical_xs = _extract_vertical_lines(drawings)
    print(f"Vertical lines: {len(vertical_xs)} lines")
    if vertical_xs:
        print(f"  X positions: {vertical_xs[:5]}..." if len(vertical_xs) > 5 else f"  X positions: {vertical_xs}")

    # Extract particles (v2.0 mode)
    particles = extract_particles(page, full_features=True)
    print(f"\nParticles: {len(particles)} total")

    # Count structured particles
    structured_types = {'NUMERIC', 'SPEC_LABEL', 'MODEL', 'MODEL_CODE',
                        'UNIT', 'SECTION', 'SIZE_HEADER', 'KW_HEADER'}
    structured = [p for p in particles if p['type'] in structured_types]
    print(f"Structured: {len(structured)} particles")

    # Test 1: WITHOUT drawings (v0.1 geometric clustering)
    print("\n--- WITHOUT DRAWINGS (geometric clustering) ---")
    cols_geometric = detect_columns(particles, drawings=None)
    print(f"Columns detected: {len(cols_geometric)}")
    for i, col in enumerate(cols_geometric, 1):
        print(f"  Col {i}: x={col['x']:.1f}, particles={col['count']}, y_range=[{col['y_min']:.1f}, {col['y_max']:.1f}]")

    # Test 2: WITH drawings (v2.0 hybrid detection)
    print("\n--- WITH DRAWINGS (hybrid detection) ---")
    cols_hybrid = detect_columns(particles, drawings=drawings)
    print(f"Columns detected: {len(cols_hybrid)}")
    for i, col in enumerate(cols_hybrid, 1):
        print(f"  Col {i}: x={col['x']:.1f}, particles={col['count']}, y_range=[{col['y_min']:.1f}, {col['y_max']:.1f}]")

    # Compare
    print("\n--- COMPARISON ---")
    print(f"Δ columns: {len(cols_hybrid) - len(cols_geometric):+d}")

    if cols_hybrid != cols_geometric:
        print("✓ Hybrid detection differs from geometric (expected)")
        print(f"  Drawing-based: {len(cols_hybrid)} columns (exact boundaries)")
        print(f"  Geometric: {len(cols_geometric)} columns (clustering)")
    else:
        print("⚠ No difference detected (unexpected if drawings exist)")

    pdf.close()

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    test_drawing_based_detection()
