# Morph — Task Completion Checklist

## After modifying code
1. Verifica import: `python -c "import morph"` (deve puntare a /home/jervis/Progetti/morph/)
2. Se modificato core/: testa tipizzazione base `typify_word('test')` 
3. Se modificato pipeline/field: E2E test su almeno 1 pagina PDF

## After adding new module/function
1. Aggiorna `__init__.py` del sub-package se è API pubblica
2. Aggiorna README.md se cambia l'architettura
3. Aggiorna docs/theory.md se cambia la matematica

## Before commit
1. `git diff` — review cambiamenti
2. `git status` — niente file non voluti
3. Test import funzionante

## No automated test suite yet
- Non ci sono test automatici (pytest) nel repo morph
- I benchmark vivono in dots.ocr/scripts/
- TODO: aggiungere tests/ con pytest
