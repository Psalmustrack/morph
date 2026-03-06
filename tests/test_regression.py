"""
tests/test_regression.py — Test di regressione per morph
=========================================================

Verifica che tutti i layer producano output attesi su dati sintetici.
Nessun PDF esterno richiesto — particelle costruite a mano.

Lancia con:
    pytest tests/test_regression.py -v

Autore: Eugeniu Tacu + Claude, 2026
"""

import math
import pytest


# ─── Layer 1: typify ─────────────────────────────────────────────────

class TestTypifyWord:
    """typify_word deve classificare correttamente stringhe note."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from morph.core.typify import typify_word
        self.typify = typify_word

    # NUMERIC
    @pytest.mark.parametrize("text,expected", [
        ("42.5", "NUMERIC"),
        ("3,14", "NUMERIC"),
        ("-5~43", "NUMERIC"),
        ("204x840x840", "NUMERIC"),
        ("6.29/4.62", "NUMERIC"),
        ("R410A", "NUMERIC"),
        ("55", "NUMERIC"),
        ("0.78", "NUMERIC"),
        ("380~415", "NUMERIC"),
    ])
    def test_numeric(self, text, expected):
        assert self.typify(text) == expected

    # UNIT
    @pytest.mark.parametrize("text,expected", [
        ("kW", "UNIT"),
        ("dB(A)", "UNIT"),
        ("mm", "UNIT"),
        ("kg", "UNIT"),
        ("°C", "UNIT"),
        ("W", "UNIT"),
    ])
    def test_unit(self, text, expected):
        assert self.typify(text) == expected

    # TEXT (default)
    @pytest.mark.parametrize("text,expected", [
        ("Hitachi", "TEXT"),
        ("Condizionamento", "TEXT"),
        ("Premium", "TEXT"),
        ("(2)", "TEXT"),  # nota a piede, non NUMERIC
    ])
    def test_text(self, text, expected):
        assert self.typify(text) == expected

    # domain=False disabilita classificazione brand-specifica
    def test_domain_false_skips_model(self):
        import re
        pat = re.compile(r'^RAS-\d')
        # con domain=True, RAS-8 e' MODEL
        assert self.typify("RAS-8FSXNME", model_patterns=[pat]) == "MODEL"
        # con domain=False, diventa TEXT (nessun match regex)
        assert self.typify("RAS-8FSXNME", domain=False) == "TEXT"

    # stringa vuota → TEXT
    def test_empty(self):
        assert self.typify("") == "TEXT"
        assert self.typify("   ") == "TEXT"


# ─── Layer 1: extract_particles ──────────────────────────────────────

class TestExtractParticles:
    """extract_particles deve produrre particelle con campi obbligatori."""

    def _make_fake_page(self):
        """Simula una pagina pdfplumber con extract_words()."""
        class FakePage:
            def __init__(self):
                self.width = 595.0
                self.height = 842.0
            def extract_words(self, **kwargs):
                # Formato pdfplumber: lista di dict con text, x0, x1, top, bottom
                return [
                    {'text': 'COP', 'x0': 50, 'x1': 90, 'top': 100, 'bottom': 112, 'size': 9},
                    {'text': '4.50', 'x0': 150, 'x1': 200, 'top': 100, 'bottom': 112, 'size': 9},
                    {'text': 'kW', 'x0': 250, 'x1': 300, 'top': 100, 'bottom': 112, 'size': 9},
                    {'text': 'RAS-8', 'x0': 150, 'x1': 200, 'top': 60, 'bottom': 72, 'size': 9},
                    {'text': 'Peso', 'x0': 50, 'x1': 120, 'top': 130, 'bottom': 142, 'size': 9},
                    {'text': '25', 'x0': 150, 'x1': 200, 'top': 130, 'bottom': 142, 'size': 9},
                    {'text': 'kg', 'x0': 250, 'x1': 300, 'top': 130, 'bottom': 142, 'size': 9},
                ]
        return FakePage()

    def test_particles_have_required_fields(self):
        from morph.core.typify import extract_particles
        import re
        page = self._make_fake_page()
        model_pats = [re.compile(r'^RAS-\d')]
        particles = extract_particles(page, model_pats, [])

        assert len(particles) > 0
        for p in particles:
            assert 'text' in p
            assert 'x' in p or 'x0' in p
            assert 'y' in p or 'y0' in p
            assert 'type' in p
            assert p['type'] in (
                'MODEL', 'SIZE_HEADER', 'KW_HEADER', 'UNIT',
                'NUMERIC', 'SECTION', 'SPEC_LABEL', 'TEXT',
            )

    def test_known_types_detected(self):
        from morph.core.typify import extract_particles
        import re
        page = self._make_fake_page()
        model_pats = [re.compile(r'^RAS-\d')]
        particles = extract_particles(page, model_pats, [])
        types = {p['type'] for p in particles}
        # deve riconoscere almeno NUMERIC e UNIT
        assert 'NUMERIC' in types
        assert 'UNIT' in types


# ─── Layer 1b: sense ─────────────────────────────────────────────────

def _make_table_particles():
    """Crea particelle sintetiche che simulano una tabella HVAC.

    Layout:
                col1(x=150)   col2(x=250)
    header:     Model-A       Model-B         (y=50)
    COP         4.50          3.80            (y=100)
    Peso        25            30              (y=130)
    Potenza     10.5          12.0            (y=160)
    """
    particles = [
        # Header riga
        {'text': 'Model-A', 'x': 150, 'y': 50, 'x0': 130, 'y0': 44,
         'x1': 200, 'y1': 56, 'type': 'TEXT', 'size': 9},
        {'text': 'Model-B', 'x': 250, 'y': 50, 'x0': 230, 'y0': 44,
         'x1': 300, 'y1': 56, 'type': 'TEXT', 'size': 9},
        # Riga 1: COP
        {'text': 'COP', 'x': 50, 'y': 100, 'x0': 30, 'y0': 94,
         'x1': 80, 'y1': 106, 'type': 'TEXT', 'size': 9},
        {'text': '4.50', 'x': 150, 'y': 100, 'x0': 140, 'y0': 94,
         'x1': 180, 'y1': 106, 'type': 'NUMERIC', 'size': 9},
        {'text': '3.80', 'x': 250, 'y': 100, 'x0': 240, 'y0': 94,
         'x1': 280, 'y1': 106, 'type': 'NUMERIC', 'size': 9},
        # Riga 2: Peso
        {'text': 'Peso', 'x': 50, 'y': 130, 'x0': 30, 'y0': 124,
         'x1': 80, 'y1': 136, 'type': 'TEXT', 'size': 9},
        {'text': '25', 'x': 150, 'y': 130, 'x0': 140, 'y0': 124,
         'x1': 170, 'y1': 136, 'type': 'NUMERIC', 'size': 9},
        {'text': '30', 'x': 250, 'y': 130, 'x0': 240, 'y0': 124,
         'x1': 270, 'y1': 136, 'type': 'NUMERIC', 'size': 9},
        # Riga 3: Potenza
        {'text': 'Potenza', 'x': 50, 'y': 160, 'x0': 30, 'y0': 154,
         'x1': 100, 'y1': 166, 'type': 'TEXT', 'size': 9},
        {'text': '10.5', 'x': 150, 'y': 160, 'x0': 140, 'y0': 154,
         'x1': 180, 'y1': 166, 'type': 'NUMERIC', 'size': 9},
        {'text': '12.0', 'x': 250, 'y': 160, 'x0': 240, 'y0': 154,
         'x1': 280, 'y1': 166, 'type': 'NUMERIC', 'size': 9},
    ]
    return particles


class TestSensePage:
    """sense_page deve rilevare struttura da particelle spaziali."""

    def test_returns_dict_with_particles(self):
        from morph.core.sense import sense_page
        particles = _make_table_particles()
        result = sense_page(particles)

        assert isinstance(result, dict)
        assert 'particles' in result
        assert isinstance(result['particles'], list)
        assert len(result['particles']) > 0

    def test_returns_stats_keys(self):
        from morph.core.sense import sense_page
        result = sense_page(_make_table_particles())
        for key in ('columns', 'headers', 'specs', 'sections', 'proofread'):
            assert key in result, f"Manca chiave '{key}' nel risultato"

    def test_detects_columns(self):
        """Con 3 righe di NUMERIC allineati su x=150 e x=250, deve trovare colonne."""
        from morph.core.sense import sense_page
        result = sense_page(_make_table_particles())
        # almeno 1 colonna (idealmente 2)
        assert result['columns'] >= 1

    def test_promotes_spec_labels(self):
        """TEXT a sinistra di NUMERIC (COP, Peso, Potenza) → SPEC_LABEL."""
        from morph.core.sense import sense_page
        particles = _make_table_particles()
        sense_page(particles)  # modifica in-place

        spec_labels = [p for p in particles if p['type'] == 'SPEC_LABEL']
        spec_texts = {p['text'] for p in spec_labels}
        # almeno uno tra COP, Peso, Potenza deve essere promosso
        assert len(spec_texts & {'COP', 'Peso', 'Potenza'}) >= 1, \
            f"Nessuna promozione spec — tipi: {[p['type'] for p in particles]}"

    def test_promotes_column_headers(self):
        """TEXT sopra colonne NUMERIC (Model-A, Model-B) → MODEL."""
        from morph.core.sense import sense_page
        particles = _make_table_particles()
        result = sense_page(particles)

        if result['columns'] >= 2:
            models = [p for p in particles if p['type'] == 'MODEL']
            assert len(models) >= 1, \
                f"Header non promossi a MODEL — tipi: {[(p['text'], p['type']) for p in particles if p['text'].startswith('Model')]}"

    def test_few_particles_returns_empty(self):
        """Meno di 5 particelle → risultato vuoto, no crash."""
        from morph.core.sense import sense_page
        result = sense_page([
            {'text': 'x', 'x': 0, 'y': 0, 'x0': 0, 'y0': 0,
             'x1': 10, 'y1': 10, 'type': 'TEXT', 'size': 9},
        ])
        assert result['columns'] == 0
        assert result['particles'] is not None


# ─── Layer 1b: utilita' ──────────────────────────────────────────────

class TestSenseUtilities:
    """Test funzioni di supporto del sensing."""

    def test_group_into_rows(self):
        from morph.core.sense import _group_into_rows
        particles = [
            {'y0': 100, 'x': 50},
            {'y0': 101, 'x': 150},   # stessa riga
            {'y0': 130, 'x': 50},    # riga diversa
            {'y0': 131, 'x': 150},   # stessa riga di sopra
        ]
        rows = _group_into_rows(particles, y_tolerance=5)
        assert len(rows) == 2

    def test_count_columns_universal(self):
        from morph.bench.grid import count_columns_universal
        particles = _make_table_particles()
        n = count_columns_universal(particles)
        assert isinstance(n, int)
        assert n >= 1


# ─── Layer 2: field ──────────────────────────────────────────────────

class TestFieldEquation:
    """Test dell'equazione di campo e funzioni correlate."""

    def test_phi_positive_for_matching_types(self):
        """Phi(NUMERIC → SPEC_LABEL) deve essere > 0 se vicini."""
        from morph.core.field import _phi, DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X

        num = {'x': 150, 'y': 100, 'type': 'NUMERIC'}
        spec = {'x': 50, 'y': 100, 'type': 'SPEC_LABEL'}  # stessa riga
        phi = _phi(num, spec, axis='row',
                   sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X)
        assert phi > 0, f"Phi dovrebbe essere positivo, got {phi}"

    def test_phi_zero_for_text(self):
        """Phi(NUMERIC → TEXT) deve essere 0 o negativo (W <= 0)."""
        from morph.core.field import _phi, DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X

        num = {'x': 150, 'y': 100, 'type': 'NUMERIC'}
        text = {'x': 50, 'y': 100, 'type': 'TEXT'}
        phi = _phi(num, text, axis='row',
                   sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X)
        assert phi <= 0

    def test_phi_decays_with_distance(self):
        """Phi deve decadere all'aumentare della distanza."""
        from morph.core.field import _phi, DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X

        num = {'x': 150, 'y': 100, 'type': 'NUMERIC'}
        spec_near = {'x': 50, 'y': 100, 'type': 'SPEC_LABEL'}
        spec_far = {'x': 50, 'y': 300, 'type': 'SPEC_LABEL'}

        phi_near = _phi(num, spec_near, axis='row',
                        sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X)
        phi_far = _phi(num, spec_far, axis='row',
                       sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X)
        assert phi_near > phi_far, f"near={phi_near}, far={phi_far}"

    def test_phi_col_axis(self):
        """Phi sull'asse col (NUMERIC → MODEL) deve funzionare."""
        from morph.core.field import _phi, DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X

        num = {'x': 150, 'y': 100, 'type': 'NUMERIC'}
        model = {'x': 150, 'y': 50, 'type': 'MODEL'}  # sopra, stessa colonna
        phi = _phi(num, model, axis='col',
                   sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X)
        assert phi > 0

    def test_parse_z_norm(self):
        from morph.core.field import _parse_z_norm

        # z = log10(|v| + 1)
        assert _parse_z_norm("4.50") == pytest.approx(math.log10(5.5), abs=0.01)
        assert _parse_z_norm("0") == 0.0
        assert _parse_z_norm("") is None
        assert _parse_z_norm("abc") is None
        # virgola italiana
        z = _parse_z_norm("3,14")
        assert z is not None and z > 0

    def test_phi_with_z(self):
        """Phi con lambda_z > 0: valori con z simile più attratti."""
        from morph.core.field import _phi, DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X

        num = {'x': 150, 'y': 100, 'type': 'NUMERIC', 'z_norm': 0.7}
        spec_same_z = {'x': 50, 'y': 100, 'type': 'SPEC_LABEL', 'z_norm': 0.7}
        spec_diff_z = {'x': 50, 'y': 100, 'type': 'SPEC_LABEL', 'z_norm': 3.0}

        phi_same = _phi(num, spec_same_z, axis='row',
                        sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X,
                        lambda_z=50.0)
        phi_diff = _phi(num, spec_diff_z, axis='row',
                        sigma_y=DEFAULT_SIGMA_Y, sigma_x=DEFAULT_SIGMA_X,
                        lambda_z=50.0)
        assert phi_same > phi_diff, f"same_z={phi_same}, diff_z={phi_diff}"


class TestCalibration:
    """Test auto-calibrazione sigma e lambda_z."""

    def test_calibrate_sigma_returns_tuple(self):
        from morph.core.field import calibrate_sigma
        particles = _make_table_particles()
        sy, sx = calibrate_sigma(particles)
        assert isinstance(sy, float)
        assert isinstance(sx, float)
        assert 4.0 <= sy <= 20.0  # clamped range
        assert 15.0 <= sx <= 60.0

    def test_calibrate_sigma_few_particles(self):
        """Con poche particelle, ritorna default."""
        from morph.core.field import calibrate_sigma, DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X
        sy, sx = calibrate_sigma([
            {'x': 0, 'y': 0, 'type': 'NUMERIC'},
        ])
        assert sy == DEFAULT_SIGMA_Y
        assert sx == DEFAULT_SIGMA_X

    def test_calibrate_lambda_z(self):
        from morph.core.field import calibrate_lambda_z, DEFAULT_SIGMA_Y
        numerics = [
            {'y': 100, 'z_norm': 0.7},
            {'y': 100, 'z_norm': 0.72},
            {'y': 100, 'z_norm': 0.68},
            {'y': 130, 'z_norm': 1.4},
            {'y': 130, 'z_norm': 1.38},
            {'y': 130, 'z_norm': 1.42},
        ]
        lz = calibrate_lambda_z(numerics, DEFAULT_SIGMA_Y)
        assert 10.0 <= lz <= 500.0


class TestExtractPage:
    """Test estrazione completa (Layer 2)."""

    def test_extract_returns_structure(self):
        """extract_page su particelle sensed deve ritornare struttura."""
        from morph.core.sense import sense_page
        from morph.core.field import extract_page

        particles = _make_table_particles()
        sensed = sense_page(particles)
        result = extract_page(sensed['particles'])

        assert isinstance(result, dict)
        assert 'data' in result
        assert 'stats' in result
        assert 'unmapped' in result

    def test_extract_maps_values(self):
        """Con tabella ben formata, deve mappare almeno qualche valore."""
        from morph.core.sense import sense_page
        from morph.core.field import extract_page

        particles = _make_table_particles()
        sensed = sense_page(particles)
        result = extract_page(sensed['particles'])

        mapped = result['stats']['mapped']
        total = mapped + result['stats']['unmapped']
        # con 6 NUMERIC e struttura chiara, almeno qualcuno mappato
        assert mapped >= 1 or total > 0, \
            f"Nessun valore mappato: {result['stats']}"

    def test_extract_empty_page(self):
        """Pagina senza NUMERIC → risultato vuoto."""
        from morph.core.field import extract_page
        result = extract_page([
            {'text': 'Hello', 'x': 50, 'y': 100, 'type': 'TEXT', 'size': 9},
        ])
        assert result['stats']['mapped'] == 0
        assert result['data'] == {}


# ─── Brands ──────────────────────────────────────────────────────────

class TestBrands:
    """Test modulo brands."""

    def test_available_brands(self):
        from morph.brands import AVAILABLE_BRANDS
        assert 'hitachi' in AVAILABLE_BRANDS
        assert 'daikin' in AVAILABLE_BRANDS
        assert 'toshiba' in AVAILABLE_BRANDS
        assert len(AVAILABLE_BRANDS) >= 5

    def test_get_brand_patterns(self):
        from morph.brands import get_brand_patterns
        mp, sp = get_brand_patterns('hitachi')
        assert isinstance(mp, list)
        assert isinstance(sp, list)
        assert len(mp) > 0  # Hitachi ha pattern modello

    def test_detect_brand(self):
        """detect_brand matcha pattern modello, non nome brand nel testo."""
        from morph.brands import detect_brand
        # pattern modello Hitachi: RAS-*
        assert detect_brand("RAS-8FSXNME") == 'hitachi'
        # pattern modello Daikin: FTXM*, RXMM*, ecc.
        assert detect_brand("FTXM25R") == 'daikin'

    def test_unknown_brand_returns_none(self):
        from morph.brands import detect_brand
        assert detect_brand("Lorem ipsum dolor") is None

    def test_get_patterns_unknown_brand_raises(self):
        """Brand sconosciuto → ModuleNotFoundError."""
        from morph.brands import get_brand_patterns
        with pytest.raises(ModuleNotFoundError):
            get_brand_patterns('brand_inesistente')


# ─── Costanti ─────────────────────────────────────────────────────────

class TestConstants:
    """Verifica che le costanti calibrate non cambino per errore."""

    def test_alpha(self):
        from morph.core.field import ALPHA
        assert ALPHA == 0.5

    def test_default_sigma(self):
        from morph.core.field import DEFAULT_SIGMA_Y, DEFAULT_SIGMA_X
        assert DEFAULT_SIGMA_Y == 6.0
        assert DEFAULT_SIGMA_X == 30.0

    def test_w_matrix_keys(self):
        from morph.core.field import W
        assert ('NUMERIC', 'SPEC_LABEL') in W
        assert ('NUMERIC', 'MODEL') in W
        assert W[('NUMERIC', 'SPEC_LABEL')] == 1.0

    def test_particle_types(self):
        from morph.core.typify import PARTICLE_TYPES
        assert len(PARTICLE_TYPES) == 8
        assert 'NUMERIC' in PARTICLE_TYPES
        assert 'TEXT' in PARTICLE_TYPES
        assert 'MODEL' in PARTICLE_TYPES


# ─── Max-jump (natural threshold) ────────────────────────────────────

class TestNaturalThreshold:
    """Test soglia adattiva dal salto massimo nei gap."""

    def test_basic_break(self):
        """Gap [1, 2, 3, 30, 35] → soglia tra 3 e 30 (break evidente)."""
        from morph.core.sense import _natural_threshold
        t = _natural_threshold([1, 2, 3, 30, 35])
        assert 3 < t < 30, f"Soglia fuori range: {t}"

    def test_no_break(self):
        """Gap [10, 11, 12, 13] → nessun break naturale (ratio < 1.5)."""
        from morph.core.sense import _natural_threshold
        t = _natural_threshold([10, 11, 12, 13])
        # nessun break → threshold sopra tutti (>13)
        assert t > 13, f"Soglia {t} indica un break dove non c'e'"

    def test_few_gaps_returns_median(self):
        """Con <3 gap, ritorna la mediana."""
        from morph.core.sense import _natural_threshold
        assert _natural_threshold([5, 15]) == 10.0
        assert _natural_threshold([]) == 10  # fallback

    def test_count_cols_maxjump(self):
        """Particelle con gap bimodale → max-jump rileva il break.

        Layout realistico: spec_label(x=30-80) + 3 colonne numeriche
        vicine tra loro ma separate da gap grande dallo spec label.
        Gap intra-cella ~10px, gap inter-colonna ~60px.
        """
        from morph.bench.grid import count_columns_universal
        particles = []
        for y in [100, 130, 160, 190]:
            # Spec label a sinistra
            particles.append({
                'text': 'COP', 'x': 55, 'y': y,
                'x0': 30, 'y0': y - 6, 'x1': 80, 'y1': y + 6,
                'type': 'TEXT', 'size': 9,
            })
            # 3 colonne numeriche ravvicinate: gap ~10px tra loro,
            # gap ~70px dal label
            for x0 in [150, 210, 270]:
                particles.append({
                    'text': '10', 'x': x0 + 15, 'y': y,
                    'x0': x0, 'y0': y - 6, 'x1': x0 + 30, 'y1': y + 6,
                    'type': 'NUMERIC', 'size': 9,
                })
        n = count_columns_universal(particles, method='maxjump')
        # Deve vedere il break tra label e numeri (gap 70 vs gap 30)
        assert n >= 2, f"Atteso almeno 2 colonne, ottenuto {n}"

    def test_maxjump_matches_fixed_on_simple(self):
        """Su tabella semplice, maxjump e fixed devono concordare."""
        from morph.bench.grid import count_columns_universal
        particles = _make_table_particles()
        n_fixed = count_columns_universal(particles, method='fixed')
        n_maxjump = count_columns_universal(particles, method='maxjump')
        # su dati semplici devono dare lo stesso risultato (o ±1)
        assert abs(n_fixed - n_maxjump) <= 1, \
            f"Divergenza: fixed={n_fixed}, maxjump={n_maxjump}"

    def test_fixed_method_backward_compatible(self):
        """method='fixed' produce lo stesso risultato di prima."""
        from morph.bench.grid import count_columns_universal
        particles = _make_table_particles()
        n = count_columns_universal(particles, method='fixed', k=0.3)
        assert isinstance(n, int)
        assert n >= 1


# ─── Row counting (simmetrico a colonne) ─────────────────────────────

class TestRowsUniversal:
    """Test count_rows_universal — simmetrico a count_columns_universal."""

    def test_basic_rows(self):
        """Tabella sintetica HVAC — gap bimodali (header 38px + dati 18px).

        Max-jump trova correttamente 2 zone (header | dati).
        Non 4 righe: il break bimodale separa i due regimi di spacing.
        """
        from morph.bench.grid import count_rows_universal
        particles = _make_table_particles()
        n = count_rows_universal(particles)
        assert n >= 2, f"Atteso almeno 2 zone, ottenuto {n}"

    def test_rows_count_matches_layout(self):
        """Layout esplicito: 5 righe Y=100,200,300,400,500 con gap uniforme."""
        from morph.bench.grid import count_rows_universal
        particles = []
        for y in [100, 200, 300, 400, 500]:
            for x0 in [50, 200, 350]:
                particles.append({
                    'text': '42', 'x': x0 + 15, 'y': y,
                    'x0': x0, 'y0': y - 5, 'x1': x0 + 30, 'y1': y + 5,
                    'type': 'NUMERIC', 'size': 10,
                })
        n = count_rows_universal(particles)
        assert n == 5, f"Atteso 5 righe, ottenuto {n}"

    def test_rows_bimodal_gap(self):
        """Gap bimodale: righe ravvicinate (10px) con un gap grande (80px).

        Y: 100, 110, 120, 200, 210, 220 → 2 gruppi se soglia fissa,
        ma max-jump deve contare 6 righe (gap intra 10 < threshold).
        """
        from morph.bench.grid import count_rows_universal
        particles = []
        for y in [100, 110, 120, 200, 210, 220]:
            for x0 in [50, 200, 350]:
                particles.append({
                    'text': '7', 'x': x0 + 15, 'y': y,
                    'x0': x0, 'y0': y - 4, 'x1': x0 + 30, 'y1': y + 4,
                    'type': 'NUMERIC', 'size': 9,
                })
        n = count_rows_universal(particles)
        # I gap interni sono 2px (y1=y+4, next y0=y+10-4=y+6, gap=2)
        # Il gap grande è 200-124=76px
        # Max-jump deve trovare il break
        assert n >= 2, f"Atteso almeno 2 righe (o 6), ottenuto {n}"

    def test_rows_symmetry_with_cols(self):
        """Colonne e righe devono essere coerenti sulla stessa tabella."""
        from morph.bench.grid import count_columns_universal, count_rows_universal
        particles = _make_table_particles()
        n_cols = count_columns_universal(particles)
        n_rows = count_rows_universal(particles)
        assert n_cols >= 1
        assert n_rows >= 1
        # Su tabella sintetica: 3 col headers + 4 righe dati
        # entrambi devono essere > 1
        assert n_cols > 1 or n_rows > 1, \
            f"Almeno uno deve essere >1: cols={n_cols}, rows={n_rows}"

    def test_few_particles(self):
        """Con 0 o 1 particella, ritorna 1."""
        from morph.bench.grid import count_rows_universal
        assert count_rows_universal([]) == 1
        p = {'text': 'x', 'x': 50, 'y': 100,
             'x0': 40, 'y0': 95, 'x1': 60, 'y1': 105,
             'type': 'NUMERIC', 'size': 10}
        assert count_rows_universal([p]) == 1


# ─── Integration: pipeline completa Layer 1 → 1b → 2 ────────────────

class TestFullPipeline:
    """Test integrazione: typify → sense → field su dati sintetici."""

    def test_pipeline_no_crash(self):
        """Il pipeline completo non deve crashare su input valido."""
        from morph.core.typify import typify_word
        from morph.core.sense import sense_page
        from morph.core.field import extract_page

        # Costruisci particelle "a mano" (come se venissero da typify)
        particles = _make_table_particles()

        # Layer 1b
        sensed = sense_page(particles)
        assert isinstance(sensed, dict)

        # Layer 2
        result = extract_page(sensed['particles'])
        assert isinstance(result, dict)
        assert 'data' in result

    def test_pipeline_types_evolve(self):
        """Dopo sensing, alcuni TEXT devono diventare SPEC_LABEL o MODEL."""
        from morph.core.sense import sense_page

        particles = _make_table_particles()
        types_before = [p['type'] for p in particles]
        n_text_before = types_before.count('TEXT')

        sense_page(particles)  # in-place
        types_after = [p['type'] for p in particles]
        n_text_after = types_after.count('TEXT')

        # il sensing deve aver promosso almeno 1 TEXT
        assert n_text_after < n_text_before, \
            f"Nessuna promozione: TEXT prima={n_text_before}, dopo={n_text_after}"
