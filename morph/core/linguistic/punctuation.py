"""
Punctuation and Spacing Module - M_p (Punctuation Multiplier) from V3

This module implements the M_p concept from Morph V3 (Fluid Text).
M_p modulates the morphogenetic field based on punctuation and spacing.

M_p Values (V3 Theory):
    - 0.0: Period (.) → WALL / end of sentence
    - 0.4: Comma (,) → PAUSE (weak context)
    - 0.8: Comma (,) → PAUSE (strong context)
    - 1.0: Normal flow
    - 1.5: Hyphen (-) → WORMHOLE / strong connection

For tables, "spacing" acts like punctuation:
    - Large gap between cells → WALL (M_p ≈ 0)
    - Small gap → FLOW (M_p ≈ 1.0)
"""

import string
from typing import List, Dict


def calculate_Mp(char: str, context: str = '') -> float:
    """
    Calculate M_p (Punctuation Multiplier) for a character.

    Based on V3 theory of Fluid Text.

    Args:
        char: The punctuation character
        context: Optional context for context-aware M_p

    Returns:
        M_p value (0.0 to 1.5)
    """
    if char == '.':
        return 0.0  # WALL - end of sentence

    if char == ',':
        # Context-aware comma (simplified for now)
        return 0.4 if len(context) < 20 else 0.8  # PAUSE

    if char == '-':
        return 1.5  # WORMHOLE - strong connection

    if char in '()':
        return 0.8  # PARENTHESIS - note/aside

    if char in '[]':
        return 0.7  # BRACKETS - reference

    if char == ':':
        return 1.2  # COLON - explanation follows

    if char == ';':
        return 0.6  # SEMICOLON - soft separation

    if char in '!?':
        return 0.0  # END - sentence terminator

    return 1.0  # NORMAL - no special effect


def analyze_spacing(x1: float, x2: float, threshold_wall: float = 50.0) -> Dict[str, float]:
    """
    Analyze spacing between two X coordinates.

    Large gaps act as "walls" (M_p ≈ 0), small gaps as normal flow (M_p ≈ 1.0).

    Args:
        x1: X coordinate of first particle
        x2: X coordinate of second particle
        threshold_wall: X distance to consider as "wall" (default 50.0)

    Returns:
        Dictionary with spacing analysis:
        - distance: Absolute X distance
        - Mp_spacing: M_p value based on spacing (0.0 to 1.0)
        - is_wall: True if spacing is large enough to be a wall
    """
    distance = abs(x2 - x1)

    # Calculate M_p based on distance
    # Linear interpolation: 0px → 1.0, threshold_wall → 0.0
    if distance >= threshold_wall:
        Mp_spacing = 0.0  # WALL
        is_wall = True
    else:
        Mp_spacing = 1.0 - (distance / threshold_wall)
        is_wall = False

    return {
        'distance': distance,
        'Mp_spacing': Mp_spacing,
        'is_wall': is_wall
    }


def has_sentence_terminator(text: str) -> bool:
    """
    Check if text ends with a sentence terminator.

    Sentence terminators create "walls" (M_p = 0.0).

    Args:
        text: Input text

    Returns:
        True if text ends with . ! ? or similar
    """
    if not text:
        return False

    return text.rstrip()[-1] in '.!?'


def get_punctuation_weight(text: str) -> float:
    """
    Calculate overall punctuation weight for a text.

    More punctuation → more structure → more likely to be a HEADER/SPEC_LABEL.
    Less punctuation → simpler → more likely to be a VALUE.

    Args:
        text: Input text

    Returns:
        Punctuation weight (0.0 to 1.0)
    """
    if not text:
        return 0.0

    punct_count = sum(1 for c in text if c in string.punctuation)
    total_chars = len(text)

    return punct_count / total_chars if total_chars > 0 else 0.0


def analyze_cell_boundaries(particles: List[dict], y_tolerance: float = 5.0) -> Dict[float, List[float]]:
    """
    Analyze cell boundaries by detecting large X gaps on each Y level.

    Cell boundaries are "walls" where M_p drops to 0.

    Args:
        particles: List of particles with x, y coordinates
        y_tolerance: Y tolerance for grouping

    Returns:
        Dictionary mapping Y coordinate -> list of X positions where walls exist
    """
    from collections import defaultdict

    # Group particles by Y
    y_groups = defaultdict(list)
    for p in particles:
        y = p.get('y', 0)
        y_rounded = round(y / y_tolerance) * y_tolerance
        x = p.get('x', 0)
        y_groups[y_rounded].append(x)

    # Find walls (large gaps) in each Y level
    walls = {}
    for y, x_positions in y_groups.items():
        x_sorted = sorted(x_positions)
        wall_positions = []

        for i in range(len(x_sorted) - 1):
            spacing = analyze_spacing(x_sorted[i], x_sorted[i + 1])
            if spacing['is_wall']:
                # Wall exists between these two X positions
                wall_x = (x_sorted[i] + x_sorted[i + 1]) / 2
                wall_positions.append(wall_x)

        if wall_positions:
            walls[y] = wall_positions

    return walls
