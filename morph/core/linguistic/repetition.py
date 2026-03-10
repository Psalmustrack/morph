"""
Repetition Detection Module - Universal pattern for repeated values

This module detects when the same value appears multiple times on the same Y coordinate.
This is a universal indicator that the value is DATA, not a HEADER.

Example:
    Y=328.3: "Refrigerante" (X=83) | "R32" (X=222) | "R32" (X=261) | "R32" (X=301)
                   ↑ HEADER                              ↑ REPEATED VALUES (3x)
"""

from collections import defaultdict
from typing import List, Dict, Set, Any


def detect_repetitions(particles: List[dict], y_tolerance: float = 5.0) -> Dict[str, dict]:
    """
    Find particles that repeat multiple times on the same Y coordinate.

    Repeated values are almost always DATA, not HEADERS or SPEC_LABELS.

    Args:
        particles: List of particle dicts with 'text', 'x', 'y' keys
        y_tolerance: Y-coordinate tolerance for grouping (default 5.0)

    Returns:
        Dictionary mapping text -> repetition info:
        {
            "R32": {
                "count": 3,
                "y_values": [328.3],
                "particles": [particle1, particle2, particle3],
                "x_positions": [222.1, 261.8, 301.5]
            }
        }
    """
    # Group particles by Y coordinate (with tolerance)
    y_groups = defaultdict(list)

    for particle in particles:
        if 'y' not in particle or 'text' not in particle:
            continue

        # Round Y to tolerance level
        y_rounded = round(particle['y'] / y_tolerance) * y_tolerance
        y_groups[y_rounded].append(particle)

    # Find repetitions within each Y group
    repetitions = {}

    for y_coord, group in y_groups.items():
        # Count text occurrences
        text_counts = defaultdict(list)
        for particle in group:
            text = particle.get('text', '')
            if text:
                text_counts[text].append(particle)

        # Record texts that appear 3+ times
        for text, occurrences in text_counts.items():
            if len(occurrences) >= 3:
                repetitions[text] = {
                    'count': len(occurrences),
                    'y_values': [y_coord],
                    'particles': occurrences,
                    'x_positions': [p.get('x', 0) for p in occurrences]
                }

    return repetitions


def get_repeated_texts(particles: List[dict], y_tolerance: float = 5.0) -> Set[str]:
    """
    Get set of texts that are repeated 3+ times on same Y.

    This is a simplified version of detect_repetitions() that just returns
    the set of repeated text values.

    Args:
        particles: List of particle dicts
        y_tolerance: Y-coordinate tolerance

    Returns:
        Set of repeated text values
    """
    repetitions = detect_repetitions(particles, y_tolerance)
    return set(repetitions.keys())


def is_repeated_value(particle: dict, all_particles: List[dict], y_tolerance: float = 5.0) -> bool:
    """
    Check if a single particle is part of a repeated pattern.

    Args:
        particle: Particle to check
        all_particles: Full list of particles
        y_tolerance: Y-coordinate tolerance

    Returns:
        True if this particle's text appears 3+ times on same Y
    """
    text = particle.get('text', '')
    if not text:
        return False

    y = particle.get('y', 0)
    y_rounded = round(y / y_tolerance) * y_tolerance

    # Count occurrences of same text on same Y
    count = 0
    for p in all_particles:
        if p.get('text') == text:
            p_y = p.get('y', 0)
            p_y_rounded = round(p_y / y_tolerance) * y_tolerance
            if p_y_rounded == y_rounded:
                count += 1

    return count >= 3


def analyze_repetition_pattern(particles: List[dict], y_tolerance: float = 5.0) -> Dict[str, Any]:
    """
    Analyze repetition patterns across all particles.

    Returns statistics about repetitions for debugging/analysis.

    Args:
        particles: List of particles
        y_tolerance: Y-coordinate tolerance

    Returns:
        Dictionary with repetition statistics
    """
    repetitions = detect_repetitions(particles, y_tolerance)

    return {
        'total_repeated_texts': len(repetitions),
        'repeated_texts': list(repetitions.keys()),
        'max_repetition_count': max((r['count'] for r in repetitions.values()), default=0),
        'repetitions_detail': repetitions
    }
