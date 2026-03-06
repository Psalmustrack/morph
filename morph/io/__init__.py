"""
morph.io — Input/Output layer.

Connects the core engine to external systems:
    - reader: PDF input adapter (PyMuPDF)
    - graph: Entity output → Graph L0 format
    - sql: Graph → flat SQL rows

The core engine is I/O agnostic. This layer handles serialization.
"""

from morph.io.reader import open_pdf, MorphoDoc, MorphoPage

__all__ = ['open_pdf', 'MorphoDoc', 'MorphoPage']
