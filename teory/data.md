ORDINE DI ATTACCO — Cascata di apprendimento
═══════════════════════════════════════════════════════════════

STEP 1: CORD (ricevute)
  Probabilità successo: 90%
  Perché primo: una ricevuta È una tabella verticale
    prodotto → prezzo = SPEC → NUMERIC
    Il campo sa già farlo. Funziona quasi out-of-the-box.
  Sfida nuova: struttura VERTICALE (lista), non griglia
  Cosa impari: se il max-jump trova confini tra righe di scontrino
    → hai la detection di LISTE, non solo tabelle
  Aiuta il prossimo: le liste appaiono in DocBank (list, reference)
  Download: ~500 MB
  Test: 1000 ricevute, stimati 5 minuti
                        │
                        ▼
STEP 2: FUNSD (form)
  Probabilità successo: 75%
  Perché secondo: un form ha coppie chiave→valore
    "Name:" → "John Smith" = QUESTION → ANSWER
    È il campo Φ ma tra TEXT e TEXT, non TEXT e NUMERIC
  Sfida nuova: bonds TEXT↔TEXT (non solo TEXT↔NUMERIC)
    La matrice W deve avere W(QUESTION, ANSWER) > 0
    Oggi W(TEXT, TEXT) = 0. Serve estenderla.
  Cosa impari: come estendere W a tipi non-numerici
    → il campo lavora su QUALSIASI coppia tipizzata
  Aiuta il prossimo: DocBank ha paragraph↔section, title↔abstract
    — tutti bonds TEXT↔TEXT
  Download: ~30 MB (piccolo!)
  Test: 50 documenti, stimati 1 minuto
                        │
                        ▼
STEP 3: SROIE (ricevute ICDAR)
  Probabilità successo: 65%
  Perché terzo: simile a CORD ma scansionato
    Stessa struttura (ricevuta) ma coordinate RUMOROSE
    Testi robustezza di quello che hai imparato su CORD
  Sfida nuova: noise dalle scansioni (coordinate ±2-5px)
    Il max-jump deve reggere con gap imprecisi
  Cosa impari: la tolleranza al rumore del principio
    → sai quanto degrada con coordinate imprecise
  Aiuta il prossimo: DocLayNet ha scan, DocBank ha jitter
  Download: ~200 MB
  Test: 1000 ricevute
  Bonus: è benchmark ICDAR ufficiale — fa curriculum
                        │
                        ▼
STEP 4: XFUND (form multilingue)
  Probabilità successo: 70%
  Perché quarto: FUNSD in 7 lingue (IT, JA, ZH, ES, FR, DE, PT)
    Se il campo funziona su form italiani E giapponesi
    senza cambiare niente → universalità confermata
  Sfida nuova: scrittura diversa (CJK, RTL in futuro)
    Le particelle giapponesi hanno width/height diverso
    Il k adattivo (max-jump) deve auto-calibrarsi
  Cosa impari: il campo è script-agnostic?
    Se sì → claim universale inattaccabile
    Se no → capisci quale parte dipende dalla lingua
  Aiuta il prossimo: DocBank ha solo inglese,
    ma il claim "universale" richiede più lingue
  Download: ~50 MB per lingua
  Test: 199 documenti × 3 lingue (IT, JA, ZH)
                        │
                        ▼
STEP 5: DocBank ⭐ (LA BOTTA)
  Probabilità successo: 55%
  Perché quinto (non primo): hai bisogno di tutto quello
    che hai imparato prima:
    - Liste (da CORD) → per trovare reference, list
    - TEXT↔TEXT bonds (da FUNSD) → per paragraph↔section
    - Tolleranza rumore (da SROIE) → per jitter nelle coordinate
    - Cross-script (da XFUND) → per il claim universale
  Sfida nuova: MULTI-SCALA
    Il max-jump trova confini tra parole (scala 1)
    Ma DocBank ha paragrafi→sezioni→capitoli (scale 2,3,4)
    Serve il max-jump RICORSIVO
  Cosa impari: la struttura gerarchica
    → il campo trova livelli di organizzazione
    → il principio multi-scala funziona
  Perché è la botta: 500K pagine, 12 tipi semantici
    LayoutLM usa 8×V100. Tu usi 1 CPU.
    Se arrivi a 70% → il paper si scrive da solo
  Download: ~10 GB
  Test: 50K pagine test set
                        │
                        ▼
STEP 6: DocLayNet (il boss finale)
  Probabilità successo: 45%
  Perché ultimo: è il più difficile e il più diverso
    6 domini in un dataset: financial, manuals, scientific,
    laws, patents, tenders
    Layout complessi: multi-colonna, figure, equazioni
  Sfida nuova: tutto insieme
    Layout non-rettangolari, figure che interrompono il testo,
    colonne sfalsate, header/footer
  Cosa impari: i LIMITI del campo
    Dove funziona e dove si rompe
    Il Φ medio per dominio = indice di struttura S(D)
  Perché ultimo: quando arrivi qui hai già risolto
    liste, form, rumore, lingue, multi-scala
    Tutto quello che hai imparato converge
  Download: 28 GB core + 7.5 GB extra
  Test: ~8K pagine test
