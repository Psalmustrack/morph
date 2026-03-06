"""
morph.core — The three-layer morphogenetic engine.

Layer 1  (typify): Gene expression — each word gets an intrinsic type
Layer 1b (sense):  Cellular differentiation — spatial context promotes types
Layer 2  (field):  Tissue formation — the morphogenetic field equation connects particles

The core is domain-invariant: only Layer 1 changes between brands
(via regex model patterns). Layers 1b and 2 are universal.
"""

from morph.core.typify import extract_particles, typify_word, PARTICLE_TYPES
from morph.core.sense import sense_page, detect_columns
from morph.core.field import extract_page

__all__ = [
    'extract_particles', 'typify_word', 'PARTICLE_TYPES',
    'sense_page', 'detect_columns',
    'extract_page',
]
