"""
morph.pipeline — Full PDF → Graph L0 + SQL + RAG Pipeline
==========================================================

Single-command processing of an entire HVAC technical catalogue.
Produces three output artefacts per PDF:

* ``_graph.json`` — Graph L0 nodes with normalised properties
* ``_rag.md``     — Heading-based text chunks for RAG ingestion
* ``_tables.json`` — Flat SQL rows for tabular queries

The pipeline orchestrates three phases:

1. **Page extraction** — each page runs through the morphogenetic
   layers (typify → sense → field) independently.
2. **Cross-page merge** — consecutive pages with compatible column
   fingerprints are fused via an endocrine-system metaphor:
   chemical signals (column fingerprints) coordinate distant tissues
   (pages) into a single organ (multi-page table).
3. **Output serialisation** — Graph L0, RAG markdown, and SQL rows
   are written to the output directory.

Usage::

    # Single PDF
    python -m morph.pipeline catalog.pdf --brand hitachi -o output/

    # Batch (all PDFs for one brand)
    python -m morph.pipeline --batch brands/hitachi/input/ --brand hitachi

    # Batch (all brands)
    python -m morph.pipeline --batch-all

Author: Eugeniu Tacu, 2026
"""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

from morph.io.reader import open_pdf
from morph.core import extract_particles, extract_page
from morph.brands import get_brand_patterns, AVAILABLE_BRANDS
from morph.io.graph import morpho_to_graph
from morph.io.sql import graph_to_rows

# Soft dependency — knowledge module is project-level, not part of morph/
try:
    import knowledge as _knowledge
except ImportError:
    _knowledge = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Phase 1 helpers: single-page extraction + RAG chunk building
# ---------------------------------------------------------------------------

def morpho_full_page(
    page,
    model_patterns: list,
    size_patterns: list,
    min_mapped: int = 3,
) -> dict:
    """Extract structured data and RAG chunks from a single PDF page.

    Runs the full morphogenetic pipeline (typify → sense → field) on one
    page and classifies the result as *technical*, *narrative*, *mixed*,
    or *empty*.

    Args:
        page: A :class:`~morph.io.reader.MorphoPage` instance.
        model_patterns: Compiled regex list for model code detection.
        size_patterns: Compiled regex list for size-header detection.
        min_mapped: Minimum mapped specs to consider the page technical.

    Returns:
        Dict with keys ``page_type``, ``structured``, ``rag_chunks``,
        ``stats``.
    """
    particles = extract_particles(page, model_patterns, size_patterns)
    if len(particles) < 5:
        return {'page_type': 'empty', 'structured': None,
                'rag_chunks': [], 'stats': {}}

    structured = extract_page(particles)
    has_data = structured['stats']['mapped'] >= min_mapped

    rag_chunks = _build_rag_chunks(particles, structured)

    n_text = sum(1 for p in particles if p['type'] in ('TEXT', 'SECTION'))
    n_data = sum(1 for p in particles if p['type'] in ('NUMERIC', 'UNIT'))

    if has_data and n_text > 20:
        page_type = 'mixed'
    elif has_data:
        page_type = 'technical'
    elif n_text > 15:
        page_type = 'narrative'
    else:
        page_type = 'empty'

    return {
        'page_type': page_type,
        'structured': structured if has_data else None,
        'rag_chunks': rag_chunks,
        'stats': {
            'particles': len(particles),
            'mapped': structured['stats']['mapped'],
            'entities': structured['stats']['entities'],
            'text_particles': n_text,
            'data_particles': n_data,
            'rag_chunks': len(rag_chunks),
            'rag_chars': sum(len(c['text']) for c in rag_chunks),
        },
    }


def _build_rag_chunks(
    particles: list[dict],
    structured: dict,
) -> list[dict]:
    """Build RAG text chunks from particles and structured output.

    Groups particles by Y-row, splits on SECTION boundaries, and
    appends a readable table chunk for pages with enough mapped specs.

    Args:
        particles: Typed particle list from :func:`extract_particles`.
        structured: Output of :func:`extract_page`.

    Returns:
        List of dicts with keys ``type``, ``section``, ``text``.
    """
    if not particles:
        return []

    sorted_parts = sorted(particles, key=lambda p: (p['y0'], p['x0']))

    # Group into visual rows
    rows: list[list[dict]] = []
    for p in sorted_parts:
        if rows and abs(p['y0'] - rows[-1][-1]['y0']) <= 3:
            rows[-1].append(p)
        else:
            rows.append([p])

    current_section = "GENERALE"
    chunks: list[dict] = []
    current_lines: list[str] = []

    for row in rows:
        section_in_row = [p for p in row if p['type'] == 'SECTION']
        if section_in_row:
            if current_lines:
                text = '\n'.join(current_lines)
                if text.strip():
                    chunks.append({
                        'type': 'text',
                        'section': current_section,
                        'text': text.strip(),
                    })
                current_lines = []
            current_section = section_in_row[0]['text'][:50]

        useful = [p for p in row if p['type'] != 'TEXT'
                  or len(p['text']) > 2]
        if useful:
            useful.sort(key=lambda p: p['x0'])
            line = ' '.join(p['text'] for p in useful)
            if len(line.strip()) > 3:
                current_lines.append(line.strip())

    if current_lines:
        text = '\n'.join(current_lines)
        if text.strip():
            chunks.append({
                'type': 'text',
                'section': current_section,
                'text': text.strip(),
            })

    # Structured table chunk (readable Markdown)
    if structured and structured['stats']['mapped'] >= 3:
        table_lines: list[str] = []
        for entity, specs in structured['data'].items():
            table_lines.append(f"## {entity}")
            for key, val in sorted(specs.items()):
                unit = f" {val['unit']}" if val.get('unit') else ""
                table_lines.append(f"- {key}: {val['value']}{unit}")
            table_lines.append("")
        if table_lines:
            chunks.append({
                'type': 'table',
                'section': 'DATI TECNICI STRUTTURATI',
                'text': '\n'.join(table_lines),
            })

    return chunks


# ---------------------------------------------------------------------------
# Phase 2: cross-page merge — endocrine system
# ---------------------------------------------------------------------------

def _page_fingerprint(structured: dict) -> tuple | None:
    """Compute a structural fingerprint for cross-page matching.

    The fingerprint captures column type and label set, allowing the
    merge logic to detect continuation pages for multi-page tables.

    Args:
        structured: Output of :func:`extract_page` (must have ``columns``).

    Returns:
        Tuple ``(col_type, frozenset_of_labels)`` or ``None``.
    """
    cols = structured.get('columns')
    if not cols:
        return None
    col_type = cols[0].get('type', '')
    col_labels = frozenset(c['label'] for c in cols)
    return (col_type, col_labels)


def _fingerprints_compatible(fp_a: tuple, fp_b: tuple) -> bool:
    """Check if two fingerprints represent the same table structure.

    Uses relaxed matching: same column type AND at least one shared
    label.  The merge is protected downstream by entity-name overlap
    checks (the real safety net).

    Args:
        fp_a: First fingerprint from :func:`_page_fingerprint`.
        fp_b: Second fingerprint.

    Returns:
        True if the fingerprints are compatible for merging.
    """
    if fp_a[0] != fp_b[0]:
        return False
    return len(fp_a[1] & fp_b[1]) >= 1


def _merge_cross_page(
    page_results: list[tuple[int, dict]],
) -> list[tuple[int, dict]]:
    """Fuse consecutive pages with compatible column structures.

    Like the endocrine system: chemical signals (fingerprints)
    coordinate distant tissues (pages) into a single organ
    (multi-page table).  Entities with the same name across pages
    receive the union of their specs.

    Lookback window: up to 3 pages apart (to skip intervening pages
    with different layouts).

    Args:
        page_results: List of ``(page_number, result_dict)`` tuples.

    Returns:
        Updated list with merged structured data.
    """
    if len(page_results) < 2:
        return page_results

    # Index technical pages with fingerprints
    tech: list[tuple[int, int, tuple]] = []
    for i, (pg, result) in enumerate(page_results):
        s = result.get('structured')
        if s and s.get('columns'):
            fp = _page_fingerprint(s)
            if fp:
                tech.append((i, pg, fp))

    if len(tech) < 2:
        return page_results

    # Build merge chains (lookback up to 3 technical pages)
    merge_into: dict[int, int] = {}
    for k in range(1, len(tech)):
        i_curr, pg_curr, fp_curr = tech[k]
        for j in range(k - 1, max(k - 4, -1), -1):
            i_prev, pg_prev, fp_prev = tech[j]
            if pg_curr - pg_prev > 3:
                break
            if _fingerprints_compatible(fp_curr, fp_prev):
                base = merge_into.get(i_prev, i_prev)
                merge_into[i_curr] = base
                break

    if not merge_into:
        return page_results

    # Group: base → [continuation indices]
    groups: dict[int, list[int]] = defaultdict(list)
    for cont, base in merge_into.items():
        groups[base].append(cont)

    # Execute merges
    out = list(page_results)
    n_merged_pages = 0

    for base_idx, cont_indices in groups.items():
        base_pg, base_result = out[base_idx]
        base_data = base_result['structured']['data']

        # Verify entity overlap (at least 1 shared name)
        base_entities = set(base_data.keys())
        any_overlap = False
        for ci in cont_indices:
            _, cont_result = out[ci]
            s = cont_result.get('structured')
            if s and s.get('data'):
                if base_entities & set(s['data'].keys()):
                    any_overlap = True
                    break

        if not any_overlap:
            continue

        # Merge: first page absorbs specs from continuations
        merged = dict(base_data)
        extra = 0
        pages = [base_pg]

        for ci in sorted(cont_indices):
            cpg, cresult = out[ci]
            pages.append(cpg)
            cs = cresult.get('structured')
            if cs and cs.get('data'):
                for entity, specs in cs['data'].items():
                    if entity not in merged:
                        merged[entity] = {}
                    for key, val in specs.items():
                        if key not in merged[entity]:
                            merged[entity][key] = val
                            extra += 1

            # Continuation: remove structured (already fused), keep RAG
            cr = dict(cresult)
            cr['structured'] = None
            out[ci] = (cpg, cr)

        # Update base with merged data
        ns = dict(base_result['structured'])
        ns['data'] = merged
        ns['stats'] = dict(ns['stats'])
        ns['stats']['mapped'] += extra
        ns['stats']['entities'] = len(merged)
        ns['stats']['total_specs'] = sum(len(v) for v in merged.values())
        ns['stats']['cross_page'] = pages

        nr = dict(base_result)
        nr['structured'] = ns
        nr['stats'] = dict(nr.get('stats', {}))
        nr['stats']['mapped'] = ns['stats']['mapped']
        nr['stats']['entities'] = ns['stats']['entities']
        out[base_idx] = (base_pg, nr)
        n_merged_pages += len(cont_indices)

    if n_merged_pages:
        logger.info(
            "  cross-page: %d pages fused into %d groups (+%d properties)",
            n_merged_pages + len(groups), len(groups),
            sum(
                out[bi][1]['structured']['stats'].get('mapped', 0)
                - page_results[bi][1]['structured']['stats'].get('mapped', 0)
                for bi in groups
                if out[bi][1].get('structured')
            ),
        )

    return out


# ---------------------------------------------------------------------------
# Phase 3: full pipeline — PDF → three output files
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: Path,
    brand: str,
    output_dir: Path | None = None,
    min_mapped: int = 3,
) -> dict:
    """Process a full PDF catalogue through the morphogenetic pipeline.

    Produces three output files: ``_graph.json``, ``_rag.md``,
    ``_tables.json`` in the specified output directory.

    Args:
        pdf_path: Path to the source PDF.
        brand: Brand name (must be in :data:`AVAILABLE_BRANDS`).
        output_dir: Output directory (default: ``../output/<name>/auto/``
            relative to the PDF).
        min_mapped: Minimum mapped specs for a page to be considered
            technical.

    Returns:
        Dict with keys ``stats`` (aggregate statistics) and ``paths``
        (output file paths as strings).
    """
    pdf_path = Path(pdf_path)
    catalog_name = pdf_path.stem

    if output_dir is None:
        output_dir = pdf_path.parent.parent / "output" / catalog_name / "auto"
    else:
        output_dir = Path(output_dir) / catalog_name / "auto"
    output_dir.mkdir(parents=True, exist_ok=True)

    model_patterns, size_patterns = get_brand_patterns(brand)
    logger.info("Morpho: %s (brand=%s)", pdf_path.name, brand)

    # --- Phase 1: page extraction ---
    page_results: list[tuple[int, dict]] = []

    with open_pdf(str(pdf_path)) as pdf:
        for pg_idx in range(len(pdf.pages)):
            page = pdf.pages[pg_idx]

            # Quick filter: skip near-empty pages
            words = page.extract_words()
            if len(words) < 15:
                continue

            result = morpho_full_page(
                page, model_patterns, size_patterns, min_mapped,
            )

            if result['page_type'] == 'empty':
                continue

            page_results.append((pg_idx + 1, result))

    # --- Phase 2: cross-page merge (endocrine system) ---
    page_results = _merge_cross_page(page_results)

    # --- Phase 3: graph/SQL conversion + accumulation ---
    all_nodes: list[dict] = []
    all_rag_chunks: list[dict] = []
    all_sql_rows: list[dict] = []
    page_stats: list[dict] = []
    total_props = 0
    total_normalized = 0

    for page_num, result in page_results:
        # Graph L0 for technical (or merged) pages
        if result['structured']:
            graph = morpho_to_graph(
                result['structured'],
                brand=brand,
                catalog_name=catalog_name,
                page=page_num,
            )
            all_nodes.extend(graph['nodes'])
            total_props += graph['stats']['total_properties']
            total_normalized += graph['stats']['normalized']

            # SQL rows
            rows = graph_to_rows(graph, page=page_num)
            all_sql_rows.extend(rows)

        # RAG chunks with page metadata
        for chunk in result['rag_chunks']:
            chunk['page'] = page_num
            all_rag_chunks.append(chunk)

        page_stats.append({
            'page': page_num,
            'type': result['page_type'],
            **result['stats'],
        })

    # Flush active-learning staging (if knowledge module available)
    if _knowledge is not None:
        _knowledge.flush_staging()

    # Re-number node IDs (global per catalogue)
    for i, node in enumerate(all_nodes):
        old_type = node['type']
        node['id'] = f"{brand}.{old_type}_{i:04d}"

    # --- Write output files ---
    base = output_dir / catalog_name
    paths: dict[str, Path] = {}

    # 1. Graph L0
    graph_out = {
        'nodes': all_nodes,
        'edges': [],
        'metadata': {
            'brand': brand,
            'catalog': catalog_name,
            'source': 'morph',
            'total_nodes': len(all_nodes),
            'total_properties': total_props,
            'normalized': total_normalized,
        },
    }
    graph_path = Path(str(base) + '_graph.json')
    graph_path.write_text(
        json.dumps(graph_out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths['graph'] = graph_path
    logger.info("  graph: %d nodes → %s", len(all_nodes), graph_path.name)

    # 2. RAG markdown
    rag_path = Path(str(base) + '_rag.md')
    _write_rag_md(all_rag_chunks, rag_path)
    paths['rag'] = rag_path
    logger.info("  rag: %d chunks → %s", len(all_rag_chunks), rag_path.name)

    # 3. SQL rows
    tables_path = Path(str(base) + '_tables.json')
    tables_path.write_text(
        json.dumps(all_sql_rows, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths['tables'] = tables_path
    logger.info("  sql: %d rows → %s", len(all_sql_rows), tables_path.name)

    # Aggregate statistics
    type_counts = Counter(ps['type'] for ps in page_stats)
    stats = {
        'catalog': catalog_name,
        'brand': brand,
        'total_pages_processed': len(page_stats),
        'page_types': dict(type_counts),
        'total_nodes': len(all_nodes),
        'total_properties': total_props,
        'total_sql_rows': len(all_sql_rows),
        'total_rag_chunks': len(all_rag_chunks),
        'normalization_rate': round(
            total_normalized / max(1, total_props) * 100, 1
        ),
    }

    logger.info(
        "  DONE: %d pages, %d nodes, %d props (norm %.1f%%), %d RAG chunks",
        stats['total_pages_processed'], stats['total_nodes'],
        stats['total_properties'], stats['normalization_rate'],
        stats['total_rag_chunks'],
    )

    return {'stats': stats, 'paths': {k: str(v) for k, v in paths.items()}}


def _write_rag_md(chunks: list[dict], path: Path) -> None:
    """Write RAG chunks in heading-based Markdown format.

    Produces a ``_rag.md`` file compatible with ``rag_build.py``'s
    heading-based chunking strategy.  Each section gets an ``## H2``
    heading; page boundaries are marked with HTML comments.

    Args:
        chunks: List of chunk dicts with ``page``, ``section``, ``text``.
        path: Output file path.
    """
    lines: list[str] = []
    current_page = None
    for chunk in chunks:
        pg = chunk.get('page', 0)
        if pg and pg != current_page:
            if current_page is not None:
                lines.append("")
            lines.append(f"<!-- page:{pg} -->")
            current_page = pg

        section = chunk.get('section', 'GENERALE')
        lines.append(f"\n## {section}\n")
        lines.append(chunk['text'])
        lines.append("")

    path.write_text('\n'.join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Batch: process all PDFs for one or more brands
# ---------------------------------------------------------------------------

def _discover_pdfs(brand: str | None = None) -> list[tuple[Path, str]]:
    """Discover all input PDFs organised by brand directory.

    Scans ``brands/<brand>/input/*.pdf`` for each available brand.

    Args:
        brand: Restrict to one brand (``None`` = all available).

    Returns:
        List of ``(pdf_path, brand_name)`` tuples.
    """
    root = Path(__file__).parent.parent
    brand_root = root / "brands"
    pairs: list[tuple[Path, str]] = []

    brands = [brand] if brand else [
        d.name for d in sorted(brand_root.iterdir())
        if d.is_dir() and (d / "input").exists()
        and d.name in AVAILABLE_BRANDS
    ]

    for b in brands:
        input_dir = brand_root / b / "input"
        if input_dir.exists():
            for pdf in sorted(input_dir.glob("*.pdf")):
                pairs.append((pdf, b))

    return pairs


def batch_process(
    brand: str | None = None,
    input_dir: Path | None = None,
    output_base: Path | None = None,
) -> dict:
    """Batch-process all PDFs for one or more brands.

    Args:
        brand: Single brand name (``None`` = all available brands).
        input_dir: Override input directory (otherwise auto-discovered).
        output_base: Override base output directory.

    Returns:
        Dict with ``total``, ``ok``, ``errors``, ``results``.
    """
    if input_dir:
        pdfs = [
            (p, brand or 'unknown')
            for p in sorted(Path(input_dir).glob("*.pdf"))
        ]
    else:
        pdfs = _discover_pdfs(brand)

    logger.info("Batch Morpho: %d PDFs", len(pdfs))
    results: list[dict] = []

    for i, (pdf_path, pdf_brand) in enumerate(pdfs, 1):
        logger.info("[%d/%d] %s (brand=%s)",
                    i, len(pdfs), pdf_path.name, pdf_brand)
        try:
            out_dir = output_base or pdf_path.parent.parent / "output"
            result = process_pdf(pdf_path, pdf_brand, output_dir=out_dir)
            result['status'] = 'ok'
            results.append(result)
        except Exception as e:
            logger.error("ERROR %s: %s", pdf_path.name, e)
            results.append({
                'status': 'error',
                'catalog': pdf_path.stem,
                'error': str(e),
            })

    ok = sum(1 for r in results if r['status'] == 'ok')
    logger.info("Batch complete: %d/%d OK", ok, len(results))

    return {
        'total': len(results),
        'ok': ok,
        'errors': len(results) - ok,
        'results': results,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Morph pipeline: PDF → Graph L0 + SQL + RAG',
    )
    parser.add_argument('pdf', nargs='?', help='Path to PDF file')
    parser.add_argument('--brand', default='hitachi',
                        help='Brand name (default: hitachi)')
    parser.add_argument('-o', '--output-dir', help='Output directory')
    parser.add_argument('--batch', metavar='DIR',
                        help='Batch mode: directory containing PDFs')
    parser.add_argument('--batch-all', action='store_true',
                        help='Batch mode: all available brands')

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%H:%M:%S',
    )

    if args.batch_all:
        report = batch_process()
        print(json.dumps(report['results'][-1:],
                         indent=2, ensure_ascii=False))
    elif args.batch:
        batch_process(
            brand=args.brand,
            input_dir=Path(args.batch),
            output_base=Path(args.output_dir) if args.output_dir else None,
        )
    elif args.pdf:
        result = process_pdf(
            Path(args.pdf),
            brand=args.brand,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        parser.print_help()
