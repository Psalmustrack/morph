# Morph — Project Overview

## Purpose
Morphogenetic table extraction from PDF documents. Training-free, GPU-free, bio-inspired.
3-layer pipeline: typify (gene expression) → sense (cellular differentiation) → field (tissue formation).

## Author
Eugeniu Tacu

## Key Results
- GriTS_Top: 79.7% PubTables-1M, 77.6% FinTabNet
- HVAC health: 95.2% (5 brand, 46 cataloghi)
- 2.1pp cross-domain gap (universalita')

## Tech Stack
- Python 3.10+ (solo dipendenza: PyMuPDF)
- Optional: numpy, rapidfuzz (benchmark)
- Zero ML training, zero GPU

## Package Structure
```
morph/
├── core/          ← Algoritmi principali
│   ├── typify.py  ← Layer 1: classificazione lessicale (8 tipi particella)
│   ├── sense.py   ← Layer 1b: sensing spaziale (colonne, header, spec_label)
│   └── field.py   ← Layer 2: campo morfogenetico (Phi, binding, entita')
├── io/            ← Input/Output
│   ├── reader.py  ← Adapter PyMuPDF (MorphoPage, MorphoDoc)
│   ├── graph.py   ← Entity → Graph L0 nodes/edges
│   └── sql.py     ← Graph → flat SQL rows
├── brands/        ← Pattern brand-specifici (opzionali)
│   ├── universal.py ← Vocabolario condiviso HVAC
│   ├── hitachi.py, daikin.py, toshiba.py, mitsubishi.py, midea.py
│   └── __init__.py  ← detect_brand(), get_brand_patterns()
├── bench/         ← Suite benchmark
│   ├── grits.py     ← Metrica GriTS (2D DP alignment)
│   ├── pubtables.py ← Adapter PubTables-1M
│   └── adaptive_k.py ← Max-ratio-jump benchmark
├── pipeline.py    ← Pipeline completa: PDF → Graph + SQL + RAG
└── __init__.py    ← v0.1.0
```

## Docs
- `docs/theory.md` — Fondamenti matematici (equazione di campo, sensing, boundary law)
- `docs/results.md` — Benchmark dettagliati (PubTables, FinTabNet, HVAC, ablation)
- `README.md` — Paper-quality bilingue EN/IT

## Relation to Locus (dots.ocr)
Morph was extracted from dots.ocr into its own repo. It's installed as editable package
in the dots.ocr venv: `pip install -e /home/jervis/Progetti/morph/`
Scripts in dots.ocr/scripts/ import from morph.* (e.g. `from morph.core.typify import typify_word`).
