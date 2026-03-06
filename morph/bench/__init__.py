"""
morph.bench — Benchmark Suite
==============================

Public benchmarks for validating Morph's table structure recognition
against standard academic datasets.

Datasets supported:

* **PubTables-1M** — 1M+ tables from PubMed scientific papers
  (Microsoft, 2022).  PASCAL-VOC XML ground truth with rows, columns,
  and spanning cells.
* **FinTabNet.c-Structure** — 112K tables from SEC financial filings
  (IBM, 2021).  Same XML format; more complex layouts (multi-level
  headers, wide tables).

Metrics:

* **GriTS** (Grid Table Similarity) — 2D optimal alignment via dynamic
  programming, from the Microsoft table-transformer repository.
  Includes ``GriTS_Top`` (structural topology) and ``GriTS_Con``
  (cell content via LCS similarity).
* **Column / Row exact match** — simpler binary accuracy.

Results (N=10,000 tables, seed=42):

* PubTables-1M:  GriTS_Top = 79.7%, col exact = 66.2%
* FinTabNet.c:   GriTS_Top = 77.6%, col exact = 62.4%
* Cross-domain gap: 2.1 pp (stable generalisation)

Modules:

* :mod:`morph.bench.pubtables` — Dataset adapter and basic metrics
* :mod:`morph.bench.grits` — GriTS metric implementation
* :mod:`morph.bench.adaptive_k` — Max-ratio-jump vs fixed-k comparison

Author: Eugeniu Tacu, 2026
"""
