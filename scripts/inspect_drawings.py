#!/usr/bin/env python3
"""
Inspect drawing types in Daikin catalog

Understand what types of drawings are in the 923 elements.
"""

from collections import Counter
from morph.io.reader import open_pdf

PDF_PATH = '/mnt/dati/home/Progetti/dots.ocr/brands/daikin/input/20220412 VRV 5 HR.pdf'
PAGE_NUM = 20

pdf = open_pdf(PDF_PATH)
page = pdf[PAGE_NUM]

drawings = page.extract_drawings()
print(f"Total drawings: {len(drawings)}\n")

# Count by type
types = Counter(d.get('type', 'unknown') for d in drawings)
print("Drawing types:")
for dtype, count in types.most_common():
    print(f"  {dtype}: {count}")

# Analyze first few of each type
print("\n--- Sample drawings ---")
for dtype in ['l', 'r', 'c', 're']:  # line, rect, curve, re (rectangle path)
    samples = [d for d in drawings if d.get('type') == dtype][:3]
    if samples:
        print(f"\n{dtype} (line/rect/curve) - {len([d for d in drawings if d.get('type') == dtype])} total:")
        for i, d in enumerate(samples, 1):
            rect = d.get('rect', (0, 0, 0, 0))
            x0, y0, x1, y1 = rect
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            print(f"  {i}. rect=({x0:.1f}, {y0:.1f}, {x1:.1f}, {y1:.1f}), dx={dx:.1f}, dy={dy:.1f}, items={len(d.get('items', []))}")

pdf.close()
