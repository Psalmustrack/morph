# Morph — Spiegazione per un matematico

## Cos'e' Morph

Morph e' un sistema per estrarre struttura tabulare da documenti PDF
senza usare ML, training, annotazioni o GPU.

Input: lista di "particelle" (parole) con coordinate `(x0, y0, x1, y1)` e testo.
Output: tabella strutturata `{entita: {spec: valore}}`.

Il principio fondante: **la struttura non va iniettata, va fatta emergere**.

---

## Architettura a layer

```
Layer 1:  typify.py    — Gene expression
          Classificazione lessicale: TEXT → {NUMERIC, UNIT, SPEC_LABEL, MODEL, ...}
          Regole regex, nessuna geometria.

Layer 1b: sense.py     — Cellular differentiation
          Sensing spaziale: promuove particelle dal contesto geometrico.
          TEXT sopra colonna di numeri → MODEL, TEXT a sinistra di numeri → SPEC_LABEL.
          Usa _natural_threshold (vedi sotto) per calibrare tolleranze.

Layer 2:  field.py     — Tissue formation (campo morfogenetico)
          Equazione di campo: per ogni NUMERIC, trova il SPEC_LABEL (riga)
          e il MODEL (colonna) a cui appartiene via argmax(Phi).

Layer 3:  pipeline.py  — Output (SQL, Graph, RAG)
```

---

## Il principio percettivo: `_natural_threshold`

Questa e' la funzione centrale. Tutto il sistema poggia su questa.

### Definizione

Data una lista di gap positivi `G = [g_1, g_2, ..., g_n]` (distanze tra particelle consecutive):

1. Ordina: `g_(1) <= g_(2) <= ... <= g_(n)`
2. Calcola i rapporti consecutivi: `r_i = g_(i+1) / g_(i)`
3. Trova il massimo: `i* = argmax(r_i)`
4. Se `r_{i*} < 1.5`: nessun confine naturale (distribuzione unimodale)
5. Altrimenti: soglia = `(g_(i*) + g_(i*+1)) / 2`

### Intuizione

I gap in una tabella hanno distribuzione bimodale:
- **Gap intra-cella**: piccoli (spazi tra parole nella stessa cella)
- **Gap inter-cella**: grandi (spazi tra colonne diverse)

Il punto di massima discontinuita' nel rapporto tra gap consecutivi ordinati
e' il confine naturale tra le due modalita'. Non serve sapere NULLA sul dominio.

### Codice (`morph/core/sense.py`, righe 96-128)

```python
def _natural_threshold(gaps: list[float]) -> float:
    if len(gaps) < 3:
        return statistics.median(gaps) if gaps else 10
    sorted_gaps = sorted(gaps)

    best_ratio = 1.0
    best_idx = 0
    for i in range(len(sorted_gaps) - 1):
        if sorted_gaps[i] > 0:
            ratio = sorted_gaps[i + 1] / sorted_gaps[i]
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i

    if best_ratio < 1.5:
        return sorted_gaps[-1] + 1  # above all = no boundary

    return (sorted_gaps[best_idx] + sorted_gaps[best_idx + 1]) / 2
```

### Risultati benchmark (su TUTTI i dataset disponibili, asse X — colonne)

Per ogni gap tra particelle consecutive in una riga, il principio classifica:
"questo gap e' un confine colonna (SI/NO)?". Confronto con ground truth.

| Dataset       | Tabelle  | Gap classificati | Precision | Recall | F1     |
|---------------|----------|------------------|-----------|--------|--------|
| PubTables-1M  | 93,142   | 12,752,714       | 93.3%     | 63.4%  | 75.5%  |
| FinTabNet     | 9,195    | 1,017,468        | 73.7%     | 64.9%  | 69.0%  |
| HVAC (nostro) | 2        | 244              | 81.7%     | 84.6%  | 83.1%  |

102K tabelle, 13.8M gap, 94 secondi su 4 core CPU. Zero parametri dominio-specifici.

**Profilo errori**: 89% degli errori sono FN (confini non trovati), 11% FP (falsi confini).
Il principio e' conservativo: se non vede bimodalita', si astiene.

---

## L'equazione di campo: `Phi`

Ogni NUMERIC (valore numerico) genera un "campo" nello spazio del documento.
Il campo attrae le particelle con cui il NUMERIC ha affinita' strutturale.

### Definizione

```
Phi(i -> j) = W(type_i, type_j) * A(i, j, axis) / d(i, j)^alpha
```

Dove:
- `W(type_i, type_j)` = peso di interazione (matrice 8x8 di affinita' tra tipi)
- `A(i, j, axis)` = allineamento direzionale (gaussiana anisotropa)
- `d(i, j)` = distanza euclidea (2D o 3D)
- `alpha = 0.5` = esponente di decadimento (sub-lineare, piu' lento di Coulomb)

### Matrice di interazione W

```python
W = {
    ('NUMERIC', 'SPEC_LABEL'):  1.0,   # attrazione riga (spec a sinistra del valore)
    ('NUMERIC', 'SIZE_HEADER'): 0.8,   # attrazione colonna (header sopra il valore)
    ('NUMERIC', 'MODEL'):       0.6,   # attrazione colonna
    ('NUMERIC', 'KW_HEADER'):   0.8,   # attrazione colonna
    ('NUMERIC', 'UNIT'):        0.7,   # attrazione riga (unita' vicino al valore)
    ('NUMERIC', 'NUMERIC'):     0.3,   # clustering debole
    ('NUMERIC', 'TEXT'):       -0.1,   # repulsione (testo narrativo)
    ('NUMERIC', 'SECTION'):     0.0,   # neutrale
}
```

### Allineamento direzionale A (`morph/core/field.py`, righe 203-233)

L'allineamento e' una gaussiana anisotropa con bias direzionale:

**Asse riga** (NUMERIC cerca SPEC_LABEL sulla stessa riga):
```
A_row(i, j) = exp(-dy^2 / sigma_y^2) * (1.2 se j e' a sinistra, 0.8 altrimenti)
```

**Asse colonna** (NUMERIC cerca MODEL nella stessa colonna):
```
A_col(i, j) = exp(-dx^2 / sigma_x^2) * (1.2 se j e' sopra, 0.8 altrimenti)
```

- `sigma_y` ~ 6px (auto-calibrato dalla geometria della pagina)
- `sigma_x` ~ 30px (auto-calibrato)
- Il bias 1.2/0.8 codifica l'invariante dei layout umani: le etichette sono a sinistra o sopra, mai a destra o sotto.

### Terza dimensione: z (gradiente di concentrazione)

```
z_norm = log10(|valore| + 1)
d_3D = sqrt(dx^2 + dy^2 + (lambda_z * dz_norm)^2)
```

Intuizione: valori con ordini di grandezza diversi vivono in "piani" diversi.
- COP (coefficiente di prestazione): z ~ 0.7
- Peso (kg): z ~ 1.4
- Rumore (dB): z ~ 1.7
- Prezzo: z ~ 3.7

`lambda_z` si auto-calibra dalla geometria dei valori nella pagina.
z opera solo sull'asse riga (non ha senso per le colonne: una colonna contiene spec diverse).

### Estrazione (`extract_page()`)

Per ogni NUMERIC sulla pagina:
1. `best_spec = argmax_s Phi(num, s, axis='row')` — trova la specifica (riga)
2. `best_col = argmax_c Phi(num, c, axis='col')` — trova l'entita' (colonna)
3. `best_unit = argmax_u Phi(num, u, axis='row')` — trova l'unita' di misura
4. Assembla: `data[best_col][best_spec] = {valore, unita'}`

---

## Sensing spaziale (`sense_page`)

Il sensing e' il pre-processore che tipizza le particelle dal contesto.
Senza sensing, il campo ha troppo poco materiale (solo regex-NUMERIC e regex-UNIT).
Con sensing: 95.2% di valori mappati. Senza: 36.5%.

### Pipeline sensing (righe 546-605 di `sense.py`)

```
1. detect_columns()          → trova scheletro colonne (cluster X di NUMERIC)
2. promote_column_headers()  → TEXT sopra una colonna → MODEL
3. detect_row_label_column() → colonna di TEXT a sinistra → SPEC_LABEL
4. promote_spec_labels()     → TEXT a sinistra di NUMERIC sulla stessa riga → SPEC_LABEL
5. promote_sections()        → TEXT con font grande → SECTION
6. proofread()               → NUMERIC isolati (senza vicini) → TEXT (DNA proofreading)
```

Il sensing usa `_natural_threshold` internamente per:
- Decidere la tolleranza riga (adaptive da row spacing)
- Raggruppare particelle in righe (`_group_into_rows`)
- Rilevare colonne strutturali

---

## Il benchmark grid (traduttore)

Per confrontare con dataset accademici (PubTables-1M, FinTabNet) che ragionano
in griglia (righe x colonne), serve un traduttore. Questo vive in `bench/grid.py`.

### Principio unificato per boundary detection

Due regimi dello stesso fenomeno:
1. **Bimodale** → `_natural_threshold` decide (il salto massimo e' il confine)
2. **Unimodale** → `gap/dimensione_particella` decide (la particella e' la scala)

### Risultati GriTS (metrica accademica) con max-jump

| Dataset      | Col exact | Row exact | GriTS_Top |
|--------------|-----------|-----------|-----------|
| PubTables-1M | 79.8%     | 80.2%     | 79.9%     |
| FinTabNet    | 77.4%     | 77.9%     | 77.6%     |

Gap cross-domain: 2.3pp (PubTables 79.9% vs FinTabNet 77.6%).
Prima del max-jump: 12.4pp. Riduzione: 81%.

**Nota critica**: GriTS 79.8% vs Boundary Precision 93.3%.
La differenza (13.5pp) e' il costo della traduzione particelle→griglia.
Il principio e' piu' preciso del traduttore.

---

## Il problema aperto: Level 1 (ricorsione)

### L'idea

Se il principio funziona per trovare confini tra particelle (Level 0),
dovrebbe funzionare anche per trovare confini tra **bond** (Level 1).

```
Level 0: particelle → _natural_threshold → bond (legami tra particelle vicine)
Level 1: bond → _natural_threshold → celle (legami tra bond vicini)
Level 2: celle → _natural_threshold → sezioni
```

Se funziona, il traduttore grid.py (355 righe) diventa 15 righe di principio
applicato a se stesso. La struttura a ogni livello emergerebbe dallo stesso
meccanismo, come un frattale.

### Il test che abbiamo fatto

Tabella di test: Toshiba MiNi-SMMS p.27 (4 colonne, 27 righe GT).

**Level 0**: 520 particelle → tipizzazione → 124 NUMERIC, 321 TEXT, 32 UNIT, 43 SEPARATOR

**Costruzione bond**: per ogni riga di particelle, bond tra particelle adiacenti.
Un bond ha: centroide `(x, y)` = media dei centroidi delle due particelle collegate.

**Level 1**: applica `_group_into_rows()` e `_natural_threshold()` ai bond.

### Risultati

```
Bond phi (campo):    78  (costruiti da _phi, NUMERIC↔UNIT)
Bond geo (prossimita): 341  (costruiti da prossimita' geometrica)

=== Solo bond phi ===
Righe emergenti: 28 (GT: 27)     ← QUASI PERFETTO!
Colonne per riga: moda=1 (GT: 4) ← FALLIMENTO

=== Phi + geo ===
Righe emergenti: 45 (GT: 27)     ← Over-segmented
Colonne per riga: moda varia      ← Rumoroso
```

### Diagnosi

**Righe (28 vs 27)**: con i soli bond phi, il Level 1 trova quasi esattamente
il numero giusto di righe. Questo conferma che il principio FUNZIONA ricorsivamente.

**Colonne (1 vs 4)**: fallimento. I bond phi nella stessa riga hanno gap X
molto uniformi — non c'e' bimodalita'. Esempio dalla riga piu' grande:

```
4 bond phi nella riga, X = [138.7, 230.3, 325.9, 439.3]
Gap: [91.6, 95.6, 113.4]
Soglia: 114.4 → 1 colonna (nessun gap la supera)
```

I gap sono 91.6, 95.6, 113.4 — il rapporto max e' 113.4/95.6 = 1.19 < 1.5.
**Non c'e' bimodalita' perche' le colonne sono equispaziate.**

Questo e' un limite fondamentale di `_natural_threshold`: funziona su
distribuzioni bimodali, ma colonne equispaziate producono gap unimodali.

### Domande aperte

1. **La rappresentazione del bond e' giusta?** Usare il centroide perde informazione.
   Un bond tra particelle a X=100 e X=200 ha centroide X=150. Ma il CONFINE
   e' tra X=200 e il prossimo bond — questa informazione si perde nel centroide.

2. **Serve un secondo principio per le colonne?** _natural_threshold vede le
   discontinuita'. Ma colonne equispaziate non hanno discontinuita'. Forse
   serve un principio basato sulla RIPETIZIONE (periodicita') invece che
   sulla DISCONTINUITA'.

3. **Il rapporto tra gap e dimensione del bond potrebbe funzionare?** Nel regime
   unimodale, bench/grid.py usa `gap / dimensione_particella`. Se
   `gap >> dimensione_bond`, c'e' un confine. Questo potrebbe funzionare
   anche a Level 1 perche' non richiede bimodalita'.

4. **La tipologia del bond conta?** Abbiamo bond "row" (stessa riga) e "col"
   (stessa colonna). A Level 1, forse solo i bond "row" dovrebbero
   partecipare alla ricerca di confini colonna, e viceversa. Questo e'
   analogo alla separazione `axis='row'`/`axis='col'` nel campo.

---

## File da allegare

Per vedere il codice completo, allega questi file:

| File | Righe | Contenuto |
|------|-------|-----------|
| `morph/core/sense.py` | ~605 | `_natural_threshold`, `_group_into_rows`, `sense_page`, sensing spaziale |
| `morph/core/field.py` | ~571 | `_phi`, `calibrate_sigma`, `extract_page`, equazione di campo |
| `morph/bench/boundaries.py` | ~438 | Test diretto del principio (classificazione binaria gap) |
| `morph/bench/grid.py` | ~355 | Traduttore particelle → griglia (max-jump + ratio) |
| `tests/test_principle.py` | ~119 | Test su tutti i dataset |

### Come lanciare i test

```bash
# Test del principio (classificazione binaria gap) — tutti i dataset
python tests/test_principle.py --axis x --cores 4

# Benchmark GriTS (traduzione in griglia) — 1000 tabelle
python -m morph.bench.adaptive_k --n 1000 --cores 4

# Test regressione (65 test unitari)
pytest tests/ -v
```

---

## Costanti del sistema

Tutte auto-calibrate o invarianti cross-domain:

| Costante | Valore | Dove | Significato |
|----------|--------|------|-------------|
| `alpha` | 0.5 | field.py | Decadimento campo (sub-lineare) |
| `sigma_y` | ~6px | field.py | Tolleranza riga (auto-calibrata) |
| `sigma_x` | ~30px | field.py | Tolleranza colonna (auto-calibrata) |
| `lambda_z` | ~50 | field.py | Peso asse z (auto-calibrato) |
| `W` | 8x8 | field.py | Matrice interazione tipi |
| `1.5` | soglia ratio | sense.py | Minimo salto per bimodalita' |
| `1.2 / 0.8` | bias direzionale | field.py | Spec a sinistra, header sopra |

---

## La tesi

> Per ogni problema dove la struttura e' implicita nei dati, esiste un principio
> auto-organizzativo che la fa emergere, ed e' piu' efficiente di qualsiasi
> approccio che tenta di iniettarla dall'esterno.

Il sistema usa 0 training, 0 GPU, 0 dati annotati.
Funziona su 3 domini diversi (paper accademici, documenti finanziari, cataloghi HVAC)
con gli stessi parametri.

Il problema Level 1 (ricorsione) e' il test finale: se lo STESSO principio
applicato al proprio output produce il livello successivo di struttura,
il sistema e' veramente auto-similare. I risultati parziali (28 righe vs 27 GT)
suggeriscono che e' possibile, ma serve un secondo principio o una
rappresentazione migliore del bond per gestire colonne equispaziate.
