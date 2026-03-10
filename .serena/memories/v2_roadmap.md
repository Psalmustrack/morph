# Morph v2.0 — Roadmap Execution

## Current Phase: PHASE 0 (Baseline)

### Status: Not started

### Goal
Raccogliere baseline completa su TUTTI i dataset prima di modificare qualsiasi codice.

### Datasets
1. **HVAC** (5 cataloghi):
   - Hitachi airH2O 600 p.8
   - Daikin VRV p.21
   - Toshiba (TBD)
   - Mitsubishi (TBD)
   - Midea (TBD)

2. **PubTables-1M** (100 tabelle random da test set)

3. **Altri** (se disponibili): SROIE, FUNSD, ICDAR

### Output Target
- `data/baseline_v0.1.json` — Dati completi
- `data/baseline_v0.1_summary.txt` — Sommario leggibile
- Ogni phase successiva confronta con questo PUNTO ZERO

### Next Steps
1. Creare `scripts/baseline_v0.1.py`
2. Implementare raccolta dati per HVAC
3. Implementare raccolta dati per PubTables
4. Eseguire baseline completa
5. Salvare risultati
6. → Passare a Phase 1

## Phases Overview

**Phase 0:** BASELINE (punto zero) ← **CURRENT**
**Phase 1:** READER++ (PyMuPDF full extraction)
**Phase 2:** TYPIFY++ (font-based + fuzzy matching)
**Phase 3:** FIELD++ Part 1 (distanza multi-dimensionale)
**Phase 4:** FIELD++ Part 2 (dualità attrattivo-repulsivo)
**Phase 5:** FIELD++ Part 3 (calibrazione contestuale)
**Phase 6:** SENSE++ (hybrid boundaries)

## Decision Points

### After Phase 3:
- **Question:** Distanza multi-dim migliora vs baseline?
- **If YES:** Proceed to Phase 4
- **If NO:** Rivedi pesi σ_font, σ_hierarchy, σ_color

### After Phase 4:
- **Question:** Dualità risolve cross-table bonds?
- **If YES:** Proceed to Phase 5
- **If NO:** Rivedi costante R (repulsione)

### After Phase 6:
- **Question:** v2.0 è completo?
- **If YES:** PR → merge → tag v2.0.0
- **If NO:** Implementa nice-to-have

## Key Principle

**L'equazione NON cambia mai:**
```
Φ = W · A / d^α
```

**Cambiano solo:**
- Input (d diventa ricco)
- Dualità (+Φ_repel)
- Calibrazione (σ contestuale)

## Files to Track

- [ ] `scripts/baseline_v0.1.py`
- [ ] `data/baseline_v0.1.json`
- [ ] `data/baseline_v0.1_summary.txt`
- [ ] `morph/io/reader.py` (Phase 1)
- [ ] `morph/core/typify.py` (Phase 2)
- [ ] `morph/core/field.py` (Phase 3, 4, 5)
- [ ] `morph/core/sense.py` (Phase 6)

## Metrics to Track

| Metric | v0.1 Baseline | Phase 3 | Phase 4 | Phase 5 | Phase 6 | Target |
|--------|---------------|---------|---------|---------|---------|--------|
| HVAC unmapped | TBD | | | | | -20% |
| PubTables GriTS | 86.0% | | | | | 95%+ |
| Cross-table bonds | TBD | | | | | 0 |
| Processing time | TBD | | | | | <2x |

## Important Notes

1. **Baseline FIRST** — Mai modificare codice senza baseline
2. **Test after EACH phase** — Confronta sempre con baseline
3. **Decision points** — Non procedi se phase non migliora
4. **Commit after EACH phase** — Branch feature/v2.0 pulito
5. **R calibration** — Decideremo empiricamente in Phase 4

## Completion Criteria

Phase 0: ✓ baseline_v0.1.json exists
Phase 1: ✓ Reader extracts 11+ features
Phase 2: ✓ Typify uses font/fuzzy
Phase 3: ✓ Field uses multi-dim distance
Phase 4: ✓ Field uses dualità
Phase 5: ✓ Field uses contextual σ
Phase 6: ✓ Sense uses hybrid boundaries

→ v2.0 COMPLETE → PR → Review → Merge → Tag
