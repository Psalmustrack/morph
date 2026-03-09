# HVAC Domain Extraction — Piano di lavoro

## Obiettivo

Arricchire morph con tipi HVAC-specifici per estrarre dati strutturati
dai cataloghi tecnici. Il core (typify + sense + field) resta universale.
Il dominio HVAC aggiunge solo regex → tipi → pesi W.

---

## Architettura

```
morph/core/typify.py    ← tipi generici (NUMERIC, TEXT, HEADER) — NON TOCCARE
morph/core/sense.py     ← confini naturali — NON TOCCARE
morph/core/field.py     ← equazione di campo — aggiungere tipi alla matrice W
morph/brands/*.py       ← regex per codici modello (gia' esistenti)
morph/hvac/             ← NUOVO: dominio HVAC
  types.py              ← regex → tipo per ogni particella
  weights.py            ← matrice W estesa (13 tipi)
  extract.py            ← API alto livello: PDF → tabelle strutturate
```

---

## I 13 tipi da estrarre

### Tier 1 — Priorita' massima (senza questi niente funziona)

#### 1. MODEL_CODE
Identifica il prodotto. Senza codice modello, i numeri non hanno padrone.

```python
patterns = {
    'hitachi':    r'R[A-Z]{2}-\d{1,2}[A-Z]{2,8}E?',
    'daikin':     r'[A-Z]{3,5}\d{2,3}[A-Z]{1,4}\d?',
    'toshiba':    r'[A-Z]{3}-\d{2,3}[A-Z\d-]{3,}',
    'mitsubishi': r'M[A-Z]{2}-\d{2,3}[A-Z\d-]+',
    'midea':      r'M[A-Z\d]+-\d{2,3}[A-Z\d/]+',
}
```

Esempi reali:
- `RAS-8FSXNME`, `RCI-6.0FSN4E` (Hitachi)
- `FTXM35R`, `RXM42R`, `FCAG71B` (Daikin)
- `RAV-GM1101ATP-E` (Toshiba)
- `MSZ-LN35VG`, `MXZ-4F80VF` (Mitsubishi)

Fonte: `knowledge/header_map.json` sezione `model_patterns` (256 pattern esistenti)

#### 2. UNIT_POWER
Dice che il numero accanto e' una potenza.

```python
r'kW|Watt?|BTU/?h|kcal/?h'
```

Esempi: `8.0 kW`, `27300 BTU/h`, `1250 W`

#### 3. UNIT_ELECTRICAL
Dice che il numero accanto e' un valore elettrico.

```python
r'[AV](?:\s|$)|Hz|kVA|kWh|V~'
```

Esempi: `230 V`, `11.3 A`, `50 Hz`, `220-240V~`

#### 4. UNIT_SOUND
Dice che il numero e' un livello sonoro.

```python
r'dB\(?A?\)?|dBA'
```

Esempi: `52 dB(A)`, `35 dBA`

#### 5. UNIT_TEMP
```python
r'[°º][CF]'
```

Esempi: `7°C`, `-15°C`, `35°C`

#### 6. UNIT_DIM
Dimensioni e peso.

```python
r'mm|cm|kg|g(?:\s|$)|m(?:\s|$)'
```

Esempi: `998 mm`, `72 kg`, `450 x 1050 x 330 mm`

#### 7. UNIT_FLOW
Portata aria/acqua e pressione.

```python
r'm[³3]/?h|l/[sm]|l/min|Pa|m³/min'
```

Esempi: `1020 m³/h`, `50 Pa`, `12.5 l/s`

#### 8. RANGE
Intervalli, coppie di valori, valori separati da delimitatore.
Nei cataloghi HVAC sono frequentissimi e NON vanno spezzati in due particelle NUMERIC.

```python
r'\d+[.,]?\d*\s*[~\-/÷]\s*\d+[.,]?\d*'   # intervalli: 5~50, 230-240, 3.5/4.2
r'\d+[.,]?\d*\s*[~\-/÷]\s*\d+[.,]?\d*\s*(?:kW|V|Hz|°C|dB|Pa|mm|kg)'  # con unita'
```

Esempi reali:
- `5~50 Pa` (range pressione statica)
- `230-240V` (range tensione alimentazione)
- `3.5/4.2 kW` (potenza raffreddamento/riscaldamento)
- `-15~48 °C` (range temperatura operativa)
- `38/42 dB(A)` (rumorosita' velocita' bassa/alta)

**Regola**: se il parser vede `3.5/4.2 kW`, crea UNA particella RANGE, non due NUMERIC.
Questo preserva il legame semantico (raffreddamento/riscaldamento, min/max, bassa/alta).

---

### Tier 2 — Priorita' alta (danno nome ai numeri)

#### 9. HEADER_COOLING
Etichette per potenza frigorifera.

```python
r'potenza\s*(in\s*)?(raffreddamento|frigorifera)'
r'capacit[aà]\s*(nominale\s*)?raffr'
r'cooling\s*capacity'
r'resa\s*frigorifera'
```

#### 10. HEADER_HEATING
Etichette per potenza termica.

```python
r'potenza\s*(in\s*)?(riscaldamento|termica)'
r'capacit[aà]\s*(nominale\s*)?risc'
r'heating\s*capacity'
r'resa\s*termica'
```

#### 11. HEADER_EFFICIENCY
Etichette per efficienza.

```python
r'\bCOP\b|\bEER\b|\bSEER\b|\bSCOP\b'
r'classe\s*energetica'
r'coefficiente.*prestazione'
r'energy\s*label|efficiency'
```

#### 12. HEADER_ELECTRICAL
Etichette per valori elettrici.

```python
r'alimentazione|tensione|corrente|fase'
r'frequenza|potenza\s*assorbita|assorbimento'
r'cos\s*[φϕf]|fattore.*potenza'
r'corrente.*spunto|fusibile'
```

#### 13. HEADER_SOUND
Etichette per valori acustici.

```python
r'livello\s*sonor[oa]|pressione\s*sonora|potenza\s*sonora'
r'rumorosit[aà]|sound\s*(pressure|power)\s*level'
r'noise\s*level'
```

---

### Tipi non nel W ma utili per post-processing

Questi non entrano nella matrice W ma servono per arricchire l'output:

- **REFRIGERANT**: `R-?\d{2,4}[A-Za-z]?` → R410A, R32, R134a
- **STANDARD**: `EN\s*\d{4,5}|ISO\s*\d{4,5}|ErP|Eurovent`
- **PRODUCT_TYPE**: `unit[aà]\s*(esterna|interna)|split|VRF|cassetta|canalizzat`
- **PIPING**: `attacchi|tubazioni|diametro\s*(liquido|gas)|dislivello`
- **DIMENSIONS_HEADER**: `dimensioni|peso\s*(netto|lordo)|L\s*[x×]\s*[AH]\s*[x×]\s*P`

---

## Matrice W (13 tipi base)

Pesi da 0.0 (nessuna affinita') a 1.0 (sempre insieme).

**Nota importante**: W(NUMERIC, UNIT_*) NON e' uniforme. Un numero vicino a "kW" ha significato
diverso da un numero vicino a "mm" o "dB(A)". I pesi riflettono la frequenza con cui
un numero generico appare vicino a ciascun tipo di unita' nei cataloghi HVAC:

- W(NUM, U_POW) = 0.95 — i numeri di potenza sono il dato piu' frequente
- W(NUM, U_ELE) = 0.9  — tensione/corrente frequentissimi
- W(NUM, U_TMP) = 0.85 — temperature operative comuni
- W(NUM, U_FLW) = 0.8  — portate presenti ma meno frequenti
- W(NUM, U_SND) = 0.7  — rumorosita' spesso in sezioni separate
- W(NUM, U_DIM) = 0.6  — dimensioni appaiono in zone dedicate, lontane dai dati prestazionali

```
              MODEL  NUM  RANGE U_POW  U_ELE  U_SND  U_TMP  U_DIM  U_FLW  H_COO  H_HEA  H_EFF  H_ELE  H_SND
MODEL_CODE     ---   0.8   0.3   0.2    0.2    0.1    0.1    0.1    0.1    0.3    0.3    0.3    0.3    0.2
NUMERIC        0.8   ---   0.3   0.95   0.9    0.7    0.85   0.6    0.8    0.7    0.7    0.7    0.7    0.5
RANGE          0.3   0.3   ---   0.7    0.7    0.5    0.8    0.3    0.5    0.5    0.5    0.4    0.5    0.3
UNIT_POWER     0.2   0.95  0.7   ---    0.1    0.0    0.1    0.0    0.0    0.8    0.8    0.5    0.3    0.0
UNIT_ELEC      0.2   0.9   0.7   0.1    ---    0.0    0.0    0.0    0.0    0.1    0.1    0.1    0.8    0.0
UNIT_SOUND     0.1   0.7   0.5   0.0    0.0    ---    0.0    0.0    0.0    0.0    0.0    0.0    0.0    0.8
UNIT_TEMP      0.1   0.85  0.8   0.1    0.0    0.0    ---    0.0    0.0    0.4    0.4    0.2    0.0    0.0
UNIT_DIM       0.1   0.6   0.3   0.0    0.0    0.0    0.0    ---    0.0    0.0    0.0    0.0    0.0    0.0
UNIT_FLOW      0.1   0.8   0.5   0.0    0.0    0.0    0.0    0.0    ---    0.2    0.2    0.0    0.0    0.0
HEADER_COOL    0.3   0.7   0.5   0.8    0.1    0.0    0.4    0.0    0.2    ---    0.3    0.5    0.1    0.0
HEADER_HEAT    0.3   0.7   0.5   0.8    0.1    0.0    0.4    0.0    0.2    0.3    ---    0.5    0.1    0.0
HEADER_EFF     0.3   0.7   0.4   0.5    0.1    0.0    0.2    0.0    0.0    0.5    0.5    ---    0.1    0.0
HEADER_ELEC    0.3   0.7   0.5   0.3    0.8    0.0    0.0    0.0    0.0    0.1    0.1    0.1    ---    0.0
HEADER_SND     0.2   0.5   0.3   0.0    0.0    0.8    0.0    0.0    0.0    0.0    0.0    0.0    0.0    ---
```

**Regola**: i pesi iniziali sono stime ragionate. Si calibrano guardando 10 pagine reali.
La struttura (13x13) non cambia, i numeri si aggiustano.

**Razionale pesi differenziati NUMERIC↔UNIT**:
- In una tabella di potenze, OGNI cella ha un numero vicino a "kW" → alta affinita' (0.95)
- In una tabella dimensioni, i "mm" appaiono in zone dedicate, isolate dai dati prestazionali → bassa affinita' (0.6)
- "dB(A)" appare spesso in sezioni separate dalla tabella principale → affinita' intermedia (0.7)

---

## Step di implementazione

### Fase 1: Regex e tipi (senza toccare il core)
- [ ] Creare `morph/hvac/types.py` con i 13 regex
- [ ] Funzione `classify_hvac(particle) -> str` che ritorna il tipo
- [ ] Testare su 5 pagine reali (1 per brand) — stampare le particelle tipizzate
- [ ] Verificare copertura: quante particelle passano da TEXT generico a tipo HVAC?

### Fase 2: Matrice W estesa
- [ ] Creare `morph/hvac/weights.py` con la matrice 13x13
- [ ] Integrare in field.py come override opzionale (il default resta il W generico)
- [ ] Testare su 5 pagine: il campo raggruppa meglio con W HVAC?
- [ ] Calibrare i pesi su 10 pagine difficili

### Fase 3: Estrattore tabelle
- [ ] Creare `morph/hvac/extract.py` con API ad alto livello
- [ ] `extract_tables(pdf_path, pages=None) -> list[Table]`
- [ ] Ogni Table ha: rows, columns, cells con testo + tipo + coordinate
- [ ] Collegare a table_store.py per output SQLite
- [ ] Testare su 5 cataloghi (1 per brand) — confrontare con pdfplumber

### Fase 4: Integrazione morph + pdfplumber

morph NON sostituisce pdfplumber. I due fanno cose diverse e complementari:

- **pdfplumber**: estrae TESTO + COORDINATE dal PDF (chars, words, bbox). E' un reader.
- **morph**: trova la STRUTTURA (confini tabella, righe, colonne). E' un analizzatore spaziale.

Oggi `table_extract.py` usa pdfplumber per ENTRAMBE le cose (1530 righe di workaround).
L'obiettivo e' separare i ruoli:

```
PRIMA:  PDF → pdfplumber (testo + struttura) → table_extract.py (1530 righe di patch)
DOPO:   PDF → PyMuPDF (testo + coordinate) → morph (struttura) → extract.py (pulito)
```

- [ ] Benchmark: morph HVAC vs logica strutturale di pdfplumber su 46 cataloghi
- [ ] Identificare i casi dove pdfplumber trova tabelle che morph non trova (e viceversa)
- [ ] Se morph >= pdfplumber sulla struttura: migrare a PyMuPDF + morph
- [ ] Se morph < pdfplumber su alcuni layout: capire quali e perche', aggiungere principi

---

## Fonti dati per i regex

Tutto quello che serve e' gia' nel progetto:

| Risorsa | Path | Cosa contiene |
|---------|------|---------------|
| Header mappati | `knowledge/header_map.json` | 1.176 mapping header → categoria |
| Header non mappati | `knowledge/unmapped_headers.json` | 6.078 header da classificare |
| Pattern modello | `header_map.json` → `model_patterns` | 256 regex codici modello |
| Cataloghi reali | `brands/*/output/*/auto/*_clean.md` | testo pulito da 46 cataloghi |
| Tabelle estratte | `brands/*/output/*/auto/*_tables.json` | struttura tabelle pdfplumber |
| Brand patterns | `morph/brands/*.py` | regex esistenti per 5 brand |

Non serve cercare fuori. Il materiale c'e' tutto.

---

## Nota: gerarchia tipi

Se in futuro servono piu' di 13 tipi, usare la gerarchia — NON espandere la matrice:

```
VALUE (W generico)
  ├── NUMERIC   (valore singolo)
  └── RANGE     (coppia/intervallo)

HEADER (W generico)
  ├── HEADER_COOLING  (W specifico, eredita da HEADER se non definito)
  ├── HEADER_HEATING
  ├── HEADER_EFFICIENCY
  ├── HEADER_SOUND
  └── HEADER_ELECTRICAL

UNIT (W generico)
  ├── UNIT_POWER
  ├── UNIT_ELECTRICAL
  ├── UNIT_SOUND
  ├── UNIT_TEMP
  ├── UNIT_DIM
  └── UNIT_FLOW
```

Un tipo non riconosciuto → fallback al padre → il campo funziona comunque.
50 sottotipi con 13 pesi base > 50 tipi con 2500 pesi incerti.
