"""
morph.core.layer1b_sense — Layer 1b: Spatial Sensing
=====================================================

Spatial sensing layer that detects columns, rows, and promotes
particle types based on their geometric arrangement.

Public API:
    - sense_page: Main orchestration function
    - detect_columns: Column boundary detection
    - detect_columns_from_drawings: Use PDF drawing objects for columns
    - detect_row_label_column: Find leftmost label column
    - promote_column_headers: Promote headers based on position
    - promote_spec_labels: Promote spec labels
    - promote_sections: Promote section headings
    - proofread: Final type corrections

Author: Eugeniu Tacu, 2026
"""

from .columns import detect_columns, detect_columns_from_drawings
from .rows import detect_row_label_column
from .promote import promote_column_headers, promote_spec_labels, promote_sections, proofread
from .orchestrate import sense_page

__all__ = [
    'sense_page',
    'detect_columns',
    'detect_columns_from_drawings',
    'detect_row_label_column',
    'promote_column_headers',
    'promote_spec_labels',
    'promote_sections',
    'proofread',
]
