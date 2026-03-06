"""
morph.io.sql — Graph L0 → Flat SQL Rows
=========================================

Unrolls Graph L0 nodes into ``{model, header, value, unit, page}`` rows
compatible with SQLite storage (table_store.py).

The graph is the primary data format. SQL is a derived view for tabular queries.

Usage::

    from morph.io.graph import morpho_to_graph
    from morph.io.sql import graph_to_rows

    graph = morpho_to_graph(extract_result, brand='hitachi')
    rows = graph_to_rows(graph, page=42)
    # rows = [{'model': 'RAS-4FSXNME', 'header': 'cop', 'value': '4.50', ...}, ...]

Author: Eugeniu Tacu, 2026
"""


def graph_to_rows(
    graph: dict,
    page: int = 0,
) -> list[dict]:
    """Unroll Graph L0 nodes into flat rows for SQL storage.

    Each node property becomes one row with model, header, value, unit, page.

    Args:
        graph: Output of :func:`morph.io.graph.morpho_to_graph`.
        page: Page number override (0 = use node's _meta.page).

    Returns:
        List of dicts with keys: model, header, value, unit, page, section.
    """
    rows = []
    for node in graph.get('nodes', []):
        model = node['name']
        node_page = page or node.get('_meta', {}).get('page', 0)

        for prop_key, prop_info in node.get('properties', {}).items():
            value = prop_info.get('value', '')
            # Serialize min/nom/max dicts as string
            if isinstance(value, dict):
                parts = []
                for k in ('min', 'nom', 'max'):
                    if k in value:
                        parts.append(str(value[k]))
                value = '/'.join(parts)
            else:
                value = str(value)

            rows.append({
                'model': model,
                'header': prop_key,
                'value': value,
                'unit': prop_info.get('unit', ''),
                'page': node_page,
                'section': prop_info.get('section', ''),
            })

    return rows
