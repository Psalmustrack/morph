# Morph Domain Modules

Domain-specific configurations for Morph extraction.

## 🏗️ Architecture

Each domain module defines:
- **Vocabulary**: SPEC_TERMS, SECTION_TERMS, UNIT_SET
- **Patterns**: model_patterns, size_patterns, exclude_patterns
- **Behavior**: use_fuzzy, require_models

## 📦 Available Domains

### 1. HVAC (`hvac.py`)
**For**: Air conditioning, heating, heat pumps, chillers, VRF/VRV systems

**Features**:
- Model code patterns (brand-specific)
- HVAC vocabulary (capacità, potenza, EER, SEER, etc.)
- Unit detection (kW, dB(A), m³/h, etc.)
- Requires MODEL particles as column headers

**Usage**:
```python
from morph.domains import HVAC

# Override with brand-specific patterns
daikin_hvac = HVAC.copy()
daikin_hvac.model_patterns = [r'FXF[A-Z]-\d+[A-Z]']
```

---

### 2. SCIENTIFIC (`scientific.py`)
**For**: Research papers, medical studies, clinical trials

**Features**:
- Scientific vocabulary (cases, controls, p-value, mean, sd, etc.)
- Statistical terms
- Medical terminology
- No MODEL requirement (uses column position)

**Usage**:
```python
from morph.domains import SCIENTIFIC

particles = extract_particles(page, domain_config=SCIENTIFIC)
```

---

### 3. FINANCIAL (`financial.py`)
**For**: Financial reports, balance sheets, income statements

**Features**:
- Financial vocabulary (revenue, assets, EBITDA, etc.)
- Currency and scale units ($, M, B)
- Time period terms (Q1, FY, YTD)
- No MODEL requirement

**Usage**:
```python
from morph.domains import FINANCIAL

particles = extract_particles(page, domain_config=FINANCIAL)
```

---

### 4. UNIVERSAL (`universal.py`)
**For**: Generic tables, unknown domains

**Features**:
- No vocabulary
- Pure spatial detection
- No MODEL requirement
- Fastest (no pattern matching)

**Usage**:
```python
from morph.domains import UNIVERSAL

particles = extract_particles(page, domain_config=UNIVERSAL)
```

---

## 🔧 Creating Custom Domains

```python
from morph.domains import DomainConfig

MY_DOMAIN = DomainConfig(
    name="my_domain",

    # Patterns (optional)
    model_patterns=[r'PRODUCT-\d+'],

    # Vocabulary
    spec_terms={'price', 'quantity', 'weight'},
    unit_set={'$', 'kg', 'pcs'},

    # Behavior
    require_models=True,
    use_fuzzy=True,
)

# Use it
particles = extract_particles(page, domain_config=MY_DOMAIN)
```

---

## 📊 Domain Comparison

| Domain | MODEL Required | Vocabulary Size | Use Case |
|--------|---------------|----------------|----------|
| **HVAC** | ✅ Yes | ~100 terms | HVAC catalogs |
| **SCIENTIFIC** | ❌ No | ~80 terms | Research papers |
| **FINANCIAL** | ❌ No | ~70 terms | Financial reports |
| **UNIVERSAL** | ❌ No | 0 terms | Generic tables |

---

## 🎯 Integration Points

Domain modules integrate with:

1. **`typify_word()`** - Uses vocabulary for type classification
2. **`extract_particles()`** - Passes domain_config down
3. **`extract_page()`** - Checks `require_models` flag

See integration guide in `/morph/core/` for implementation details.

---

**Created**: 2026-03-10
**Morph Version**: v2.1
