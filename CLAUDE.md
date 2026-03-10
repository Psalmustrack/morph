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

## TODO (parcheggiati)

- [ ] Aggiungere tests/ con pytest (attualmente zero test automatici)
- [ ] Benchmark su ICDAR, secondo dominio (non-HVAC)
- [ ] Processi biologici da implementare: termoregolazione, apoptosi, DNA proofreading (vedi MEMORY.md in dots.ocr)
- [ ] Paper: "Self-organizing spatial inference for structured document parsing: a morphogenetic approach"
- [ ] Pubblicazione GitHub (repo privata per ora)
