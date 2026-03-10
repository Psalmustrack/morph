"""
morph.core — The three-layer morphogenetic engine (v2.1 - layer directories).

Layer 1  (layer1_typify):  Gene expression — each word gets an intrinsic type
Layer 1b (layer1b_sense):  Cellular differentiation — spatial context promotes types
Layer 2  (layer2_field):   Tissue formation — the morphogenetic field equation connects particles

The core is domain-invariant: only Layer 1 changes between brands
(via regex model patterns). Layers 1b and 2 are universal.

v2.1 Refactoring: Large modules split into layer directories for maintainability.
Backward compatibility: old imports (morph.core.field, etc.) still work.
"""

# Layer 1: Typify (intrinsic type classification)
from morph.core.layer1_typify import extract_particles, typify_word, PARTICLE_TYPES

# Layer 1b: Sense (spatial promotion)
from morph.core.layer1b_sense import sense_page, detect_columns

# Layer 2: Field (morphogenetic equation)
from morph.core.layer2_field import extract_page

__all__ = [
    'extract_particles', 'typify_word', 'PARTICLE_TYPES',
    'sense_page', 'detect_columns',
    'extract_page',
]
