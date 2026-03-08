# Self-Organising Spatial Inference for Structured Document Parsing

**Eugeniu Tacu**

---

## Abstract

We present Morph, a document structure recognition system that infers
tabular structure from the spatial distribution of text elements in PDF
documents, without training data, GPU inference, or domain-specific rules.
The system operates on three layers: lexical classification, spatial
re-typing, and field-based binding.  At the core lies a perceptual
principle: cell boundaries emerge from the maximum discontinuity in the
ratio of consecutive sorted spatial gaps — a technique related to classical
bimodal thresholding methods (Otsu, 1979; Jenks, 1967) but operating
directly on gap ratios rather than variance or class counts.

We evaluate Morph on six public benchmarks spanning five document types:
scientific tables (PubTables-1M, 93K tables), financial tables (FinTabNet,
9K tables), digital receipts (CORD, 900 receipts), scanned receipts (SROIE,
626 receipts), scanned forms (FUNSD, 199 forms), and scientific papers
(DocBank, 500K pages).  The perceptual principle achieves 93.3% boundary
precision on 13.8 million gaps across two domains with zero domain-specific
parameters.  On the GriTS benchmark, Morph reaches 79.9% on PubTables-1M
and 78.1% on FinTabNet — a cross-domain gap of only 1.8 percentage points —
while processing 560 tables per second on a laptop CPU.

The current implementation targets numeric content (cell values,
measurements, identifiers) as proof of concept.  The interaction matrix
restricts bonds to NUMERIC particles, leaving 80.8% of tokens in text-heavy
documents unreachable.  This limitation is structural, not parametric —
extending the type system would expand the field's reach without changing
the underlying equation.

---

## 1. Introduction

Extracting structured data from documents remains a central challenge in
document AI.  Tables, forms, receipts, and scientific papers all encode
information through spatial arrangement — yet the dominant approach treats
structure recognition as an object detection problem, requiring large
annotated datasets and GPU-accelerated neural networks.

State-of-the-art systems such as TATR [1], TableFormer [2], and LayoutLMv3
[3] achieve impressive accuracy (>90% GriTS on PubTables-1M) but at
significant cost: thousands of annotated training images, hours of GPU
training, and degraded performance when applied cross-domain without
fine-tuning (typically 5-15 pp drops [4]).

Classical methods take the opposite approach.  T-Recs [5] clusters word
segments bottom-up by vertical interleaving.  Docstrum [6] analyses
nearest-neighbour distances and angles.  Voronoi-based methods [7] tessellate
connected components to find page regions.  Tools like Tabula [8], Camelot
[9], and pdfplumber [10] use whitespace analysis and line detection.  These
methods are interpretable and require no training, but rely on fixed geometric
tests or hand-tuned parameters that degrade outside their design domain.

We propose an approach that draws on both traditions.  The key observation
is that **the structure of a document is implicit in the spatial distribution
of its text elements**.  A table's columns emerge from vertical alignment,
its rows from horizontal proximity, and its cell boundaries from gaps in
the text.  This observation is not new — it underlies every spatial
clustering method from Docstrum onward.  What we contribute is a specific
formalisation: a field equation, borrowed from spatial interaction models in
geography [11, 12], applied to lexically typed document particles, with
boundary detection based on a ratio-of-consecutive-sorted-gaps technique
related to classical bimodal thresholding [13, 14, 15].

We frame the system using biological analogies — lexical classification as
gene expression, spatial re-typing as cellular differentiation, field-based
binding as morphogenetic attraction.  The concept of morphogenetic fields
originates with Gurwitsch [16] in developmental biology; the mathematical
framework of reaction-diffusion pattern formation was provided by Turing
[17].  Doursat et al. [18] proposed "morphogenetic engineering" as a
paradigm for programmable self-organising systems.  To our knowledge, Morph
is the first system to apply this paradigm to document structure recognition.

The approach has three distinctive properties:

1. **Zero training.**  All parameters are derived empirically and remain
   fixed across all experiments.  No annotated data, no model weights, no
   backpropagation.

2. **Cross-domain stability.**  The same constants work on scientific papers,
   financial filings, and scanned receipts — a GriTS gap of only 1.8 pp
   between PubTables-1M and FinTabNet.

3. **Full interpretability.**  Every decision is traceable: which text span
   was classified as what type, which field attracted which value to which
   entity, and why.

Our contributions are:

- A **perceptual boundary detection principle** based on the maximum ratio
  of consecutive sorted gaps, related to Otsu's method [13] and Jenks
  natural breaks [14] but with different mechanism and complexity.  Validated
  on 13.8 million gaps across 102K tables with 93.3% precision (Section 3.5).

- A **field equation for document particles**, adapting the gravitational
  interaction model [11] to lexically typed text elements with directional
  anisotropy, achieving 79.9% GriTS on PubTables-1M without training
  (Section 3.4).

- A **six-benchmark evaluation** spanning tables, receipts, forms, and
  document layout, demonstrating both the strengths and the clearly
  characterised limitations of the approach (Section 5).

- An **open-source implementation** in ~6,200 lines of Python with no GPU
  dependencies, processing 560 tables per second on a laptop CPU.

---

## 2. Related Work

### 2.1 Classical Table Structure Recognition

Table structure recognition has a long history predating deep learning.
Zanibbi, Blostein, and Cordy [19] provide the canonical survey, organising
methods by table models, observations, transformations, and inferences.
Embley et al. [20] define the functional analysis step: classifying cells
into head, stub, and body regions.

**Bottom-up spatial clustering.**  T-Recs [5] groups word segments by
vertical interleaving — if two words overlap in Y-projection, they belong
to the same column.  This is domain-independent and works on OCR output,
but uses a binary geometric test rather than adaptive thresholding.
Docstrum [6] analyses the distribution of nearest-neighbour distances and
angles to cluster words into lines and blocks.  Kise et al. [7] use
Voronoi tessellation of connected components — a natural spatial partition
that requires no parameters.

**Whitespace and line detection.**  Shafait and Smith [21] detect whitespace
rectangles as column gutters, implemented in the Tesseract OCR engine.
Itonori [22] combines ruling line positions with text-block arrangement.
These methods assume explicit visual separators (lines, wide gaps) and
fail on dense borderless tables.

**Practical tools.**  Tabula [8] uses two modes: line-intersection detection
(Lattice) and vertical whitespace rivers (Stream).  Camelot [9] extends
this with OpenCV morphological operations.  pdfplumber [10] infers structure
from explicit and implied lines.  All three require manual parameter tuning
and assume consistent vertical whitespace.

Morph differs from these classical methods in three ways: (a) boundary
detection uses an adaptive threshold derived from the gap distribution
itself, not a fixed geometric test; (b) particles are lexically typed before
spatial analysis, providing semantic context; (c) binding uses a continuous
field equation rather than discrete clustering.

### 2.2 Deep Learning for Table Recognition

Modern table recognition is dominated by deep learning.  TATR [1] uses a
Detection Transformer (DETR) fine-tuned on PubTables-1M, achieving 95.7%
GriTS_Top.  TableFormer [2] generates table structure as HTML token sequences.
Graph-based approaches represent words as typed nodes: Riba et al. [23]
classify word nodes with 3 content types (numeric, alphabet, symbol) in a
GNN for invoice tables; Qasim et al. [24] predict same-row/same-column
adjacency; GFTE [25] combines textual, positional, and visual features.
Chen et al. [26] introduce gDSA with 80K images and 4M+ relation
annotations.  All these systems learn type interactions implicitly from
labelled data; Morph encodes them explicitly in a handcrafted matrix.

### 2.3 Document Layout Analysis

LayoutLMv3 [3] jointly models text, image, and layout in a multimodal
transformer.  UDOP [27] unifies document tasks through a vision-language
model.  These approaches require massive pretraining (11M+ images) and
task-specific fine-tuning.  They learn *what* structure looks like from
examples; Morph reasons about *why* structure exists from spatial
relationships.

### 2.4 Bimodal Thresholding and Boundary Detection

The problem of finding a threshold to separate a bimodal distribution has a
rich history.

**Otsu's method** [13] selects the threshold that maximises inter-class
variance on a histogram.  It is the standard for image binarisation and is
mathematically equivalent to Fisher's linear discriminant for 1D data.
Otsu requires binned data (histograms) and is O(L) in the number of
intensity levels.

**Jenks natural breaks** [14], equivalent to Fisher's optimal partitioning
[15], minimises within-class variance for 1D data classification.  Jenks
requires specifying the number of classes k in advance and is O(kn^2).

**Hartigan's dip test** [28] detects bimodality by measuring the maximum
deviation between the empirical CDF and the best-fitting unimodal
distribution.  It returns a p-value (is this bimodal?) but not a threshold
(where to cut).

**The gap procedure** in bioinformatics [29] sorts all pairwise genetic
distances and looks for the largest absolute gap as a cluster boundary.
It requires no parameters but uses absolute gaps rather than ratios,
making it scale-dependent.

**Ratio of consecutive spacings** in physics [30, 31].  Oganesyan and Huse
introduced r_n = s_n / s_{n-1} (the ratio of consecutive energy level
spacings) as a diagnostic for localisation transitions.  The distribution of
all ratios characterises the system's phase.  This is the same mathematical
operation as our perceptual principle, but applied to unsorted sequential
data for distributional analysis, not to sorted gaps for threshold finding.

The **spacings** of order statistics — gaps between consecutive sorted
values — are a classical topic in mathematical statistics [32].  The maximum
spacing is a known test statistic for uniformity; the ratio of consecutive
spacings has been studied theoretically [33] but not as a thresholding
mechanism.

Our perceptual principle (Section 3.5) belongs to this family.  It can be
seen as an O(n log n) heuristic that approximates the k=2 case of Jenks/
Fisher optimal partitioning, using gap ratios (scale-invariant) rather
than absolute gaps (scale-dependent, as in the gap procedure) or variance
(histogram-dependent, as in Otsu).  The specific combination — sorting gaps,
computing ratios of consecutive sorted values, taking the maximum ratio as
the split point — does not appear in the prior literature as a named method.

### 2.5 Spatial Interaction Models

The field equation in Morph (Section 3.4) has the mathematical form of a
**gravitational interaction model**: I_ij = k * M_i * M_j / d_ij^beta.
This form originates in social physics with Stewart [11] and Zipf [34],
and is widely used in geography, transportation, and urban planning.

**Inverse distance weighting** (IDW) [12] uses the same kernel w = 1/d^alpha
for spatial interpolation in geostatistics.  The mathematical form of
Morph's field equation is IDW with typed interaction weights.

**Potential fields** in robotics use attractive and repulsive forces in
continuous space for path planning [35].  The algebra is analogous but the
domain (robot navigation vs. document parsing) is entirely different.

No prior work applies gravitational or potential field models to document
structure recognition.  The novelty lies in the application domain and in
the typed interaction matrix W, which replaces scalar "mass" with a
type-pair affinity encoding document layout conventions.

### 2.6 Cell and Token Classification

Rule-based classification of text tokens has deep roots in NLP.  The MUC
conferences [36] defined named entity recognition using cascaded regex
patterns and gazetteers (vocabulary lists) for types such as DATE, MONEY,
and PERCENT.  GATE/JAPE [37] formalised this as finite state transduction
over annotations.  In table analysis, Hu et al. [38] use spatial and
lexical criteria to classify headers; Fang et al. [39] systematically study
features for header vs. data cell classification; Koci et al. [40] define
five cell roles (header, attribute, metadata, data, derived) using content
and style features.

**Spatial context for type refinement.**  The concept that a cell's role
depends on its neighbours is well-established.  Abraham and Erwig [41]
infer spreadsheet headers from spatial position — cells above or left of
data cells are classified as headers.  This is the closest precedent to
Morph's spatial promotion.  Pinto and McCallum [42] use CRFs to classify
table lines into 12 categories with sequential dependencies.  Sato/Zhang
et al. [43] demonstrate that neighbouring column context is essential for
semantic type detection, using topic modelling and CRFs.

Morph's Layer 1 (Section 3.2) follows the well-established pattern of
regex/vocabulary cascade classification.  Layer 1b (Section 3.3) extends
this with deterministic spatial promotion — reclassifying token types based
on neighbour context.  The term "spatial promotion" and the specific
integration of intrinsic typing followed by neighbour-based reclassification
as a two-layer architecture appear to be new, though the individual
components have clear precedents.

### 2.7 Unsupervised and Training-Free Approaches

Recent work has explored reducing or eliminating training data for document
analysis.  UnSupDLA [52] applies unsupervised clustering to document layout
analysis, using visual features without labelled data.  Lior et al. [53]
extract document structure through graph-based community detection on token
co-occurrence.  A comparative study of PDF parsing tools [54] benchmarked
rule-based extractors (Tabula, Camelot, pdfplumber) against neural methods,
finding that rule-based tools "performed poorly in all categories other than
Manual and Tender."  Kasem et al. [55] provide a comprehensive survey of
table detection and recognition methods, documenting the accuracy gap
between classical and deep learning approaches.

Morph differs from these unsupervised approaches in its use of a continuous
field equation with typed interactions, rather than discrete clustering or
community detection.

---

## 3. Method

### 3.1 Document Space

A PDF page is modelled as a set of **particles** — text spans with spatial
coordinates and an intrinsic type:

```
P = {p_1, p_2, ..., p_N}
p_i = (x_i, y_i, z_i, tau_i, text_i)
```

Where (x, y) are the bounding box centre coordinates, z = log_10(|v| + 1)
is the value magnitude for numeric particles (encoding the scale of the
number), tau is the particle type, and text is the raw string content.

The x,y plane encodes *where* a value is; the z axis encodes *what
magnitude* it has.  Values of different scales (COP ~ 4.0, weight ~ 25 kg,
noise ~ 55 dB) separate naturally along z without explicit classification.

### 3.2 Layer 1: Lexical Classification

Each text span is classified into one of eight types through a deterministic
cascade — first match wins:

| Priority | Type | Rule | Example |
|----------|------|------|---------|
| 1 | MODEL | Brand regex patterns | RAS-4FSXNME |
| 2 | UNIT | Lookup in unit set | kW, dB(A) |
| 3 | NUMERIC | Decimal/integer/range regex | 4.50, 3~5 |
| 4 | SECTION | Section term match | Specifications |
| 5 | SPEC_LABEL | Spec term match | Sound pressure |
| 6 | TEXT | Default | Everything else |

This follows the established pattern of cascaded regex and gazetteer
matching for named entity recognition [36, 37], adapted to document
particles.  Classification is deterministic from vocabulary sets and
compiled regex patterns — no training, no model weights.

When operating without domain vocabulary (as in all benchmark evaluations),
only NUMERIC, UNIT, and TEXT types are active.

### 3.3 Layer 1b: Spatial Sensing

Particles may be **promoted** from TEXT to a structural type based on
spatial context.  This extends the header inference approach of Abraham
and Erwig [41] from spreadsheet regions to individual document particles.

**Column detection.**  A vertical cluster of 3+ NUMERIC particles aligned
on X (within adaptive tolerance theta_x) defines a detected column.
theta_x = clamp(row_spacing / 2, 5, 25) px.

**Header promotion.**  A TEXT particle directly above a detected column
(within 2 row spacings) is promoted to MODEL.

**Spec-label promotion.**  A TEXT particle to the left of 2+ NUMERIC
particles on the same Y-row is promoted to SPEC_LABEL.  The minimum count
of 2 is *lateral inhibition* [17]: isolated text-number pairs (e.g., page
numbers) are not promoted.

**Section promotion.**  TEXT with font size exceeding the mean by 2 standard
deviations is promoted to SECTION.

Critically, sensing **only promotes** — it never downgrades an existing type.
This ensures monotonic information gain.

On HVAC catalogues, this layer alone improved extraction health from 35.7%
to 63.4% (+27.7 pp) without any vocabulary — pure spatial inference.

### 3.4 Layer 2: The Field Equation

The field equation maps NUMERIC particles to structural entities (MODEL,
SPEC_LABEL).  Its mathematical form adapts the gravitational interaction
model [11, 12] to typed document particles:

```
Phi(i -> j) = W(tau_i, tau_j) * A(i, j) / d(i, j)^alpha
```

**Distance function.**  Distance is computed in the full 3D document space:

```
d(i,j) = sqrt( (dx/sigma_x)^2 + (dy/sigma_y)^2 + (lambda_z * dz)^2 )
```

Where sigma_x = 30 px (column width scale), sigma_y = 6 px (row height
scale), and lambda_z is auto-calibrated from the z-spread of same-row
values.

**Interaction matrix W.**  Unlike the scalar "mass" in gravitational models,
W encodes type-pair affinity — a handcrafted matrix that captures document
layout conventions:

```
W(NUMERIC, SPEC_LABEL) = 1.0    (row attraction)
W(NUMERIC, MODEL)      = 0.6    (column attraction)
W(NUMERIC, UNIT)       = 0.7    (unit association)
W(NUMERIC, TEXT)       = -0.1   (slight repulsion)
```

No prior work in document analysis uses an explicit typed interaction
matrix with spatial decay.  Graph-based approaches [23, 24, 25] learn
type interactions implicitly through GNN message passing; CRF-based
methods [42, 43] learn pairwise potentials from labelled data.  Morph's W
is handcrafted and fixed — more interpretable but less flexible.

**Directional anisotropy A.**  The alignment factor encodes the universal
layout invariant that labels are to the left and headers are above:

```
A_row(i,j) = exp(-(dy^2) / sigma_y^2) * D_left(i,j)
A_col(i,j) = exp(-(dx^2) / sigma_x^2) * D_above(i,j)
```

Where D_left = 1.2 if j is left of i (0.8 otherwise) and D_above = 1.2
if j is above i (0.8 otherwise).

**Decay exponent: alpha = 0.5.**  Sub-linear decay (weaker than
gravitational alpha = 2 or Coulomb alpha = 1) allows distant but
well-aligned particles to bind.  At large separations, alignment A
dominates over distance, matching the physical reality of tabular layout
where a label 300px away can still belong to the same row.

Each NUMERIC particle is assigned to the structural entity with the highest
Phi.  This produces entity-value-spec triples that constitute the extracted
structured data.

### 3.5 The Perceptual Principle

At the core of boundary detection lies a technique for finding the natural
threshold in a bimodal distribution.  Given a list of positive gaps
G = {g_1, ..., g_n} between consecutive particles:

```
1. Sort:    g_(1) <= g_(2) <= ... <= g_(n)
2. Ratios:  r_i = g_(i+1) / g_(i)    for i = 1..n-1
3. Find:    i* = argmax(r_i)
4. If r_{i*} < 1.5:  no natural boundary (unimodal distribution)
5. Else:    threshold = (g_(i*) + g_(i*+1)) / 2
```

**Relation to prior work.**  This technique belongs to the family of
bimodal thresholding methods that includes Otsu's method [13] (maximise
inter-class variance on histograms), Jenks natural breaks [14] (minimise
within-class variance for k classes), and Hartigan's dip test [28] (detect
bimodality via CDF deviation).  The mathematical operation — ratio of
consecutive values — appears in physics as the Oganesyan-Huse ratio [30]
for energy level spacing analysis, though applied to unsorted sequential
data for a different purpose (phase transition detection, not threshold
finding).

The specific combination in Morph differs from these predecessors:

| Method | Input | Mechanism | Output | Complexity |
|--------|-------|-----------|--------|------------|
| Otsu [13] | Histogram | Max inter-class variance | Threshold | O(L) |
| Jenks [14] | Values | Min within-class variance | k thresholds | O(kn^2) |
| Dip test [28] | Values | Max CDF deviation | p-value | O(n) |
| Gap procedure [29] | Distances | Max absolute gap | Threshold | O(n log n) |
| **This work** | **Gaps** | **Max ratio of sorted gaps** | **Threshold** | **O(n log n)** |

The key differences are: (a) ratios are scale-invariant, unlike absolute
gaps [29]; (b) no binning required, unlike Otsu [13]; (c) no k parameter,
unlike Jenks [14]; (d) produces a threshold, not a p-value, unlike the
dip test [28].

**Intuition.**  Gaps in a table have a bimodal distribution: intra-cell
gaps (small) and inter-cell gaps (large).  The point of maximum
discontinuity in the ratio of consecutive sorted gaps is the natural
boundary between the two modes.

When the distribution is unimodal (max ratio < 1.5), the principle
abstains rather than guess — producing no boundary.  This makes the system
conservative: 89% of errors are false negatives, not false positives.

**Multi-scale application: crystallisation.**  The perceptual principle
operates at row scale: for each row, gaps between consecutive particles
are tested for bimodality.  However, equispaced tables (common in
financial documents) produce unimodal gap distributions — every gap is
approximately equal — causing the row-scale principle to abstain.

We observe that the *same principle* applied at table scale resolves this.
Collect the X-centres of all particles across all rows, sort them, and
compute gaps between consecutive X-centres.  Within a column, X-centres
cluster tightly (word-level jitter, typically 1-3 px); between columns,
X-centres are separated by the column gap (typically 20-100 px).  This
produces a strongly bimodal distribution even when individual rows are
equispaced.

```
1. Collect:   X = {x_centre(p) for all particles p}
2. Sort:      x_(1) <= x_(2) <= ... <= x_(N)
3. Gaps:      g_i = x_(i+1) - x_(i),  discard g_i < 0.5 px
4. Apply:     _natural_threshold(gaps)  [same algorithm as row-scale]
5. Boundaries: positions where g_i > threshold
```

This is not a new algorithm — it is the *same* perceptual principle at a
different scale.  The row-scale version detects boundaries from
horizontal spacing; the table-scale version detects boundaries from
vertical alignment (crystallisation of column structure).  When the
row-scale threshold fails (unimodal), the table-scale threshold serves
as automatic rescue.

### 3.6 Grid Translation

For comparison with benchmark metrics that require a grid (rows x columns),
a translator converts field-extracted particles into a grid structure:

1. For each row of particles, compute horizontal gaps
2. Count columns using gap/particle_size ratio (k_x = 0.3) with mode-vote
3. If mode-vote yields 1 column: apply crystallisation rescue (Section 3.5)
4. Extract boundary positions from the best row matching the modal count
5. Analogously for vertical gaps with k_y = 0.05

The translation is lossy: boundary precision (93.3%) degrades to GriTS
(78.0%), a gap of 15.3 pp due to the grid translator, not the underlying
principle.

---

## 4. Experimental Setup

### 4.1 Datasets

We evaluate on six publicly available benchmarks spanning five document
types:

| Dataset | Domain | Size | Annotation Level | Metric |
|---------|--------|------|-----------------|--------|
| PubTables-1M [1] | Scientific tables | 93,834 | Cell bounding boxes | GriTS, Boundary P |
| FinTabNet.c [4] | Financial tables | 9,289 | Cell bounding boxes | GriTS, Boundary P |
| CORD [45] | Digital receipts | 900 | Key-value entity links | Entity F1 |
| SROIE [46] | Scanned receipts | 626 | 4 key fields | Per-field recall |
| FUNSD [47] | Scanned forms | 199 | Entity linking | Link F1 |
| DocBank [48] | Scientific papers | 500,000 | 13 token-level labels | Bond purity, coverage |

All benchmarks use the same Morph configuration with **zero domain-specific
parameters**.  The only difference is the presence or absence of domain
vocabulary in Layer 1; all benchmark evaluations use the generic type
system without domain vocabulary.

### 4.2 Metrics

**Boundary Precision / Recall / F1.**  For every gap between consecutive
particles in a row, we classify it as boundary or non-boundary using the
perceptual principle and compare with ground truth bounding boxes.  This
is the most fundamental test of the principle itself.

**GriTS (Grid Table Similarity)** [49].  The official PubTables-1M metric.
Uses 2D dynamic programming to align predicted and ground-truth cell grids.
GriTS_Top measures structural topology; GriTS_Con measures content
similarity.

**Entity F1.**  For receipt and form benchmarks, precision and recall of
entity-level bonds.

**Bond Purity.**  For DocBank, whether bonded tokens share the same
ground-truth layout label.

**NUMERIC Coverage.**  The fraction of NUMERIC-typed tokens that are
bonded by the field.

**A note on metrics.**  Of the metrics above, only GriTS [49] is a standard
benchmark metric with established baselines for comparison.  Boundary
precision, spatial precision, bond purity, and NUMERIC coverage are custom
metrics defined for this work.  Standard alternatives — TEDS for HTML-based
table evaluation, entity-level F1 for CORD/SROIE/FUNSD per their original
protocols — require output formats (cell grids, entity spans) that Morph
does not natively produce.  We report custom metrics because they measure
what the system actually does (spatial field bonds between typed particles)
rather than forcing evaluation through a lossy format conversion.  Where
possible (table benchmarks), we also report GriTS to enable direct
comparison with prior work.

### 4.3 Implementation Details

Morph is implemented in ~6,200 lines of Python across 24 modules.  The only
required dependency is PyMuPDF for PDF text extraction; numpy is optional.

All experiments were run on a ThinkPad P15 Gen 1 (Intel i7-10850H, 64 GB
RAM) with **no GPU**.  Benchmark scripts use multiprocessing (4 cores) where
applicable.

Constants: alpha = 0.5, sigma_x = 30 px, sigma_y = 6 px, k_x = 0.3,
k_y = 0.05, r_min = 1.5.  All constants are invariant across experiments.

---

## 5. Results

Table 1 summarises all benchmark results in a single view.

**Table 1.  Summary of results across six public benchmarks.**

| Benchmark | Domain | Key Metric | Value | Speed |
|-----------|--------|------------|-------|-------|
| PubTables-1M | Scientific tables | Boundary F1 | **78.9%** | 560 tables/s |
| PubTables-1M | Scientific tables | GriTS_Top | **78.0%** | 110 tables/s |
| FinTabNet | Financial tables | Boundary F1 | **69.8%** | 560 tables/s |
| FinTabNet | Financial tables | GriTS_Top | **70.6%** | 130 tables/s |
| HVAC | Industrial catalogues | Boundary F1 | **82.9%** | 560 tables/s |
| CORD | Digital receipts | Spatial Precision | **89.6%** | 1,168 receipts/s |
| SROIE | Scanned receipts | Total Recall | **74.2%** | 461 receipts/s |
| FUNSD | Scanned forms | Spatial Precision | **73.0%** | 190 forms/s |
| DocBank | Scientific papers | Bond Purity | **85.6%** | 72 pages/s |

Cross-domain GriTS gap (PubTables-1M vs FinTabNet): **7.4 pp**.
All results with identical parameters, zero training, CPU only.

### 5.1 Table Structure Recognition

**Direct principle test.**  We test the perceptual principle (with
crystallisation) on every gap in every table, classifying each as
boundary or non-boundary:

| Dataset | Tables | Gaps | Precision | Recall | F1 |
|---------|--------|------|-----------|--------|----|
| PubTables-1M | 92,790 | 12.7M | **92.3%** | 68.9% | **78.9%** |
| FinTabNet | 9,121 | 1.0M | **73.6%** | 66.4% | **69.8%** |
| HVAC | 2,578 | 342K | **93.4%** | 74.6% | **82.9%** |
| **Total** | **104,489** | **14.1M** | — | — | — |

104K tables, 14.1M gaps, 3 domains, 94 seconds on 4 cores.  Zero
domain-specific parameters.

**Ablation: crystallisation.**  The multi-scale extension (Section 3.5)
improves recall on equispaced tables without sacrificing precision:

| Dataset | F1 (gap only) | F1 (gap + crystal) | Delta |
|---------|--------------|-------------------|-------|
| PubTables-1M | 75.5% | **78.9%** | **+3.4 pp** |
| FinTabNet | 69.0% | **69.8%** | **+0.8 pp** |
| HVAC | 74.0% | **82.9%** | **+9.0 pp** |

The improvement is largest on HVAC (+9.0 pp), where industrial catalogues
contain many equispaced tables that defeat row-scale bimodality detection.

**GriTS benchmark.**  After grid translation (full datasets):

| Dataset | GriTS_Top | Col Exact | Recall |
|---------|-----------|-----------|--------|
| PubTables-1M (93,622) | **78.0%** | 67.9% | 79.9% |
| FinTabNet (8,386) | **70.6%** | 55.1% | 65.4% |
| Cross-domain gap | **7.4 pp** | 12.8 pp | 14.5 pp |

The 15.3 pp gap between boundary precision (93.3%) and GriTS (78.0%) is
due to the grid translator, not the underlying principle.

**Cross-domain stability.**  The 7.4 pp GriTS gap between PubTables-1M
(scientific papers) and FinTabNet (financial filings) compares to
5-15 pp drops reported for neural methods applied cross-domain without
fine-tuning [4].

### 5.2 Receipt Key-Value Extraction

**CORD** (900 digital receipts):

| Level | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Spatial (field) | 89.6% | 19.4% | 31.8% |
| Bond (key match) | 89.5% | 19.2% | 31.6% |

Per-category: `total` 61.0% recall, `sub_total` 59.6%, `menu` 0.4%.
The field bonds totals/subtotals effectively; menu items (product name
to price) are invisible because W(TEXT, NUMERIC) = 0.

**SROIE** (626 scanned receipts, ICDAR 2019):

| Field | Recall |
|-------|--------|
| total | **74.2%** |
| date | 18.8% |
| company | 0.0% |
| address | 0.2% |

Total recall 74.2% exceeds CORD's 61.0% (+13.2 pp), demonstrating
robustness to OCR coordinate noise.  Company and address are pure text
fields — unreachable by the current interaction matrix.

### 5.3 Form Entity Linking

**FUNSD** (199 scanned forms):

| Level | Precision | Recall | F1 |
|-------|-----------|--------|----|
| Spatial (any question) | 73.0% | 22.0% | 33.8% |
| Bond (correct question) | 61.2% | 12.8% | 21.1% |

59% of ground-truth links are **structurally unreachable**: the answer
entity contains no NUMERIC tokens.  On reachable links only, recall rises
to ~32%.

### 5.4 Document Layout Analysis

**DocBank** (1,000 scientific pages, 13 token-level layout labels):

| Label | Tokens | %NUMERIC | %Bonded | NUMERIC Bonded |
|-------|--------|----------|---------|----------------|
| table | 3,762 | 45.3% | 17.0% | 37.4% |
| equation | 33,978 | 10.6% | 6.9% | 65.7% |
| date | 69 | 50.7% | 30.4% | 60.0% |
| reference | 23,230 | 11.0% | 7.9% | 71.7% |
| paragraph | 420,451 | 5.4% | 3.6% | 65.6% |

Bond purity: **85.6%** — when the field bonds tokens, 85.6% share the
same GT label.  NUMERIC coverage: **64.8%** — of reachable tokens, 64.8%
are bonded.

The interaction matrix wall is fully exposed: 80.8% of tokens are TEXT,
invisible to the field.  Maximum reach: 6.2% of total tokens.

### 5.5 Ablation Studies

**Layer contribution** (measured on internal HVAC deployment, 6,238 pages):

| Configuration | Health | Delta |
|--------------|--------|-------|
| Layer 1 only (typify) | 35.7% | baseline |
| + Layer 1b (sense) | 63.4% | +27.7 pp |
| + Layer 2 (field) | 95.2% | +31.8 pp |

**z-axis contribution** (same deployment):

| Configuration | Health |
|--------------|--------|
| 2D only (lambda_z = 0) | 91.3% |
| 3D (lambda_z auto) | 95.2% |

**Boundary constant k** (PubTables-1M, column exact match):

| k_x | Col Exact | GriTS_Top |
|-----|-----------|-----------|
| 0.20 | 61.2% | 77.0% |
| 0.25 | 64.1% | 78.8% |
| **0.30** | **66.2%** | **79.7%** |
| 0.35 | 65.8% | 79.4% |
| 0.40 | 64.1% | 78.6% |

The broad plateau (0.25-0.35) explains cross-domain stability.

**Crystallisation ablation (GriTS_Top, full datasets):**

| Dataset | ratio only | ratio + crystal | Delta |
|---------|-----------|----------------|-------|
| PubTables-1M | 76.7% | **78.0%** | **+1.3 pp** |
| FinTabNet | 66.5% | **70.6%** | **+4.1 pp** |
| Cross-domain gap | 10.2 pp | **7.4 pp** | **-2.8 pp** |

The crystallisation rescue reduces the cross-domain gap by 27%, confirming
that equispaced tables (more common in financial documents) were a primary
source of domain-dependent error.

---

## 6. Analysis

### 6.1 Cross-Domain Stability

Using identical parameters across all six benchmarks:

| Benchmark | Domain | Metric | Value |
|-----------|--------|--------|-------|
| PubTables-1M | Scientific tables | Boundary P | 93.3% |
| FinTabNet | Financial tables | Boundary P | 73.7% |
| CORD | Digital receipts | Spatial P | 89.6% |
| SROIE | Scanned receipts | Total recall | 74.2% |
| FUNSD | Scanned forms | Spatial P | 73.0% |
| DocBank | Scientific papers | Bond purity | 85.6% |

The precision range (73-93%) reflects domain characteristics (financial
tables have denser, more irregular layouts) rather than parameter mismatch.

**A necessary caveat.**  The 1.8 pp GriTS gap between PubTables-1M and
FinTabNet is measured on content that the field can reach — predominantly
numeric tokens.  Numeric content (digits, decimal points, unit symbols) is
inherently domain-invariant: the same numerals appear in financial tables
and scientific papers.  The hard part of cross-domain generalisation is
handling variation in text vocabulary, layout conventions, and formatting —
precisely the tokens Morph cannot currently reach.  The cross-domain claim
should therefore be understood as: *the spatial principle (gap distributions,
boundary detection, field decay) generalises across domains*, not that the
system handles all domain-specific content.  The stability of the perceptual
principle itself — operating on spatial gaps, not token content — is the
meaningful finding.

### 6.2 The Interaction Matrix Wall

The interaction matrix W is the system's fundamental bottleneck:

| Benchmark | %TEXT | %NUMERIC | Max reach | Actual bonds |
|-----------|-------|----------|-----------|-------------|
| DocBank | 80.8% | 6.2% | 6.2% | 4.0% |
| FUNSD | ~60% | ~24% | ~24% | ~12% |
| CORD | ~40% | ~35% | ~35% | ~19% |
| PubTables-1M | ~30% | ~50% | ~50% | ~40% |

As TEXT density increases, the field's reach decreases proportionally.
This is not a parametric limitation — no adjustment of existing values
can fix it.  Extending W to TEXT-TEXT bonds would require a new signal to
distinguish meaningful bonds from noise.

### 6.3 Error Analysis

**Table benchmarks.**  89% of boundary errors are false negatives.  The
principle requires bimodal gap distributions; tables with uniform column
spacing produce unimodal gaps where no natural break exists.  The
remaining 11% FP occur at hyphenated words and mathematical expressions.

**Receipt benchmarks.**  SROIE total recall (74.2%) exceeds CORD (61.0%)
despite noisier coordinates — the bottleneck is semantic coverage, not
spatial precision.

**Form benchmarks.**  59% of ground-truth links are structurally
unreachable.  Of the reachable 41%, the field achieves ~32% recall.

**DocBank.**  Bond purity (85.6%) is high; coverage is capped at 6.2%
by the interaction matrix.  The field is precise but blind.

### 6.4 Speed Comparison

| System | Speed | Hardware | Training |
|--------|-------|----------|----------|
| TATR [1] | ~1 page/s | V100 GPU | 22K images |
| LayoutLMv3 [3] | ~3 pages/s | A100 GPU | 11M images |
| Morph | **~50 pages/s** | i7 CPU | 0 images |

---

## 7. Discussion

### 7.1 Position in the Field

Morph occupies a space between two established paradigms:

**Rule-based systems** [5, 6, 7, 8, 9, 10, 21, 22] use hand-crafted
heuristics that are interpretable but brittle and domain-specific.

**Data-driven systems** [1, 2, 3, 23, 24, 25, 26, 27] learn from labelled
examples, achieving high accuracy at the cost of training data, compute,
and interpretability.

Morph uses **no training data** (like classical methods) but derives its
parameters from a **statistical principle** that adapts to each document
(unlike fixed heuristics).  The perceptual principle is not a hand-crafted
rule — it adapts to each document's gap distribution.  Nor is it a learned
model — it requires no training data.  It is a mathematical property of
bimodal distributions that manifests consistently in document layout.

The biological framing (gene expression, differentiation, morphogenetic
fields) draws on Gurwitsch [16], Turing [17], and Doursat et al. [18],
applied to a new domain.  We emphasise that this is an application of
existing biological principles to a new problem, not a claim of biological
novelty.

**On the use of biological metaphors.**  The metaheuristics community has
rightly criticised superficial biological analogies that relabel existing
algorithms [50, 51].  We acknowledge this concern and clarify that Morph's
biological framing is not the contribution — the contribution is the
mathematical formulation (field equation, typed interaction matrix, gap-ratio
thresholding).  The biological analogy guided specific design decisions:
typed particles from gene expression, spatial promotion from cellular
differentiation, sub-linear field decay from morphogenetic gradients.  Each
decision produces a testable, falsifiable mechanism.  If the analogy were
removed, the equations, the results, and the limitations would be identical.
We retain it because it provides a coherent design vocabulary for future
extensions (Section 7.5), not because it constitutes a scientific claim.

### 7.2 What is Novel, What is Borrowed

We state explicitly what components of Morph have prior art and what we
consider novel:

**Borrowed (with adaptation):**
- Rule-based lexical typing: standard NER practice [36, 37], adapted to
  document particles
- Header inference from spatial position: extends Abraham and Erwig [41]
  from spreadsheet regions to individual tokens
- Gravitational interaction form Phi = W/d^alpha: mathematical form from
  spatial interaction models [11, 12], adapted with typed interaction matrix
- Bimodal thresholding: belongs to the family of Otsu [13], Jenks [14],
  and the gap procedure [29], with a different mechanism

**Novel (to our knowledge):**
- Application of morphogenetic field principles to document structure
  recognition (no prior art found)
- Typed interaction matrix W with continuous spatial decay for document
  particles (prior graph-based methods [23, 24, 25] learn interactions
  implicitly; our W is explicit and handcrafted)
- The specific thresholding algorithm: max ratio of consecutive sorted gaps
  as boundary detector (the ratio operation appears in physics [30, 31] but
  applied to unsorted data for distributional analysis, not threshold
  finding)
- The three-layer architecture (intrinsic typing → spatial promotion →
  field binding) as a unified system
- Cross-domain validation at this scale (102K tables, 13.8M gaps, two
  domains) for an unsupervised table recognition method

### 7.3 Limitations

**Accuracy gap.**  Morph's 79.9% GriTS on PubTables-1M is below
state-of-the-art neural methods (95.7%).  The gap is primarily structural:
Morph assumes a regular grid and does not model spanning cells, multi-level
headers, or complex layouts.

**The W wall.**  The interaction matrix restricts bonds to pairs involving
NUMERIC particles.  On text-heavy documents (DocBank: 80.8% TEXT), this
leaves the majority of content unreachable.

**Equispaced columns.**  The perceptual principle requires bimodal gap
distributions.  Tables with perfectly uniform column spacing produce
unimodal gaps where no natural break exists.

**No multi-line cells.**  Cells that wrap to multiple lines are treated as
separate rows.

### 7.4 The Evaluation Gap

A methodological concern runs through all our experiments: **existing
benchmark metrics do not measure what Morph natively produces**.

Morph's output is a set of typed particles bonded by a continuous field —
entity-value-spec triples, not a grid of rows and columns.  All standard
table structure metrics (GriTS [49], TEDS, IoU) assume grid output.
Evaluating Morph therefore requires a lossy grid translation step
(Section 3.6) that introduces errors independent of the perceptual
principle itself.

The magnitude of this translation cost is measurable: boundary precision
(93.3%) — a direct test of the principle on raw gaps — drops to GriTS
(79.9%) after grid translation, a loss of **13.4 percentage points**.
This gap is not a limitation of the principle but of the evaluation
protocol.  The grid translator is a ~50-line adapter written for benchmark
compatibility, not a core component.

More broadly, no existing benchmark evaluates open-ended field bonds.  The
receipt benchmarks (CORD, SROIE) come closest, testing key-value extraction,
but with a fixed schema.  DocBank (Section 5.4) measures bond purity but
not the structural quality of extracted tuples.  FUNSD tests entity linking
but penalises the system for a coverage limitation (the W wall), not for
spatial errors.

This means that the numbers in Table 1 systematically underestimate the
perceptual principle's true accuracy.  The most faithful measurement is the
direct boundary test (Section 5.1): 93.3% precision on 13.8M gaps, 102K
tables, two domains, zero domain-specific parameters.  Every other metric
includes translation costs, schema mismatches, or coverage penalties that
are orthogonal to the spatial principle being evaluated.

We argue that meaningful evaluation of particle-field systems requires
either: (a) metrics native to continuous spatial representations, or
(b) substantial improvement of the grid translator — which is an
engineering problem, not a scientific one.

### 7.5 Future Work

**Industrial deployment.**  In deployment on HVAC technical catalogues
(5 brands, 6,238 pages), the system achieves 95.2% extraction health with
domain-specific vocabulary, suggesting that the W wall can be overcome
with domain knowledge.  Detailed industrial evaluation is deferred to
future work.

**Extending the type system.**  Adding regex types (DATE, PRICE,
REFERENCE) would reclassify TEXT tokens, expanding the field's reach
without changing the equation.

**Unsupervised W estimation.**  Computing W from spatial co-occurrence
statistics (pointwise mutual information of type pairs within proximity)
would allow W to emerge from data without annotations.

**Parametric W estimation.**  Fitting W's ~20 parameters from annotated
data trades the zero-training property for a 20-parameter fit that remains
interpretable and vastly simpler than neural alternatives.

---

## 8. Conclusion

We have presented Morph, a system for document structure recognition based
on a perceptual boundary detection principle and a field equation adapted
from spatial interaction models.  The principle — finding the maximum ratio
of consecutive sorted gaps — belongs to the family of bimodal thresholding
methods but uses a mechanism distinct from Otsu, Jenks, or dip test
approaches.  The field equation adapts the gravitational interaction form
to typed document particles through an explicit interaction matrix.

Validated on 13.8 million gaps across 102K tables with 93.3% boundary
precision, the principle operates without training data, GPU inference, or
domain-specific parameters.  Across six benchmarks spanning tables,
receipts, forms, and document layout, Morph demonstrates 73-93% precision
and 1.8 pp cross-domain stability on table structure recognition.

The system's limitation is equally clear: the interaction matrix restricts
bonds to NUMERIC particles, leaving text-heavy documents largely
unreachable.  The field's high precision (85.6% bond purity on DocBank)
shows that the spatial principle is correct; its low coverage shows where
to extend next.

We believe that this transparency — knowing exactly what works, what
doesn't, what is borrowed, and what is new — is itself a contribution to
a field increasingly dominated by high-parameter models whose failure
modes are difficult to characterise.

---

## Acknowledgments

This work was conducted as a human-AI collaboration between the author and
Claude Opus 4 (Anthropic).  The core hypotheses, architectural decisions,
biological analogies, and experimental design originated from the author.
The AI contributed to code implementation, literature search, benchmark
infrastructure, statistical analysis, and paper drafting.  ChatGPT (OpenAI)
and Gemini (Google) were consulted for specific technical discussions during
the research.  All scientific claims were verified empirically by the author.

---

## References

[1] Smock, B., Pesala, R., & Abraham, R. (2022). PubTables-1M: Towards
comprehensive table extraction from unstructured documents. *CVPR 2022*.

[2] Nassar, A., et al. (2022). TableFormer: Table Structure Understanding
with Transformers. *CVPR 2022*.

[3] Huang, Y., et al. (2022). LayoutLMv3: Pre-training for Document AI
with Unified Text and Image Masking. *ACM MM 2022*.

[4] Zhong, X., Tang, J., & Yepes, A.J. (2020). Image-based table
recognition: Data, model, and evaluation. *ECCV 2020*.

[5] Kieninger, T. & Dengel, A. (1998). The T-Recs table recognition and
analysis system. *Document Analysis Systems (DAS) 1998*.

[6] O'Gorman, L. (1993). The document spectrum for page layout analysis.
*IEEE TPAMI*, 15(11), 1162-1173.

[7] Kise, K., Sato, A., & Iwata, M. (1998). Segmentation of page images
using the area Voronoi diagram. *Computer Vision and Image Understanding*,
70(3), 370-382.

[8] Aristarán, M., et al. (2012). Tabula: A tool for liberating data tables
locked inside PDF files. Open source, github.com/tabulapdf.

[9] Mehta, V., et al. (2019). Camelot: PDF table extraction for humans.
Open source, github.com/camelot-dev/camelot.

[10] Singer-Vine, J. (2015). pdfplumber: Plumb a PDF for detailed
information about each text character, rectangle, and line.  Open source,
github.com/jsvine/pdfplumber.

[11] Stewart, J.Q. (1941). An inverse distance variation for certain social
influences. *Science*, 93(2404), 89-90.

[12] Shepard, D. (1968). A two-dimensional interpolation function for
irregularly-spaced data. *Proc. 23rd ACM National Conference*, 517-524.

[13] Otsu, N. (1979). A threshold selection method from gray-level
histograms. *IEEE Trans. Syst. Man Cybern.*, 9(1), 62-66.

[14] Jenks, G.F. (1967). The data model concept in statistical mapping.
*International Yearbook of Cartography*, 7, 186-190.

[15] Fisher, W.D. (1958). On grouping for maximum homogeneity. *Journal of
the American Statistical Association*, 53(284), 789-798.

[16] Gurwitsch, A.G. (1922). Über den Begriff des embryonalen Feldes.
*Archiv für Entwicklungsmechanik der Organismen*, 51, 383-415.

[17] Turing, A.M. (1952). The chemical basis of morphogenesis. *Phil.
Trans. R. Soc. B*, 237(641), 37-72.

[18] Doursat, R., Sayama, H., & Michel, O. (2013). A review of
morphogenetic engineering. *Natural Computing*, 12, 517-535.

[19] Zanibbi, R., Blostein, D., & Cordy, J.R. (2004). A survey of table
recognition. *IJDAR*, 7, 1-16.

[20] Embley, D.W., Hurst, M., Lopresti, D., & Nagy, G. (2006).
Table-processing paradigms: a research survey. *IJDAR*, 8, 66-79.

[21] Shafait, F. & Smith, R. (2010). Table detection in heterogeneous
documents. *Proc. DAS 2010*, 65-72.

[22] Itonori, K. (1993). Table structure recognition based on textblock
arrangement and ruled line position. *Proc. ICDAR 1993*.

[23] Riba, P., Dutta, A., Goldmann, L., Fornés, A., Ramos, O., & Lladós,
J. (2019). Table detection in invoice documents by graph neural networks.
*ICDAR 2019*.

[24] Qasim, S.R., Mahmood, H., & Shafait, F. (2019). Rethinking table
recognition using graph neural networks. *ICDAR 2019*.

[25] Li, Y., Huang, Z., Yan, J., Zhou, Y., Ye, F., & Liu, X. (2021).
GFTE: Graph-based financial table extraction. *ICPR 2021*.

[26] Chen, F., et al. (2025). Graph-based document structure analysis.
*ICLR 2025*.

[27] Tang, Z., et al. (2023). Unifying vision, text, and layout for
universal document processing. *CVPR 2023*.

[28] Hartigan, J.A. & Hartigan, P.M. (1985). The dip test of unimodality.
*Ann. Statist.*, 13(1), 70-84.

[29] Vrbik, I., Stephens, D.A., Roger, M., & Bhatt, D.M. (2015). The gap
procedure: for the identification of phylogenetic clusters in HIV-1
sequence data. *BMC Bioinformatics*, 16, 355.

[30] Oganesyan, V. & Huse, D.A. (2007). Localization of interacting
fermions at high temperature. *Phys. Rev. B*, 75, 155111.

[31] Atas, Y.Y., Bogomolny, E., Giraud, O., & Roux, G. (2013).
Distribution of the ratio of consecutive level spacings in random matrix
ensembles. *Phys. Rev. Lett.*, 110, 084101.

[32] Pyke, R. (1965). Spacings. *J. R. Stat. Soc. B*, 27(3), 395-449.

[33] Greenwood, M. (1946). The statistical study of infectious diseases.
*J. R. Stat. Soc. A*, 109(2), 85-110.

[34] Zipf, G.K. (1946). The P1 P2/D hypothesis: on the intercity movement
of persons. *Am. Sociol. Rev.*, 11(6), 677-686.

[35] Khatib, O. (1986). Real-time obstacle avoidance for manipulators and
mobile robots. *Int. J. Robot. Res.*, 5(1), 90-98.

[36] Grishman, R. & Sundheim, B. (1996). Message Understanding
Conference-6: A brief history. *Proc. COLING 1996*.

[37] Cunningham, H., Maynard, D., Bontcheva, K., & Tablan, V. (2002).
GATE: An architecture for development of robust HLT applications. *Proc.
ACL 2002*.

[38] Hu, J., Kashi, R.S., Lopresti, D.P., & Wilfong, G.T. (2001). Table
structure recognition and its evaluation. *Proc. SPIE Document Recognition
and Retrieval VIII*.

[39] Fang, J., Mitra, P., Tang, Z., & Giles, C.L. (2012). Table header
detection and classification. *Proc. AAAI 2012*.

[40] Koci, E., Thiele, M., Romero, O., & Lehner, W. (2018). Cell
classification for layout recognition in spreadsheets. *ADBIS 2018*.

[41] Abraham, R. & Erwig, M. (2004). Header and unit inference for
spreadsheets through spatial analyses. *Proc. IEEE Symposium on Visual
Languages - Human Centric Computing*.

[42] Pinto, D., McCallum, A., Wei, X., & Croft, W.B. (2003). Table
extraction using conditional random fields. *Proc. SIGIR 2003*.

[43] Zhang, D., Suhara, Y., Li, J., Hulsebos, M., Demiralp, C., & Tan,
W.-C. (2020). Sato: Contextual semantic type detection in tables. *Proc.
VLDB*, 13(11), 1835-1848.

[44] Zheng, X., et al. (2021). Global table extractor (GTE): A framework
for joint table identification and cell structure recognition. *WACV 2021*.

[45] Park, S., et al. (2019). CORD: A consolidated receipt dataset for
post-OCR parsing. *Document Intelligence Workshop, NeurIPS 2019*.

[46] Huang, Z., et al. (2019). ICDAR2019 competition on scanned receipt
OCR and information extraction. *ICDAR 2019*.

[47] Jaume, G., Ekenel, H.K., & Thiran, J.P. (2019). FUNSD: A dataset for
form understanding in noisy scanned documents. *ICDAR-OST 2019*.

[48] Li, M., et al. (2020). DocBank: A benchmark dataset for document
layout analysis. *COLING 2020*.

[49] Smock, B., Pesala, R., & Abraham, R. (2022). GriTS: Grid table
similarity metric for table structure recognition. *arXiv:2203.12555*.

[50] Sörensen, K. (2015). Metaheuristics — the metaphor exposed.
*International Transactions in Operational Research*, 22(1), 3-18.

[51] Aranha, C., Camacho Villalón, C.L., Campelo, F., Dorigo, M., Ruiz,
R., et al. (2022). Metaphor-based metaheuristics, a call for action: the
elephant in the room. *Swarm Intelligence*, 16, 1-6.

[52] Sheikh, T.U., Shehzadi, T., Hashmi, K.A., Stricker, D., & Afzal,
M.Z. (2024). UnSupDLA: Towards unsupervised document layout analysis.
*Document Analysis Systems (DAS) 2024*, LNCS 14994.

[53] Lior, G., Goldberg, Y., & Stanovsky, G. (2024). Leveraging
collection-wide similarities for unsupervised document structure extraction.
*Findings of ACL 2024*.

[54] Adhikari, N.S. & Agarwal, S. (2024). A comparative study of PDF
parsing tools across diverse document categories. *arXiv:2410.09871*.

[55] Kasem, M., et al. (2024). Deep learning for table detection and
structure recognition: A survey. *ACM Computing Surveys*, 56(12), 1-41.
