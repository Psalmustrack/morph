"""
morph.core.layer1_typify.classify — Particle Type Classification
================================================================

Assign intrinsic types to PDF words based on textual content.
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
                domain: bool = True,
                font_flags: int = 0,
                font_size: float = 0,
                use_fuzzy: bool = False) -> str:
    """Assign an intrinsic type to a single PDF word.

    Classification cascade (first match wins)::

        0. EXCLUDE_PATTERNS → TEXT  (marketing, navigation)
        1. Font hints (v2.0) — bold → MODEL, size<8 → NUMERIC/UNIT
        2. Semantic patterns (v2.0) — DATE, EMAIL, REFERENCE, STANDARD
        3. size_patterns    → SIZE_HEADER
        4. model_patterns   → MODEL
        5. "N kW" format    → KW_HEADER
        6. UNIT_SET         → UNIT
        7. Numeric regex    → NUMERIC
        8. SECTION_TERMS    → SECTION (with fuzzy matching if use_fuzzy=True)
        9. SPEC_TERMS       → SPEC_LABEL (with fuzzy matching if use_fuzzy=True)
        10. fallback        → TEXT

    With ``domain=False``, steps 3-5 and 8-9 are skipped. This mode is used
    when spatial sensing (Layer 1b) handles domain classification instead.

    Font hints (v2.0):
        - Bold (flags & 0x10) + alphanumeric → likely MODEL
        - Size < 8 + numeric → likely NUMERIC/UNIT
        - Helps eliminate ~25% MODEL misclassifications

    Fuzzy matching (v2.0):
        - use_fuzzy=True enables typo/OCR tolerance for SPEC_LABEL/SECTION
        - "Capacita" ≈ "Capacità" (80%+ match)
        - Requires rapidfuzz library

    Args:
        text: The word's text content.
        model_patterns: Compiled regex list for brand-specific model codes.
        size_patterns: Compiled regex list for size/capacity column headers.
        domain: If False, skip domain-specific vocabulary and patterns.
        font_flags: Font flags (0x10=bold, 0x2=italic, 0x4=serif, 0x8=mono).
        font_size: Font size in points (for NUMERIC/UNIT hint).
        use_fuzzy: Enable fuzzy matching for SPEC_LABEL/SECTION (v2.0).

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

    # 1. Font hints (v2.0) — use typography to guide classification
    is_bold = (font_flags & 0x10) != 0  # 0x10 = bold flag
    is_small = font_size > 0 and font_size < 8

    # Bold + alphanumeric → likely MODEL (eliminates ~25% MODEL errors)
    if is_bold and domain and re.match(r'^[A-Z0-9][A-Z0-9\-]{2,}$', t):
        return 'MODEL'

    # Small size + numeric → likely NUMERIC/UNIT (not headers)
    if is_small and re.match(r'^[\d.,]+$', t):
        return 'NUMERIC'

    # 2. Semantic patterns (v2.0) — universal patterns across domains
    # DATE: "2023-01-15", "15/01/2023", "Gen 2023", "Jan 2023"
    if re.match(r'^\d{4}-\d{2}-\d{2}$', t) or re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', t):
        return 'TEXT'  # Dates are metadata, not specs
    if re.match(r'^(Gen|Feb|Mar|Apr|Mag|Giu|Lug|Ago|Set|Ott|Nov|Dic|Jan|May|Jun|Jul|Aug|Sep|Oct|Dec)\s+\d{4}$', t):
        return 'TEXT'

    # EMAIL: "info@domain.com"
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', t):
        return 'TEXT'

    # REFERENCE/STANDARD: "EN 14511", "ISO 9001", "CE", "ErP"
    if re.match(r'^(EN|ISO|IEC|ASHRAE)\s*\d+', t):
        return 'TEXT'  # Standards are metadata
    if t in ('CE', 'ErP', 'RoHS', 'WEEE'):
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
        # 6. Section header (with fuzzy matching if enabled)
        words_in = set(tl.split())
        if words_in & SECTION_TERMS and len(t) > 8:
            return 'SECTION'

        # Fuzzy match for SECTION (typo/OCR tolerance)
        if use_fuzzy and len(t) > 8:
            try:
                from rapidfuzz import fuzz
                for section_term in SECTION_TERMS:
                    if fuzz.ratio(tl, section_term) >= 80:  # 80% similarity threshold
                        return 'SECTION'
            except ImportError:
                pass  # Soft dependency — skip fuzzy if not available

        # 7. Spec label (word match or substring match)
        if words_in & SPEC_TERMS:
            return 'SPEC_LABEL'
        if len(t) > 12 and any(kw in tl for kw in SPEC_SUBSTRINGS):
            return 'SPEC_LABEL'

        # Fuzzy match for SPEC_LABEL (typo/OCR tolerance)
        if use_fuzzy and len(t) > 5:
            try:
                from rapidfuzz import fuzz
                for spec_term in SPEC_TERMS:
                    if fuzz.ratio(tl, spec_term) >= 85:  # 85% similarity threshold
                        return 'SPEC_LABEL'
            except ImportError:
                pass  # Soft dependency — skip fuzzy if not available

    return 'TEXT'
