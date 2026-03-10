"""
Morph — Morphogenetic Table Extraction Engine
==============================================

A training-free, GPU-free approach to structured data extraction from PDF
documents. Inspired by biological morphogenesis: each word is a "particle"
with spatial coordinates and an intrinsic type. Table structure emerges from
the spatial distribution — no grid search, no neural network.

Architecture (3-layer pipeline)::

    Layer 1  (layer1_typify)   — Gene expression: classify words by content
    Layer 1b (layer1b_sense)   — Cellular differentiation: promote types by context
    Layer 2  (layer2_field)    — Tissue formation: the morphogenetic field equation

Key result: 95.2% health on 6,238 pages across 5 HVAC brands.
GriTS_Top: 79.7% PubTables-1M, 77.6% FinTabNet — cross-domain gap 2.1pp.

Quick start::

    from morph.io.reader import open_pdf
    from morph.core import extract_particles, extract_page
    from morph.brands import get_brand_patterns

    model_pats, size_pats = get_brand_patterns('hitachi')
    with open_pdf('catalog.pdf') as pdf:
        page = pdf[0]
        particles = extract_particles(page, model_pats, size_pats)
        result = extract_page(particles)
        print(f"Mapped: {result['stats']['mapped']} values")

Formula::

    Phi(i -> j) = W(type_i, type_j) * A_directed(i, j) / d(i, j)^alpha

    where d = sqrt(dx^2 + dy^2 + (lambda_z * dz)^2)

Author: Eugeniu Tacu, 2026
"""

__version__ = '0.1.0'
