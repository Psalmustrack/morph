"""
HVAC domain configuration.

Vocabulary and patterns for HVAC equipment catalogs (air conditioning,
heating systems, heat pumps, chillers, etc.).
"""

from .base import DomainConfig


HVAC = DomainConfig(
    name="hvac",

    # Model patterns (filled externally by brand)
    model_patterns=[],
    size_patterns=[],

    # HVAC vocabulary - from morph.brands.universal
    spec_terms={
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
    },

    spec_substrings={
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
    },

    section_terms={
        # IT
        'performance', 'prestazioni', 'dati', 'caratteristiche',
        'moduli', 'circuito', 'unità', 'panoramica', 'tecnici',
        'specifiche', 'generale', 'riepilogo',
        # EN
        'specifications', 'technical', 'general', 'overview',
        'features', 'summary',
    },

    unit_set={
        'kw', 'db(a)', 'dba', 'mm', 'kg', 'l', 'l/h', 'm3/h', 'm³/h', 'm',
        'inch', 'a', 'v', 'hz', 'mm²', 'mm2', '°c', 'w', '%', 'ø',
        'pa', 'hp', 'm³/min', 'm3/min', 'hz/v', '°cbs', '°cbu',
        '-', '- / kg', 'rpm', 'bar', 'kwh', 'kw/h', 'mpa',
        'cfm', 'btu/h', 'kcal/h', 'g/h', 'ml/h',
    },

    exclude_patterns=[
        r'^Fai\s+clic',
        r'^accedere\s+ai',
        r'^NOVITÀ$',
        r'^tecnici:$',
        r'^pag\.?\s*\d+$',
        r'^www\.',
        r'^https?://',
    ],

    use_fuzzy=True,
    require_models=True,  # HVAC tables need MODEL codes as column headers
)
