# Morph — Project Overview

## Purpose
Morphogenetic table extraction from PDF documents. Training-free, GPU-free, bio-inspired.
3-layer pipeline: typify (gene expression) → sense (cellular differentiation) → field (tissue formation).

## Author
Eugeniu Tacu

## Current Status
- **v0.1.0** (main branch): Baseline stabile
  - GriTS_Top: 86.0% (dopo MAX voting + bbox clipping)
  - Boundary precision: 92.3%
  - HVAC health: 95.2% (5 brand, 46 cataloghi)
  
- **v2.0** (feature/v2.0 branch): In sviluppo — campo morfogenetico COMPLETO
  - Vision: Morph con TUTTI i sensi (geo + typo + struct + vettoriale)
  - Principio: Φ = W·A/d^α IMMUTABILE, ma d diventa multi-dimensionale
  - Roadmap: 6 phases (ROADMAP_v2.md)
  - Phase 0: BASELINE su tutti i dataset (HVAC + PubTables + SROIE + FUNSD)
  - Phase 1-6: Reader++, Typify++, Field++ (multi-dim + dualità + contesto), Sense++

## Tech Stack
- Python 3.10+ (dipendenza base: PyMuPDF)
- v2.0 adds: ftfy (50KB), rapidfuzz (200KB) for robustness
- Zero ML training, zero GPU

## Package Structure
```
morph/
├── core/          ← Algoritmi principali
│   ├── typify.py  ← Layer 1: classificazione lessicale (8 tipi particella)
│   ├── sense.py   ← Layer 1b: sensing spaziale (colonne, header, spec_label)
│   └── field.py   ← Layer 2: campo morfogenetico (Phi, binding, entita')
├── io/            ← Input/Output
│   ├── reader.py  ← Adapter PyMuPDF (v2.0: estrae font/hierarchy/drawings/TOC)
│   ├── graph.py   ← Entity → Graph L0 nodes/edges
│   └── sql.py     ← Graph → flat SQL rows
├── brands/        ← Pattern brand-specifici (opzionali)
├── bench/         ← Suite benchmark (grits.py, pubtables.py)
├── scripts/       ← Script baseline e test
│   └── baseline_v0.1.py  ← Raccolta baseline multi-dataset
├── data/          ← Dati baseline e risultati
│   └── baseline_v0.1.json  ← Punto zero per confronti
├── pipeline.py    ← Pipeline completa
├── ROADMAP_v2.md  ← Piano maniacale v2.0 (6 phases)
├── CLAUDE.md      ← Istruzioni per Claude (aggiornato con v2.0)
└── __init__.py    ← Versione corrente
```

## Key Files v2.0
- `ROADMAP_v2.md` — Piano completo con 6 phases, decision points, metriche
- `CLAUDE.md` — Istruzioni aggiornate con visione v2.0
- `data/baseline_v0.1.json` — Baseline multi-dataset (HVAC + PubTables + altri)
- `scripts/baseline_v0.1.py` — Script raccolta baseline

## v2.0 Vision
**Campo morfogenetico multi-sensoriale:**
- d² = dx² + dy² + dz² + df² + dh² + dc²  (multi-dimensional distance)
- Φ_total = Φ_attract + Φ_repel  (dualità)
- σ = f(section, language, has_borders)  (calibrazione contestuale)

**Strati di informazione che v2.0 vede:**
1. Geometria (x, y) — v0.1 ✓
2. Tipografia (font, bold, color) — v2.0
3. Struttura (span/line/block hierarchy) — v2.0
4. Vettoriale (linee, bordi) — v2.0
5. Metadati (TOC, author, title) — v2.0
6. Spazio negativo (whitespace repulsion) — v2.0
7. Baseline (allineamento preciso) — v2.0

**Euristica diventa fisica:**
- Max-jump → caso particolare di Φ_total=0
- Cristallizzazione → caso particolare di repulsione periodica
- Le euristiche EMERGONO dal campo completo

## Docs
- `docs/theory.md` — Fondamenti matematici
- `docs/results.md` — Benchmark dettagliati
- `README.md` — Paper-quality bilingue EN/IT
- `ROADMAP_v2.md` — Piano v2.0 completo

## Branch Strategy
```
main (v0.1.0 stabile, 86.0% GriTS)
  └─ feature/v2.0 (sviluppo, target 97%+ GriTS)
```

## Relation to Locus (dots.ocr)
Morph extracted from dots.ocr as independent package.
Installed editable in dots.ocr venv: `pip install -e /home/jervis/Progetti/morph/`
Scripts in dots.ocr/scripts/ import from morph.*

## Contributors v2.0
- **Eugeniu Tacu:** Creatività, visione, "pensare fuori dagli schemi"
- **Claude Code (Sonnet 4.5):** Implementazione, architettura tecnica
- **Claude Opus 4:** Validazione metodologica (Phase 0 baseline, calibrazione R)
