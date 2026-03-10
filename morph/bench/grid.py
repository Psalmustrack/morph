#!/usr/bin/env python3
"""
morph.bench.grid — Adattatore particelle → griglia (righe/colonne)
==================================================================

Traduce il linguaggio di Morpho (particelle, prossimita', campo) nel
linguaggio dei benchmark accademici (righe, colonne, celle).

**Queste funzioni NON appartengono al core.** Servono solo per confrontare
Morpho con dataset come PubTables-1M e FinTabNet che ragionano in griglia.

Principio unificato per boundary detection:
  1. Bimodale → max-jump decide (il salto e' il confine)
  2. Unimodale → ratio gap/dimensione decide (la particella e' la scala)

Due regimi dello stesso fenomeno: il confine emerge dal contrasto
tra vuoto e pieno, che sia locale (max-jump) o globale (ratio).

Author: Eugeniu Tacu, 2026
"""

import statistics
from collections import Counter

# Principi percettivi dal core — il sensing li usa per capire lo spazio,
# il benchmark li riusa per tradurre in griglia.
from morph.core.layer1b_sense.columns import _natural_threshold
from morph.core.layer1b_sense.rows import _estimate_row_spacing_all, _group_into_rows



# ---------------------------------------------------------------------------
# Column spacing & grouping
# ---------------------------------------------------------------------------

def _estimate_col_spacing_all(particles: list[dict]) -> float:
    """Estimate column spacing from ALL particles.

    Simmetrico a _estimate_row_spacing_all ma sull'asse X.

    Returns:
        Median column spacing in pixels.
    """
    xs = sorted(set(round(p['x0']) for p in particles))
    if len(xs) < 3:
        return 30.0
    gaps = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    if not gaps:
        return 30.0
    gaps.sort()
    median_gap = gaps[len(gaps) // 2]
    normal_gaps = [g for g in gaps if 0 < g < median_gap * 2.5]
    return statistics.median(normal_gaps) if normal_gaps else 30.0


def _group_into_columns(particles: list[dict],
                        x_tolerance: float | None = None) -> list[list[dict]]:
    """Group particles into columns by X-axis proximity.

    Simmetrico a _group_into_rows ma sull'asse X.
    Tolerance adattiva: calcolata da col_spacing se non specificata.

    Args:
        particles: Particelle da raggruppare.
        x_tolerance: Max X distance per stessa colonna. Se None,
                     auto-calcolata come ``max(8.0, col_spacing * 0.5)``.

    Returns:
        Lista di colonne, ciascuna una lista di particelle.
    """
    if not particles:
        return []
    if x_tolerance is None:
        col_spacing = _estimate_col_spacing_all(particles)
        x_tolerance = max(8.0, col_spacing * 0.5)

    cols = []
    for p in sorted(particles, key=lambda p: p['x0']):
        placed = False
        for col in cols:
            col_x = sum(it['x0'] for it in col) / len(col)
            if abs(p['x0'] - col_x) < x_tolerance:
                col.append(p)
                placed = True
                break
        if not placed:
            cols.append([p])

    return cols


# ---------------------------------------------------------------------------
# Column counting (X-axis boundaries)
# ---------------------------------------------------------------------------

def _count_cols_ratio(row_particles: list[dict],
                      k: float = 0.3) -> int:
    """Count columns in a row using the universal boundary law.

    The boundary criterion: ``gap > avg_particle_width * k``

    k=0.3 validated on 93,834 PubTables-1M tables: 66.6% col exact.

    Args:
        row_particles: Particles in a single row.
        k: Gap-to-width ratio threshold (universal boundary law).

    Returns:
        Number of detected columns.
    """
    if len(row_particles) < 2:
        return max(1, len(row_particles))

    ps = sorted(row_particles, key=lambda p: p['x0'])
    widths = [p['x1'] - p['x0'] for p in ps]
    gaps = [ps[i + 1]['x0'] - ps[i]['x1'] for i in range(len(ps) - 1)]

    if not gaps:
        return 1

    avg_w = sum(widths) / len(widths)
    if avg_w <= 0:
        avg_w = 10

    threshold = avg_w * k
    n_cols = 1
    for g in gaps:
        if g > threshold:
            n_cols += 1
    return n_cols


def _count_cols_maxjump(row_particles: list[dict],
                        global_threshold: float | None = None) -> int:
    """Count columns in a row using max-ratio-jump threshold.

    Due regimi dello stesso principio (contrasto vuoto/pieno):
    1. Bimodale → max-jump decide (il salto e' il confine)
    2. Unimodale → ratio gap/dimensione decide (la particella e' la scala)

    Args:
        row_particles: Particelle di una singola riga.
        global_threshold: Soglia fallback (calcolata su tutte le righe).

    Returns:
        Numero di colonne rilevate.
    """
    if len(row_particles) < 2:
        return max(1, len(row_particles))

    ps = sorted(row_particles, key=lambda p: p['x0'])
    gaps = [ps[i + 1]['x0'] - ps[i]['x1'] for i in range(len(ps) - 1)]
    # Filtra gap negativi (overlap)
    pos_gaps = [g for g in gaps if g > 0]

    if not pos_gaps:
        return 1

    if len(pos_gaps) >= 3:
        threshold = _natural_threshold(pos_gaps)
        if threshold > max(pos_gaps):
            # Nessun break bimodale locale.
            # Il globale aiuta solo se LUI trova un break.
            if (global_threshold is not None
                    and global_threshold <= max(pos_gaps)):
                threshold = global_threshold
            else:
                # Fallback unimodale: ratio gap/dimensione particella.
                # Se gap > dimensione → tutti confini (celle separate).
                # Se gap < dimensione → nessun confine (testo continuo).
                widths = [p['x1'] - p['x0'] for p in ps
                          if p['x1'] > p['x0']]
                med_w = statistics.median(widths) if widths else 10
                med_gap = statistics.median(pos_gaps)
                if med_gap > med_w * 0.5:
                    threshold = min(pos_gaps) - 0.1
                else:
                    threshold = max(pos_gaps) + 1
    elif global_threshold is not None:
        threshold = global_threshold
    else:
        # Pochi gap, nessun fallback → euristica mediana
        threshold = statistics.median(pos_gaps) * 2

    n_cols = 1
    for g in gaps:
        if g > threshold:
            n_cols += 1
    return n_cols


def count_columns_universal(particles: list[dict],
                            k: float = 0.3,
                            method: str = 'maxjump') -> int:
    """Detect column count with row-mode voting.

    Each row (>= 2 particles) votes for a column count; the mode wins.
    Uses ALL particles — effective on both numeric and text-heavy tables.

    Methods:
        - ``'maxjump'``: soglia adattiva dal salto massimo nei gap (default).
          Validato cross-domain: PubTables 79.7%, FinTabNet 77.6%, gap 2.1pp.
        - ``'fixed'``: soglia fissa ``gap > avg_w * k``.
          Validato su PubTables: 66.6% col exact con k=0.3.

    Args:
        particles: All particles on the page.
        k: Gap-to-width ratio threshold (solo per method='fixed').
        method: ``'maxjump'`` (default) o ``'fixed'``.

    Returns:
        Most common column count across all rows.
    """
    if len(particles) < 2:
        return max(1, len(particles))

    rows = _group_into_rows(particles)

    if method == 'maxjump':
        # Calcola threshold globale come fallback per righe con pochi gap
        all_gaps = []
        for row in rows:
            if len(row) < 2:
                continue
            ps = sorted(row, key=lambda p: p['x0'])
            for i in range(len(ps) - 1):
                g = ps[i + 1]['x0'] - ps[i]['x1']
                if g > 0:
                    all_gaps.append(g)
        global_threshold = _natural_threshold(all_gaps) if all_gaps else None

        votes = []
        for row in rows:
            if len(row) < 2:
                continue
            votes.append(_count_cols_maxjump(row, global_threshold))
    else:
        votes = []
        for row in rows:
            if len(row) < 2:
                continue
            votes.append(_count_cols_ratio(row, k=k))

    if not votes:
        return 1

    return Counter(votes).most_common(1)[0][0]


# ---------------------------------------------------------------------------
# Row counting (Y-axis boundaries)
# ---------------------------------------------------------------------------

def _count_rows_maxjump(col_particles: list[dict],
                        global_threshold: float | None = None) -> int:
    """Count rows in a column using max-ratio-jump threshold.

    Simmetrico a _count_cols_maxjump ma sui gap Y.
    Due regimi dello stesso principio (contrasto vuoto/pieno):
    1. Bimodale → max-jump decide (il salto e' il confine)
    2. Unimodale → ratio gap/dimensione decide (la particella e' la scala)

    Args:
        col_particles: Particelle di una singola colonna.
        global_threshold: Soglia fallback (calcolata su tutte le colonne).

    Returns:
        Numero di righe rilevate.
    """
    if len(col_particles) < 2:
        return max(1, len(col_particles))

    ps = sorted(col_particles, key=lambda p: p['y0'])
    gaps = [ps[i + 1]['y0'] - ps[i]['y1'] for i in range(len(ps) - 1)]
    pos_gaps = [g for g in gaps if g > 0]

    if not pos_gaps:
        return 1

    if len(pos_gaps) >= 3:
        threshold = _natural_threshold(pos_gaps)
        if threshold > max(pos_gaps):
            # Nessun break bimodale locale.
            # Il globale aiuta solo se LUI trova un break.
            if (global_threshold is not None
                    and global_threshold <= max(pos_gaps)):
                threshold = global_threshold
            else:
                # Fallback unimodale: ratio gap/dimensione particella.
                # Se gap > dimensione → tutti confini (righe separate).
                # Se gap < dimensione → nessun confine (testo continuo).
                heights = [p['y1'] - p['y0'] for p in ps
                           if p['y1'] > p['y0']]
                med_h = statistics.median(heights) if heights else 10
                med_gap = statistics.median(pos_gaps)
                if med_gap > med_h * 0.5:
                    threshold = min(pos_gaps) - 0.1
                else:
                    threshold = max(pos_gaps) + 1
    elif global_threshold is not None:
        threshold = global_threshold
    else:
        threshold = statistics.median(pos_gaps) * 2

    n_rows = 1
    for g in gaps:
        if g > threshold:
            n_rows += 1
    return n_rows


def count_rows_universal(particles: list[dict],
                         method: str = 'maxjump') -> int:
    """Detect row count with column-mode voting.

    Simmetrico a count_columns_universal:
    ogni colonna (>= 2 particelle) vota per un row count; la moda vince.

    Args:
        particles: All particles on the page.
        method: ``'maxjump'`` (default).

    Returns:
        Most common row count across all columns.
    """
    if len(particles) < 2:
        return max(1, len(particles))

    cols = _group_into_columns(particles)

    # Calcola threshold globale come fallback per colonne con pochi gap
    all_gaps = []
    for col in cols:
        if len(col) < 2:
            continue
        ps = sorted(col, key=lambda p: p['y0'])
        for i in range(len(ps) - 1):
            g = ps[i + 1]['y0'] - ps[i]['y1']
            if g > 0:
                all_gaps.append(g)
    global_threshold = _natural_threshold(all_gaps) if all_gaps else None

    votes = []
    for col in cols:
        if len(col) < 2:
            continue
        votes.append(_count_rows_maxjump(col, global_threshold))

    if not votes:
        return 1

    return Counter(votes).most_common(1)[0][0]
