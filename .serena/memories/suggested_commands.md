# Morph — Suggested Commands

## Install (editable mode)
```bash
pip install -e /home/jervis/Progetti/morph/
pip install -e "/home/jervis/Progetti/morph/[bench]"  # con numpy+rapidfuzz
```

## Test import
```bash
python -c "from morph.core.typify import typify_word; print(typify_word('RAS-8FSXNME'))"
python -c "from morph.io.reader import open_pdf; print('OK')"
```

## Quick E2E test (singola pagina)
```bash
python -c "
from morph.io.reader import open_pdf
from morph.core.typify import extract_particles
from morph.core.sense import sense_page
from morph.core.field import extract_page
from morph.brands import get_brand_patterns

doc = open_pdf('/path/to/catalog.pdf')
page = doc[30]
mp, sp = get_brand_patterns('hitachi')
particles = extract_particles(page, mp, sp)
result = sense_page(particles)
entities = extract_page(result['particles'])
print(f'Entities: {len(entities[\"entities\"])}')
"
```

## Run benchmarks (richiede dataset scaricati)
```bash
# Da dots.ocr (dove vivono gli script)
cd /mnt/dati/home/Progetti/dots.ocr
source .venv/bin/activate
python scripts/bench_pubtables.py
python scripts/bench_grits.py
python scripts/bench_adaptive_k.py
```

## Git
```bash
cd /home/jervis/Progetti/morph
git status
git log --oneline
git diff
```

## System
- `git`, `ls`, `cd`, `grep`, `find` — standard Linux
- Python venv: `source /mnt/dati/home/Progetti/dots.ocr/.venv/bin/activate`
