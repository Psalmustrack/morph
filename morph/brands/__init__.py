"""
morph.brands — Brand-Specific Pattern Definitions
===================================================

Each brand provides compiled regex patterns for:
    - MODEL_PATTERNS: model code recognition (e.g., "RAS-4FSXNME" → MODEL)
    - SIZE_HEADER_PATTERNS: size column headers (e.g., "50B" → SIZE_HEADER)

These are the only components that change between brands.
The core engine (sense + field) is invariant.

Available brands: hitachi, daikin, toshiba, mitsubishi, midea

Usage::

    from morph.brands import get_brand_patterns

    model_pats, size_pats = get_brand_patterns('hitachi')

Author: Eugeniu Tacu, 2026
"""

import importlib

# Available brands — correspond to .py files in this directory
AVAILABLE_BRANDS = (
    'hitachi', 'daikin', 'toshiba', 'mitsubishi', 'midea',
)

# Cache of loaded brand modules
_BRAND_CACHE: dict[str, object] = {}


def _load_brand(brand: str):
    """Load a brand module and cache it."""
    if brand in _BRAND_CACHE:
        return _BRAND_CACHE[brand]
    mod = importlib.import_module(f'.{brand}', package='morph.brands')
    _BRAND_CACHE[brand] = mod
    return mod


def get_brand_patterns(brand: str) -> tuple[list, list]:
    """Get (MODEL_PATTERNS, SIZE_HEADER_PATTERNS) for a brand.

    Args:
        brand: Brand name (one of :data:`AVAILABLE_BRANDS`).

    Returns:
        Tuple of (model_patterns, size_header_patterns) — both lists
        of compiled regex objects.
    """
    mod = _load_brand(brand)
    return mod.MODEL_PATTERNS, getattr(mod, 'SIZE_HEADER_PATTERNS', [])


def get_all_patterns() -> dict[str, tuple[list, list]]:
    """Load patterns for all brands.

    Returns:
        Dict ``{brand: (MODEL_PATTERNS, SIZE_HEADER_PATTERNS)}``.
    """
    result = {}
    for brand in AVAILABLE_BRANDS:
        result[brand] = get_brand_patterns(brand)
    return result


def detect_brand(text: str) -> str | None:
    """Detect brand from a text string (e.g., a model code).

    Tests all brands in order. First match wins.

    Args:
        text: Text to match against all brand patterns.

    Returns:
        Brand name, or None if no match.
    """
    for brand in AVAILABLE_BRANDS:
        model_pats, size_pats = get_brand_patterns(brand)
        for pat in model_pats:
            if pat.match(text):
                return brand
        for pat in size_pats:
            if pat.match(text):
                return brand
    return None
