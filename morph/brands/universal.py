"""
morph.brands.universal — Cross-Brand HVAC Vocabulary
=====================================================

Shared vocabulary across all brands. These sets do NOT change between
brands — they are the "common genome" of HVAC document structure.

Contains:
    - UNIT_SET: recognized measurement units
    - SPEC_TERMS: word-match technical specification labels
    - SPEC_SUBSTRINGS: substring-match technical labels
    - SECTION_TERMS: section heading markers
    - EXCLUDE_PATTERNS: text to reject (marketing, navigation)

Author: Eugeniu Tacu, 2026
"""

import re

# ─── Measurement units ───────────────────────────────────────────────

UNIT_SET = frozenset({
    'kw', 'db(a)', 'dba', 'mm', 'kg', 'l', 'l/h', 'm3/h', 'm³/h', 'm',
    'inch', 'a', 'v', 'hz', 'mm²', 'mm2', '°c', 'w', '%', 'ø',
    'pa', 'hp', 'm³/min', 'm3/min', 'hz/v', '°cbs', '°cbu',
    '-', '- / kg', 'rpm', 'bar', 'kwh', 'kw/h', 'mpa',
    'cfm', 'btu/h', 'kcal/h', 'g/h', 'ml/h',
})

# ─── Spec label terms (exact word match) ─────────────────────────────

SPEC_TERMS = frozenset({
    # Performance
    'capacità', 'potenza', 'pressione', 'portata', 'efficienza',
    'assorbimento', 'prevalenza', 'deumidificazione',
    # Indices
    'seer', 'scop', 'cop', 'eer', 'eseer', 'iplv',
    'classe', 'eta', 'gwp',
    # Acoustics
    'sonora', 'rumore', 'rumorosità',
    # Physical
    'dimensioni', 'peso', 'massa', 'altezza', 'larghezza',
    'profondità', 'lunghezza', 'diametro', 'sezione', 'volume',
    # Components
    'compressore', 'ventilatore', 'scambiatore', 'filtro',
    'pannello', 'pannellatura', 'serbatoio', 'vaso',
    'motore', 'griglia', 'pompa', 'valvola',
    # Fluids
    'refrigerante', 'carica', 'precarica',
    # Electrical
    'alimentazione', 'corrente', 'fusibile', 'tensione',
    # Connections
    'attacchi', 'connessione', 'collegament', 'tubazioni', 'condensa',
    'scarico', 'finitura',
    # Controls
    'controller', 'telecomando', 'comando',
    # Operational
    'range', 'temperatura', 'temp',
    'riscaldatore', 'backup',
    'campo', 'nominale', 'regime', 'spunto',
    # Commercial
    'prezzo', 'codice',
    # Categories
    'raffrescamento', 'riscaldamento', 'combinazione',
    'stagionale',
})

# ─── Spec label terms (substring match for long technical terms) ─────

SPEC_SUBSTRINGS = (
    'riscald', 'raffredd', 'inerzial', 'espansion', 'attacchi',
    'operativ', 'conduttor', 'frigorifer', 'elettric', 'sonor',
    'assorbita', 'collegabil', 'funzionam', 'tubazion',
    'potenza sonora', 'pressione sonora', 'campo di',
    'sanitario', 'backup', 'serbatoio',
    'nominale', 'condensa', 'accoppiament', 'impostabil',
    'campo operativ',
    # EN
    'cooling', 'heating', 'capacity', 'airflow', 'noise',
    'weight', 'dimension', 'refrigerant', 'power supply',
    'sound pressure', 'sound power',
    'nominal', 'drain', 'piping', 'wiring',
)

# ─── Section heading terms ───────────────────────────────────────────

SECTION_TERMS = frozenset({
    # IT
    'performance', 'prestazioni', 'dati', 'caratteristiche',
    'moduli', 'circuito', 'unità', 'panoramica', 'tecnici',
    'specifiche', 'generale', 'riepilogo',
    # EN
    'specifications', 'technical', 'general', 'overview',
    'features', 'summary',
})

# ─── Exclusion patterns (marketing, navigation) ─────────────────────

EXCLUDE_PATTERNS = (
    re.compile(r'^Fai\s+clic', re.IGNORECASE),
    re.compile(r'^accedere\s+ai', re.IGNORECASE),
    re.compile(r'^NOVITÀ$', re.IGNORECASE),
    re.compile(r'^tecnici:$', re.IGNORECASE),
    re.compile(r'^pag\.?\s*\d+$', re.IGNORECASE),
    re.compile(r'^www\.', re.IGNORECASE),
    re.compile(r'^https?://', re.IGNORECASE),
)
