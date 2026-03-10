#!/usr/bin/env python3
"""
Inspect drawing items (path segments) in Daikin catalog
"""

from morph.io.reader import open_pdf

PDF_PATH = '/mnt/dati/home/Progetti/dots.ocr/brands/daikin/input/20220412 VRV 5 HR.pdf'
PAGE_NUM = 20

pdf = open_pdf(PDF_PATH)
page = pdf[PAGE_NUM]

drawings = page.extract_drawings()

print("Sample drawing items (first 10 stroke paths):\n")
strokes = [d for d in drawings if d.get('type') == 's'][:10]

for i, d in enumerate(strokes, 1):
    rect = d.get('rect', (0, 0, 0, 0))
    items = d.get('items', [])
    print(f"{i}. type='s', rect={rect}, {len(items)} items")

    # Show first 3 items
    for j, item in enumerate(items[:3], 1):
        # item is typically a tuple like ('l', (x, y)) or ('m', (x, y)) or ('c', ...)
        print(f"     item {j}: {item}")

    if len(items) > 3:
        print(f"     ... ({len(items) - 3} more items)")
    print()

pdf.close()
