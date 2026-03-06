# Morph — Self-Organising Table Structure Recognition

> *"For every problem where structure is implicit in the data, there exists a biological
> principle that makes it emerge — and it is more efficient than any approach that
> attempts to inject it from outside."*

**Morph** is a morphogenetic engine for extracting structured data from PDF
technical catalogues.  It uses three bio-inspired layers — gene expression,
cellular differentiation, and field attraction — to recognise table structure
**without training data, GPU inference, or domain-specific rules**.

The engine operates directly on PDF text spans (not images) and produces
Graph L0 nodes, SQL rows, and RAG chunks in a single pass.

---

## Key Results

| Metric | Value | Context |
|--------|-------|---------|
| **GriTS_Top** (PubTables-1M) | **79.7%** | N=10,000, seed=42 |
| **GriTS_Top** (FinTabNet.c) | **77.6%** | N=10,000, seed=42 |
| Cross-domain gap | **2.1 pp** | Stable generalisation |
| Column exact match | **66.2%** | PubTables-1M |
| HVAC catalogue health | **95.2%** | 6,238 pages, 5 brands |
| Pages processed | **6,238** | 46 catalogues |
| Processing speed | **~50 pages/s** | i7-10850H, no GPU |

### Benchmark Comparison

The GriTS metric (Grid Table Similarity) is the official benchmark of
PubTables-1M (Microsoft, 2022).  It uses optimal 2D dynamic-programming
alignment, making it robust to off-by-one errors that inflate simple
exact-match metrics.

```
Method              PubTables-1M    FinTabNet.c     Gap
──────────────────  ──────────────  ──────────────  ────────
Morph (k=0.3)          79.7%           77.6%         2.1 pp
Morph (max-jump)       79.9%           78.1%         1.8 pp
```

The max-ratio-jump variant replaces the fixed boundary constant with an
adaptive threshold computed from the natural break in the gap distribution.
It reduces the cross-domain gap without degrading in-domain performance.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    morph.pipeline                        │
│         PDF → Graph L0 + SQL rows + RAG chunks          │
└────────────┬────────────────────────────────┬───────────┘
             │                                │
    ┌────────▼────────┐              ┌────────▼────────┐
    │   morph.core    │              │    morph.io     │
    │                 │              │                 │
    │  typify (L1)    │              │  reader (PDF)   │
    │    ↓            │              │  graph (L0)     │
    │  sense  (L1b)   │              │  sql   (flat)   │
    │    ↓            │              │                 │
    │  field  (L2)    │              └─────────────────┘
    └────────┬────────┘
             │
    ┌────────▼────────┐
    │  morph.brands   │
    │                 │
    │  universal.py   │  ← shared HVAC genome
    │  hitachi.py     │  ← brand regex patterns
    │  daikin.py      │
    │  toshiba.py     │
    │  mitsubishi.py  │
    │  midea.py       │
    └─────────────────┘
```

### Layer 1 — Gene Expression (`typify.py`)

Lexical classification of every PDF text span into one of 10 particle types:

| Type | Rule | Example |
|------|------|---------|
| `NUMERIC` | Regex: decimal/integer/range | `4.50`, `230`, `3~5` |
| `UNIT` | Lookup in `UNIT_SET` | `kW`, `dB(A)`, `mm` |
| `MODEL` | Brand regex patterns | `RAS-4FSXNME` |
| `SIZE_HEADER` | Brand size patterns | `50B` |
| `SPEC_LABEL` | Word/substring match | `Potenza sonora` |
| `SECTION` | Section term match | `Specifiche tecniche` |
| `EXCLUDED` | Marketing/navigation | `Fai clic qui` |
| `KW_HEADER` | `kW` in header context | `kW` above a column |
| `TEXT` | Default | Everything else |

**No training, no model weights.** Classification is deterministic from
vocabulary sets and compiled regex patterns.

### Layer 1b — Cellular Differentiation (`sense.py`)

Spatial reasoning that re-types particles based on their neighbours:

1. **Column detection** — vertical clusters of 3+ NUMERIC particles
   aligned on X (tolerance: adaptive from row spacing, clamped [5, 25] px)
2. **Header promotion** — TEXT above a detected column → MODEL
3. **Spec-label promotion** — TEXT to the left of NUMERIC (same Y-row,
   min 2 pairs required for activation = *lateral inhibition*)
4. **Section promotion** — TEXT with font size > mean + 2σ → SECTION
5. **DNA Proofreading** — local consistency checks on promoted types

This layer alone improved HVAC health from 35.7% to 63.4% (+27.7 pp)
without touching any vocabulary or regex pattern — pure spatial inference.

### Layer 2 — Tissue Differentiation (`field.py`)

The morphogenetic field equation maps NUMERIC values to MODEL entities:

```
Φ(i → j) = W · A_directed / d^α
```

Where:
- **d** is the 3D distance: `d² = (Δx/σ_x)² + (Δy/σ_y)² + (Δz/σ_z)²`
  with `z = log₁₀(|value| + 1)` (magnitude axis)
- **W** is the column alignment weight (Gaussian on Δx from nearest column)
- **A_directed** is a directional anisotropy factor (values below headers
  attract more strongly than values to the side)
- **α = 0.5** (sub-linear decay — weaker than gravity, allowing distant
  but well-aligned values to still bind)

Constants (derived empirically, validated on 10K+ tables):
- `σ_x = 30 px` (column width scale)
- `σ_y = 6 px` (row height scale)
- `k_x = 0.3` (universal boundary constant for columns)
- `k_y = 0.05` (universal boundary constant for rows)

The **universal boundary law**: a gap is a cell boundary when
`gap > avg_element_size × k`.  This single principle, with k=0.3 for
columns and k=0.05 for rows, achieves 66.2% column exact match on
PubTables-1M without any learned parameters.

### Cross-Page Merge (Endocrine System)

Multi-page tables are detected by column fingerprinting: consecutive pages
with compatible column types and overlapping entity names are fused.
Lookback window: 3 pages (to skip intervening pages with different layouts).

---

## Quick Start

```python
from morph.io.reader import open_pdf
from morph.core.typify import extract_particles
from morph.core.field import extract_page

# Read a PDF page
with open_pdf('catalog.pdf') as doc:
    page = doc[0]

    # Layer 1: gene expression
    particles = extract_particles(page, model_patterns=[], size_patterns=[])

    # Layer 1b + 2: sensing + field extraction
    result = extract_page(particles)

    print(f"Entities: {result['stats']['entities']}")
    print(f"Mapped specs: {result['stats']['mapped']}")
    for entity, specs in result['data'].items():
        print(f"\n{entity}:")
        for key, val in specs.items():
            print(f"  {key}: {val['value']} {val.get('unit', '')}")
```

### Full Pipeline

```bash
# Single PDF
python -m morph.pipeline catalog.pdf --brand hitachi -o output/

# Batch (all PDFs for one brand)
python -m morph.pipeline --batch brands/hitachi/input/ --brand hitachi

# Batch (all brands)
python -m morph.pipeline --batch-all
```

### Benchmarks

```bash
# GriTS on PubTables-1M (1000 tables, 4 cores)
python -m morph.bench.grits --n 1000 --cores 4

# GriTS on FinTabNet (cross-domain)
python -m morph.bench.grits --dataset fintabnet --n 1000 --cores 4

# Max-jump vs fixed-k comparison
python -m morph.bench.adaptive_k --n 1000 --cores 4
```

---

## Package Structure

```
morph/
├── __init__.py           # Public API, version, architecture docstring
├── pyproject.toml        # Package metadata
├── pipeline.py           # Full pipeline: PDF → Graph + SQL + RAG
├── README.md             # This file
│
├── core/                 # Processing layers
│   ├── __init__.py       # Re-exports
│   ├── typify.py         # L1: lexical particle classification
│   ├── sense.py          # L1b: spatial sensing + promotions
│   └── field.py          # L2: morphogenetic field equation
│
├── io/                   # Input/output adapters
│   ├── __init__.py       # Re-exports
│   ├── reader.py         # PyMuPDF PDF reader
│   ├── graph.py          # Entity → Graph L0 nodes
│   └── sql.py            # Graph → flat SQL rows
│
├── brands/               # Brand-specific patterns
│   ├── __init__.py       # Brand loader + detect_brand()
│   ├── universal.py      # Cross-brand HVAC vocabulary
│   ├── hitachi.py        # 30 model code patterns
│   ├── daikin.py         # 34 model + 3 size patterns
│   ├── toshiba.py        # 12 model code patterns
│   ├── mitsubishi.py     # 23 model code patterns
│   └── midea.py          # 24 model code patterns
│
├── bench/                # Benchmark suite
│   ├── __init__.py       # Results summary
│   ├── pubtables.py      # PubTables-1M adapter
│   ├── grits.py          # GriTS metric (Microsoft, MIT)
│   └── adaptive_k.py     # Max-ratio-jump experiment
│
└── docs/                 # Extended documentation
    ├── theory.md         # Mathematical foundations
    └── results.md        # Detailed benchmark results
```

**Total**: ~3,500 lines of production code across 18 modules.

---

## Strengths

1. **Zero training** — no annotated data, no model weights, no GPU.
   Deterministic from first principles + vocabulary.

2. **Cross-domain generalisation** — GriTS gap of only 2.1 pp between
   scientific papers (PubTables-1M) and financial filings (FinTabNet),
   despite never having seen either domain during development.

3. **Biological composability** — each layer is independently testable and
   replaceable.  The sensing layer alone contributed +27.7 pp health
   improvement without touching any vocabulary.

4. **Multi-brand scalability** — adding a new HVAC brand requires only
   a ~50-line regex file.  The core engine is invariant.

5. **Speed** — ~50 pages/second on CPU (i7-10850H).  No batching delays,
   no GPU scheduling, no model loading.

6. **Interpretability** — every decision is traceable: which particle was
   typed how, which field attracted which value to which model.  No black
   boxes.

## Weaknesses

1. **GriTS_Top < 80%** — competitive but not state-of-the-art.  Neural
   table detectors (TATR, TableFormer) achieve 85-95% but require GPU
   inference and large training sets.

2. **Spanning cells** — the engine assumes a regular grid.  Spanning cells
   (merged rows/columns) are not explicitly modelled, degrading GriTS on
   complex tables.

3. **Column detection relies on k=0.3** — a single constant for all table
   types.  The max-ratio-jump variant helps (+0.2-0.5 pp) but does not
   fully adapt to extreme layouts (e.g., 2-column vs 20-column tables).

4. **No row-label column detection** — the first column (often text labels)
   is not distinguished from data columns.  This reduces column exact match
   and occasionally causes misalignment.

5. **HVAC-specific vocabulary** — the brand patterns and spec terms are
   HVAC-domain.  Applying to a new domain (automotive, pharmaceutical)
   requires a new vocabulary layer (the "genome"), though the engine
   itself is domain-agnostic.

6. **No multi-line cell support** — cells that wrap to multiple lines are
   treated as separate rows, inflating the row count.

7. **Cross-page merge heuristic** — relies on column fingerprinting, which
   fails when table structure changes mid-page or when page numbers are
   embedded in the table area.

---

## Dependencies

**Required:**
- Python >= 3.11
- PyMuPDF (fitz) >= 1.23

**Optional (benchmarks):**
- numpy
- PubTables-1M dataset (words + XML annotations)
- FinTabNet.c-Structure dataset

**Optional (pipeline integration):**
- `knowledge` module (header normalisation, active learning)
- `parsers` module (numeric value parsing)

---

## Citing

If you use Morph in academic work, please cite:

```
Tacu, E. (2026). Self-organising spatial inference for structured
document parsing: a morphogenetic approach. Unpublished manuscript.
```

---

## Licenza / License

Questo codice e' parte del progetto Locus.  I benchmark GriTS includono
codice adattato dal repository Microsoft table-transformer (MIT License).

This code is part of the Locus project.  The GriTS benchmarks include
code adapted from the Microsoft table-transformer repository (MIT License).

---

# Sezione Italiana

## Morph — Riconoscimento Auto-Organizzante della Struttura Tabellare

**Morph** e' un motore morfogenetico per l'estrazione di dati strutturati
da cataloghi tecnici PDF.  Usa tre layer bio-ispirati — espressione genica,
differenziazione cellulare, e attrazione di campo — per riconoscere la
struttura delle tabelle **senza dati di training, inferenza GPU, o regole
specifiche per dominio**.

### Risultati Principali

| Metrica | Valore | Contesto |
|---------|--------|----------|
| **GriTS_Top** (PubTables-1M) | **79.7%** | N=10K, seed=42 |
| **GriTS_Top** (FinTabNet.c) | **77.6%** | N=10K, seed=42 |
| Gap cross-dominio | **2.1 pp** | Generalizzazione stabile |
| Health cataloghi HVAC | **95.2%** | 6.238 pagine, 5 brand |
| Velocita' | **~50 pag/s** | i7-10850H, nessuna GPU |

### Architettura a 3 Layer

1. **Layer 1 — Espressione Genica** (`typify.py`):
   Classificazione lessicale di ogni span PDF in 10 tipi di particella.
   Nessun training: classificazione deterministica da vocabolari e regex.

2. **Layer 1b — Differenziazione Cellulare** (`sense.py`):
   Ragionamento spaziale che ri-tipizza le particelle in base ai vicini.
   Rileva colonne verticali, promuove header, etichette spec, sezioni.
   Questo layer da solo ha migliorato la health HVAC del +27.7 pp.

3. **Layer 2 — Differenziazione Tissutale** (`field.py`):
   L'equazione di campo morfogenetico mappa valori NUMERIC a entita' MODEL:
   `Φ(i→j) = W · A / d^α` con distanza 3D (x, y, z=log₁₀(|v|+1)).

### Legge Universale dei Confini

Un gap e' un confine cella quando `gap > dim_media_elemento × k`.
Con k=0.3 per colonne e k=0.05 per righe, questa singola legge raggiunge
il 66.2% di column exact match su PubTables-1M senza parametri appresi.

### Punti di Forza

- **Zero training**: nessun dato annotato, nessun peso del modello
- **Generalizzazione cross-dominio**: gap di soli 2.1 pp tra paper
  scientifici e filing finanziari
- **Componibilita' biologica**: ogni layer e' testabile e sostituibile
  indipendentemente
- **Velocita'**: ~50 pagine/s su CPU, nessun collo di bottiglia GPU
- **Interpretabilita'**: ogni decisione e' tracciabile

### Punti Deboli

- **GriTS < 80%**: competitivo ma non state-of-the-art rispetto a
  detector neurali (85-95%)
- **Spanning cells**: non modellate esplicitamente
- **Vocabolario HVAC-specifico**: il dominio richiede un layer di
  conoscenza ("genoma"), anche se il motore e' domain-agnostic
- **Nessun supporto celle multi-riga**

### Tesi Centrale

> Per ogni problema dove la struttura e' implicita nei dati, esiste un
> principio biologico che la fa emergere, ed e' piu' efficiente di
> qualsiasi approccio che tenta di iniettarla dall'esterno.

Morph e' un data point a favore: 200 righe di sensing → +27.7% health,
zero training, zero GPU.  La **terza via** tra regole manuali e ML
data-driven: **principi auto-organizzativi**.

---

*Autore: Eugeniu Tacu, 2026*
