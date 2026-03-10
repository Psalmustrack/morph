"""
Universal domain configuration.

No domain-specific vocabulary. Pure spatial detection based on geometry,
typography, and layout. Use this for documents without known domain patterns
or for generic table extraction.
"""

from .base import DomainConfig


UNIVERSAL = DomainConfig(
    name="universal",

    # No patterns or vocabulary
    model_patterns=[],
    size_patterns=[],
    spec_terms=set(),
    spec_substrings=set(),
    section_terms=set(),
    unit_set=set(),
    exclude_patterns=[],

    # Behavior
    use_fuzzy=False,  # No fuzzy matching without vocabulary
    require_models=False,  # Pure spatial detection
)
