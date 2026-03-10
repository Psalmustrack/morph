"""
morph.core.layer1_typify — Layer 1: Particle Type Classification
==================================================================

Type classification layer that assigns intrinsic types to PDF words
based on their textual content (no spatial information at this stage).

Public API:
    - typify_word: Classify a single word
    - extract_particles: Convert PDF page to typed particles

Author: Eugeniu Tacu, 2026
"""

from .classify import typify_word, PARTICLE_TYPES
from .extract import extract_particles

__all__ = [
    'typify_word',
    'extract_particles',
    'PARTICLE_TYPES',
]
