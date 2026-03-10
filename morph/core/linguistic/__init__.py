"""
Linguistic Analysis Module - Layer 1.5

Universal linguistic pattern recognition for particle refinement.

This module sits between Layer 1 (typify) and Layer 2 (field),
applying universal linguistic rules to refine particle classifications.

Main entry point:
    refine_particles() - refines particle type classifications

Submodules:
    patterns - structural format recognition
    repetition - repeated value detection
    punctuation - M_p (Punctuation Multiplier) and spacing analysis
    refine - main refinement orchestrator
"""

from .refine import refine_particles, apply_linguistic_refinement, analyze_refinement_impact
from .patterns import analyze_format, classify_pattern, is_likely_header, is_likely_unit
from .repetition import detect_repetitions, get_repeated_texts, is_repeated_value
from .punctuation import calculate_Mp, analyze_spacing, analyze_cell_boundaries

__all__ = [
    # Main API
    'refine_particles',
    'apply_linguistic_refinement',
    'analyze_refinement_impact',

    # Pattern analysis
    'analyze_format',
    'classify_pattern',
    'is_likely_header',
    'is_likely_unit',

    # Repetition detection
    'detect_repetitions',
    'get_repeated_texts',
    'is_repeated_value',

    # Punctuation and spacing
    'calculate_Mp',
    'analyze_spacing',
    'analyze_cell_boundaries',
]
