"""
morph.core.layer2_field — Layer 2: Morphogenetic Field
=======================================================

Field bonding layer that uses the morphogenetic field equation Φ
to associate numeric values with their entity/spec labels.

Public API:
    - extract_page: Main orchestration function
    - calibrate_sigma: Calibrate spatial sigma parameters
    - calibrate_lambda_z: Calibrate magnitude lambda parameter
    - merge_multiline_specs: Merge specs spanning multiple lines

Author: Eugeniu Tacu, 2026
"""

from .extract import extract_page
from .calibrate import calibrate_sigma, calibrate_lambda_z
from .merge import merge_multiline_specs

__all__ = [
    'extract_page',
    'calibrate_sigma',
    'calibrate_lambda_z',
    'merge_multiline_specs',
]
