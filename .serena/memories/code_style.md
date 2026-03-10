# Morph — Code Style & Conventions

## Language
- Commenti: italiano
- Docstring: inglese (per pubblicazione)
- README/docs: bilingue EN+IT

## Python
- Type hints: sì, Python 3.10+ syntax (`list[dict]`, `str | None`)
- Docstring: presenti su funzioni pubbliche, stile conciso
- Encoding: UTF-8
- Path: `pathlib.Path`
- Import: standard lib → third-party → local (raggruppati)

## Naming
- Funzioni: snake_case
- Classi: PascalCase (MorphoPage, MorphoDoc)
- Costanti: UPPER_CASE (PARTICLE_TYPES, W_MATRIX)
- Private: prefisso `_` (es. `_cluster_by_x`, `_parse_z_norm`)
- Moduli: snake_case singolare (typify, sense, field)

## Architecture Patterns
- **Layered pipeline**: typify → sense → field (ordine rigoroso)
- **Particles everywhere**: dizionari `{text, x0, y0, x1, y1, type, ...}` come unita' base
- **Soft dependencies**: `try/except ImportError` per moduli opzionali (knowledge.py, parsers.py)
- **Brand patterns opzionali**: il sensing funziona senza brand, i brand sono boost
- **Zero side effects**: funzioni pure, no stato globale (eccetto pipeline.py)

## Constants & Magic Numbers
- Tutte le soglie hanno nomi espliciti e commenti (es. `k_x=0.3`, `k_y=0.05`)
- W_MATRIX: pesi campo morfogenetico, documentati in theory.md
- PARTICLE_TYPES: 8 tipi (NUMERIC, TEXT, MODEL, SPEC_LABEL, SECTION, UNIT, SKIP, CODE)
