# 🚀 ROAD TO MORPH v2.0

**Vision:** Morph con TUTTI i sensi — il campo morfogenetico completo come in natura.

**Principio fondamentale:** L'equazione NON cambia. L'input diventa ricco.

```
Φ = W · A / d^α     ← IMMUTABILE

d² = Σᵢ (Δᵢ / σᵢ)²  ← MULTI-DIMENSIONALE

Φ_total = Φ_attract + Φ_repel  ← DUALITÀ
```

---

## 📊 ARCHITETTURA ATTUALE (v0.1)

### La catena di trasformazione:

```
┌──────────────────────────────────────────────────────────────┐
│ LAYER 0: READER (morph/io/reader.py)                         │
│                                                               │
│  PDF → PyMuPDF → extract_words() → particles                 │
│                                                               │
│  Input:  PDF file                                            │
│  Output: [{text, x0, top, x1, bottom, size}, ...]           │
│                                                               │
│  OGGI USA:                                                    │
│    ✓ text                                                     │
│    ✓ bbox (x0, top, x1, bottom)                              │
│    ✓ size                                                     │
│                                                               │
│  NON USA (ma PyMuPDF fornisce):                              │
│    ✗ font name                                                │
│    ✗ flags (bold, italic, mono)                              │
│    ✗ color (RGB)                                              │
│    ✗ origin (baseline)                                        │
│    ✗ ascender/descender                                       │
│    ✗ span_id, line_id, block_id (hierarchy)                  │
│    ✗ drawings (linee, rettangoli)                            │
│    ✗ metadati PDF (TOC, author, title)                       │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1: TYPIFY (morph/core/typify.py)                       │
│                                                               │
│  particles → typify_word() → particles con TYPE               │
│                                                               │
│  Input:  [{text, x, y, size}, ...]                          │
│  Output: [{text, x, y, size, type}, ...]                    │
│                                                               │
│  Funzioni chiave:                                            │
│    • typify_word(text, size) → type                          │
│    • extract_particles(page) → particles tipizzate           │
│                                                               │
│  OGGI USA:                                                    │
│    ✓ regex patterns (NUMERIC, UNIT, MODEL, etc.)            │
│    ✓ size (per distinguere HEADER vs TEXT)                   │
│                                                               │
│  NON USA:                                                     │
│    ✗ font/bold (MODEL sempre bold, NUMERIC mai bold)         │
│    ✗ fuzzy matching (typo/OCR errors)                        │
│    ✗ lingua detection (RTL, CJK)                             │
│    ✗ pattern semantici avanzati (DATE, EMAIL, STANDARD)      │
│    ✗ vocabolario contestuale (da TOC)                        │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2: FIELD (morph/core/field.py)                         │
│                                                               │
│  particles → extract_page() → {entity: {spec: value}}        │
│                                                               │
│  Input:  particles con type                                  │
│  Output: structured data dict                                │
│                                                               │
│  Funzioni chiave:                                            │
│    • calibrate_sigma(particles) → σ_x, σ_y                   │
│    • calibrate_lambda_z(numerics) → λ_z                      │
│    • _phi(p1, p2, axis, σ_y, σ_x, λ_z) → Φ                  │
│    • extract_page(particles) → result dict                   │
│                                                               │
│  EQUAZIONE CAMPO:                                            │
│    Φ = W · exp(-d²/σ²) · z_affinity                          │
│                                                               │
│    dove:                                                      │
│      d² = (dx/σ_x)² + (dy/σ_y)²     (solo geometria)         │
│      z_affinity = z_boost se magnitude match                 │
│                                                               │
│  OGGI USA:                                                    │
│    ✓ Posizione (x, y)                                        │
│    ✓ Magnitude (z_norm per NUMERIC)                          │
│    ✓ merge_multiline_specs (Y-tolerance 9px)                │
│                                                               │
│  NON USA:                                                     │
│    ✗ Font affinity (stesso font → più vicini)                │
│    ✗ Hierarchy affinity (stesso span → molto vicini)         │
│    ✗ Color affinity                                          │
│    ✗ Baseline alignment (più preciso di bbox)                │
│    ✗ Repulsione (whitespace)                                 │
│    ✗ Calibrazione contestuale (σ per sezione)                │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3: SENSE (morph/core/sense.py)                         │
│                                                               │
│  particles → sense_page() → columns, row_label_col, etc.     │
│                                                               │
│  Funzioni chiave:                                            │
│    • detect_columns(particles) → column boundaries           │
│    • _natural_threshold(gaps) → max ratio threshold          │
│    • _crystallize_columns(particles) → periodic alignment    │
│    • promote_* → raffinamento types                          │
│    • sense_page(particles) → enhanced structure              │
│                                                               │
│  OGGI USA:                                                    │
│    ✓ Gap detection (X-axis)                                  │
│    ✓ Natural threshold (max ratio)                           │
│    ✓ Crystallization (periodic rescue)                       │
│                                                               │
│  NON USA:                                                     │
│    ✗ Drawings (linee verticali = column splits esatti!)      │
│    ✗ Whitespace areas (confini TRA tabelle)                  │
│    ✗ Calibrazione contestuale                                │
└──────────────────────────────────────────────────────────────┘
```

---

## 🎯 ARCHITETTURA TARGET (v2.0)

### Cosa cambia in ogni layer:

```
┌──────────────────────────────────────────────────────────────┐
│ LAYER 0: READER++ (PyMuPDF FULL)                             │
│                                                               │
│  NUOVE ESTRAZIONI:                                           │
│    ✓ Font name, flags (bold/italic), color                   │
│    ✓ Origin (baseline), ascender/descender                   │
│    ✓ Span/line/block hierarchy IDs                           │
│    ✓ Drawings (linee, rettangoli, paths)                     │
│    ✓ Metadati PDF (title, author, TOC, lang)                 │
│    ✓ Images (per futuro)                                     │
│                                                               │
│  PREPROCESSING:                                              │
│    ✓ ftfy.fix_text() — fix encoding                          │
│    ✓ normalize_unicode() — "℃" → "°C"                        │
│                                                               │
│  Output: RICH particles                                      │
│    [{text, x, y, size, font, bold, color, baseline,          │
│      span_id, line_id, block_id}, ...]                       │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1: TYPIFY++ (SEMANTICA ROBUSTA)                        │
│                                                               │
│  NUOVE CLASSIFICAZIONI:                                      │
│    ✓ Font-based rules (bold → MODEL, regular → NUMERIC)      │
│    ✓ Fuzzy matching (rapidfuzz per typo/OCR)                 │
│    ✓ Lingua detection (langdetect)                           │
│    ✓ Pattern semantici:                                      │
│        - DATE, EMAIL, PHONE, URL                             │
│        - REFERENCE (Fig/Tab/Eq), SECTION_NUMBER              │
│        - STANDARD (ISO/EN/DIN)                               │
│    ✓ Unicode classification (CIRCLED_DIGIT → LIST_MARKER)    │
│    ✓ Vocabolario contestuale (carica vocab per sezione TOC)  │
│                                                               │
│  Output: particles con TYPE robusto                          │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2: FIELD++ (CAMPO MULTI-DIMENSIONALE + DUALITÀ)        │
│                                                               │
│  EQUAZIONE CAMPO (IMMUTABILE):                               │
│    Φ = W · A / d^α                                           │
│                                                               │
│  DISTANZA MULTI-DIMENSIONALE:                                │
│    d² = (dx/σ_x)² + (dy/σ_y)² + (dz·λ_z)²                   │
│         + (df/σ_f)² + (dh/σ_h)² + (dc/σ_c)²                 │
│                                                               │
│    dove:                                                      │
│      df = distanza font:                                     │
│           0 se stesso font+size, 1 altrimenti                │
│                                                               │
│      dh = distanza hierarchy:                                │
│           0.0 se stesso span                                 │
│           0.5 se stesso line                                 │
│           1.0 se block diverso                               │
│                                                               │
│      dc = distanza color:                                    │
│           Euclidean in RGB space                             │
│                                                               │
│  DUALITÀ ATTRATTIVO-REPULSIVO:                               │
│    Φ_attract = W · A / d^α         (esistente)               │
│    Φ_repel = -R · area_void / d_void^α  (nuovo)              │
│                                                               │
│    Φ_total = Φ_attract + Φ_repel                             │
│                                                               │
│    Confine naturale dove Φ_total = 0                         │
│                                                               │
│  CALIBRAZIONE CONTESTUALE:                                   │
│    σ = f(section, language, has_borders)                     │
│                                                               │
│    Es: sezione "Specifiche" → σ_x=10, σ_y=5 (dense)         │
│        sezione "Dimensioni" → σ_x=30, σ_y=15 (rade)         │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3: SENSE++ (HYBRID BOUNDARIES)                         │
│                                                               │
│  HYBRID DETECTION:                                           │
│    if has_vertical_lines:                                    │
│        col_splits = [line.x for line in v_lines]             │
│    else:                                                      │
│        col_splits = campo Φ_total = 0                        │
│                                                               │
│  WHITESPACE ANALYSIS:                                        │
│    Rettangoli vuoti grandi = confini TRA tabelle             │
│                                                               │
│  CALIBRAZIONE CONTESTUALE:                                   │
│    Natural threshold k = f(section)                          │
└──────────────────────────────────────────────────────────────┘
```

---

## 🛠️ IMPLEMENTATION ROADMAP

### **PHASE 1: READER++ (PyMuPDF full extraction)**

**Obiettivo:** Estrarre TUTTO da PyMuPDF

**Files modificati:**
- `morph/io/reader.py`

**Modifiche:**

1. **MorphoPage.extract_words()** — arricchire output
   ```python
   # OGGI:
   return {
       'text': text,
       'x0': bbox[0], 'top': bbox[1],
       'x1': bbox[2], 'bottom': bbox[3],
       'size': size,
   }

   # DOMANI:
   return {
       'text': ftfy.fix_text(text),
       'x0': bbox[0], 'top': bbox[1],
       'x1': bbox[2], 'bottom': bbox[3],
       'size': size,
       # NUOVO:
       'font': span['font'],
       'flags': span['flags'],
       'is_bold': bool(span['flags'] & 16),
       'is_italic': bool(span['flags'] & 2),
       'color': span['color'],
       'origin': span['origin'],
       'ascender': span['ascender'],
       'descender': span['descender'],
       'span_id': f'{block_idx}_{line_idx}_{span_idx}',
       'line_id': f'{block_idx}_{line_idx}',
       'block_id': block_idx,
   }
   ```

2. **MorphoDoc** — estrarre metadati
   ```python
   def __init__(self, path: str):
       self._doc = fitz.open(str(path))
       self.metadata = self._doc.metadata
       self.toc = self._doc.get_toc()
       self.has_drawings = {}  # cache per pagina

   def get_page_context(self, page_num: int) -> dict:
       """Contesto per calibrazione"""
       section = self._find_section(page_num)
       return {
           'section': section,
           'language': self.metadata.get('language', 'en'),
           'title': self.metadata.get('title', ''),
       }
   ```

3. **Nuovo: extract_drawings()** per page
   ```python
   def extract_drawings(self) -> dict:
       """Estrae linee verticali/orizzontali"""
       drawings = self._page.get_drawings()

       v_lines = []  # [(x, y1, y2), ...]
       h_lines = []  # [(y, x1, x2), ...]

       for d in drawings:
           # ... analizza paths
           pass

       return {'vertical': v_lines, 'horizontal': h_lines}
   ```

**Test:**
```python
# Test 1: Font extraction
pdf = open_pdf('test.pdf')
words = pdf[0].extract_words()
assert 'font' in words[0]
assert 'is_bold' in words[0]

# Test 2: Metadati
assert pdf.metadata is not None
assert pdf.toc is not None

# Test 3: Drawings
drawings = pdf[0].extract_drawings()
assert 'vertical' in drawings
```

**Dipendenze:**
```bash
pip install ftfy  # 50KB
```

**Deliverable:** Reader che estrae TUTTO da PyMuPDF

---

### **PHASE 2: TYPIFY++ (Classificazione robusta)**

**Obiettivo:** Usare font/flags per classificazione + fuzzy matching

**Files modificati:**
- `morph/core/typify.py`

**Modifiche:**

1. **typify_word()** — usa font/bold
   ```python
   def typify_word(text: str, size: float,
                   font: str = '', is_bold: bool = False) -> str:
       """Classificazione con font flags"""

       # REGOLA 1: NUMERIC mai bold
       if _is_numeric(text):
           if is_bold:
               return 'TEXT'  # probabilmente non è un valore
           if 'Regular' in font and size <= 7.5:
               return 'NUMERIC'  # alta confidenza
           return 'NUMERIC'

       # REGOLA 2: MODEL sempre bold
       if is_bold and size >= 7:
           if _is_model_pattern(text):
               return 'MODEL'

       # ... resto logica esistente
   ```

2. **Nuovo: fuzzy_match_vocab()**
   ```python
   from rapidfuzz import fuzz

   def fuzzy_match_vocab(text: str, vocab: list[str],
                         threshold: int = 85) -> str | None:
       """Fuzzy matching per typo/OCR"""
       for term in vocab:
           score = fuzz.ratio(text.lower(), term.lower())
           if score >= threshold:
               return term
       return None

   # In typify_word:
   if match := fuzzy_match_vocab(text, SPEC_VOCAB):
       return 'SPEC_LABEL'
   ```

3. **Nuovo: pattern semantici**
   ```python
   # DATE pattern
   if re.match(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', text):
       return 'DATE'

   # EMAIL
   if re.match(r'[^@]+@[^@]+\.[^@]+', text):
       return 'EMAIL'

   # REFERENCE (Fig. 3, Tab. 2, Eq. 1)
   if re.match(r'(Fig|Tab|Eq)\.\s*\d+', text, re.I):
       return 'REFERENCE'

   # STANDARD (ISO 9001, EN 14511)
   if re.match(r'(ISO|EN|DIN)\s*\d+', text):
       return 'STANDARD'
   ```

4. **extract_particles()** — passa font info
   ```python
   for word in words:
       ptype = typify_word(
           word['text'],
           word['size'],
           font=word.get('font', ''),
           is_bold=word.get('is_bold', False)
       )
       # ... crea particle con font/hierarchy
   ```

**Test:**
```python
# Test 1: Bold detection
assert typify_word('FXFA', 7.0, 'Bold', True) == 'MODEL'
assert typify_word('FXFA', 7.0, 'Regular', False) == 'TEXT'

# Test 2: Fuzzy matching
assert fuzzy_match_vocab('Potenza frigorifica',
                         ['Potenza frigorifera']) == 'Potenza frigorifera'

# Test 3: Patterns
assert typify_word('Fig. 3', 10, '') == 'REFERENCE'
assert typify_word('ISO 9001', 10, '') == 'STANDARD'
```

**Dipendenze:**
```bash
pip install rapidfuzz  # 200KB
```

**Deliverable:** Typify che usa font + fuzzy + pattern semantici

---

### **PHASE 3: FIELD++ Part 1 (Distanza multi-dimensionale)**

**Obiettivo:** Campo che vede font + hierarchy

**Files modificati:**
- `morph/core/field.py`

**Modifiche:**

1. **_phi()** — distanza multi-dimensionale
   ```python
   def _phi(
       p1: dict,
       p2: dict,
       axis: str,
       sigma_y: float,
       sigma_x: float,
       lambda_z: float = 0,
       # NUOVI parametri:
       sigma_font: float = 1.0,
       sigma_hierarchy: float = 0.5,
       sigma_color: float = 50.0,
   ) -> float:
       """Φ con distanza multi-dimensionale"""

       # Distanza geometrica (esistente)
       dx = abs(p1['x'] - p2['x']) / sigma_x
       dy = abs(p1['y'] - p2['y']) / sigma_y

       # NUOVO: Distanza font
       df = 0.0
       if p1.get('font') != p2.get('font'):
           df = 1.0
       elif p1.get('size', 0) != p2.get('size', 0):
           df = 0.5

       # NUOVO: Distanza hierarchy
       dh = 0.0
       if p1.get('span_id') == p2.get('span_id'):
           dh = 0.0  # stesso span → vicinissimi
       elif p1.get('line_id') == p2.get('line_id'):
           dh = 0.5  # stessa line → vicini
       else:
           dh = 1.0  # diversi

       # NUOVO: Distanza color
       dc = 0.0
       if p1.get('color') and p2.get('color'):
           c1 = p1['color']
           c2 = p2['color']
           # Euclidean in RGB
           r1, g1, b1 = (c1>>16)&0xFF, (c1>>8)&0xFF, c1&0xFF
           r2, g2, b2 = (c2>>16)&0xFF, (c2>>8)&0xFF, c2&0xFF
           dc = ((r1-r2)**2 + (g1-g2)**2 + (b1-b2)**2)**0.5 / sigma_color

       # Distanza TOTALE multi-dimensionale
       d_squared = dx**2 + dy**2 + (df/sigma_font)**2 + \
                   (dh/sigma_hierarchy)**2 + dc**2

       # Z-axis affinity (esistente)
       z_aff = 1.0
       if lambda_z > 0 and axis == 'row':
           # ... logica esistente z_norm
           pass

       # Φ = W · exp(-d²) · z_aff
       return W * math.exp(-d_squared) * z_aff
   ```

2. **calibrate_sigma()** — calibra anche σ_font, σ_hierarchy
   ```python
   def calibrate_sigma(particles: list[dict]) -> dict:
       """Calibra σ per tutte le dimensioni"""

       # Geometria (esistente)
       sigma_y, sigma_x = _calibrate_spatial(particles)

       # NUOVO: Font
       sigma_font = 1.0  # per ora fisso

       # NUOVO: Hierarchy
       sigma_hierarchy = 0.5  # per ora fisso

       # NUOVO: Color
       sigma_color = 50.0  # ~20% di 255

       return {
           'sigma_y': sigma_y,
           'sigma_x': sigma_x,
           'sigma_font': sigma_font,
           'sigma_hierarchy': sigma_hierarchy,
           'sigma_color': sigma_color,
       }
   ```

3. **extract_page()** — usa σ multi-dimensionale
   ```python
   def extract_page(particles: list[dict]) -> dict:
       # ...

       # Calibra TUTTE le dimensioni
       sigmas = calibrate_sigma(particles)

       # Calcola Φ con tutte le dimensioni
       for num in numerics:
           for spec in specs:
               phi = _phi(num, spec, 'row', **sigmas)
               # ...
   ```

**Test:**
```python
# Test 1: Font affinity
p1 = {'x': 100, 'y': 50, 'font': 'Arial-Bold', 'size': 12,
      'span_id': 's1', 'line_id': 'l1', 'color': 0}
p2_same = {'x': 200, 'y': 50, 'font': 'Arial-Bold', 'size': 12,
           'span_id': 's2', 'line_id': 'l1', 'color': 0}
p2_diff = {'x': 200, 'y': 50, 'font': 'Arial-Regular', 'size': 10,
           'span_id': 's2', 'line_id': 'l2', 'color': 0}

phi_same = _phi(p1, p2_same, 'row', 30, 30)
phi_diff = _phi(p1, p2_diff, 'row', 30, 30)

assert phi_same > phi_diff  # stesso font → phi più alto

# Test 2: Hierarchy affinity
p1 = {'x': 100, 'y': 50, 'span_id': 's1'}
p2_span = {'x': 200, 'y': 50, 'span_id': 's1'}  # stesso span
p2_line = {'x': 200, 'y': 50, 'span_id': 's2', 'line_id': 'l1'}
p2_block = {'x': 200, 'y': 50, 'span_id': 's3', 'line_id': 'l2'}

phi_span = _phi(p1, p2_span, 'row', 30, 30)
phi_line = _phi(p1, p2_line, 'row', 30, 30)
phi_block = _phi(p1, p2_block, 'row', 30, 30)

assert phi_span > phi_line > phi_block
```

**Metrica:**
- Test su pagina HVAC Daikin p.21
- Conta `unmapped` prima/dopo
- Target: -20% unmapped

**Deliverable:** Campo che vede font + hierarchy + color

---

### **PHASE 4: FIELD++ Part 2 (Dualità repulsiva)**

**Obiettivo:** Φ_repel per confini naturali

**Files modificati:**
- `morph/core/field.py`

**Modifiche:**

1. **Nuovo: _compute_whitespace()**
   ```python
   def _compute_whitespace(particles: list[dict],
                           page_width: float,
                           page_height: float) -> list[dict]:
       """Calcola rettangoli di spazio vuoto"""

       # Breuel 2002: whitespace rectangles
       # 1. Crea griglia binaria (occupato/vuoto)
       # 2. Trova rettangoli massimali vuoti
       # 3. Filtra piccoli (noise)

       rects = []  # [{x, y, width, height, area}, ...]

       # ... implementazione

       return rects
   ```

2. **Nuovo: _phi_repel()**
   ```python
   def _phi_repel(
       p1: dict,
       p2: dict,
       whitespace_rects: list[dict],
       R: float = 0.5,  # costante repulsiva
       alpha: float = ALPHA,
   ) -> float:
       """Φ repulsivo da spazio vuoto"""

       # Trova rettangoli vuoti TRA p1 e p2
       x_min = min(p1['x'], p2['x'])
       x_max = max(p1['x'], p2['x'])
       y_min = min(p1['y'], p2['y'])
       y_max = max(p1['y'], p2['y'])

       # Area vuota totale tra p1 e p2
       total_void = 0
       for rect in whitespace_rects:
           # Se rettangolo interseca regione p1-p2
           if (rect['x'] < x_max and rect['x']+rect['width'] > x_min and
               rect['y'] < y_max and rect['y']+rect['height'] > y_min):
               total_void += rect['area']

       if total_void == 0:
           return 0

       # Distanza tra p1 e p2
       d = ((p1['x']-p2['x'])**2 + (p1['y']-p2['y'])**2)**0.5

       # Φ_repel = -R · area / d^α
       return -R * total_void / (d ** alpha)
   ```

3. **extract_page()** — Φ_total = Φ_attract + Φ_repel
   ```python
   def extract_page(particles: list[dict],
                    page_width: float = 595,
                    page_height: float = 842) -> dict:
       # ...

       # NUOVO: Calcola whitespace
       whitespace = _compute_whitespace(particles, page_width, page_height)

       # Per ogni NUMERIC, calcola Φ_total
       for num in numerics:
           best_spec = None
           best_phi_total = -float('inf')

           for spec in specs:
               # Φ attract (esistente)
               phi_a = _phi(num, spec, 'row', **sigmas)

               # NUOVO: Φ repel
               phi_r = _phi_repel(num, spec, whitespace)

               # Φ total
               phi_total = phi_a + phi_r

               if phi_total > best_phi_total:
                   best_phi_total = phi_total
                   best_spec = spec

           # Se Φ_total < 0 → respinto, non assegnare
           if best_phi_total > 0 and best_spec:
               # ... assegna
               pass
   ```

**Test:**
```python
# Test: Due tabelle separate da grande spazio vuoto
particles_table1 = [...]  # y = 100-200
particles_table2 = [...]  # y = 400-500
# Spazio vuoto: y = 200-400 (area grande)

result = extract_page(particles_table1 + particles_table2)

# Particelle table1 NON devono legarsi con table2
# perché Φ_repel è forte
```

**Metrica:**
- Test su pagina con 2 tabelle separate
- Verifica che NON si mescolino
- Target: 0 cross-table bonds

**Deliverable:** Campo con dualità attrattivo-repulsivo

---

### **PHASE 5: FIELD++ Part 3 (Calibrazione contestuale)**

**Obiettivo:** σ adattivo per sezione (da TOC)

**Files modificati:**
- `morph/core/field.py`

**Modifiche:**

1. **calibrate_sigma()** — usa contesto
   ```python
   def calibrate_sigma(
       particles: list[dict],
       context: dict | None = None
   ) -> dict:
       """Calibra σ con contesto"""

       # Calibrazione geometrica base
       sigma_y_base, sigma_x_base = _calibrate_spatial(particles)

       # NUOVO: Adatta per sezione
       if context and 'section' in context:
           section = context['section'].lower()

           # Sezioni dense (specs, electrical)
           if 'specific' in section or 'electric' in section:
               sigma_y = sigma_y_base * 0.7
               sigma_x = sigma_x_base * 0.7

           # Sezioni rade (dimensions, installation)
           elif 'dimension' in section or 'install' in section:
               sigma_y = sigma_y_base * 1.3
               sigma_x = sigma_x_base * 1.3

           else:
               sigma_y = sigma_y_base
               sigma_x = sigma_x_base
       else:
           sigma_y = sigma_y_base
           sigma_x = sigma_x_base

       return {
           'sigma_y': sigma_y,
           'sigma_x': sigma_x,
           # ... altri σ
       }
   ```

2. **extract_page()** — accetta context
   ```python
   def extract_page(
       particles: list[dict],
       context: dict | None = None
   ) -> dict:
       """Extract con calibrazione contestuale"""

       # Calibra con contesto
       sigmas = calibrate_sigma(particles, context=context)

       # ... resto invariato
   ```

3. **Uso da reader:**
   ```python
   # In application code:
   doc = open_pdf('catalog.pdf')
   page = doc[10]

   context = doc.get_page_context(10)
   # → {'section': 'Specifiche tecniche', 'language': 'it'}

   particles = extract_particles(page)
   result = extract_page(particles, context=context)
   ```

**Test:**
```python
# Test: Stessa pagina con context diversi
particles = [...]  # mixed dense/sparse

result_dense = extract_page(particles, context={'section': 'Specifiche'})
result_sparse = extract_page(particles, context={'section': 'Dimensioni'})

# Dense context → più valori mapped (σ piccolo)
# Sparse context → meno valori mapped (σ grande, più selettivo)

assert result_dense['stats']['mapped'] > result_sparse['stats']['mapped']
```

**Deliverable:** Campo che si adatta al contesto del documento

---

### **PHASE 6: SENSE++ (Hybrid boundaries)**

**Obiettivo:** Usa drawings se presenti, altrimenti campo

**Files modificati:**
- `morph/core/sense.py`

**Modifiche:**

1. **Nuovo: detect_columns_from_drawings()**
   ```python
   def detect_columns_from_drawings(
       drawings: dict,
       particles: list[dict]
   ) -> list[float]:
       """Colonne da linee verticali"""

       v_lines = drawings['vertical']

       if not v_lines:
           return []

       # Filtra linee lunghe (>100px)
       long_lines = [x for x, y1, y2 in v_lines
                     if abs(y2 - y1) > 100]

       # Cluster per X (tolleranza 2px)
       col_splits = []
       for x in sorted(long_lines):
           if not col_splits or x - col_splits[-1] > 2:
               col_splits.append(x)

       return col_splits
   ```

2. **detect_columns()** — hybrid
   ```python
   def detect_columns(
       particles: list[dict],
       drawings: dict | None = None
   ) -> list[float]:
       """Hybrid column detection"""

       # PRIORITY 1: Drawings (se presenti)
       if drawings:
           col_splits = detect_columns_from_drawings(drawings, particles)
           if col_splits:
               return col_splits

       # FALLBACK: Campo (esistente)
       return _detect_columns_field(particles)
   ```

3. **Whitespace-based global boundaries**
   ```python
   def detect_table_boundaries(
       particles: list[dict],
       whitespace: list[dict]
   ) -> list[tuple]:
       """Trova confini TRA tabelle"""

       # Trova grandi rettangoli vuoti orizzontali
       h_separators = [
           rect for rect in whitespace
           if rect['width'] > 200 and rect['height'] > 50
       ]

       # Ogni separator definisce un confine
       boundaries = []
       for sep in sorted(h_separators, key=lambda r: r['y']):
           y_split = sep['y'] + sep['height'] / 2
           boundaries.append((0, y_split, 595, y_split))

       return boundaries
   ```

**Test:**
```python
# Test 1: PDF con bordi (scientific paper)
drawings = extract_drawings_from_pdf('paper.pdf', page=5)
col_splits = detect_columns(particles, drawings=drawings)
# Deve usare linee verticali

# Test 2: PDF senza bordi (HVAC)
col_splits = detect_columns(particles, drawings=None)
# Deve usare campo

# Test 3: Multi-table page
boundaries = detect_table_boundaries(particles, whitespace)
assert len(boundaries) >= 1  # almeno 1 confine trovato
```

**Deliverable:** Boundary detection che usa TUTTO (drawings + campo + whitespace)

---

## 📈 METRICHE DI SUCCESSO

### Per ogni phase:

| Phase | Metrica | Baseline | Target |
|-------|---------|----------|--------|
| 1 (Reader++) | Features estratte | 3 | 11+ |
| 2 (Typify++) | Classificazione accuracy | ? | +10% |
| 3 (Field++ Pt1) | Unmapped particles | baseline | -20% |
| 4 (Field++ Pt2) | Cross-table bonds | ? | 0 |
| 5 (Field++ Pt3) | Context adaptation | N/A | σ varies ±30% |
| 6 (Sense++) | Boundary accuracy | ? | +15% |

### Overall (v2.0):

- **Field mapping accuracy:** +20-30% (stima)
- **Boundary detection:** +15-25% (dipende da dataset)
- **Robustezza:** +15% su OCR/scan (con fuzzy)
- **Universalità:** Tabelle bordered + borderless

---

## 🧪 TEST SUITE

### Test files necessari:

1. **HVAC_borderless.pdf** — Daikin/Hitachi (dense, no borders)
2. **Scientific_paper.pdf** — PubTables (bordered, spanning)
3. **Scanned_catalog.pdf** — OCR errors, encoding issues
4. **Multi_table_page.pdf** — Pagina con 2+ tabelle separate
5. **Mixed_lang.pdf** — IT/EN mixed, RTL text

### Test per ogni phase:

```python
# test_reader.py
def test_font_extraction():
    ...

def test_metadata_extraction():
    ...

def test_drawings_extraction():
    ...

# test_typify.py
def test_font_based_classification():
    ...

def test_fuzzy_matching():
    ...

def test_semantic_patterns():
    ...

# test_field.py
def test_multidim_distance():
    ...

def test_font_affinity():
    ...

def test_hierarchy_affinity():
    ...

def test_repulsion():
    ...

def test_contextual_calibration():
    ...

# test_sense.py
def test_hybrid_columns():
    ...

def test_whitespace_boundaries():
    ...
```

---

## 🎯 PRIORITÀ & SEQUENZA

### **MUST HAVE (core v2.0):**
1. ✅ Phase 1: Reader++ (PyMuPDF full)
2. ✅ Phase 2: Typify++ (font + fuzzy)
3. ✅ Phase 3: Field++ Pt1 (distanza multi-dim)
4. ✅ Phase 4: Field++ Pt2 (dualità)

### **SHOULD HAVE (completezza):**
5. ⭐ Phase 5: Field++ Pt3 (calibrazione contestuale)
6. ⭐ Phase 6: Sense++ (hybrid boundaries)

### **NICE TO HAVE (robustezza extra):**
- Lingua detection (langdetect)
- Pattern semantici avanzati (DATE, EMAIL, etc.)
- Unicode classification
- Image OCR (futuro)

---

## 🚦 DECISION POINTS

### Dopo Phase 3:
**Question:** La distanza multi-dimensionale migliora abbastanza?
- **Se SÌ:** Procedi a Phase 4 (dualità)
- **Se NO:** Rivedi pesi σ_font, σ_hierarchy

### Dopo Phase 4:
**Question:** La dualità risolve cross-table bonds?
- **Se SÌ:** Procedi a Phase 5
- **Se NO:** Rivedi R (costante repulsiva)

### Dopo Phase 6:
**Question:** v2.0 è completo abbastanza?
- **Se SÌ:** Release, poi adatta a benchmark
- **Se NO:** Aggiungi nice-to-have

---

## 📦 DELIVERABLES

### v2.0 Release:

```
morph/
├── io/
│   └── reader.py          ← PyMuPDF full (11+ features)
├── core/
│   ├── typify.py          ← Font + fuzzy + patterns
│   ├── field.py           ← Multi-dim + dualità + context
│   └── sense.py           ← Hybrid boundaries
├── tests/
│   ├── test_reader.py
│   ├── test_typify.py
│   ├── test_field.py
│   └── test_sense.py
└── ROADMAP_v2.md          ← Questo file!
```

### Documentazione:

- **ARCHITECTURE.md** — Architettura completa v2.0
- **API.md** — API reference aggiornata
- **EXAMPLES.md** — Esempi d'uso

---

## 🎉 VISION FINALE

**Morph v2.0 = Campo morfogenetico COMPLETO**

Come un organismo biologico:
- **Multi-sensoriale** (geo + typo + struct + vettoriale)
- **Duale** (attrazione + repulsione)
- **Adattivo** (calibrazione contestuale)
- **Robusto** (fuzzy + encoding fix)

**L'equazione resta semplice:**
```
Φ = W · A / d^α
```

**Ma il mondo che vede è RICCO.**

---

**Pronto per partire? 🚀**
