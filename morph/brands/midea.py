"""
morph.brands.midea — Midea Model Code Patterns
================================================

Compiled regex patterns for recognising Midea HVAC model codes.
Derived from ``known_models.json``.

Pattern groups (most-specific first):

* VRF Outdoor — MDV-V, MV/MV8
* VRF Indoor — MI, MIH
* Commercial — MCA, MCD, MCY, MTI, MTJ, MUE
* Residential — MFA, MFM, MSAG, MSCB, MSEP, MSFA
* Heat Pumps — MEHP, RSJ
* Modular Hydronic — MHA, MHC, MHS, MSC
* Accessories — GK, GUF, EZ, EA

Author: Eugeniu Tacu, 2026
"""

import re

BRAND = 'midea'

# Model code patterns — ordered most-specific first
MODEL_PATTERNS = [
    # VRF outdoor
    re.compile(r'^MDV-V\d', re.IGNORECASE),            # MDV-V100WHN8(At)
    re.compile(r'^MV8?-\d', re.IGNORECASE),            # MV8-252WV2RN1E(PRO)

    # VRF indoor
    re.compile(r'^MIH?\d', re.IGNORECASE),             # MI2-15DGDN18, MIH100Q4N18

    # Commercial
    re.compile(r'^MCA\d', re.IGNORECASE),              # MCA3U-12HRFNX(GA)
    re.compile(r'^MCD\d', re.IGNORECASE),              # MCD1-24HRFNX(GA)
    re.compile(r'^MCY-', re.IGNORECASE),               # MCY-MHP0404HS-E
    re.compile(r'^MTI[U]?-\d', re.IGNORECASE),         # MTI-24HWFNX, MTIU-07HWFNX
    re.compile(r'^MTJ-\d', re.IGNORECASE),             # MTJ-09HWFNX
    re.compile(r'^MUE[U]?-\d', re.IGNORECASE),         # MUE-24HRFNX, MUEU-18HRFNX

    # Residential
    re.compile(r'^MFA\d', re.IGNORECASE),              # MFA2U-09HRFNX
    re.compile(r'^MFM-\d', re.IGNORECASE),             # MFM-48HRFN8
    re.compile(r'^MSAG[A-Z]*-', re.IGNORECASE),        # MSAGBU-09HRFN7
    re.compile(r'^MSCB\d', re.IGNORECASE),             # MSCB1BU-09HRFN8
    re.compile(r'^MSEP[A-Z]*-', re.IGNORECASE),        # MSEPBU-09HRFN8
    re.compile(r'^MSFA[A-Z]*-', re.IGNORECASE),        # MSFAAU-09HRFN8B

    # Heat pumps
    re.compile(r'^MEHP-', re.IGNORECASE),              # MEHP-IB07V2
    re.compile(r'^RSJ-\d', re.IGNORECASE),             # RSJ-08/80RDN7-B1

    # Modular hydronic
    re.compile(r'^MHA-', re.IGNORECASE),               # MHA-V10W/D2N8-B
    re.compile(r'^MHC-', re.IGNORECASE),               # MHC-V10WD2N7
    re.compile(r'^MHS-', re.IGNORECASE),               # MHS-SVC50-RN7TL-B
    re.compile(r'^MSC-\d', re.IGNORECASE),             # MSC-120D2N8-A

    # Accessories
    re.compile(r'^GK-\d', re.IGNORECASE),              # GK-3009AS2
    re.compile(r'^GUF-\d', re.IGNORECASE),             # GUF-100RD4
    re.compile(r'^EZ-\d', re.IGNORECASE),              # EZ-09RD6-I
    re.compile(r'^EA-', re.IGNORECASE),                # EA-S3.68K
]

# Size header patterns (Midea does not use them)
SIZE_HEADER_PATTERNS = []
