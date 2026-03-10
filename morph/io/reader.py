"""
morph.io.reader — PDF Input Adapter
====================================

Abstracts the PDF backend (PyMuPDF/fitz) behind a uniform interface.
Morph doesn't know and doesn't care which library reads the PDF.

Backend: PyMuPDF (fitz) — 20-50x faster than pdfplumber, more accurate
on inverted text and decimal numbers.

Usage::

    from morph.io.reader import open_pdf

    with open_pdf('catalog.pdf') as doc:
        for page in doc.pages:
            words = page.extract_words()

Author: Eugeniu Tacu, 2026
"""

import fitz


class MorphoPage:
    """PDF page wrapper with extract_particles()-compatible interface.

    Wraps a PyMuPDF page and provides word extraction in a format
    that matches what the core engine (typify.py) expects.

    Attributes:
        width: Page width in points.
        height: Page height in points.
        page_number: 1-based page number.
    """

    __slots__ = ('_page', 'width', 'height', 'page_number')

    def __init__(self, fitz_page: fitz.Page):
        self._page = fitz_page
        self.width = fitz_page.rect.width
        self.height = fitz_page.rect.height
        self.page_number = fitz_page.number + 1  # 1-based

    def extract_words(self, full_features: bool = True, **kwargs) -> list[dict]:
        """Extract words with bounding boxes and rich PyMuPDF features.

        PyMuPDF spans are already grouped by font/style from the PDF.
        In a technical catalog, each span corresponds to a semantic unit
        (label, value, unit) — keeping them whole preserves multi-word
        labels that extract_page() expects.

        Args:
            full_features: If True (default), extract all PyMuPDF features
                (font, color, hierarchy, baseline). If False, extract only
                basic features (text, bbox, size) for v0.1 compatibility.

        Returns:
            List of dicts with keys:
                - Basic (v0.1): text, x0, top, x1, bottom, size
                - Full (v2.0): + font, flags, color, origin, ascender,
                  descender, span_num, line_num, block_num
        """
        page_dict = self._page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        words = []
        for block_num, block in enumerate(page_dict.get("blocks", [])):
            if block.get("type") != 0:  # text blocks only
                continue
            for line_num, line in enumerate(block.get("lines", [])):
                for span_num, span in enumerate(line.get("spans", [])):
                    text = span["text"].strip()
                    if not text:
                        continue

                    # Basic features (v0.1 compatibility)
                    word = {
                        'text': text,
                        'x0': span["bbox"][0],
                        'top': span["bbox"][1],
                        'x1': span["bbox"][2],
                        'bottom': span["bbox"][3],
                        'size': span.get("size", 0),
                    }

                    # Full features (v2.0)
                    if full_features:
                        word.update({
                            # Typography
                            'font': span.get("font", ""),
                            'flags': span.get("flags", 0),  # bold, italic, mono, serif
                            'color': span.get("color", 0),  # RGB as int

                            # Baseline & metrics
                            'origin': span.get("origin", (0, 0)),  # (x, y) baseline point
                            'ascender': span.get("ascender", 0),
                            'descender': span.get("descender", 0),

                            # Hierarchy (parent-child structure)
                            'span_num': span_num,
                            'line_num': line_num,
                            'block_num': block_num,
                        })

                    words.append(word)

        return words

    def extract_drawings(self) -> list[dict]:
        """Extract vector drawings (lines, rectangles, borders).

        Useful for detecting table borders in bordered tables.

        Returns:
            List of dicts with keys: type, rect, color, width, items
        """
        drawings = self._page.get_drawings()
        return [
            {
                'type': d.get('type', ''),  # 'l' (line), 'r' (rect), 'c' (curve)
                'rect': d.get('rect', (0, 0, 0, 0)),  # (x0, y0, x1, y1)
                'color': d.get('color', None),  # RGB tuple or None
                'width': d.get('width', 0),  # line width
                'items': d.get('items', []),  # path items
            }
            for d in drawings
        ]


class MorphoDoc:
    """PDF document wrapper. Context manager compatible with pdfplumber.

    Usage::

        with MorphoDoc('catalog.pdf') as doc:
            page = doc[0]
            words = page.extract_words()
    """

    def __init__(self, path: str):
        self._doc = fitz.open(str(path))

    @property
    def pages(self) -> list[MorphoPage]:
        """All pages as MorphoPage objects."""
        return [MorphoPage(self._doc[i]) for i in range(len(self._doc))]

    def __len__(self):
        return len(self._doc)

    def __getitem__(self, idx) -> MorphoPage:
        return MorphoPage(self._doc[idx])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._doc.close()

    def close(self):
        """Explicitly close the document."""
        self._doc.close()

    def get_toc(self) -> list[tuple]:
        """Extract table of contents (TOC).

        Useful for calibrazione contestuale (σ = f(section)).
        Each TOC entry is a tuple (level, title, page_num).

        Returns:
            List of (level, title, page_num) tuples.
        """
        return self._doc.get_toc()

    def get_metadata(self) -> dict:
        """Extract document metadata.

        Returns:
            Dict with keys: author, title, subject, keywords, creator,
            producer, creationDate, modDate, format, encryption, etc.
        """
        return self._doc.metadata or {}


def open_pdf(path: str) -> MorphoDoc:
    """Open a PDF for Morph processing.

    Drop-in replacement for ``pdfplumber.open()``.

    Args:
        path: Path to PDF file.

    Returns:
        MorphoDoc context manager.
    """
    return MorphoDoc(path)
