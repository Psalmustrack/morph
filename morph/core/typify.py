"""
morph.core.typify — Layer 1: Particle Type Classification (Gene Expression)
============================================================================

Each word extracted from a PDF page receives an intrinsic type based solely
on its textual content — no spatial information is used at this stage.

Biological analogy: gene expression. A cell's identity is first determined
by its internal DNA (content), before external signals (position) refine it.

Particle types (8 total)::

    MODEL        — Product model code (e.g., "RAS-4FSXNME")
    SIZE_HEADER  — Size/capacity column header (e.g., "50B")
    KW_HEADER    — Power column header (e.g., "4 kW")
    UNIT         — Unit of measurement (e.g., "kW", "dB(A)")
    NUMERIC      — Numeric value (e.g., "4.50", "204x840x840")
    SECTION      — Section heading (e.g., "Specifications")
    SPEC_LABEL   — Technical specification label (e.g., "COP", "Sound pressure")
    TEXT         — Unclassified text (default; may be promoted by Layer 1b)

Pipeline::

    PDF page → PyMuPDF words → typify_word() → _merge_fragments() → particles
                                                                        ↓
                                                              sense_page() [Layer 1b]

Only this layer changes between brands (via model/size regex patterns).
With ``domain=False``, only universal types (NUMERIC, UNIT, TEXT) are assigned —
the domain-specific types emerge later from spatial sensing.

Author: Eugeniu Tacu, 2026
"""

import re

from morph.brands import get_brand_patterns, AVAILABLE_BRANDS  # noqa: F401
from morph.brands.universal import (
    UNIT_SET, SPEC_TERMS, SPEC_SUBSTRINGS,
    SECTION_TERMS, EXCLUDE_PATTERNS,
)

# The 8 particle types, ordered by specificity
PARTICLE_TYPES = (
    'MODEL', 'SIZE_HEADER', 'KW_HEADER', 'UNIT',
    'NUMERIC', 'SECTION', 'SPEC_LABEL', 'TEXT',
)


def typify_word(text: str,
                model_patterns: list = None,
                size_patterns: list = None,
                domain: bool = True) -> str:
    """Assign an intrinsic type to a single PDF word.

    Classification cascade (first match wins)::

        0. EXCLUDE_PATTERNS → TEXT  (marketing, navigation)
        1. size_patterns    → SIZE_HEADER
        2. model_patterns   → MODEL
        3. "N kW" format    → KW_HEADER
        4. UNIT_SET         → UNIT
        5. Numeric regex    → NUMERIC
        6. SECTION_TERMS    → SECTION
        7. SPEC_TERMS       → SPEC_LABEL
        8. fallback         → TEXT

    With ``domain=False``, steps 1-3 and 6-7 are skipped. This mode is used
    when spatial sensing (Layer 1b) handles domain classification instead.

    Args:
        text: The word's text content.
        model_patterns: Compiled regex list for brand-specific model codes.
        size_patterns: Compiled regex list for size/capacity column headers.
        domain: If False, skip domain-specific vocabulary and patterns.

    Returns:
        One of :data:`PARTICLE_TYPES`.
    """
    t = text.strip()
    if not t:
        return 'TEXT'
    tl = t.lower().rstrip('.')

    # 0. Exclude marketing / navigation patterns
    for pat in EXCLUDE_PATTERNS:
        if pat.match(t):
            return 'TEXT'

    # --- Domain-specific block (skip if domain=False) ---
    if domain:
        # 1. SIZE_HEADER (must come BEFORE MODEL — "50B" is a size, not a model)
        if size_patterns:
            for pat in size_patterns:
                if pat.match(t):
                    return 'SIZE_HEADER'

        # 2. Model code
        if model_patterns:
            for pat in model_patterns:
                if pat.match(t):
                    return 'MODEL'

        # 3. kW header (e.g., "4 kW", "10 kW", "6,5kW")
        if re.match(r'^\d+[.,]?\d*\s*kW$', t):
            return 'KW_HEADER'

    # 4. Pure unit of measurement
    if tl.strip() in UNIT_SET:
        return 'UNIT'

    # 5. Numeric value (with various formats)
    if re.match(r'^\(\d{1,2}\)$', t):        # Note references: (1), (2)
        return 'TEXT'
    cleaned = re.sub(r'\s', '', tl)
    if cleaned and re.match(r'^[\d.,/\-()x×°%~+:]+$', cleaned) and any(c.isdigit() for c in cleaned):
        return 'NUMERIC'
    if re.match(r'^[\d.]+x[\d.]+x[\d.]+$', t.replace(',', '')):  # Dimensions
        return 'NUMERIC'
    if re.match(r'^-?\d+[~]', t):              # Range: "-5~43"
        return 'NUMERIC'
    if re.match(r'^\d+N?~/', t):               # Power supply: "3N~/50/380~415"
        return 'NUMERIC'
    if re.match(r'^R\d{3}', t):                # Refrigerant: "R410A", "R290"
        return 'NUMERIC'

    # --- Domain-specific vocabulary (skip if domain=False) ---
    if domain:
        # 6. Section header
        words_in = set(tl.split())
        if words_in & SECTION_TERMS and len(t) > 8:
            return 'SECTION'

        # 7. Spec label (word match or substring match)
        if words_in & SPEC_TERMS:
            return 'SPEC_LABEL'
        if len(t) > 12 and any(kw in tl for kw in SPEC_SUBSTRINGS):
            return 'SPEC_LABEL'

    return 'TEXT'


def _merge_fragments(particles: list[dict],
                     model_patterns: list = None,
                     size_patterns: list = None,
                     y_tolerance: float = 2,
                     x_gap_max: float = 8) -> list[dict]:
    """Reassemble fragmented glyphs on the same line.

    Some PDFs encode "6,5 kW" as 4 separate glyphs: "6", ",", "5", "kW".
    This pass fuses adjacent short fragments and re-classifies the result.

    Only fuses sequences of "atomic" particles (text <= 4 chars each,
    close in X) — does not touch already-complete words.

    Args:
        particles: List of typed particles.
        model_patterns: Brand-specific model patterns for re-typing.
        size_patterns: Brand-specific size patterns for re-typing.
        y_tolerance: Max Y gap to consider same row (px).
        x_gap_max: Max X gap between adjacent fragments (px).

    Returns:
        Particle list with fragments merged where beneficial.
    """
    if not particles:
        return particles

    # Group by row (same Y within tolerance)
    rows: list[list[dict]] = []
    for p in sorted(particles, key=lambda p: (p['y0'], p['x0'])):
        if rows and abs(p['y0'] - rows[-1][0]['y0']) <= y_tolerance:
            rows[-1].append(p)
        else:
            rows.append([p])

    merged = []
    for row in rows:
        if len(row) < 2:
            merged.extend(row)
            continue

        row.sort(key=lambda p: p['x0'])

        i = 0
        while i < len(row):
            # Find sequence of short adjacent fragments
            j = i
            while (j + 1 < len(row)
                   and len(row[j]['text']) <= 4
                   and len(row[j + 1]['text']) <= 4
                   and (row[j + 1]['x0'] - row[j]['x1']) < x_gap_max):
                j += 1

            if j > i:
                frag_texts = [row[k]['text'] for k in range(i, j + 1)]
                combined = ''.join(frag_texts)
                new_type = typify_word(combined, model_patterns, size_patterns)

                # Only merge if resulting type is "useful" (not generic TEXT)
                if new_type != 'TEXT':
                    y1_max = max(row[k]['y1'] for k in range(i, j + 1))
                    merged.append({
                        'text': combined[:80],
                        'x': (row[i]['x0'] + row[j]['x1']) / 2,
                        'y': (row[i]['y0'] + y1_max) / 2,
                        'y0': row[i]['y0'],
                        'y1': y1_max,
                        'x0': row[i]['x0'],
                        'x1': row[j]['x1'],
                        'type': new_type,
                        'size': row[i]['size'],
                    })
                    i = j + 1
                    continue

            merged.append(row[i])
            i += 1

    return merged


def extract_particles(page,
                      model_patterns: list = None,
                      size_patterns: list = None,
                      domain: bool = True) -> list[dict]:
    """Extract and classify all words from a PDF page into particles.

    This is the main entry point for Layer 1. Each word becomes a "particle"
    with spatial coordinates and an intrinsic type.

    Particle dict keys::

        text  — Textual content (truncated to 80 chars)
        x     — Horizontal center
        y     — Vertical center
        x0    — Left edge
        x1    — Right edge
        y0    — Top edge
        y1    — Bottom edge
        type  — One of PARTICLE_TYPES
        size  — Font size (points)

    Pipeline::

        1. extract_words() with x_tolerance=1.5
        2. typify_word() on each word
        3. _merge_fragments() to reassemble broken glyphs
        4. sense_page() [Layer 1b] to promote TEXT by spatial context

    With ``domain=False``, typify assigns only NUMERIC/UNIT/TEXT.
    Spatial sensing (Layer 1b) then promotes TEXT to structural types.

    Args:
        page: A PDF page object (MorphoPage or pdfplumber Page).
        model_patterns: Brand-specific model code regex list.
        size_patterns: Brand-specific size header regex list.
        domain: If False, defer domain classification to sensing.

    Returns:
        List of particle dicts, spatially sensed and ready for Layer 2.
    """
    words_raw = page.extract_words(
        keep_blank_chars=True,
        x_tolerance=1.5,
        extra_attrs=["fontname", "size"],
    )
    particles = []
    for w in words_raw:
        text = w['text'].strip()
        if not text:
            continue
        ptype = typify_word(text, model_patterns, size_patterns, domain=domain)
        particles.append({
            'text': text[:80],
            'x': (w['x0'] + w['x1']) / 2,
            'y': (w['top'] + w['bottom']) / 2,
            'y0': w['top'],
            'y1': w['bottom'],
            'x0': w['x0'],
            'x1': w['x1'],
            'type': ptype,
            'size': w.get('size', 0),
        })

    # Reassemble fragmented glyphs (e.g., "6" + ",5" + "k" + "W" → "6,5kW")
    particles = _merge_fragments(particles, model_patterns, size_patterns)

    # Layer 1b: spatial sensing promotes TEXT → structural types
    from morph.core.sense import sense_page
    result = sense_page(particles)
    particles = result['particles']

    return particles
