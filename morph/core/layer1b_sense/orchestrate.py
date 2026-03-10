"""
morph.core.layer1b_sense.orchestrate — Sensing Pipeline
=======================================================

Main entry point: sense_page() orchestrates all sensing stages.
"""

from .columns import detect_columns
from .rows import detect_row_label_column, assign_row_ids, promote_orphan_sections
from .promote import (
    promote_column_headers,
    promote_spec_labels,
    promote_sections,
    proofread,
)


def sense_page(particles: list[dict],
               drawings: list[dict] | None = None) -> dict:
    """Run complete spatial sensing on a page.

    **v2.0 Phase 6:** Accepts optional drawings for hybrid boundary detection.

    This is the main entry point for Layer 1b. Orchestrates all
    sensing stages in order, modifying particles in-place.

    Pipeline::

        1. detect_columns()          → structural skeleton (hybrid: drawings or geometric)
        2. promote_column_headers()  → TEXT above columns → MODEL
        3. detect_row_label_column() → TEXT left of columns → SPEC_LABEL
        4. promote_spec_labels()     → TEXT left of NUMERIC → SPEC_LABEL
        5. promote_sections()        → large TEXT → SECTION
        6. proofread()               → isolated NUMERIC → TEXT

    Args:
        particles: Typed particles from Layer 1.
        drawings: Optional drawings from page.extract_drawings() (v2.0).

    Returns:
        Dict with keys:
            - ``particles``: Modified particle list
            - ``columns``: Number of detected structural columns
            - ``headers``: Number of promoted column headers
            - ``row_labels``: Number of promoted row labels
            - ``specs``: Number of promoted spec labels
            - ``sections``: Number of promoted sections
            - ``proofread``: Number of demoted particles
    """
    if len(particles) < 5:
        return {'particles': particles,
                'columns': 0, 'headers': 0, 'specs': 0,
                'sections': 0, 'proofread': 0}

    # 1. Structural skeleton (v2.0: hybrid detection)
    columns = detect_columns(particles, drawings=drawings)

    # 2. Column headers (apical text → MODEL)
    promoted_headers = promote_column_headers(particles, columns)

    # 2.5. Row-label column (left-aligned text → SPEC_LABEL)
    promoted_row_labels = detect_row_label_column(particles, columns)

    # 3. Spec labels (lateral text → SPEC_LABEL)
    promoted_specs = promote_spec_labels(particles)

    # 4. Sections (large font → SECTION)
    promoted_sections = promote_sections(particles)

    # 5. DNA proofreading — demote incoherent particles
    demoted = proofread(particles, columns=columns)

    # 6. Row segmentation — assign row_id to each particle
    row_info = assign_row_ids(particles)

    # 7. Promote orphan sections — SECTION → SPEC_LABEL in rows with
    #    NUMERICs but no spec (prevents orphan numerics)
    promoted_orphans = promote_orphan_sections(particles)

    return {
        'particles': particles,
        'columns': len(columns),
        'headers': len(promoted_headers),
        'row_labels': len(promoted_row_labels),
        'specs': len(promoted_specs),
        'sections': len(promoted_sections),
        'proofread': len(demoted),
        'rows': len(row_info),
        'orphan_promotions': len(promoted_orphans),
    }
