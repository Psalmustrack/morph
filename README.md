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
| **Boundary Precision** | **93.3%** | 13.8M gaps, 102K tables, 3 domains |
| **Field Cell Accuracy** (PubTables-1M) | **72.3%** | 93,834 tables, zero vocabulary |
| **Field Cell Accuracy** (FinTabNet.c) | **76.8%** | 9,289 tables, zero vocabulary |
| **GriTS_Top** (PubTables-1M) | **79.9%** | N=10,000, max-jump |
| **GriTS_Top** (FinTabNet.c) | **78.1%** | N=10,000, max-jump |
| Cross-domain gap (columns) | **0.7 pp** | Field equation, full scale |
| **CORD Bond F1** (receipts) | **31.6%** | 800 receipts, zero vocabulary |
| CORD Precision (campo puro) | **89.6%** | 800 receipts, translation cost 0.1pp |
| **FUNSD Bond F1** (forms) | **21.1%** | 149 forms, 59% links unreachable (no NUMERIC) |
| **SROIE Total Recall** (scanned receipts) | **74.2%** | 626 receipts, noisy OCR coordinates |
| HVAC catalogue health | **95.2%** | 6,238 pages, 5 brands |
| Pages processed | **6,238** | 46 catalogues |
| Processing speed | **560 tab/s** | i7-10850H, no GPU |

### Direct Principle Test (Boundary Classification)

The most fundamental metric: for every gap between consecutive particles,
does `_natural_threshold` correctly classify it as boundary / non-boundary?

```
Dataset         Tables    Gaps classified   Precision   Recall    F1
PubTables-1M    93,142    12,752,714        93.3%       63.4%     75.5%
FinTabNet        9,195     1,017,468        73.7%       64.9%     69.0%
HVAC                 2           244        81.7%       84.6%     83.1%
```

**102K tables, 13.8M gaps, 94 seconds.** Zero domain-specific parameters.

### Field Equation Benchmark (Bond Accuracy)

The field equation (`Φ = W · A / d^α`) assigns every NUMERIC particle
to an entity (column) and a spec (row).  Bond accuracy measures whether
these assignments match GT bounding boxes, via majority voting.

```
Dataset          Tables     Col %    Row %    Cell %   Coverage   Speed
───────────────  ─────────  ───────  ───────  ───────  ─────────  ──────────
PubTables-1M      93,834    83.9     81.6     72.3     99.9%      560 tab/s
FinTabNet          9,289    83.2     93.0     76.8     100.0%     278 tab/s
───────────────  ─────────  ───────  ───────  ───────  ─────────  ──────────
Cross-domain gap             0.7pp            4.5pp
```

**103,123 tables in 200 seconds.** Zero training, zero GPU, zero vocabulary.
With HVAC domain vocabulary → 95%+ cell accuracy (+20 pp).

### GriTS Benchmark (Grid Translation)

The GriTS metric (Grid Table Similarity) is the official benchmark of
PubTables-1M (Microsoft, 2022).  It measures accuracy *after* translation
to a grid (rows x columns).

```
Method              PubTables-1M    FinTabNet.c     Gap
──────────────────  ──────────────  ──────────────  ────────
Morph (max-jump)       79.9%           78.1%         1.8 pp
```

The 13.4 pp gap between Boundary Precision (93.3%) and GriTS (79.9%)
is entirely due to the grid translator, not the underlying principle.

### CORD Benchmark (Receipt Key-Value Extraction)

CORD (Consolidated Receipt Dataset) contains 1,000 Indonesian receipts with
word-level annotations.  Each receipt has key→value bonds (e.g. "TOTAL" → "31.000").
Unlike tables, receipts are vertical lists — this tests whether the field
equation generalises beyond grid structures.

**Metric**: Entity-level F1 with 4 levels of strictness.

```
Level               Split    Prec     Recall   F1       Receipts
──────────────────  ───────  ───────  ───────  ───────  ────────
Spatial (campo)     test     87.7%    19.0%    31.3%    100
Spatial (campo)     train    89.6%    19.4%    31.8%    800
Bond (key match)    test     87.5%    18.6%    30.7%    100
Bond (key match)    train    89.5%    19.2%    31.6%    800
```

**Translation cost**: 0.1–0.5 pp (spatial → bond).  On receipts the field
output maps directly to F1 with essentially zero translation loss.

**Per-category recall** (train, 800 receipts):
- `total`: 61.0% — the field bonds total/cash/change to their values
- `sub_total`: 59.6% — subtotal, tax, discount bonds work
- `menu`: 0.4% — menu items (product → price) are invisible to the field

**Speed**: 1,168 receipts/s on CPU.

The bottleneck is clear: menu items are TEXT→NUMERIC pairs where the product
name has no SPEC_LABEL type.  The field ignores them because `W(TEXT, NUMERIC) = 0`.
This weakness directly maps to FUNSD (the next benchmark in the cascade),
where extending W to TEXT↔TEXT bonds is the central challenge.

### FUNSD Benchmark (Form Entity Linking)

FUNSD (Form Understanding in Noisy Scanned Documents) contains 199 scanned
forms with word-level annotations and entity linking (question→answer pairs).
This is the first TEXT↔TEXT benchmark: both questions ("TO:", "DATE:") and
answers ("George Baroody", "12/10/98") are mostly text, not numeric.

**Metric**: Entity-linking F1 at two levels.

```
Level               Split    Prec     Recall   F1       Forms
──────────────────  ───────  ───────  ───────  ───────  ─────
Spatial (any Q)     test     53.4%    19.2%    28.2%    50
Spatial (any Q)     train    73.0%    22.0%    33.8%    149
Bond (correct Q)    test     44.7%    13.5%    20.8%    50
Bond (correct Q)    train    61.2%    12.8%    21.1%    149
```

**Translation cost**: 5.6–9.2 pp (spatial → bond).  Higher than CORD (0.1 pp)
because the field sometimes points to the wrong question entity.

**Structural bottleneck**:
- 59% of GT links are **unreachable** — the answer entity has no NUMERIC words
- Only 22–24% of answer words are NUMERIC (the rest is pure text)
- Only 3% of question words are NUMERIC → field cannot target them
- On reachable links only: recall rises to ~32%

**Diagnosis**: `W(TEXT, TEXT) = 0` is the root cause.  The field cannot create
bonds between text entities.  Extending W is the next architectural step —
it would unlock both FUNSD (form understanding) and CORD menu items.

**Speed**: 190 forms/s on CPU.

### SROIE Benchmark (Scanned Receipt Key Extraction)

SROIE (ICDAR 2019 Scanned Receipts) contains 626 scanned receipt images with
word-level OCR bounding boxes and 4 key GT fields: company, address, date, total.
Unlike CORD (digital receipts), SROIE uses real scanned images with noisy OCR
coordinates (±2-5px jitter).  This tests whether the field equation degrades
with coordinate noise.

**Metric**: Per-field recall (presence of bonded GT words).

```
Campo       Present   Absent   NoMatch   Reachable   Recall
──────────  ────────  ───────  ────────  ──────────  ───────
company          0      626      598           0      0.0%
date           118      508        3         203     18.8%
address          1      624      559           1      0.2%
total          464      161       35         503     74.2%
```

**Key finding: total recall 74.2% > CORD 61.0%** — the field is robust to
OCR noise.  Scanned coordinates do not degrade the spatial principle.

**Per-field analysis**:
- `total`: 74.2% — best field, NUMERIC matching is noise-tolerant
- `date`: 18.8% — dates contain digits, but partial matching limits recall
- `company` / `address`: 0.0% / 0.2% — pure TEXT fields, `W(TEXT, TEXT) = 0`
- 598/559 NoMatch — OCR noise breaks token-level GT matching

**Macro F1**: 14.6% (P=10.6%, R=23.3%).  Low because 3 of 4 fields are TEXT-only.

**Speed**: 461 receipts/s on CPU (2.3x faster than CORD — fewer particles/receipt).

**Type distribution**: 48.4% TEXT, 29.5% NUMERIC, 18.0% SPEC_LABEL, 2.5% SECTION.

**Comparison with CORD**: Same receipt domain, different input quality:
- SROIE total recall (74.2%) > CORD total recall (61.0%) → +13.2 pp
- Both hit the same structural wall: TEXT fields invisible to the field

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
# Field equation bond accuracy (PubTables-1M, all tables)
python -m morph.bench.pubtables --n 0

# Field equation bond accuracy (FinTabNet, cross-domain)
python -m morph.bench.pubtables --dataset fintabnet --n 0

# Direct principle test (all tables, all 3 datasets)
python tests/test_principle.py --axis x --cores 4

# Quick principle test (1000 per dataset)
python -m morph.bench.boundaries --n 1000 --dataset all --cores 4

# GriTS on PubTables-1M (1000 tables, 4 cores)
python -m morph.bench.grits --n 1000 --cores 4

# GriTS on FinTabNet (cross-domain)
python -m morph.bench.grits --dataset fintabnet --n 1000 --cores 4

# Max-jump vs fixed-k comparison
python -m morph.bench.adaptive_k --n 1000 --cores 4

# CORD receipt benchmark (test split, 100 receipts)
python -m morph.bench.cord --split test

# CORD receipt benchmark (train split, 800 receipts)
python -m morph.bench.cord --split train

# FUNSD form entity linking (test split, 50 forms)
python -m morph.bench.funsd --split test

# FUNSD form entity linking (train split, 149 forms)
python -m morph.bench.funsd --split train

# SROIE scanned receipt benchmark (all 626 receipts)
python -m morph.bench.sroie

# SROIE with verbose output
python -m morph.bench.sroie --n 100 --verbose

# Regression tests (65 tests)
pytest tests/ -v
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
│   ├── grid.py           # Grid translator (particles → rows/columns)
│   ├── boundaries.py     # Direct principle test (gap classification)
│   ├── cord.py           # CORD receipt benchmark (F1, 4 levels)
│   ├── funsd.py          # FUNSD form entity linking (F1, 2 levels)
│   ├── sroie.py          # SROIE scanned receipt benchmark (noise tolerance)
│   └── adaptive_k.py     # Max-ratio-jump experiment
│
└── docs/                 # Extended documentation
    ├── theory.md         # Mathematical foundations
    ├── results.md        # Detailed benchmark results
    └── morph_for_mathematician.md  # Full system explanation for external review
```

**Total**: ~6,200 lines across 24 modules (core + bench + io + brands).

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

3. **Equispaced columns are invisible to the principle** — `_natural_threshold`
   requires bimodal gap distributions.  Tables with perfectly uniform column
   spacing produce unimodal gaps where no natural break exists.  The grid
   translator falls back to `gap/particle_size` ratio in these cases.

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
- CORD dataset (receipt JSON annotations)
- FUNSD dataset (form entity linking annotations)
- SROIE dataset (scanned receipt OCR boxes + key JSON)

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
| **Precision confini** | **93.3%** | 13.8M gap, 102K tabelle, 3 domini |
| **Cell accuracy campo** (PubTables-1M) | **72.3%** | 93.834 tabelle, zero vocabolario |
| **Cell accuracy campo** (FinTabNet.c) | **76.8%** | 9.289 tabelle, zero vocabolario |
| **GriTS_Top** (PubTables-1M) | **79.9%** | N=10K, max-jump |
| **GriTS_Top** (FinTabNet.c) | **78.1%** | N=10K, max-jump |
| Gap cross-dominio (colonne) | **0.7 pp** | Campo, full scale |
| **CORD Bond F1** (ricevute) | **31.6%** | 800 ricevute, zero vocabolario |
| CORD Precision (campo puro) | **89.6%** | 800 ricevute, costo traduzione 0.1pp |
| **FUNSD Bond F1** (form) | **21.1%** | 149 form, 59% link irraggiungibili (no NUMERIC) |
| **SROIE Total Recall** (ricevute scansionate) | **74.2%** | 626 ricevute, OCR rumoroso |
| Health cataloghi HVAC | **95.2%** | 6.238 pagine, 5 brand |
| Velocita' | **560 tab/s** | i7-10850H, nessuna GPU |

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

### Il Principio Percettivo

Il confine tra celle emerge dalla **discontinuita' massima** nella
distribuzione dei gap. `_natural_threshold` ordina i gap, trova il
rapporto consecutivo massimo, e piazza la soglia nel punto di salto.

Testato su 13.8 milioni di gap in 102K tabelle: **93.3% precision**
su 3 domini (paper, finanza, HVAC) con zero parametri dominio-specifici.

### Punti di Forza

- **Zero training**: nessun dato annotato, nessun peso del modello
- **Generalizzazione cross-dominio**: gap di soli 1.8 pp tra paper
  scientifici e filing finanziari, testato su 3 domini
- **Componibilita' biologica**: ogni layer e' testabile e sostituibile
  indipendentemente
- **Velocita'**: ~50 pagine/s su CPU, nessun collo di bottiglia GPU
- **Interpretabilita'**: ogni decisione e' tracciabile

### Punti Deboli

- **GriTS ~ 80%**: competitivo ma non state-of-the-art rispetto a
  detector neurali (85-95%). Il gap e' nella traduzione griglia, non
  nel principio (93.3% precision nativa)
- **Colonne equispaziate**: il principio richiede bimodalita' nei gap.
  Tabelle con spaziatura uniforme non hanno un break naturale
- **Spanning cells**: non modellate esplicitamente
- **Vocabolario HVAC-specifico**: il dominio richiede un layer di
  conoscenza ("genoma"), anche se il motore e' domain-agnostic

### Tesi Centrale

> Per ogni problema dove la struttura e' implicita nei dati, esiste un
> principio biologico che la fa emergere, ed e' piu' efficiente di
> qualsiasi approccio che tenta di iniettarla dall'esterno.

Morph e' un data point a favore: 200 righe di sensing → +27.7% health,
zero training, zero GPU.  La **terza via** tra regole manuali e ML
data-driven: **principi auto-organizzativi**.

---

*Autore: Eugeniu Tacu, 2026*
