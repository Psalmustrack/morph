"""
morph.core.layer1_typify.extract — Particle Extraction Pipeline
===============================================================

Main entry point for Layer 1: convert PDF page to typed particles.
"""

from typing import Optional
from .classify import typify_word
from .fragments import _merge_fragments


def extract_particles(page,
                      model_patterns: list = None,
                      size_patterns: list = None,
                      domain: bool = True,
                      full_features: bool = False,
                      domain_config: Optional['DomainConfig'] = None) -> list[dict]:
    """Extract and classify all words from a PDF page into particles.

    This is the main entry point for Layer 1. Each word becomes a "particle"
    with spatial coordinates and an intrinsic type.

    Particle dict keys (basic - v0.1)::

        text  — Textual content (full text, no length limit)
        x     — Horizontal center
        y     — Vertical center
        x0    — Left edge
        x1    — Right edge
        y0    — Top edge
        y1    — Bottom edge
        type  — One of PARTICLE_TYPES
        size  — Font size (points)

    Additional keys (v2.0 with full_features=True)::

        font        — Font name (e.g., "MyriadPro-Bold")
        flags       — Font flags (bold, italic, mono, serif)
        color       — RGB color as int
        origin      — (x, y) baseline point tuple
        ascender    — Font ascender height
        descender   — Font descender depth
        span_num    — Span index within line
        line_num    — Line index within block
        block_num   — Block index within page

    Pipeline::

        1. extract_words() with full_features flag
        2. typify_word() on each word
        3. _merge_fragments() to reassemble broken glyphs
        4. sense_page() [Layer 1b] to promote TEXT by spatial context

    With ``domain=False``, typify assigns only NUMERIC/UNIT/TEXT.
    Spatial sensing (Layer 1b) then promotes TEXT to structural types.

    Args:
        page: A PDF page object (MorphoPage or pdfplumber Page).
        model_patterns: (DEPRECATED) Use domain_config instead.
        size_patterns: (DEPRECATED) Use domain_config instead.
        domain: (DEPRECATED) Use domain_config instead.
        full_features: If True, extract rich PyMuPDF features (v2.0).
        domain_config: DomainConfig instance (v2.1+).

    Returns:
        List of particle dicts, spatially sensed and ready for Layer 2.
    """
    words_raw = page.extract_words(
        full_features=full_features,
        # Legacy pdfplumber args (ignored by MorphoPage)
        keep_blank_chars=True,
        x_tolerance=1.5,
        extra_attrs=["fontname", "size"],
    )
    particles = []
    for w in words_raw:
        text = w['text'].strip()
        if not text:
            continue

        # Pass font hints to typify_word (v2.0)
        font_flags = w.get('flags', 0) if full_features else 0
        font_size = w.get('size', 0)

        # Use domain_config (v2.1+) or legacy parameters
        if domain_config is not None:
            ptype = typify_word(
                text,
                font_flags=font_flags,
                font_size=font_size,
                domain_config=domain_config
            )
        else:
            # Legacy mode (backward compatibility)
            ptype = typify_word(
                text, model_patterns, size_patterns,
                domain=domain,
                font_flags=font_flags,
                font_size=font_size,
                use_fuzzy=full_features
            )

        # Basic particle (v0.1 compatibility)
        particle = {
            'text': text,  # Full text (no truncation)
            'x': (w['x0'] + w['x1']) / 2,
            'y': (w['top'] + w['bottom']) / 2,
            'y0': w['top'],
            'y1': w['bottom'],
            'x0': w['x0'],
            'x1': w['x1'],
            'type': ptype,
            'size': w.get('size', 0),
        }

        # Rich features (v2.0)
        if full_features:
            particle.update({
                'font': w.get('font', ''),
                'flags': w.get('flags', 0),
                'color': w.get('color', 0),
                'origin': w.get('origin', (0, 0)),
                'ascender': w.get('ascender', 0),
                'descender': w.get('descender', 0),
                'span_num': w.get('span_num', 0),
                'line_num': w.get('line_num', 0),
                'block_num': w.get('block_num', 0),
            })

        particles.append(particle)

    # Reassemble fragmented glyphs (e.g., "6" + ",5" + "k" + "W" → "6,5kW")
    if domain_config is not None:
        particles = _merge_fragments(particles, domain_config=domain_config)
    else:
        # Legacy mode
        particles = _merge_fragments(particles, model_patterns, size_patterns)

    # Layer 1b: spatial sensing promotes TEXT → structural types
    from morph.core import sense_page

    # v2.0 Phase 6: Extract drawings for hybrid boundary detection
    drawings = None
    if hasattr(page, 'extract_drawings'):
        drawings = page.extract_drawings()

    result = sense_page(particles, drawings=drawings)
    particles = result['particles']

    return particles
