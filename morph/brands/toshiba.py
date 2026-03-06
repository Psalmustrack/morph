"""
morph.brands.toshiba — Toshiba Model Code Patterns
====================================================

Compiled regex patterns for recognising Toshiba HVAC model codes.
Derived from ``known_models.json`` and processed catalogues.

Pattern groups (most-specific first):

* VRF Indoor — RAV-GM, RAV-**
* VRF Outdoor — MAP, SUG, MUP, UP (Super/Digital Inverter)
* BC Controllers — RBM
* Ventilation — VN-U
* Controllers / Accessories — TCB, RTD, TAW, WDC
* Residential — RAS-B (note overlap with Hitachi RAS patterns)

Author: Eugeniu Tacu, 2026
"""

import re

BRAND = 'toshiba'

# Model code patterns — ordered most-specific first
MODEL_PATTERNS = [
    # VRF indoor
    re.compile(r'^RAV-GM\d', re.IGNORECASE),           # RAV-GM1101KRTP-E
    re.compile(r'^RAV-[A-Z]{2}\d', re.IGNORECASE),    # RAV-* generic

    # VRF outdoor (Super/Digital Inverter)
    re.compile(r'^MAP\d', re.IGNORECASE),              # MAP01006FT8(J)P-E
    re.compile(r'^SUG\d', re.IGNORECASE),              # SUG01001MT8(J)P-E
    re.compile(r'^MUP\d', re.IGNORECASE),              # MUP01001HT8(J)P-E
    re.compile(r'^UP\d{3,4}', re.IGNORECASE),          # UP0031HP-E

    # BC controllers
    re.compile(r'^RBM-[A-Z]\d', re.IGNORECASE),       # RBM-A101UPVA-E

    # Ventilation
    re.compile(r'^VN-U\d', re.IGNORECASE),             # VN-U00151SY-E

    # Controllers / accessories
    re.compile(r'^TCB-', re.IGNORECASE),               # TCB-SF160C6BE
    re.compile(r'^RTD-', re.IGNORECASE),               # RTD-10, RTD-HO
    re.compile(r'^TAW-', re.IGNORECASE),               # TAW-190RHC
    re.compile(r'^WDC\d', re.IGNORECASE),              # WDC3-86S

    # Residential (overlap caution: Hitachi also uses RAS-)
    re.compile(r'^RAS-B?\d{2}', re.IGNORECASE),        # RAS-B13...
]

# Size header patterns (Toshiba does not use them)
SIZE_HEADER_PATTERNS = []
