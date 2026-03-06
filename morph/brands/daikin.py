"""
morph.brands.daikin — Daikin Model Code Patterns
==================================================

Compiled regex patterns for recognising Daikin HVAC model codes.
Derived from Morpho v2 prototype and ``known_models.json``.

Pattern groups (most-specific first):

* VRV Indoor — FX** (cassette, ducted, wall, floor)
* Wall-mount — FTXM, FTXA, CTXM, CTXA, FDXM
* VRV Outdoor — RXYQ, RXYS, RXYN, RXYA, RXYLQ, RXMLQ, RWEYQ, REYQ, REYA
* Sky Air — RZAG, RZASG, AZAS, FBA, FFA, FCAG
* Residential Outdoor — RXJ, RXM, RXZ
* Altherma (heat pumps) — EB**, EP**, ER**, ERST, ERPT
* Controllers / Accessories — BRC, BEV, BYCQ, EKMBP, EWYE
* Ventilation — CYAL, CYAM, CYAS

Also provides SIZE_HEADER_PATTERNS for Daikin's column-sizing
convention (e.g. ``50B``, ``RXYN10B``).

Author: Eugeniu Tacu, 2026
"""

import re

BRAND = 'daikin'

# Model code patterns — ordered most-specific first
MODEL_PATTERNS = [
    # VRV indoor (cassette / ducted / wall / floor)
    re.compile(r'^FX[A-Z]{2}[\s-]', re.IGNORECASE),   # FXFN-B, FXSN-B
    re.compile(r'^FX[A-Z]{2}\d', re.IGNORECASE),       # FXFQ100B, FXSA140A
    re.compile(r'^FX[A-Z]{2}$', re.IGNORECASE),        # FXFN, FXSN (prefix)

    # Wall-mount
    re.compile(r'^FTXM\d', re.IGNORECASE),             # FTXM20A, FTXM50A
    re.compile(r'^FTXA\d', re.IGNORECASE),             # FTXA20AW/CW
    re.compile(r'^CTXM\d', re.IGNORECASE),             # CTXM15A
    re.compile(r'^CTXA\d', re.IGNORECASE),             # CTXA15AW/CW
    re.compile(r'^FDXM-', re.IGNORECASE),              # FDXM-F9

    # VRV outdoor
    re.compile(r'^RXYQ', re.IGNORECASE),               # RXYQ, RXYQQ10U
    re.compile(r'^RXYS[A-Z]', re.IGNORECASE),          # RXYSA4AV1
    re.compile(r'^RXYN[\s-]?B$', re.IGNORECASE),       # RXYN-B (VRV CO2)
    re.compile(r'^RXYA\d', re.IGNORECASE),             # RXYA10A
    re.compile(r'^RXYLQ', re.IGNORECASE),              # RXYLQ10T
    re.compile(r'^RXMLQ', re.IGNORECASE),              # RXMLQ8T
    re.compile(r'^RWEYQ', re.IGNORECASE),              # RWEYQ10T9
    re.compile(r'^REYQ', re.IGNORECASE),               # REYQ10U
    re.compile(r'^REYA\d', re.IGNORECASE),             # REYA10A

    # Sky Air
    re.compile(r'^RZAG', re.IGNORECASE),               # RZAG100NV1
    re.compile(r'^RZASG', re.IGNORECASE),              # RZASG100MV1
    re.compile(r'^AZAS', re.IGNORECASE),               # AZAS100MV1
    re.compile(r'^FBA-', re.IGNORECASE),               # FBA-A
    re.compile(r'^FFA-', re.IGNORECASE),               # FFA-A9
    re.compile(r'^FCAG-', re.IGNORECASE),              # FCAG-A

    # Residential outdoor
    re.compile(r'^RXJ\d', re.IGNORECASE),              # RXJ20A
    re.compile(r'^RXM\d', re.IGNORECASE),              # RXM25A9
    re.compile(r'^RXZ\d', re.IGNORECASE),              # RXZ25N

    # Altherma (heat pumps)
    re.compile(r'^E[BPRK][A-Z]{2}', re.IGNORECASE),   # EBLA, EPRA, ERGA
    re.compile(r'^ERST', re.IGNORECASE),               # ERST17D
    re.compile(r'^ERPT', re.IGNORECASE),               # ERPT20X

    # Controllers / accessories
    re.compile(r'^BRC', re.IGNORECASE),                # BRC controller
    re.compile(r'^BEV\d', re.IGNORECASE),              # BEV EV block
    re.compile(r'^BYCQ', re.IGNORECASE),               # BYCQ panels
    re.compile(r'^EKMBP', re.IGNORECASE),              # EKMBPP1
    re.compile(r'^EWYE', re.IGNORECASE),               # EWYE-CZ

    # Ventilation
    re.compile(r'^CYAL', re.IGNORECASE),               # CYAL100DK125CB
    re.compile(r'^CYAM', re.IGNORECASE),               # CYAM100DK80CB
    re.compile(r'^CYAS', re.IGNORECASE),               # CYAS100DK80CB
]

# Size header patterns (Daikin uses "50B", "RXYN10B", etc.)
SIZE_HEADER_PATTERNS = [
    re.compile(r'^\d{1,3}B$'),                         # 10B, 40B, 50B, 63B, 80B
    re.compile(r'^RXYN\d+B$', re.IGNORECASE),          # RXYN10B
    re.compile(r'^FX[A-Z]{2}\d+B$', re.IGNORECASE),   # FXFN40B, FXSN50B
]
