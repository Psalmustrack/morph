"""Esperimento Reazione-Diffusione — promozione tipi via primo vicino.

L'idea: ogni particella TEXT ha probabilita' per MODEL, SPEC_LABEL, TEXT.
Ad ogni iterazione, guarda SOLO i primi vicini (Von Neumann/Moore).
I gap spaziali agiscono come membrane cellulari che confinano la diffusione.

Differenza fondamentale con field_sense (fallito):
  field_sense:   ogni TEXT → tutti i NUMERIC (O(T*N), broadcast, nessun confine)
  reaz-diff:     ogni particella → solo primi vicini (O(N), confinato)

Test sulle 2 tabelle HVAC con ground truth.
Confronto con sense.py standard.
"""
from __future__ import annotations

import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

# --- Costanti ---
HVAC_DIR = Path('/mnt/dati/home/Progetti/dataset/hvac')
NUMERIC_RE = re.compile(
    r'^[(\-]?\d+([.,/x×]\d+)*[)%°]?$'
    r'|^R\d{3}'
    r'|^\d+[~]\d+'
    r'|^\d+[.,]\d+$'
)
UNIT_SET = {
    'kw', 'w', 'db', 'db(a)', 'dba', 'kg', 'mm', 'v', 'a', 'hz',
    'kpa', 'pa', 'kwh', 'l/h', 'm³/h', 'm3/h', 'rpm', 'l/s',
    'btu/h', 'kbtu/h', 'kcal/h', 'mpa', 'bar', '°c', 'l',
}


# ================================================================
# 1. Caricamento e tipizzazione base
# ================================================================

def load_words(name: str) -> list[dict]:
    """Carica parole dal JSON HVAC e tipizza con regex base."""
    path = HVAC_DIR / 'words' / f'{name}_words.json'
    raw = json.loads(path.read_text())

    particles = []
    for w in raw:
        text = w['text'].strip()
        if not text:
            continue
        x0, y0, x1, y1 = w['bbox']
        ptype = _typify_base(text)
        particles.append({
            'text': text[:80],
            'x': (x0 + x1) / 2,
            'y': (y0 + y1) / 2,
            'x0': x0, 'x1': x1,
            'y0': y0, 'y1': y1,
            'type': ptype,
            'size': 0,  # JSON non ha font info
        })
    return particles


def _typify_base(text: str) -> str:
    """Tipizzazione minimale: NUMERIC, UNIT, TEXT. Nessun domain."""
    t = text.strip()
    tl = t.lower().rstrip('.')
    if tl in UNIT_SET:
        return 'UNIT'
    cleaned = re.sub(r'\s', '', tl)
    if cleaned and re.match(r'^[\d.,/\-()x×°%~+:]+$', cleaned) and any(c.isdigit() for c in cleaned):
        return 'NUMERIC'
    if re.match(r'^R\d{3}', t):
        return 'NUMERIC'
    return 'TEXT'


# ================================================================
# 2. Raggruppamento in righe (replica da sense.py)
# ================================================================

def _estimate_row_spacing(particles: list[dict]) -> float:
    """Stima spaziatura verticale tra righe."""
    ys = sorted(set(round(p['y0'], 1) for p in particles))
    if len(ys) < 2:
        return 10.0
    gaps = [ys[i+1] - ys[i] for i in range(len(ys)-1)]
    gaps = [g for g in gaps if g > 1.0]
    return statistics.median(gaps) if gaps else 10.0


def group_into_rows(particles: list[dict],
                    y_tolerance: float | None = None) -> list[list[dict]]:
    """Raggruppa particelle in righe per prossimita' Y."""
    if not particles:
        return []
    if y_tolerance is None:
        row_spacing = _estimate_row_spacing(particles)
        y_tolerance = max(4.0, row_spacing * 0.5)

    rows: list[list[dict]] = []
    for p in sorted(particles, key=lambda p: p['y0']):
        placed = False
        for row in rows:
            row_y = sum(it['y0'] for it in row) / len(row)
            if abs(p['y0'] - row_y) < y_tolerance:
                row.append(p)
                placed = True
                break
        if not placed:
            rows.append([p])
    return rows


# ================================================================
# 3. Costruzione grafo di adiacenza (primo vicino)
# ================================================================

def build_adjacency(particles: list[dict],
                    rows: list[list[dict]]) -> dict[int, dict]:
    """Costruisce grafo di adiacenza: per ogni particella, i 4 primi vicini.

    Vicini:
      - left:  particella piu' vicina a sinistra nella stessa riga
      - right: particella piu' vicina a destra nella stessa riga
      - above: particella piu' vicina sopra nella stessa colonna (±30px)
      - below: particella piu' vicina sotto nella stessa colonna (±30px)

    Returns:
        Dict[id_particella → {left, right, above, below}] dove ogni valore
        e' l'indice della particella vicina o None.
    """
    # Mappa id(p) → indice per accesso rapido
    id_to_idx = {id(p): i for i, p in enumerate(particles)}

    # Indice riga per ogni particella
    p_to_row = {}
    for row_idx, row in enumerate(rows):
        for p in row:
            p_to_row[id(p)] = row_idx

    adj = {i: {'left': None, 'right': None, 'above': None, 'below': None}
           for i in range(len(particles))}

    # Vicini orizzontali (stessa riga)
    for row in rows:
        sorted_row = sorted(row, key=lambda p: p['x0'])
        for k in range(len(sorted_row)):
            idx = id_to_idx[id(sorted_row[k])]
            if k > 0:
                adj[idx]['left'] = id_to_idx[id(sorted_row[k-1])]
            if k < len(sorted_row) - 1:
                adj[idx]['right'] = id_to_idx[id(sorted_row[k+1])]

    # Vicini verticali (stessa colonna ±30px)
    col_tol = 30.0
    # Per ogni particella, cerca la piu' vicina sopra/sotto con X simile
    sorted_by_y = sorted(range(len(particles)), key=lambda i: particles[i]['y0'])

    for pos, idx in enumerate(sorted_by_y):
        p = particles[idx]

        # Cerca sopra: scorro all'indietro
        best_above = None
        best_above_dist = float('inf')
        for j in range(pos - 1, -1, -1):
            other_idx = sorted_by_y[j]
            other = particles[other_idx]
            dy = p['y0'] - other['y0']
            if dy > 100:  # troppo lontano, stop
                break
            if abs(p['x'] - other['x']) < col_tol and dy > 0:
                if dy < best_above_dist:
                    best_above_dist = dy
                    best_above = other_idx
        adj[idx]['above'] = best_above

        # Cerca sotto: scorro in avanti
        best_below = None
        best_below_dist = float('inf')
        for j in range(pos + 1, len(sorted_by_y)):
            other_idx = sorted_by_y[j]
            other = particles[other_idx]
            dy = other['y0'] - p['y0']
            if dy > 100:
                break
            if abs(p['x'] - other['x']) < col_tol and dy > 0:
                if dy < best_below_dist:
                    best_below_dist = dy
                    best_below = other_idx
        adj[idx]['below'] = best_below

    return adj


# ================================================================
# 4. REAZIONE-DIFFUSIONE
# ================================================================

def reaction_diffusion(particles: list[dict],
                       adj: dict[int, dict],
                       iterations: int = 3,
                       verbose: bool = False) -> list[dict]:
    """Promuove particelle TEXT via diffusione a primo vicino.

    Ogni particella TEXT mantiene probabilita' per 3 stati:
      p_MODEL, p_SPEC, p_TEXT

    Regole di reazione (ispettore locale):
      - Se vicino a destra e' NUMERIC → aumento p_SPEC (spec a sinistra dei numeri)
      - Se vicino sotto e' NUMERIC  → aumento p_MODEL (header sopra i numeri)
      - Se nessun NUMERIC vicino    → aumento p_TEXT

    Regole di diffusione (primo vicino):
      - Se vicino a sinistra e' diventato SPEC → io NON divento SPEC
        (inibizione laterale)
      - Se vicino sopra e' diventato MODEL → io NON divento MODEL
        (max 1 header per colonna)

    Il gap spaziale agisce come membrana: se non c'e' vicino,
    il segnale non si propaga.
    """
    n = len(particles)

    # Stato: solo TEXT partecipano alla diffusione
    # NUMERIC e UNIT sono fissi (gia' tipizzati)
    state = []
    for p in particles:
        if p['type'] == 'TEXT':
            state.append({'p_MODEL': 0.33, 'p_SPEC': 0.33, 'p_TEXT': 0.34})
        else:
            # Tipi fissi: probabilita' 1.0 sul proprio tipo
            state.append(None)

    for it in range(iterations):
        # Copia stato per aggiornamento sincrono
        new_state = [s.copy() if s else None for s in state]

        for idx in range(n):
            if state[idx] is None:
                continue  # non TEXT, skip

            s = state[idx]
            ns = new_state[idx]
            p = particles[idx]
            neighbors = adj[idx]

            # --- REAZIONE: guardo i miei vicini diretti ---

            # Reazione SPEC: se ho NUMERIC a destra → voglio diventare SPEC
            right_idx = neighbors['right']
            if right_idx is not None and particles[right_idx]['type'] == 'NUMERIC':
                ns['p_SPEC'] += 0.3

            # Reazione SPEC propagata: se il mio vicino destro e' TEXT
            # e il SUO vicino destro e' NUMERIC → segnale indiretto (piu' debole)
            if right_idx is not None and state[right_idx] is not None:
                rr_idx = adj[right_idx]['right']
                if rr_idx is not None and particles[rr_idx]['type'] == 'NUMERIC':
                    ns['p_SPEC'] += 0.1  # segnale piu' debole a 2 hop

            # Reazione MODEL: se ho NUMERIC sotto → voglio diventare MODEL
            below_idx = neighbors['below']
            if below_idx is not None and particles[below_idx]['type'] == 'NUMERIC':
                ns['p_MODEL'] += 0.3

            # Reazione MODEL propagata: se il mio vicino sotto e' TEXT
            # e il SUO vicino sotto e' NUMERIC → segnale indiretto
            if below_idx is not None and state[below_idx] is not None:
                bb_idx = adj[below_idx]['below']
                if bb_idx is not None and particles[bb_idx]['type'] == 'NUMERIC':
                    ns['p_MODEL'] += 0.1

            # Boost MODEL: se ho NUMERIC sotto-sotto (2 NUMERIC in colonna)
            # Questo significa una vera colonna, non un caso isolato
            if below_idx is not None and particles[below_idx]['type'] == 'NUMERIC':
                bb_idx = adj[below_idx]['below']
                if bb_idx is not None and particles[bb_idx]['type'] == 'NUMERIC':
                    ns['p_MODEL'] += 0.2  # colonna confermata

            # --- INIBIZIONE LATERALE (anti-doppia promozione) ---

            # Se il mio vicino sinistro e' gia' SPEC (o tendente SPEC),
            # io non devo diventare SPEC (due SPEC consecutive = errore)
            left_idx = neighbors['left']
            if left_idx is not None and state[left_idx] is not None:
                if state[left_idx]['p_SPEC'] > 0.5:
                    ns['p_SPEC'] *= 0.3  # forte inibizione

            # Se il mio vicino sopra e' gia' MODEL, io non devo diventare MODEL
            above_idx = neighbors['above']
            if above_idx is not None and state[above_idx] is not None:
                if state[above_idx]['p_MODEL'] > 0.5:
                    ns['p_MODEL'] *= 0.5  # inibizione verticale

            # --- NESSUN SEGNALE → resta TEXT ---
            has_numeric_neighbor = False
            for dir_key in ('left', 'right', 'above', 'below'):
                nidx = neighbors[dir_key]
                if nidx is not None and particles[nidx]['type'] == 'NUMERIC':
                    has_numeric_neighbor = True
                    break
            if not has_numeric_neighbor:
                ns['p_TEXT'] += 0.2

            # Normalizza
            total = ns['p_MODEL'] + ns['p_SPEC'] + ns['p_TEXT']
            if total > 0:
                ns['p_MODEL'] /= total
                ns['p_SPEC'] /= total
                ns['p_TEXT'] /= total

        state = new_state

        if verbose:
            # Conta stati dominanti
            counts = Counter()
            for idx in range(n):
                if state[idx] is None:
                    counts[particles[idx]['type']] += 1
                else:
                    dominant = max(state[idx], key=state[idx].get)
                    counts[dominant.replace('p_', '')] += 1
            print(f"  Iterazione {it+1}: {dict(counts)}")

    # --- COLLASSO: ogni particella assume il tipo con p massima ---
    promoted = {'MODEL': 0, 'SPEC_LABEL': 0}
    for idx in range(n):
        if state[idx] is None:
            continue
        s = state[idx]
        dominant = max(s, key=s.get)

        if dominant == 'p_MODEL' and s['p_MODEL'] > 0.4:
            particles[idx]['type'] = 'MODEL'
            particles[idx]['_sensed'] = 'reaction_diffusion'
            promoted['MODEL'] += 1
        elif dominant == 'p_SPEC' and s['p_SPEC'] > 0.4:
            particles[idx]['type'] = 'SPEC_LABEL'
            particles[idx]['_sensed'] = 'reaction_diffusion'
            promoted['SPEC_LABEL'] += 1
        # else: resta TEXT

    return particles


# ================================================================
# 5. Sensing standard (per confronto)
# ================================================================

def run_standard_sensing(particles: list[dict]) -> list[dict]:
    """Esegue sensing standard da morph.core.sense."""
    import copy
    ps = copy.deepcopy(particles)

    # Importa sense_page
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from morph.core.sense import sense_page

    result = sense_page(ps)
    return result['particles']


# ================================================================
# 6. Confronto
# ================================================================

def compare_results(original: list[dict],
                    sensed: list[dict],
                    diffused: list[dict],
                    name: str):
    """Confronta tipi assegnati da sense.py vs reazione-diffusione."""
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  Particelle totali: {len(original)}")

    # Conteggi per tipo
    orig_types = Counter(p['type'] for p in original)
    sense_types = Counter(p['type'] for p in sensed)
    diff_types = Counter(p['type'] for p in diffused)

    print(f"\n  {'Tipo':<15} {'Base':>8} {'Sense':>8} {'ReazDiff':>8}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8}")
    all_types = sorted(set(list(orig_types) + list(sense_types) + list(diff_types)))
    for t in all_types:
        print(f"  {t:<15} {orig_types.get(t, 0):>8} {sense_types.get(t, 0):>8} {diff_types.get(t, 0):>8}")

    # Concordanza sense vs diffusion (solo su particelle non-TEXT in almeno uno)
    agree = 0
    disagree = 0
    disagree_details = []
    for i in range(len(original)):
        st = sensed[i]['type']
        dt = diffused[i]['type']
        if st == dt:
            agree += 1
        else:
            if st != 'TEXT' or dt != 'TEXT':  # solo se almeno uno ha promosso
                disagree += 1
                if disagree <= 10:
                    disagree_details.append(
                        f"    [{i}] '{original[i]['text'][:25]:<25}' "
                        f"sense={st:<12} reaz-diff={dt:<12} "
                        f"pos=({original[i]['x0']:.0f}, {original[i]['y0']:.0f})"
                    )

    total_promoted_s = sum(1 for p in sensed if p['type'] not in ('TEXT', 'NUMERIC', 'UNIT'))
    total_promoted_d = sum(1 for p in diffused if p['type'] not in ('TEXT', 'NUMERIC', 'UNIT'))

    print(f"\n  Promozioni sense.py:     {total_promoted_s}")
    print(f"  Promozioni reaz-diff:    {total_promoted_d}")
    print(f"  Concordanza totale:      {agree}/{len(original)} ({100*agree/len(original):.1f}%)")
    print(f"  Disaccordi (promossi):   {disagree}")

    if disagree_details:
        print(f"\n  Prime {len(disagree_details)} discordanze:")
        for d in disagree_details:
            print(d)

    # Analisi qualitativa: le promozioni del reaz-diff hanno senso?
    print(f"\n  --- Promozioni reazione-diffusione ---")
    rd_promoted = [p for p in diffused if p.get('_sensed') == 'reaction_diffusion']
    for p in rd_promoted[:15]:
        print(f"    {p['type']:<12} '{p['text'][:30]:<30}' "
              f"pos=({p['x0']:.0f}, {p['y0']:.0f})")

    # Promozioni sense.py per confronto
    print(f"\n  --- Promozioni sense.py ---")
    s_promoted = [p for p in sensed if p.get('_sensed')]
    for p in s_promoted[:15]:
        print(f"    {p['type']:<12} '{p['text'][:30]:<30}' "
              f"pos=({p['x0']:.0f}, {p['y0']:.0f}) [{p.get('_sensed', '')}]")


# ================================================================
# MAIN
# ================================================================

def main():
    import copy

    tables = [
        'toshiba_minismms_p27',
        'hitachi_canalizzata_p24',
    ]

    for name in tables:
        # 1. Carica e tipizza base
        particles_base = load_words(name)

        # 2. Sensing standard (copia)
        particles_sense = run_standard_sensing(particles_base)

        # 3. Reazione-diffusione (copia)
        particles_rd = copy.deepcopy(particles_base)
        rows = group_into_rows(particles_rd)
        adj = build_adjacency(particles_rd, rows)

        print(f"\n--- Reazione-Diffusione su {name} ---")
        print(f"  Particelle: {len(particles_rd)}")
        print(f"  Righe: {len(rows)}")

        # Statistiche adiacenza
        n_links = sum(
            1 for idx in adj
            for d in ('left', 'right', 'above', 'below')
            if adj[idx][d] is not None
        )
        print(f"  Link adiacenza: {n_links} ({n_links/len(particles_rd):.1f} per particella)")

        particles_rd = reaction_diffusion(
            particles_rd, adj, iterations=3, verbose=True
        )

        # 4. Confronto
        compare_results(particles_base, particles_sense, particles_rd, name)


if __name__ == '__main__':
    main()
