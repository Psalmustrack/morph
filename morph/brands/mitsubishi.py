"""
morph.brands.mitsubishi — Mitsubishi Electric Model Code Patterns
==================================================================

Compiled regex patterns for recognising Mitsubishi Electric HVAC
model codes.  Derived from ``known_models.json``.

Pattern groups (most-specific first):

* VRF Indoor (City Multi) — PEFY, PFFY, PLFY, PKFY, PCFY, PMFY
* VRF Outdoor (City Multi) — PUHY, PUMY, PURY, PQHY, PQRY
* Commercial (Mr. Slim / Power Inverter) — PCA, PEAD, PKA, PLA, PUZ
* Residential (M-Series / S-Series) — MSZ, MXZ, MLZ
* Indoor Commercial — SEZ, SFZ, SLZ, SUZ
* Ecodan (heat pumps) — PUHZ
* Controllers — CMB, CMH, MMD
* Generic Mitsubishi — P<3-letter>-

Author: Eugeniu Tacu, 2026
"""

import re

BRAND = 'mitsubishi_electric'

# Model code patterns — ordered most-specific first
MODEL_PATTERNS = [
    # VRF indoor — City Multi
    re.compile(r'^PEFY-[A-Z]\d', re.IGNORECASE),      # PEFY-M100VMA-A1
    re.compile(r'^PFFY-[A-Z]\d', re.IGNORECASE),      # PFFY-P20VEM-E
    re.compile(r'^PLFY-[A-Z]\d', re.IGNORECASE),      # PLFY-M100VEM6-E
    re.compile(r'^PKFY-[A-Z]\d', re.IGNORECASE),      # PKFY-P100VKM-E
    re.compile(r'^PCFY-[A-Z]\d', re.IGNORECASE),      # PCFY-P100VKM-E
    re.compile(r'^PMFY-[A-Z]\d', re.IGNORECASE),      # PMFY-P20VBM-E

    # VRF outdoor — City Multi
    re.compile(r'^PUHY-', re.IGNORECASE),              # PUHY-HP200YNW-A
    re.compile(r'^PUMY-', re.IGNORECASE),              # PUMY-P112VKM6(-BS)
    re.compile(r'^PURY-', re.IGNORECASE),              # PURY-M300YNW-A1
    re.compile(r'^PQHY-', re.IGNORECASE),              # PQHY-P200YLM-A1
    re.compile(r'^PQRY-', re.IGNORECASE),              # PQRY-P200YLM-A1

    # Commercial — Mr. Slim / Power Inverter
    re.compile(r'^PCA-[A-Z]\d', re.IGNORECASE),       # PCA-M100KA2
    re.compile(r'^PEAD-[A-Z]\d', re.IGNORECASE),      # PEAD-M100JA2
    re.compile(r'^PKA-[A-Z]\d', re.IGNORECASE),       # PKA-M100KAL2
    re.compile(r'^PLA-[A-Z]\d', re.IGNORECASE),       # PLA-M100EA2
    re.compile(r'^PUZ-[A-Z]\d', re.IGNORECASE),       # PUZ-M100VKA2

    # Residential — M-Series / S-Series
    re.compile(r'^MSZ-[A-Z]{2}\d', re.IGNORECASE),    # MSZ-AP60VGK
    re.compile(r'^MXZ-\d', re.IGNORECASE),             # MXZ-2F33VF4
    re.compile(r'^MLZ-[A-Z]{2}\d', re.IGNORECASE),    # MLZ-KP25VG

    # Indoor commercial
    re.compile(r'^SEZ-[A-Z]\d', re.IGNORECASE),       # SEZ-M25DA2
    re.compile(r'^SFZ-[A-Z]\d', re.IGNORECASE),       # SFZ-M25VA
    re.compile(r'^SLZ-[A-Z]\d', re.IGNORECASE),       # SLZ-M25FA2
    re.compile(r'^SUZ-', re.IGNORECASE),               # SUZ-M71VA

    # Ecodan (heat pumps)
    re.compile(r'^PUHZ-', re.IGNORECASE),              # PUHZ-SHW230YKA2

    # Controllers
    re.compile(r'^CMB-[A-Z]\d', re.IGNORECASE),       # CMB-M1012V-J1
    re.compile(r'^CMH-', re.IGNORECASE),               # CMH-WM250V-A
    re.compile(r'^MMD-', re.IGNORECASE),               # MMD-UPV0501HY-E

    # Generic Mitsubishi (P + 3 letters + dash)
    re.compile(r'^P[A-Z]{3}-'),
]

# Size header patterns (Mitsubishi Electric does not use them)
SIZE_HEADER_PATTERNS = []
