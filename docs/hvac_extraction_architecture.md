# HVAC Extraction Architecture — 3-Storage System

**Date:** 2026-03-10
**Status:** Design Phase
**Purpose:** Architettura completa per estrazione dati HVAC da cataloghi PDF con storage multi-modale

---

## 🎯 Vision

Estrarre da cataloghi HVAC PDF **tre tipi di informazione**:

1. **SQL**: Dati tabellari strutturati (numeri, specs tecniche)
2. **RAG**: Chunks descrittivi testuali (paragrafi, features narrative)
3. **Graph**: Relazioni semantiche cross-page (compatibilità, accessori, serie)

## 🏗️ I 3 Storage con Ruoli Distinti

### **1. SQL: Dati Tabellari (PostgreSQL)**

**Contenuto:**
- Valori numerici strutturati da tabelle
- Specifiche tecniche quantitative
- Misure, performance, dimensioni

**Esempio:**
```sql
model_name  | spec_name                 | value | unit
------------|---------------------------|-------|-----
FXFA-20A    | Capacità raffrescamento   | 2.2   | kW
FXFA-20A    | COP                       | 4.05  | -
FXFA-20A    | Peso                      | 12    | kg
FXFA-20A    | Dimensioni (LxPxH)        | 800   | mm
```

**Use Cases:**
- Query analitiche: "Tutti i modelli con COP > 4"
- Comparazioni numeriche
- BI dashboards
- Export per Excel/reporting

---

### **2. RAG: Chunks Descrittivi (Pinecone/Weaviate)**

**Contenuto:**
- Paragrafi descrittivi
- Features narrative
- Note tecniche
- Vantaggi/benefici
- Istruzioni d'uso

**Esempio:**
```
Chunk 1 (page 5):
"La serie FXFA utilizza tecnologia inverter DC che garantisce
un controllo preciso della temperatura con consumi ridotti.
Ideale per applicazioni residenziali e light commercial."
[embeddings: vector[1536]]
{metadata: {series: "FXFA", topic: "technology", page: 5}}

Chunk 2 (page 8):
"Dotato di filtro autopulente che riduce la manutenzione.
Funzione sleep per comfort notturno ottimale."
[embeddings: vector[1536]]
{metadata: {model: "FXFA-20A", topic: "features", page: 8}}
```

**Use Cases:**
- Ricerca semantica: "Unità con bassa manutenzione"
- Context per LLM queries
- Chatbot/assistenti
- Similarity search

---

### **3. Graph: Relazioni Cross-Page (Neo4j)**

**Contenuto:**
- Collegamenti tra entità sparse nel catalogo
- Compatibilità modello-accessorio
- Appartenenza a serie/gamma
- Brand relationships

**Esempio:**
```cypher
// Nodi
(m:Model {name: "FXFA-20A"})
(s:Series {name: "FXFA"})
(b:Brand {name: "Daikin"})
(c:Controller {name: "BRC1E"})
(a:Accessory {name: "Kit KRP2A"})

// Relazioni
(m)-[:PART_OF_SERIES]->(s)
(s)-[:BRAND]->(b)
(m)-[:COMPATIBLE_WITH {page: 30}]->(c)
(s)-[:REQUIRES_ACCESSORY {page: 35}]->(a)
```

**Use Cases:**
- Navigazione relazioni: "Accessori compatibili con FXFA-20A"
- Pattern discovery: "Serie simili per compatibilità"
- Recommender systems
- Cross-referencing automatico

---

## 📐 Pipeline di Estrazione

### **Overview:**

```
PDF Catalog
    ↓
┌───┴────────────────────────────────────────┐
│  LAYER 1: Morph Reader (PyMuPDF)           │
│  - Estrae TUTTO il contenuto               │
│  - Particles (text + bbox + features)      │
│  - Drawings (borders)                      │
│  - Metadata (TOC, structure)               │
└───┬────────────────────────────────────────┘
    ↓
┌───┴────────────────────────────────────────┐
│  LAYER 2: Content Classification           │
│  - Tabelle → extract_tables()              │
│  - Paragrafi → extract_descriptions()      │
│  - Menzioni → extract_relations()          │
└───┬────────────────────────────────────────┘
    ↓
    ├─→ [SQL] Dati tabellari
    ├─→ [RAG] Chunks descrittivi + embeddings
    └─→ [Graph] Relazioni estratte + cross-refs
```

### **Ingestion Flow:**

```
┌──────────────────────────────────────────────┐
│  extract_catalog_full(pdf_path, brand)       │
│  ↓                                            │
│  Per ogni pagina:                             │
│    1. extract_tables(page)        → SQL      │
│    2. extract_descriptions(page)  → RAG      │
│    3. extract_relations(page)     → Graph    │
└──────────────────────────────────────────────┘
         ↓              ↓              ↓
    PostgreSQL    Pinecone/Weaviate   Neo4j
```

---

## 🛠️ Implementazione: locus/scripts/extract.py

### **1. extract_tables(page, brand=None) → SQL**

```python
def extract_tables(page, brand=None) -> dict:
    """Estrae dati tabellari strutturati.

    Pipeline:
    1. extract_particles(page, full_features=True)  # Morph v2.0
    2. extract_page(particles, sigma_*, R=0)        # Field mapping
    3. Arricchimento HVAC (classify_header, classify_unit)
    4. Ricostruzione nomi modello completi

    Returns:
        {
            'type': 'tabular',
            'entities': ["FXFA-20A", "FXFA-25A", ...],
            'specs': {
                "Capacità raffrescamento | kW": {
                    'unit': 'kW',
                    'hvac_type': 'HEADER_COOLING',
                    'values': {"FXFA-20A": 2.2, "FXFA-25A": 2.8}
                }
            },
            'stats': {'mapped': 27, 'unmapped': 0, 'entities': 3}
        }
    """
    # Step 1-2: Morph v2.0 pipeline
    particles = extract_particles(page, full_features=True)
    result = extract_page(
        particles,
        sigma_font=50,
        sigma_hierarchy=30,
        sigma_color=100,
        R=0,
    )

    # Step 3: Arricchimento HVAC
    enriched_specs = {}
    for spec_name, spec_data in result['data'].items():
        spec_type = classify_header_raw(spec_name)
        unit_type = classify_unit(spec_data.get('unit', ''))

        enriched_specs[spec_name] = {
            **spec_data,
            'hvac_type': spec_type,
            'unit_type': unit_type,
        }

    # Step 4: Ricostruzione nomi modello
    entities = reconstruct_model_names(result['data'].keys(), particles, brand)

    return {
        'type': 'tabular',
        'entities': entities,
        'specs': enriched_specs,
        'stats': result['stats']
    }
```

**Output SQL Schema:**

```sql
CREATE TABLE hvac_data (
    id SERIAL PRIMARY KEY,

    -- Source metadata
    brand VARCHAR(50),
    catalog VARCHAR(200),
    page INTEGER,

    -- Entity (modello)
    model_name VARCHAR(100),
    series VARCHAR(50),

    -- Spec
    spec_name VARCHAR(200),
    spec_category VARCHAR(50),  -- da hvac_type

    -- Value
    value FLOAT,
    unit VARCHAR(20),

    -- Confidence (da Morph)
    phi_spec FLOAT,
    phi_col FLOAT,

    -- Audit
    extracted_at TIMESTAMP DEFAULT NOW()
);

-- Indici
CREATE INDEX idx_model ON hvac_data(model_name);
CREATE INDEX idx_spec_cat ON hvac_data(spec_category);
CREATE INDEX idx_brand ON hvac_data(brand);
```

---

### **2. extract_descriptions(page) → RAG**

```python
def extract_descriptions(page) -> dict:
    """Estrae chunks di testo descrittivo.

    Pipeline:
    1. extract_particles(page, full_features=True)
    2. Filtra solo particles DESCRIPTION, FEATURE, NOTE
    3. Raggruppa in paragrafi coerenti (stesso topic/sezione)
    4. Genera embeddings (opzionale, può essere fatto dopo)

    Returns:
        {
            'type': 'descriptive',
            'chunks': [
                {
                    'text': "La serie FXFA utilizza tecnologia inverter...",
                    'bbox': {'x': 50, 'y': 100, 'width': 400, 'height': 60},
                    'page': 5,
                    'metadata': {
                        'section': 'Overview',
                        'series': 'FXFA',
                        'topic': 'technology'
                    }
                }
            ]
        }
    """
    particles = extract_particles(page, full_features=True)

    # Filtra solo testo descrittivo
    desc_particles = [p for p in particles
                      if p['type'] in ['DESCRIPTION', 'FEATURE', 'NOTE', 'SECTION']]

    # Raggruppa in paragrafi coerenti
    chunks = group_into_paragraphs(desc_particles)

    # Estrai metadata dal contesto
    for chunk in chunks:
        chunk['metadata'] = extract_chunk_metadata(chunk, particles)

    return {
        'type': 'descriptive',
        'chunks': chunks
    }
```

**Helper Functions:**

```python
def group_into_paragraphs(particles, y_tolerance=15):
    """Raggruppa particles vicine in paragrafi.

    Logica:
    - Stesso blocco/linea → stesso paragrafo
    - Y distance < y_tolerance → continua paragrafo
    - Nuovo blocco → nuovo paragrafo
    """
    paragraphs = []
    current = []

    for p in sorted(particles, key=lambda x: (x['y'], x['x'])):
        if not current:
            current.append(p)
        elif abs(p['y'] - current[-1]['y']) < y_tolerance:
            current.append(p)
        else:
            # Nuovo paragrafo
            text = ' '.join(x['text'] for x in current)
            if len(text) > 20:  # Skippa frammenti troppo corti
                paragraphs.append({
                    'text': text,
                    'bbox': compute_bbox(current),
                    'particles': current
                })
            current = [p]

    # Ultimo paragrafo
    if current:
        text = ' '.join(x['text'] for x in current)
        if len(text) > 20:
            paragraphs.append({
                'text': text,
                'bbox': compute_bbox(current),
                'particles': current
            })

    return paragraphs


def extract_chunk_metadata(chunk, all_particles):
    """Estrae metadata dal contesto circostante.

    - Cerca SECTION/TITLE nelle vicinanze (sopra il chunk)
    - Cerca MODEL mentions nel chunk
    - Identifica topic keywords (cooling, heating, efficiency, etc.)
    """
    metadata = {}

    # Cerca section header sopra il chunk
    chunk_y = chunk['bbox']['y']
    headers = [p for p in all_particles
               if p['type'] in ['SECTION', 'TITLE']
               and p['y'] < chunk_y
               and abs(p['y'] - chunk_y) < 100]

    if headers:
        metadata['section'] = headers[-1]['text']  # Più vicino

    # Cerca mentions di modelli/serie
    text = chunk['text'].lower()
    if 'serie' in text or 'series' in text:
        # Extract series name
        if m := re.search(r'serie (\w+)', text, re.I):
            metadata['series'] = m.group(1).upper()

    # Topic classification
    topics = []
    if any(kw in text for kw in ['raffrescamento', 'cooling', 'freddo']):
        topics.append('cooling')
    if any(kw in text for kw in ['riscaldamento', 'heating', 'caldo']):
        topics.append('heating')
    if any(kw in text for kw in ['efficien', 'cop', 'eer', 'risparmio']):
        topics.append('efficiency')
    if any(kw in text for kw in ['manutenzione', 'filtro', 'pulizia']):
        topics.append('maintenance')

    if topics:
        metadata['topics'] = topics

    return metadata
```

**RAG Ingestion:**

```python
# Dopo estrazione chunks
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')

for chunk in rag_chunks:
    # Generate embedding
    embedding = model.encode(chunk['text'])

    # Insert to vector store
    pinecone.upsert(
        id=f"{catalog}_{page}_{chunk_id}",
        values=embedding.tolist(),
        metadata={
            'text': chunk['text'],
            'page': chunk['page'],
            'catalog': catalog,
            **chunk['metadata']
        }
    )
```

---

### **3. extract_relations(page, catalog_context=None) → Graph**

```python
def extract_relations(page, page_num, catalog_context=None) -> dict:
    """Estrae menzioni di relazioni per knowledge graph.

    Pipeline:
    1. extract_particles(page, full_features=True)
    2. Pattern matching per relazioni comuni
    3. NER per entity recognition (opzionale, con spaCy/LLM)

    Returns:
        {
            'type': 'relational',
            'relations': [
                {
                    'from': 'FXFA-20A',
                    'type': 'COMPATIBLE_WITH',
                    'to': 'Controller BRC1E',
                    'page': 30,
                    'confidence': 0.9
                }
            ]
        }
    """
    particles = extract_particles(page, full_features=True)
    text = ' '.join(p['text'] for p in particles)

    relations = []

    # Pattern 1: "compatibile con X"
    for m in re.finditer(r'compatibile con ([A-Z0-9\-]+)', text, re.I):
        relations.append({
            'from': None,  # Will be inferred from context
            'type': 'COMPATIBLE_WITH',
            'to': m.group(1),
            'page': page_num,
            'confidence': 0.8
        })

    # Pattern 2: "serie X include/comprende modelli Y, Z"
    if m := re.search(r'serie (\w+).{0,50}(include|comprende|composta da)(.+)', text, re.I):
        series = m.group(1)
        models_text = m.group(3)
        # Extract model names
        models = re.findall(r'([A-Z]{3,5}-?\d+[A-Z]*)', models_text)
        for model in models:
            relations.append({
                'from': model,
                'type': 'PART_OF_SERIES',
                'to': series,
                'page': page_num,
                'confidence': 0.9
            })

    # Pattern 3: "richiede accessorio X"
    for m in re.finditer(r'richiede (kit|accessorio) ([A-Z0-9\-]+)', text, re.I):
        relations.append({
            'from': None,  # Context-dependent
            'type': 'REQUIRES_ACCESSORY',
            'to': m.group(2),
            'page': page_num,
            'confidence': 0.7
        })

    # Pattern 4: Brand mentions
    brands = ['Daikin', 'Hitachi', 'Mitsubishi', 'Toshiba', 'Midea']
    for brand in brands:
        if brand.lower() in text.lower():
            relations.append({
                'from': None,  # Context-dependent
                'type': 'BRAND',
                'to': brand,
                'page': page_num,
                'confidence': 0.9
            })

    return {
        'type': 'relational',
        'relations': relations
    }
```

**Graph Ingestion:**

```cypher
// Create nodes
MERGE (m:Model {name: $model_name})
MERGE (s:Series {name: $series_name})
MERGE (b:Brand {name: $brand_name})
MERGE (c:Controller {name: $controller_name})

// Create relationships
MATCH (m:Model {name: $model_name})
MATCH (c:Controller {name: $controller_name})
MERGE (m)-[r:COMPATIBLE_WITH {
    page: $page,
    confidence: $confidence,
    catalog: $catalog
}]->(c)
```

---

## 🔄 Funzione Unificata: extract_catalog_full()

```python
def extract_catalog_full(pdf_path, brand=None, pages=None):
    """Estrazione completa per tutti e 3 gli storage.

    Args:
        pdf_path: Path al PDF
        brand: Brand per pattern matching (opzionale)
        pages: Lista pagine o range (opzionale, default: tutte)

    Returns:
        {
            'catalog_info': {...},
            'sql': [...],      # Dati tabellari → PostgreSQL
            'rag': [...],      # Chunks → Pinecone/Weaviate
            'graph': [...],    # Relazioni → Neo4j
        }
    """
    pdf = open_pdf(pdf_path)
    catalog_name = Path(pdf_path).name

    sql_data = []
    rag_chunks = []
    graph_edges = []

    page_range = parse_page_range(pages, len(pdf))

    for page_num in page_range:
        page = pdf[page_num]

        # Estrazione parallela dei 3 tipi di contenuto
        tables = extract_tables(page, brand)
        descriptions = extract_descriptions(page)
        relations = extract_relations(page, page_num)

        # Accumula risultati
        if tables and tables['stats']['mapped'] >= 3:
            sql_data.append({
                'page': page_num,
                'catalog': catalog_name,
                'brand': brand,
                **tables
            })

        if descriptions['chunks']:
            for chunk in descriptions['chunks']:
                chunk['page'] = page_num
                chunk['catalog'] = catalog_name
            rag_chunks.extend(descriptions['chunks'])

        if relations['relations']:
            for rel in relations['relations']:
                rel['catalog'] = catalog_name
            graph_edges.extend(relations['relations'])

    pdf.close()

    return {
        'catalog_info': {
            'file': catalog_name,
            'brand': brand,
            'pages_processed': len(page_range),
            'extracted_at': datetime.now().isoformat()
        },
        'sql': sql_data,
        'rag': rag_chunks,
        'graph': graph_edges,
    }
```

---

## 📊 Output Example

```json
{
  "catalog_info": {
    "file": "20220412 VRV 5 HR.pdf",
    "brand": "daikin",
    "pages_processed": 45,
    "extracted_at": "2026-03-10T15:30:00"
  },

  "sql": [
    {
      "page": 20,
      "catalog": "20220412 VRV 5 HR.pdf",
      "brand": "daikin",
      "entities": ["FXFA-20A", "FXFA-25A", "FXFA-32A"],
      "specs": {
        "Capacità raffrescamento | kW": {
          "unit": "kW",
          "hvac_type": "HEADER_COOLING",
          "values": {
            "FXFA-20A": 2.2,
            "FXFA-25A": 2.8,
            "FXFA-32A": 3.6
          }
        }
      },
      "stats": {"mapped": 27, "unmapped": 0, "entities": 3}
    }
  ],

  "rag": [
    {
      "text": "La serie FXFA utilizza tecnologia inverter DC che garantisce un controllo preciso della temperatura con consumi ridotti. Ideale per applicazioni residenziali e light commercial.",
      "page": 5,
      "catalog": "20220412 VRV 5 HR.pdf",
      "bbox": {"x": 50, "y": 100, "width": 400, "height": 60},
      "metadata": {
        "section": "Serie FXFA - Overview",
        "series": "FXFA",
        "topics": ["cooling", "efficiency"]
      }
    }
  ],

  "graph": [
    {
      "from": "FXFA-20A",
      "type": "COMPATIBLE_WITH",
      "to": "Controller BRC1E",
      "page": 30,
      "catalog": "20220412 VRV 5 HR.pdf",
      "confidence": 0.8
    },
    {
      "from": "FXFA-20A",
      "type": "PART_OF_SERIES",
      "to": "FXFA",
      "page": 5,
      "catalog": "20220412 VRV 5 HR.pdf",
      "confidence": 0.9
    }
  ]
}
```

---

## 🎯 CLI Usage

```bash
# Estrazione completa
python -m locus.scripts.extract \
    brands/daikin/input/"20220412 VRV 5 HR.pdf" \
    --brand daikin \
    --output output/daikin_vrv5.json

# Solo SQL (dati tabellari)
python -m locus.scripts.extract \
    brands/daikin/input/"20220412 VRV 5 HR.pdf" \
    --brand daikin \
    --mode sql \
    --output output/daikin_vrv5_sql.json

# Pagine specifiche
python -m locus.scripts.extract \
    brands/daikin/input/"20220412 VRV 5 HR.pdf" \
    --pages 20-25 \
    --brand daikin
```

---

## 🚀 Roadmap di Implementazione

### **Phase 1: SQL Foundation** (MVP)
- ✅ Morph v2.0 base già pronta
- 🔲 `extract_tables()` con arricchimento HVAC
- 🔲 `reconstruct_model_names()` helper
- 🔲 PostgreSQL schema + ingestion
- 🔲 Test su Daikin + Hitachi catalogs

### **Phase 2: RAG Integration**
- 🔲 `extract_descriptions()` con chunking intelligente
- 🔲 `group_into_paragraphs()` e metadata extraction
- 🔲 Embedding generation (SentenceTransformer)
- 🔲 Pinecone/Weaviate setup + ingestion

### **Phase 3: Graph Construction**
- 🔲 `extract_relations()` con pattern matching
- 🔲 Context inference per relazioni incomplete
- 🔲 Neo4j schema + ingestion
- 🔲 Cross-page relation linking

### **Phase 4: Unification**
- 🔲 `extract_catalog_full()` orchestration
- 🔲 CLI completo con argparse
- 🔲 Validation e error handling
- 🔲 Batch processing per cataloghi multipli

---

## 💡 Advanced Features (Future)

### **LLM-Powered Enhancements:**
1. **Relation extraction con LLM** invece di regex
2. **Entity linking** cross-catalog (stesso modello in cataloghi diversi)
3. **Semantic chunking** con topic modeling
4. **Missing value inference** da descrizioni (RAG → SQL)

### **Quality Assurance:**
1. **Confidence scores** per ogni extraction
2. **Validation rules** per specs (range plausibili)
3. **Anomaly detection** per valori outlier
4. **Human-in-the-loop** per low confidence items

### **Multi-Modal:**
1. **Image extraction** per diagrammi/schemi
2. **Table cell images** per merged/complex cells
3. **OCR fallback** per PDF scansionati

---

## 📚 Dependencies

```python
# Core
morph>=2.0  # Già nel venv
hvac  # Classification utilities

# RAG
sentence-transformers
pinecone-client
# or weaviate-client

# Graph
neo4j

# NLP (optional)
spacy
rapidfuzz  # Già usato da Morph

# Utils
argparse
pathlib
json
re
```

---

## 🎯 Success Metrics

**SQL Extraction:**
- ✅ ≥95% mapped values (già raggiunto con Morph v2.0)
- ✅ 0 false positives in entity detection
- ✅ Complete model name reconstruction

**RAG Quality:**
- ✅ Chunks coerenti (≥50 chars, max 500 chars)
- ✅ Metadata accuracy ≥90%
- ✅ Embedding quality (similarity tests)

**Graph Completeness:**
- ✅ Compatibilità accessori ≥80% coverage
- ✅ Serie relationships 100% coverage
- ✅ Brand links 100% coverage

---

**Next Step:** Implementare Phase 1 (SQL Foundation) dopo validazione benchmark 2907 tabelle.
