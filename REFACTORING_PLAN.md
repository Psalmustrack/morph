# Morph v2.0 → v2.1 Refactoring Plan
**Date**: 2026-03-10
**Goal**: Separate layers into clear directories for better maintainability

---

## 🎯 Current Structure

```
morph/core/
├── __init__.py         (20 lines)
├── typify.py           (411 lines) ✅ OK size
├── sense.py            (840 lines) ⚠️  TOO BIG
└── field.py            (730 lines) ⚠️  TOO BIG
```

---

## 🏗️ Target Structure (Layer Directories)

```
morph/core/
├── __init__.py                    # Re-export tutto (backward compat)
│
├── layer1_typify/
│   ├── __init__.py                # Export: typify_word, extract_particles
│   ├── classify.py                # typify_word() [210 lines]
│   ├── fragments.py               # _merge_fragments() [80 lines]
│   └── extract.py                 # extract_particles() [120 lines]
│
├── layer1b_sense/
│   ├── __init__.py                # Export: sense_page, detect_columns, etc.
│   ├── columns.py                 # Column detection [300 lines]
│   │   ├── _cluster_by_x()
│   │   ├── _natural_threshold()
│   │   ├── _nn_column_evidence()
│   │   ├── _crystallize_columns()
│   │   ├── _extract_vertical_lines()
│   │   ├── detect_columns_from_drawings()
│   │   └── detect_columns()
│   │
│   ├── rows.py                    # Row detection [150 lines]
│   │   ├── _estimate_row_spacing()
│   │   ├── _estimate_row_spacing_all()
│   │   ├── _group_into_rows()
│   │   └── detect_row_label_column()
│   │
│   ├── promote.py                 # Type promotion [250 lines]
│   │   ├── promote_column_headers()
│   │   ├── promote_spec_labels()
│   │   ├── promote_sections()
│   │   └── proofread()
│   │
│   └── orchestrate.py             # sense_page() [140 lines]
│
└── layer2_field/
    ├── __init__.py                # Export: extract_page, calibrate_sigma, etc.
    ├── calibrate.py               # Calibration [150 lines]
    │   ├── calibrate_sigma()
    │   └── calibrate_lambda_z()
    │
    ├── phi.py                     # Field computation [250 lines]
    │   ├── _parse_z_norm()
    │   ├── _assign_z_to_specs()
    │   ├── _directed_alignment()
    │   ├── _phi()
    │   └── _phi_repel()
    │
    ├── merge.py                   # Multiline merging [80 lines]
    │   └── merge_multiline_specs()
    │
    └── extract.py                 # extract_page() [250 lines]
```

---

## 📊 Function Distribution

### **Layer 1: Typify** (411 lines → 3 files)

| File | Functions | Lines |
|------|-----------|-------|
| `classify.py` | `typify_word()` | ~210 |
| `fragments.py` | `_merge_fragments()` | ~80 |
| `extract.py` | `extract_particles()` | ~120 |

### **Layer 1b: Sense** (840 lines → 4 files)

| File | Functions | Lines |
|------|-----------|-------|
| `columns.py` | Column detection (7 funcs) | ~300 |
| `rows.py` | Row detection (4 funcs) | ~150 |
| `promote.py` | Type promotion (4 funcs) | ~250 |
| `orchestrate.py` | `sense_page()` | ~140 |

### **Layer 2: Field** (730 lines → 4 files)

| File | Functions | Lines |
|------|-----------|-------|
| `calibrate.py` | Calibration (2 funcs) | ~150 |
| `phi.py` | Field Φ (5 funcs) | ~250 |
| `merge.py` | `merge_multiline_specs()` | ~80 |
| `extract.py` | `extract_page()` | ~250 |

---

## 🔄 Migration Strategy

### **Phase 1: Create New Structure** (NO breaking changes)

1. Create new directories with `__init__.py`
2. Copy functions into new files
3. Keep old files INTACT
4. New structure imports from old files

```python
# morph/core/layer2_field/__init__.py
from ..field import extract_page, calibrate_sigma  # Temporary!
__all__ = ['extract_page', 'calibrate_sigma']
```

### **Phase 2: Move Functions** (Still backward compatible)

1. Move functions to new files
2. Old files re-export from new structure
3. Add deprecation warnings

```python
# morph/core/field.py (old file)
import warnings
from .layer2_field.extract import extract_page
from .layer2_field.calibrate import calibrate_sigma

warnings.warn(
    "Importing from morph.core.field is deprecated. "
    "Use morph.core.layer2_field instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['extract_page', 'calibrate_sigma', ...]
```

### **Phase 3: Update Internal Imports** (Cleanup)

1. Update all imports in Morph codebase
2. Update tests
3. Update benchmarks

```python
# Before:
from morph.core.field import extract_page

# After:
from morph.core.layer2_field import extract_page
```

### **Phase 4: Remove Old Files** (v3.0 - breaking)

1. Delete old `field.py`, `sense.py`, `typify.py`
2. Update documentation
3. Announce breaking change

---

## ✅ Backward Compatibility

### **Root `__init__.py`** maintains old API:

```python
# morph/core/__init__.py
"""
Morph v2.1 - Layer-organized architecture

For backward compatibility, old imports still work:
    from morph.core.field import extract_page  # OK (deprecated)

Recommended new imports:
    from morph.core.layer2_field import extract_page
"""

# Layer 1: Typify
from .layer1_typify import typify_word, extract_particles

# Layer 1b: Sense
from .layer1b_sense import (
    sense_page, detect_columns, detect_row_label_column,
    promote_column_headers, promote_spec_labels, promote_sections
)

# Layer 2: Field
from .layer2_field import (
    extract_page, calibrate_sigma, calibrate_lambda_z,
    merge_multiline_specs
)

# Backward compat (deprecated)
from . import field, sense, typify  # Old modules still importable

__all__ = [
    # Layer 1
    'typify_word', 'extract_particles',
    # Layer 1b
    'sense_page', 'detect_columns', 'detect_row_label_column',
    'promote_column_headers', 'promote_spec_labels', 'promote_sections',
    # Layer 2
    'extract_page', 'calibrate_sigma', 'calibrate_lambda_z',
    'merge_multiline_specs',
    # Old (deprecated)
    'field', 'sense', 'typify',
]
```

---

## 🧪 Testing Strategy

### **Test 1: Import Compatibility**
```python
# Old imports (should work with deprecation warning)
from morph.core.field import extract_page
from morph.core.sense import sense_page
from morph.core.typify import typify_word

# New imports (should work)
from morph.core.layer2_field import extract_page
from morph.core.layer1b_sense import sense_page
from morph.core.layer1_typify import typify_word
```

### **Test 2: Functional Equivalence**
```bash
# Run full test suite
pytest morph/tests/

# Run HVAC benchmark - MUST be 99.93%!
python -m morph.bench.hvac --n 100

# Run public benchmarks
python -m morph.bench.pubtables --n 500
python -m morph.bench.fintabnet --n 500
```

### **Test 3: Performance**
```python
# Before/after timing comparison
import time
from morph.core import extract_page

# Measure extraction time on 100 pages
# Target: NO performance degradation
```

---

## 📝 Documentation Updates

1. **ARCHITECTURE.md** - Add layer diagram
2. **API.md** - Update import examples
3. **MIGRATION.md** - Guide for v2.0 → v2.1
4. **CHANGELOG.md** - Document refactoring

---

## ⏱️ Time Estimate

| Phase | Task | Time |
|-------|------|------|
| 1 | Create structure + __init__.py | 30 min |
| 2 | Split typify.py (3 files) | 30 min |
| 3 | Split sense.py (4 files) | 1h 30min |
| 4 | Split field.py (4 files) | 1h 30min |
| 5 | Update imports in codebase | 30 min |
| 6 | Test suite + benchmarks | 1h |
| 7 | Documentation | 30 min |
| **TOTAL** | | **6 hours** |

---

## 🚦 Success Criteria

- ✅ All tests pass (pytest)
- ✅ HVAC benchmark: 99.93% maintained
- ✅ PubTables: 99.9% coverage maintained
- ✅ Backward compatibility: old imports work
- ✅ No performance degradation
- ✅ Clear layer separation

---

## 🎯 Implementation Order

1. ✅ Create REFACTORING_PLAN.md (questo file)
2. 🔄 Create directory structure
3. 🔄 Split typify.py
4. 🔄 Split field.py
5. 🔄 Split sense.py
6. 🔄 Update root __init__.py
7. 🔄 Test everything
8. ✅ Commit v2.1

---

**Ready to start? Let's do Phase 1: Create Structure! 🚀**
