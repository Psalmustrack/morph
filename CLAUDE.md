# Morph — Istruzioni per Claude

## Progetto

Engine di estrazione tabelle da PDF ispirato alla morfogenesi biologica. Training-free, GPU-free.
Pipeline a 3 layer: typify (gene expression) → sense (cellular differentiation) → field (tissue formation).

**Autore**: Eugeniu Tacu
**Licenza**: MIT
**Versione**: 0.1.0

## Architettura

```
PDF → [PyMuPDF] → word list
                      │
              ┌───────▼───────┐
              │  Layer 1:     │  typify.py — classificazione lessicale
              │  typify       │  8 tipi: NUMERIC, TEXT, MODEL, SPEC_LABEL,
              │               │          SECTION, UNIT, SKIP, CODE
              └───────┬───────┘
              ┌───────▼───────┐
              │  Layer 1b:    │  sense.py — sensing spaziale
              │  sense        │  Colonne NUMERIC, header, spec_label, section
              └───────┬───────┘
              ┌───────▼───────┐
              │  Layer 2:     │  field.py — campo morfogenetico
              │  field        │  Phi(i→j) = W · A_directed / d^alpha
              └───────┬───────┘
                      │
              Entity list → Graph L0 / SQL / RAG
```

## Struttura package

```
morph/
├── core/              ← Algoritmi (non toccare senza capire la matematica)
│   ├── typify.py      ← Layer 1: classificazione lessicale (294 righe)
│   ├── sense.py       ← Layer 1b: sensing spaziale (646 righe)
│   └── field.py       ← Layer 2: campo morfogenetico (572 righe)
├── io/                ← Input/Output
│   ├── reader.py      ← Adapter PyMuPDF (MorphoPage, MorphoDoc, open_pdf)
│   ├── graph.py       ← Entity → Graph L0 (nodi + edges JSON)
│   └── sql.py         ← Graph → righe SQL flat
├── brands/            ← Pattern brand-specifici (OPZIONALI — il sensing funziona senza)
│   ├── universal.py   ← Vocabolario condiviso HVAC
│   ├── hitachi.py, daikin.py, toshiba.py, mitsubishi.py, midea.py
│   └── __init__.py    ← detect_brand(), get_brand_patterns()
├── bench/             ← Suite benchmark (richiede numpy + rapidfuzz)
│   ├── grits.py       ← Metrica GriTS (2D DP alignment, MIT)
│   ├── pubtables.py   ← Adapter PubTables-1M
│   └── adaptive_k.py  ← Max-ratio-jump benchmark
├── pipeline.py        ← Pipeline end-to-end: PDF → Graph + SQL + RAG
└── __init__.py        ← v0.1.0
```

## File chiave

- `docs/theory.md` — Fondamenti matematici (equazione di campo, boundary law, complessita')
- `docs/results.md` — Benchmark (PubTables-1M, FinTabNet, HVAC, ablation study)
- `README.md` — Paper-quality bilingue (EN + IT)

## Risultati benchmark

| Dataset | GriTS_Top | Note |
|---------|-----------|------|
| PubTables-1M | 79.7% | 93K tabelle |
| FinTabNet | 77.6% | 10K tabelle |
| HVAC (5 brand) | 95.2% health | 46 cataloghi, 6238 pagine |
| Cross-domain gap | 2.1pp | Universalita' confermata |

## Relazione con Locus (dots.ocr)

Morph e' stato estratto da `dots.ocr` come package indipendente.

- **dots.ocr** (`/mnt/dati/home/Progetti/dots.ocr`): pipeline PDF-to-RAG multi-brand completa (MinerU, pdfplumber, SQLite, ChromaDB, Knowledge Graph). Usa morph come dipendenza.
- **morph** (`/home/jervis/Progetti/morph`): solo l'engine di estrazione tabelle. Zero dipendenze esterne oltre PyMuPDF.

Gli script di benchmark vivono in `dots.ocr/scripts/` e importano da `morph.*`.
Il venv condiviso e' in `dots.ocr/.venv/` con `pip install -e /home/jervis/Progetti/morph/`.

## Convenzioni codice

- **Lingua commenti**: italiano
- **Lingua docstring**: inglese (per pubblicazione)
- **Type hints**: Python 3.10+ (`list[dict]`, `str | None`)
- **Path**: `pathlib.Path`
- **Naming**: snake_case funzioni, PascalCase classi, UPPER_CASE costanti
- **Private**: prefisso `_`
- **Zero side effects**: funzioni pure, no stato globale (eccetto pipeline.py)
- **Soft dependencies**: `try/except ImportError` per moduli opzionali

## Costanti importanti

| Costante | Valore | Dove |
|----------|--------|------|
| k_x (boundary colonne) | 0.3 | field.py |
| k_y (boundary righe) | 0.05 | field.py |
| alpha (decadimento campo) | 2.0 | field.py |
| W_MATRIX | 8x8 pesi | field.py |
| PARTICLE_TYPES | 8 tipi | typify.py |

## Ambiente

```bash
# Attivare SEMPRE il venv prima di eseguire qualsiasi cosa
source /mnt/dati/home/Progetti/dots.ocr/.venv/bin/activate

# Verifica che morph punti al repo giusto
python -c "import morph; print(morph.__file__)"
# Output atteso: /home/jervis/Progetti/morph/morph/__init__.py (o /mnt/dati/...)
```

## Comandi utili

```bash
# Quick test
python -c "from morph.core.typify import typify_word; print(typify_word('42.5'))"

# E2E su pagina singola
python -c "
from morph.io.reader import open_pdf
from morph.core.typify import extract_particles
from morph.core.sense import sense_page
from morph.core.field import extract_page
doc = open_pdf('/path/to/catalog.pdf')
particles = extract_particles(doc[30], [], [])
result = sense_page(particles)
entities = extract_page(result['particles'])
print(f'Entities: {len(entities[\"entities\"])}')
"
```

## Regole

1. **Non modificare core/ senza capire la matematica** — leggere docs/theory.md prima
2. **Le soglie (k_x, k_y, alpha, W) sono calibrate su benchmark** — cambiare solo con ablation study
3. **I brands sono opzionali** — il sensing (Layer 1b) funziona senza pattern brand-specifici
4. **Soft dependencies** — morph deve funzionare standalone con solo PyMuPDF
5. **Aggiornare docs/** se cambia la matematica o i risultati
6. **Aggiornare README.md** se cambia l'architettura

## 🚀 MORPH v2.0 — CAMPO MORFOGENETICO COMPLETO

**Status:** In sviluppo su branch `feature/v2.0`
**Baseline:** v0.1.0 (main branch) — GriTS 86.0%, precision 92.3%
**Vision:** Morph con TUTTI i sensi — campo multi-sensoriale come in natura

### Principio fondamentale

**L'equazione NON cambia:**
```
Φ = W · A / d^α
```

**Ma cambia:**
- **d diventa RICCO** (multi-dimensionale: geo + font + hierarchy + color)
- **+Φ_repel** (dualità attrattivo-repulsivo)
- **σ contestuale** (calibrazione adattiva da TOC/metadati)

### La visione (conversazione con Opus)

Morph v0.1 vede solo 3 feature (text, bbox, size) — come un organismo con UN solo senso (posizione).

PyMuPDF estrae 10+ strati di informazione:
1. Geometria (x, y, width, height)
2. Tipografia (font, bold, size, color)
3. Struttura (spans, lines, blocks hierarchy)
4. Vettoriale (linee, rettangoli, bordi)
5. Metadati (TOC, author, title, lingua)
6. Drawings (separatori visivi)
7. Baseline (allineamento preciso)
... e altro

**Morph v2.0 = campo che vede TUTTO.**

Come un embrione biologico non usa solo gradienti chimici, ma anche:
- Tensione meccanica
- Segnali elettrici
- Espressione genetica
- Concentrazioni locali

**Morph v2.0 usa:**
- Geometria (x, y)
- Tipografia (font, bold, color)
- Struttura (span, line, block hierarchy)
- Vuoto (spazio negativo — repulsione!)
- Contesto (TOC section → calibra σ)

### Roadmap (6 phases)

**Vedi:** `ROADMAP_v2.md` per dettagli completi

**Phase 0:** BASELINE (punto zero)
- 5 PDF HVAC + 100 PubTables + altri dataset
- Salva TUTTO: particles, types, bonds, unmapped, accuracy
- Questo è il PUNTO ZERO per confronti

**Phase 1:** READER++ (PyMuPDF full)
- Estrae font, bold, color, hierarchy, baseline, drawings, TOC
- Output: particles RICCHE (11+ features vs 3 attuali)

**Phase 2:** TYPIFY++ (semantica robusta)
- Usa font/bold per classificazione (MODEL sempre bold, NUMERIC mai bold)
- Fuzzy matching (rapidfuzz) per typo/OCR
- Pattern semantici (DATE, EMAIL, REFERENCE, STANDARD)

**Phase 3:** FIELD++ Part 1 (distanza multi-dimensionale)
- d² = dx² + dy² + dz² + df² + dh² + dc²
- Font affinity, hierarchy affinity, color affinity
- Campo vede similarità tipografica, non solo geometrica

**Phase 4:** FIELD++ Part 2 (dualità repulsiva)
- Φ_total = Φ_attract + Φ_repel
- Whitespace = forza repulsiva
- Confini emergono dove Φ_total = 0
- Max-jump diventa caso particolare del campo duale!

**Phase 5:** FIELD++ Part 3 (calibrazione contestuale)
- σ = f(section, language, has_borders)
- "Specifiche" → σ piccolo (dense)
- "Dimensioni" → σ grande (sparse)
- Il campo RESPIRA con il documento

**Phase 6:** SENSE++ (hybrid boundaries)
- Se drawings presenti → usa linee verticali (esatte!)
- Altrimenti → usa campo Φ_total=0
- Whitespace per confini TRA tabelle

### Decision points

**Dopo Phase 3:**
- Distanza multi-dim migliora? → SÌ: Phase 4, NO: rivedi pesi σ

**Dopo Phase 4:**
- Dualità risolve cross-table? → SÌ: Phase 5, NO: rivedi R

**Dopo Phase 6:**
- v2.0 completo? → SÌ: release, NO: nice-to-have

### Metriche target (stimate)

- Field mapping: +20-30% accuracy
- Boundary detection: +15-25% (dipende da dataset)
- Robustezza OCR: +15% (con fuzzy)
- Universalità: tabelle bordered + borderless

### Branch strategy

```
main (v0.1.0 stabile)
  └─ feature/v2.0 (sviluppo)
       └─ phase1, phase2, ... (sotto-branch se necessario)
```

Quando v2.0 pronto: PR → review → merge → tag v2.0.0

### File chiave v2.0

- `ROADMAP_v2.md` — Piano maniacale completo
- `data/baseline_v0.1.json` — Baseline multi-dataset
- `scripts/baseline_v0.1.py` — Script raccolta baseline
- `morph/io/reader.py` — PyMuPDF full extraction
- `morph/core/typify.py` — Font-based + fuzzy
- `morph/core/field.py` — Multi-dim + dualità + contesto
- `morph/core/sense.py` — Hybrid boundaries

### Contributori visione v2.0

- **Eugeniu (utente):** Creatività, visione, "pensare fuori dagli schemi"
- **Claude Code (Sonnet 4.5):** Implementazione, architettura tecnica
- **Claude Opus 4:** Validazione metodologica, correzioni critiche (Phase 0, calibrazione R)

**Insieme:** v0.1 → v2.0 senza fare "fix su fix su fix" — trasformazione sistematica!

---

## TODO (parcheggiati per dopo v2.0)

- [ ] Aggiungere tests/ con pytest (attualmente zero test automatici)
- [ ] Benchmark su ICDAR, secondo dominio (non-HVAC)
- [ ] Processi biologici da implementare: termoregolazione, apoptosi, DNA proofreading (vedi MEMORY.md in dots.ocr)
- [ ] Paper: "Self-organizing spatial inference for structured document parsing: a morphogenetic approach"
- [ ] Pubblicazione GitHub pubblica
