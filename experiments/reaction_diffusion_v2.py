"""Reazione-Diffusione v2 — Gierer-Meinhardt computazionale.

Differenze da v1:
  1. INIBIZIONE VERTICALE per MODEL: particelle nella stessa banda X
     competono. La piu' forte (piu' NUMERIC sotto) sopprime le altre.
     I 124 MODEL falsi devono collassare alla decina reale.

  2. ATTIVAZIONE SPEC con BIAS DI FRONTIERA: il segnale del NUMERIC
     viaggia verso sinistra e si accumula contro la "parete" (particella
     senza niente alla sua sinistra). Come molecole contro la membrana.

  3. MAX-JUMP come MEMBRANA: _natural_threshold definisce il raggio
     dell'inibitore. Il gap spaziale e' la membrana cellulare.

Modello biologico: Gierer-Meinhardt (1972), estensione di Turing (1952).
  - Attivatore: segnale NUMERIC (corto raggio, si propaga ai vicini)
  - Inibitore: competizione locale (lungo raggio dentro la banda)
  - Membrana: gap spaziale (max-jump)
"""
from __future__ import annotations

import copy
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
# 1. Caricamento e tipizzazione base (identico a v1)
# ================================================================

def load_words(name: str) -> list[dict]:
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
            'size': 0,
        })
    return particles


def _typify_base(text: str) -> str:
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
# 2. Raggruppamento in righe e colonne
# ================================================================

def _estimate_row_spacing(particles: list[dict]) -> float:
    ys = sorted(set(round(p['y0'], 1) for p in particles))
    if len(ys) < 2:
        return 10.0
    gaps = [ys[i+1] - ys[i] for i in range(len(ys)-1)]
    gaps = [g for g in gaps if g > 1.0]
    return statistics.median(gaps) if gaps else 10.0


def group_into_rows(particles: list[dict],
                    y_tolerance: float | None = None) -> list[list[dict]]:
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


def _natural_threshold(gaps: list[float]) -> float:
    """Max-jump: la membrana emerge dalla distribuzione dei gap."""
    if len(gaps) < 3:
        return statistics.median(gaps) if gaps else 10
    sorted_gaps = sorted(gaps)
    best_ratio = 1.0
    best_idx = 0
    for i in range(len(sorted_gaps) - 1):
        if sorted_gaps[i] > 0:
            ratio = sorted_gaps[i + 1] / sorted_gaps[i]
            if ratio > best_ratio:
                best_ratio = ratio
                best_idx = i
    if best_ratio < 1.5:
        return sorted_gaps[-1] + 1  # nessun confine naturale
    return (sorted_gaps[best_idx] + sorted_gaps[best_idx + 1]) / 2


# ================================================================
# 3. Costruzione grafo di adiacenza (primo vicino)
# ================================================================

def build_adjacency(particles: list[dict],
                    rows: list[list[dict]]) -> dict[int, dict]:
    """Grafo a primo vicino: left, right, above, below per ogni particella."""
    id_to_idx = {id(p): i for i, p in enumerate(particles)}
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

    # Vicini verticali (colonna ±30px)
    col_tol = 30.0
    sorted_by_y = sorted(range(len(particles)), key=lambda i: particles[i]['y0'])

    for pos, idx in enumerate(sorted_by_y):
        p = particles[idx]
        # Sopra
        best_above, best_dist = None, float('inf')
        for j in range(pos - 1, -1, -1):
            other_idx = sorted_by_y[j]
            other = particles[other_idx]
            dy = p['y0'] - other['y0']
            if dy > 100:
                break
            if abs(p['x'] - other['x']) < col_tol and dy > 0 and dy < best_dist:
                best_dist = dy
                best_above = other_idx
        adj[idx]['above'] = best_above

        # Sotto
        best_below, best_dist = None, float('inf')
        for j in range(pos + 1, len(sorted_by_y)):
            other_idx = sorted_by_y[j]
            other = particles[other_idx]
            dy = other['y0'] - p['y0']
            if dy > 100:
                break
            if abs(p['x'] - other['x']) < col_tol and dy > 0 and dy < best_dist:
                best_dist = dy
                best_below = other_idx
        adj[idx]['below'] = best_below

    return adj


# ================================================================
# 4. REAZIONE-DIFFUSIONE v2 (Gierer-Meinhardt)
# ================================================================

def reaction_diffusion_v2(particles: list[dict],
                          adj: dict[int, dict],
                          rows: list[list[dict]],
                          iterations: int = 3,
                          verbose: bool = False) -> list[dict]:
    """Promozione tipi via attivatore-inibitore a primo vicino.

    v2 rispetto a v1:
      1. Attivazione MODEL pesata: conta QUANTI numeric hai sotto
         (catena verticale). "6,9kW" con 10 NUMERIC sotto batte "-" con 1.
      2. Inibizione verticale: particelle nella stessa banda X competono.
         La piu' forte sopprime le altre (lateral inhibition colonnare).
      3. Attivazione SPEC con bias frontiera: il segnale del NUMERIC
         si accumula contro il bordo sinistro (parete cellulare).
      4. Max-jump come raggio dell'inibitore.
    """
    n = len(particles)
    id_to_idx = {id(p): i for i, p in enumerate(particles)}

    # Pre-calcolo: per ogni particella, conta NUMERIC sotto (catena)
    numeric_below_count = [0] * n
    for idx in range(n):
        count = 0
        cur = adj[idx].get('below')
        visited = set()
        while cur is not None and cur not in visited:
            visited.add(cur)
            if particles[cur]['type'] == 'NUMERIC':
                count += 1
                cur = adj[cur].get('below')
            else:
                break
        numeric_below_count[idx] = count

    # Pre-calcolo: per ogni particella, ha qualcosa a sinistra?
    has_left = [adj[i]['left'] is not None for i in range(n)]

    # Pre-calcolo: col_tolerance dalla distribuzione X dei gap
    all_x_gaps = []
    for row in rows:
        sr = sorted(row, key=lambda p: p['x0'])
        for k in range(len(sr) - 1):
            gap = sr[k+1]['x0'] - sr[k]['x1']
            if gap > 0:
                all_x_gaps.append(gap)
    col_tolerance = _natural_threshold(all_x_gaps) if all_x_gaps else 30.0

    if verbose:
        print(f"  Col tolerance (max-jump membrana): {col_tolerance:.1f}px")
        print(f"  Gap X: min={min(all_x_gaps):.1f} max={max(all_x_gaps):.1f} "
              f"median={statistics.median(all_x_gaps):.1f}" if all_x_gaps else "  No gaps")

    # Stato iniziale
    state = []
    for p in particles:
        if p['type'] == 'TEXT':
            state.append({'p_MODEL': 0.33, 'p_SPEC': 0.33, 'p_TEXT': 0.34})
        else:
            state.append(None)

    for it in range(iterations):
        new_state = [s.copy() if s else None for s in state]

        for idx in range(n):
            if state[idx] is None:
                continue

            ns = new_state[idx]
            p = particles[idx]
            neighbors = adj[idx]

            # ============================================
            # ATTIVAZIONE MODEL (segnale verticale)
            # ============================================
            # Forza proporzionale al numero di NUMERIC sotto (catena)
            n_below = numeric_below_count[idx]
            if n_below >= 3:
                ns['p_MODEL'] += 0.5   # colonna forte: 3+ numeri
            elif n_below >= 1:
                ns['p_MODEL'] += 0.2   # colonna debole: 1-2 numeri
            # Nessun NUMERIC sotto → nessuna attivazione MODEL

            # ============================================
            # INIBIZIONE VERTICALE per MODEL
            # (Gierer-Meinhardt: inibitore a raggio piu' ampio)
            # ============================================
            # Se un vicino nella stessa banda X ha p_MODEL piu' alto,
            # io vengo soppresso. L'inibitore agisce nella banda verticale.
            above_idx = neighbors['above']
            if above_idx is not None and state[above_idx] is not None:
                if abs(particles[above_idx]['x'] - p['x']) < col_tolerance:
                    if state[above_idx]['p_MODEL'] > state[idx]['p_MODEL']:
                        ns['p_MODEL'] *= 0.3  # forte soppressione

            below_idx = neighbors['below']
            if below_idx is not None and state[below_idx] is not None:
                if abs(particles[below_idx]['x'] - p['x']) < col_tolerance:
                    if state[below_idx]['p_MODEL'] > state[idx]['p_MODEL']:
                        ns['p_MODEL'] *= 0.3

            # ============================================
            # ATTIVAZIONE SPEC (segnale orizzontale con bias frontiera)
            # ============================================
            # Il NUMERIC a destra attiva la SPEC.
            # Peso: 1/(1+dx) — decadimento con distanza.
            # BIAS FRONTIERA: se non ho niente a sinistra (parete),
            # il segnale si accumula (x1.5).
            right_idx = neighbors['right']
            if right_idx is not None and particles[right_idx]['type'] == 'NUMERIC':
                dx = max(1, particles[right_idx]['x0'] - p['x1'])
                activation = 1.0 / (1.0 + dx / 50.0)  # normalizzato
                # Bias frontiera: se sono al bordo sinistro → boost
                if not has_left[idx]:
                    activation *= 1.5  # parete cellulare
                ns['p_SPEC'] += activation

            # Propagazione a 2 hop: se il mio vicino destro e' TEXT
            # e il suo vicino destro e' NUMERIC → segnale indiretto
            if right_idx is not None and state[right_idx] is not None:
                rr_idx = adj[right_idx]['right']
                if rr_idx is not None and particles[rr_idx]['type'] == 'NUMERIC':
                    dx = max(1, particles[rr_idx]['x0'] - p['x1'])
                    activation = 0.5 / (1.0 + dx / 50.0)  # piu' debole
                    if not has_left[idx]:
                        activation *= 1.5
                    ns['p_SPEC'] += activation

            # ============================================
            # INIBIZIONE LATERALE per SPEC
            # (due SPEC consecutive = errore)
            # ============================================
            left_idx = neighbors['left']
            if left_idx is not None and state[left_idx] is not None:
                if state[left_idx]['p_SPEC'] > 0.5:
                    ns['p_SPEC'] *= 0.4  # inibizione

            # ============================================
            # ATTENUAZIONE: nessun NUMERIC vicino → resta TEXT
            # ============================================
            has_numeric = False
            for dir_key in ('left', 'right', 'above', 'below'):
                nidx = neighbors[dir_key]
                if nidx is not None and particles[nidx]['type'] == 'NUMERIC':
                    has_numeric = True
                    break
            # Estendi: NUMERIC a 2 hop
            if not has_numeric:
                for dir_key in ('left', 'right', 'above', 'below'):
                    nidx = neighbors[dir_key]
                    if nidx is not None:
                        for dir2 in ('left', 'right', 'above', 'below'):
                            nn = adj[nidx][dir2]
                            if nn is not None and particles[nn]['type'] == 'NUMERIC':
                                has_numeric = True
                                break
                    if has_numeric:
                        break

            if not has_numeric:
                ns['p_TEXT'] += 0.3

            # Normalizza
            total = ns['p_MODEL'] + ns['p_SPEC'] + ns['p_TEXT']
            if total > 0:
                ns['p_MODEL'] /= total
                ns['p_SPEC'] /= total
                ns['p_TEXT'] /= total

        state = new_state

        if verbose:
            counts = Counter()
            for idx in range(n):
                if state[idx] is None:
                    counts[particles[idx]['type']] += 1
                else:
                    dominant = max(state[idx], key=state[idx].get)
                    counts[dominant.replace('p_', '')] += 1
            print(f"  Iterazione {it+1}: {dict(counts)}")

    # ============================================
    # COLLASSO con soglie differenziate
    # ============================================
    promoted = {'MODEL': 0, 'SPEC_LABEL': 0}
    for idx in range(n):
        if state[idx] is None:
            continue
        s = state[idx]
        dominant = max(s, key=s.get)

        # MODEL: soglia piu' alta (0.45) + deve avere almeno 1 NUMERIC sotto
        if dominant == 'p_MODEL' and s['p_MODEL'] > 0.45 and numeric_below_count[idx] >= 1:
            particles[idx]['type'] = 'MODEL'
            particles[idx]['_sensed'] = 'rd_v2'
            particles[idx]['_n_below'] = numeric_below_count[idx]
            promoted['MODEL'] += 1

        # SPEC: soglia standard (0.4)
        elif dominant == 'p_SPEC' and s['p_SPEC'] > 0.4:
            particles[idx]['type'] = 'SPEC_LABEL'
            particles[idx]['_sensed'] = 'rd_v2'
            promoted['SPEC_LABEL'] += 1

    return particles


# ================================================================
# 5. Sensing standard (per confronto)
# ================================================================

def run_standard_sensing(particles: list[dict]) -> list[dict]:
    ps = copy.deepcopy(particles)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from morph.core.sense import sense_page
    result = sense_page(ps)
    return result['particles']


# ================================================================
# 6. Confronto dettagliato
# ================================================================

def compare_results(original, sensed, diffused, name):
    print(f"\n{'='*65}")
    print(f"  {name}")
    print(f"{'='*65}")
    print(f"  Particelle totali: {len(original)}")

    orig_types = Counter(p['type'] for p in original)
    sense_types = Counter(p['type'] for p in sensed)
    diff_types = Counter(p['type'] for p in diffused)

    print(f"\n  {'Tipo':<15} {'Base':>8} {'Sense':>8} {'RD_v2':>8} {'Delta':>8}")
    print(f"  {'-'*15} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    all_types = sorted(set(list(orig_types) + list(sense_types) + list(diff_types)))
    for t in all_types:
        s = sense_types.get(t, 0)
        d = diff_types.get(t, 0)
        delta = d - s
        sign = '+' if delta > 0 else ''
        print(f"  {t:<15} {orig_types.get(t, 0):>8} {s:>8} {d:>8} {sign}{delta:>7}")

    # Concordanza
    agree, disagree = 0, 0
    disagree_details = []
    for i in range(len(original)):
        st, dt = sensed[i]['type'], diffused[i]['type']
        if st == dt:
            agree += 1
        elif st != 'TEXT' or dt != 'TEXT':
            disagree += 1
            if disagree <= 15:
                disagree_details.append(
                    f"    [{i:3d}] '{original[i]['text'][:25]:<25}' "
                    f"sense={st:<12} rd_v2={dt:<12} "
                    f"pos=({original[i]['x0']:.0f}, {original[i]['y0']:.0f})"
                )

    total_s = sum(1 for p in sensed if p['type'] not in ('TEXT', 'NUMERIC', 'UNIT'))
    total_d = sum(1 for p in diffused if p['type'] not in ('TEXT', 'NUMERIC', 'UNIT'))

    print(f"\n  Promozioni sense.py:     {total_s}")
    print(f"  Promozioni RD v2:        {total_d}")
    print(f"  Concordanza:             {agree}/{len(original)} ({100*agree/len(original):.1f}%)")
    print(f"  Disaccordi (promossi):   {disagree}")

    if disagree_details:
        print(f"\n  Discordanze:")
        for d in disagree_details:
            print(d)

    # Promozioni RD v2
    print(f"\n  --- MODEL promossi da RD v2 ---")
    models = [p for p in diffused if p.get('_sensed') == 'rd_v2' and p['type'] == 'MODEL']
    for p in models[:20]:
        n_below = p.get('_n_below', '?')
        print(f"    '{p['text'][:35]:<35}' pos=({p['x0']:.0f}, {p['y0']:.0f})  "
              f"NUMERIC sotto: {n_below}")

    print(f"\n  --- SPEC_LABEL promossi da RD v2 ---")
    specs = [p for p in diffused if p.get('_sensed') == 'rd_v2' and p['type'] == 'SPEC_LABEL']
    for p in specs[:20]:
        left = '(frontiera)' if not any(
            q['x1'] < p['x0'] and abs(q['y0'] - p['y0']) < 5
            for q in diffused if q is not p
        ) else ''
        print(f"    '{p['text'][:35]:<35}' pos=({p['x0']:.0f}, {p['y0']:.0f})  {left}")

    # Confronto diretto MODEL: sense vs rd_v2
    print(f"\n  --- Confronto MODEL ---")
    sense_models = {p['text'] for p in sensed if p['type'] == 'MODEL'}
    rd_models = {p['text'] for p in diffused if p['type'] == 'MODEL'}
    print(f"    Sense: {sorted(sense_models)}")
    print(f"    RD v2: {sorted(rd_models)}")
    print(f"    Solo in sense: {sorted(sense_models - rd_models)}")
    print(f"    Solo in RD v2: {sorted(rd_models - sense_models)}")


# ================================================================
# MAIN
# ================================================================

def main():
    tables = [
        'toshiba_minismms_p27',
        'hitachi_canalizzata_p24',
    ]

    for name in tables:
        particles_base = load_words(name)
        particles_sense = run_standard_sensing(particles_base)

        particles_rd = copy.deepcopy(particles_base)
        rows = group_into_rows(particles_rd)
        adj = build_adjacency(particles_rd, rows)

        print(f"\n{'#'*65}")
        print(f"# Reazione-Diffusione v2 su {name}")
        print(f"{'#'*65}")
        print(f"  Particelle: {len(particles_rd)}, Righe: {len(rows)}")

        particles_rd = reaction_diffusion_v2(
            particles_rd, adj, rows, iterations=3, verbose=True
        )

        compare_results(particles_base, particles_sense, particles_rd, name)


if __name__ == '__main__':
    main()
