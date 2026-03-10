#!/usr/bin/env python3
"""
Debug vertical line extraction
"""

from morph.io.reader import open_pdf

PDF_PATH = '/mnt/dati/home/Progetti/dots.ocr/brands/daikin/input/20220412 VRV 5 HR.pdf'
PAGE_NUM = 20

pdf = open_pdf(PDF_PATH)
page = pdf[PAGE_NUM]

drawings = page.extract_drawings()

# Manual vertical line extraction with debug output
vertical_count = 0
horizontal_count = 0
min_height = 5  # lowered from 30 to catch short segments

print("Checking first 50 stroke paths for vertical lines...\n")

strokes = [d for d in drawings if d.get('type') == 's'][:50]

for i, d in enumerate(strokes, 1):
    items = d.get('items', [])

    for item in items:
        if not isinstance(item, tuple) or len(item) < 3:
            continue

        cmd = item[0]
        if cmd != 'l':
            continue

        p1 = item[1]
        p2 = item[2]

        x1 = p1.x if hasattr(p1, 'x') else p1[0]
        y1 = p1.y if hasattr(p1, 'y') else p1[1]
        x2 = p2.x if hasattr(p2, 'x') else p2[0]
        y2 = p2.y if hasattr(p2, 'y') else p2[1]

        dx = abs(x2 - x1)
        dy = abs(y2 - y1)

        if dy >= min_height and dx < 3:
            vertical_count += 1
            x_mid = (x1 + x2) / 2
            print(f"{i}. VERTICAL: x={x_mid:.2f}, dy={dy:.1f}, dx={dx:.3f}")
            print(f"   ({x1:.2f}, {y1:.2f}) → ({x2:.2f}, {y2:.2f})")
        elif dx >= min_height and dy < 3:
            horizontal_count += 1

print(f"\nSummary:")
print(f"  Vertical lines (dy≥{min_height}, dx<3): {vertical_count}")
print(f"  Horizontal lines (dx≥{min_height}, dy<3): {horizontal_count}")

pdf.close()
