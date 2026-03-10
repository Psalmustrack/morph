"""
Cell Spanning Detection - Layer 2.5

Detects and expands merged cells in table data using geometric analysis.

When a table has merged cells (cells that span multiple columns), the PDF
typically places the text at the CENTER of the merged cell. This module
detects such cases by analyzing X coordinates and expands the value to
all covered columns.

Example:
    Column positions: [200, 300, 400, 500]
    Value @ X=250 → between 200 and 300 → spans 2 columns
    Value @ X=350 → between 300 and 500 → spans 3 columns!

This is a universal geometric algorithm that works for any table.
"""

from typing import List, Dict, Tuple, Any


def detect_column_positions(particles: List[dict], entity_names: List[str]) -> Dict[str, float]:
    """
    Detect X coordinate for each entity/column by finding entity name particles.

    Args:
        particles: All particles from the page
        entity_names: List of entity names (e.g., model names)

    Returns:
        Dictionary mapping entity_name -> X coordinate
    """
    entity_positions = {}

    for entity in entity_names:
        # Find particle with this entity text
        for p in particles:
            if p.get('text', '').strip() == entity.strip():
                entity_positions[entity] = p.get('x', 0)
                break

    return entity_positions


def calculate_cell_span(value_x: float, column_positions: List[float], tolerance: float = 20.0) -> Tuple[int, int]:
    """
    Calculate which columns a value spans based on its X coordinate.

    Strategy: When text is centered in a merged cell, its CENTER coordinate
    will be equidistant from the first and last column of the span.

    For example:
        Columns at X = [200, 300, 400, 500]
        Value centered at X = 250 → center of span (200, 300) → spans 2 columns
        Value centered at X = 300 → aligned with single column → spans 1 column
        Value centered at X = 350 → center of span (200, 500) → spans 4 columns!

    Args:
        value_x: X coordinate of the value (should be center of bounding box)
        column_positions: Sorted list of column X positions
        tolerance: Tolerance for considering value "centered" in span (default 20px)

    Returns:
        (start_col_idx, end_col_idx) - indices of first and last covered columns
    """
    if not column_positions:
        return (0, 0)

    if len(column_positions) == 1:
        return (0, 0)

    # Sort columns by X position and keep track of original indices
    sorted_cols = sorted(enumerate(column_positions), key=lambda x: x[1])

    # Strategy: Check all possible spans (from 1 column to N columns)
    # and find the span whose center is closest to value_x

    best_span = (0, 0)
    best_distance = float('inf')

    # Check all possible spans
    for start_i in range(len(sorted_cols)):
        for end_i in range(start_i, len(sorted_cols)):
            start_idx, start_x = sorted_cols[start_i]
            end_idx, end_x = sorted_cols[end_i]

            # Calculate geometric center of this span
            if start_i == end_i:
                # Single column - center is the column position
                span_center = start_x
            else:
                # Multiple columns - center is midpoint between first and last
                span_center = (start_x + end_x) / 2

            # Calculate distance from value center to span center
            distance = abs(value_x - span_center)

            # Update best span if this is closer
            if distance < best_distance:
                best_distance = distance
                best_span = (min(start_idx, end_idx), max(start_idx, end_idx))

    # Return best span if distance is within tolerance
    if best_distance < tolerance:
        return best_span

    # Fallback: assign to nearest single column
    nearest_idx = min(range(len(column_positions)),
                     key=lambda i: abs(column_positions[i] - value_x))
    return (nearest_idx, nearest_idx)


def expand_merged_cells(data: Dict[str, Dict[str, dict]],
                       particles: List[dict],
                       entities: List[str]) -> Dict[str, Dict[str, dict]]:
    """
    Expand merged cells by detecting cell spans and copying values.

    Only fills EMPTY cells — never overwrites values already assigned
    by the Phi field. A spec row is a merge candidate only when fewer
    entities have a value than the total number of entities.

    Args:
        data: Result from extract_page - {entity: {spec: {value, unit, x, y, ...}}}
        particles: All particles from the page
        entities: List of entity names (column headers)

    Returns:
        Expanded data with merged cells properly assigned to all columns
    """
    if not data or not entities or len(entities) < 2:
        return data

    # Step 1: Detect column positions
    entity_positions = detect_column_positions(particles, entities)
    if len(entity_positions) < 2:
        return data

    # Create ordered list of (entity, x_position)
    entity_x_list = [(entity, entity_positions[entity])
                     for entity in entities
                     if entity in entity_positions]
    entity_x_list.sort(key=lambda x: x[1])

    column_positions = [x for _, x in entity_x_list]
    entity_order = [entity for entity, _ in entity_x_list]
    n_entities = len(entity_order)

    # Step 2: Deep-copy existing data (preserve all Phi assignments)
    expanded_data = {}
    for entity in data:
        expanded_data[entity] = dict(data[entity])

    # Collect all specs
    all_specs = set()
    for entity_data in data.values():
        all_specs.update(entity_data.keys())

    # Step 3: For each spec, expand ONLY if there are empty cells
    for spec in all_specs:
        # Count how many entities already have this spec
        entities_with_value = [e for e in entity_order if e in data and spec in data[e]]
        entities_without_value = [e for e in entity_order if e not in entities_with_value]

        # All entities covered → nothing to expand
        if not entities_without_value:
            continue

        # Only 1 value for many entities → likely a merged cell
        if len(entities_with_value) == 0:
            continue

        # For each existing value, calculate its span and fill empty cells
        for source_entity in entities_with_value:
            value_info = data[source_entity][spec]

            # Calculate center of value's bounding box
            x0 = value_info.get('x0', value_info.get('x', 0))
            x1 = value_info.get('x1', value_info.get('x', 0))

            if x1 > x0:
                value_center = (x0 + x1) / 2
            else:
                value_center = value_info.get('x', 0)

            # Calculate span
            start_idx, end_idx = calculate_cell_span(value_center, column_positions)

            # Fill ONLY empty cells in the span
            for idx in range(start_idx, end_idx + 1):
                if idx < n_entities:
                    target_entity = entity_order[idx]
                    # Never overwrite existing values!
                    if target_entity in entities_without_value:
                        if target_entity not in expanded_data:
                            expanded_data[target_entity] = {}
                        if spec not in expanded_data[target_entity]:
                            expanded_data[target_entity][spec] = value_info

    return expanded_data


def analyze_merge_impact(original_data: dict, expanded_data: dict) -> Dict[str, Any]:
    """
    Analyze the impact of cell spanning detection.

    Returns statistics about how many cells were expanded.

    Args:
        original_data: Data before merge expansion
        expanded_data: Data after merge expansion

    Returns:
        Dictionary with merge statistics
    """
    orig_count = sum(len(specs) for specs in original_data.values())
    expanded_count = sum(len(specs) for specs in expanded_data.values())

    filled_cells = expanded_count - orig_count

    return {
        'original_cells': orig_count,
        'expanded_cells': expanded_count,
        'filled_by_merge': filled_cells,
        'improvement_pct': (filled_cells / orig_count * 100) if orig_count > 0 else 0
    }
