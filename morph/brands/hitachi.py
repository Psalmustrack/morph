"""
morph.brands.hitachi — Hitachi Model Code Patterns
====================================================

Compiled regex patterns for recognising Hitachi HVAC model codes
in PDF text particles.  Derived from ``header_map.json`` (256 model
patterns) and ``known_models.json``.

Pattern groups (most-specific first):

* Residential — RAK, RAC, RAM, RAD, RAF, RAI
* VRF Indoor — RPI, RPK, RPC, RPF, RCI, RCD, RNC
* VRF Outdoor — RAS-<digit>, RASM
* Heat Pump / Hydronic — RWM, RWD, RWH, RWLT, HWM, HWD
* DHW Tanks — DHWT
* Chiller — KPI, RCME
* Controllers — PC-AR
* Accessories — ATW, SPX, CH-AP, AG, MH, DBS, RHMA, RASC
* Generic Hitachi — R<2-letter>-<alphanum>

Author: Eugeniu Tacu, 2026
"""

import re

BRAND = 'hitachi'

# Model code patterns — ordered most-specific first
MODEL_PATTERNS = [
    # Residential (monosplit, multisplit)
    re.compile(r'^RAK-[A-Z]{1,3}\d{2}'),      # RAK-CJ25PHAE, RAK-DJ35RHAE
    re.compile(r'^RAC-[A-Z]{1,3}\d{2}'),      # RAC-CJ25WHAE
    re.compile(r'^RAM-\d{2}'),                  # RAM-53NYP3E
    re.compile(r'^RAD-\d{2}'),                  # RAD-18QPE
    re.compile(r'^RAF-'),                       # RAF-25RXE
    re.compile(r'^RAI-'),                       # RAI-25RPE

    # VRF indoor
    re.compile(r'^RPI[LH]?-'),                  # RPI-1.5FSR1E, RPIL-0.4FSR1E
    re.compile(r'^RPK-'),                       # RPK-0.6FSR(H)M
    re.compile(r'^RPC-'),                       # RPC-1.5FSR
    re.compile(r'^RPF[I]?-'),                   # RPF-1.0FSN2E, RPFI-1.0FSN2E
    re.compile(r'^RCI[M]?-'),                   # RCI-1.0FSR1, RCIM-0.4FSRE
    re.compile(r'^RCD-'),                       # RCD-0.8FSR
    re.compile(r'^RNC-'),                       # RNC-

    # VRF outdoor
    re.compile(r'^RAS-\d'),                     # RAS-4FSXNME, RAS-10FSXNME
    re.compile(r'^RASM-'),                      # RASM-2VTW2E

    # Heat pump / hydronic
    re.compile(r'^RWM-'),                       # RWM-1.5R2E
    re.compile(r'^RWD-'),                       # RWD-1.5RW3E
    re.compile(r'^RWH-'),                       # RWH-4.0(V)NFE
    re.compile(r'^RWLT-'),                      # RWLT-3.0VN1E
    re.compile(r'^HWM-'),                       # HWM-W2E
    re.compile(r'^HWD-'),                       # HWD-W2E-220S

    # DHW / tanks
    re.compile(r'^DHWT-'),                      # DHWT-200S-3.0H2E

    # Chiller
    re.compile(r'^KPI-'),                       # KPI-1002E4E
    re.compile(r'^RCME-'),                      # RCME-

    # Controllers
    re.compile(r'^PC-AR'),                      # PC-ARFH3E, PC-ARFG2-E

    # Accessories
    re.compile(r'^ATW-'),                       # ATW-CBX-01
    re.compile(r'^SPX-'),                       # SPX-WFG03
    re.compile(r'^CH-AP'),                      # CH-AP04MSSX
    re.compile(r'^AG-'),                        # AG-
    re.compile(r'^MH-'),                        # MH-108AN
    re.compile(r'^DBS-'),                       # DBS-
    re.compile(r'^RHMA'),                       # RHMA
    re.compile(r'^RASC-'),                      # RASC-

    # Generic Hitachi (R + 2 letters + dash + alphanum)
    re.compile(r'^R[A-Z]{2}-[A-Z]{0,2}\d'),
]

# Size header patterns (Hitachi does not use them)
SIZE_HEADER_PATTERNS = []
