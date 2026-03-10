"""
Particle Refinement Module - Layer 1.5

This module refines particle type classifications using universal linguistic patterns.
It sits between Layer 1 (typify) and Layer 2 (field).

The refinement uses three universal principles:
1. Pattern Recognition - structural format analysis
2. Repetition Detection - repeated values are data, not headers
3. Spacing Analysis - large gaps separate different semantic units

These principles are domain-independent and work for any table/document.
"""

from typing import List, Dict, Any, Union, Tuple
from .patterns import analyze_format, is_likely_header, is_likely_unit
from .repetition import get_repeated_texts


def refine_particles(particles: List[dict]) -> List[dict]:
    """
    Refine particle type classifications using linguistic analysis.

    This is Layer 1.5: sits between extract_particles() and extract_page().

    Rules (universal, not domain-specific):
    1. If text repeats 3+ times on same Y → TYPE = TEXT (not SPEC_LABEL)
    2. If format is "xx(y)" and short → TYPE = UNIT (not SPEC_LABEL)
    3. If format is long Title Case phrase → TYPE = SPEC_LABEL (not TEXT)
    4. If format is ALPHANUMERIC_CODE and repeated → TYPE = TEXT (not NUMERIC)

    Args:
        particles: List of particle dicts from extract_particles()

    Returns:
        List of refined particles with corrected TYPE field
    """
    if not particles:
        return particles

    # Step 1: Detect repeated texts
    repeated_texts = get_repeated_texts(particles)

    # Step 2: Refine each particle
    refined = []
    for particle in particles:
        refined_particle = particle.copy()

        # Get current classification
        current_type = particle.get('type', 'UNKNOWN')
        text = particle.get('text', '')

        if not text:
            refined.append(refined_particle)
            continue

        # Analyze format
        fmt = analyze_format(text)

        # RULE 1: Repeated values are TEXT/VALUE, not SPEC_LABEL
        if text in repeated_texts:
            if current_type in ['SPEC_LABEL', 'HEADER']:
                refined_particle['type'] = 'TEXT'
                refined_particle['_refinement'] = 'repeated_value'

        # RULE 2: Units with parentheses are UNIT, not SPEC_LABEL
        elif is_likely_unit(text):
            if current_type == 'SPEC_LABEL':
                refined_particle['type'] = 'UNIT'
                refined_particle['_refinement'] = 'unit_format'

        # RULE 3: Long Title Case phrases are SPEC_LABEL, not TEXT
        elif is_likely_header(text):
            if current_type in ['TEXT', 'UNKNOWN']:
                refined_particle['type'] = 'SPEC_LABEL'
                refined_particle['_refinement'] = 'header_format'

        # RULE 4: Short codes that are repeated should be TEXT, not MODEL
        elif fmt['pattern'] == 'ALPHANUMERIC_CODE' and text in repeated_texts:
            if current_type == 'MODEL':
                refined_particle['type'] = 'TEXT'
                refined_particle['_refinement'] = 'repeated_code'

        # RULE 5: Pure numeric repeated values are NUMERIC, not SPEC_LABEL
        elif fmt['pattern'] in ['NUMERIC', 'NUMERIC_DECIMAL'] and text in repeated_texts:
            if current_type == 'SPEC_LABEL':
                refined_particle['type'] = 'NUMERIC'
                refined_particle['_refinement'] = 'repeated_numeric'

        refined.append(refined_particle)

    return refined


def analyze_refinement_impact(original: List[dict], refined: List[dict]) -> Dict[str, Any]:
    """
    Analyze the impact of refinement on particle classifications.

    Useful for debugging and validation.

    Args:
        original: Original particles from extract_particles()
        refined: Refined particles from refine_particles()

    Returns:
        Dictionary with refinement statistics
    """
    changes = []

    for orig, ref in zip(original, refined):
        orig_type = orig.get('type', 'UNKNOWN')
        ref_type = ref.get('type', 'UNKNOWN')

        if orig_type != ref_type:
            changes.append({
                'text': orig.get('text', ''),
                'x': orig.get('x', 0),
                'y': orig.get('y', 0),
                'original_type': orig_type,
                'refined_type': ref_type,
                'refinement': ref.get('_refinement', 'unknown')
            })

    # Group by refinement reason
    by_reason = {}
    for change in changes:
        reason = change['refinement']
        if reason not in by_reason:
            by_reason[reason] = []
        by_reason[reason].append(change)

    return {
        'total_changes': len(changes),
        'changes': changes,
        'by_reason': by_reason,
        'change_rate': len(changes) / len(original) if original else 0
    }


def apply_linguistic_refinement(particles: List[dict], verbose: bool = False) -> Union[List[dict], Tuple[List[dict], Dict[str, Any]]]:
    """
    Apply linguistic refinement and optionally return analysis.

    This is the main entry point for Layer 1.5.

    Args:
        particles: Original particles from extract_particles()
        verbose: If True, return (refined_particles, analysis)

    Returns:
        If verbose=False: refined particles
        If verbose=True: (refined_particles, analysis_dict)
    """
    refined = refine_particles(particles)

    if verbose:
        analysis = analyze_refinement_impact(particles, refined)
        return refined, analysis
    else:
        return refined
