# Mathematical Foundations

> *Self-organising spatial inference for structured document parsing:
> a morphogenetic approach.*

This document presents the mathematical framework behind Morph.
Notation follows the convention: bold for vectors, italic for scalars,
blackboard bold for sets.

---

## 1. Document Space

A PDF page is a collection of **particles** — text spans with spatial
coordinates and an intrinsic type.  Formally:

```
P = {p_1, p_2, ..., p_N}

p_i = (x_i, y_i, z_i, tau_i, text_i)
```

Where:
- **(x, y)** are the centre coordinates of the text bounding box (px)
- **z** is the *value magnitude*: `z = log_10(|v| + 1)` for NUMERIC
  particles, or the median z of nearby NUMERIC for SPEC_LABEL
- **tau** is the particle type (one of 8 types, see below)
- **text** is the raw string content

The key insight: **document space is three-dimensional**.  The x,y plane
encodes *where* a value is; the z axis encodes *what magnitude* it has.
Values of different scales (COP ~ 4.0 → z ~ 0.7; weight ~ 25 kg → z ~ 1.4;
noise ~ 55 dB → z ~ 1.7; prices ~ 5000 → z ~ 3.7) naturally separate
along z without any explicit classification.

---

## 2. Type System (Layer 1)

Classification cascade — first match wins:

| Priority | Type | Rule | Example |
|----------|------|------|---------|
| 0 | EXCLUDED | Exclusion regex | "Fai clic qui" |
| 1 | SIZE_HEADER | Brand size patterns | "50B" |
| 2 | MODEL | Brand model patterns | "RAS-4FSXNME" |
| 3 | KW_HEADER | "kW" in header context | "kW" |
| 4 | UNIT | Lookup in UNIT_SET | "dB(A)" |
| 5 | NUMERIC | Decimal/integer/range regex | "4.50" |
| 6 | SECTION | Section term match | "Specifications" |
| 7 | SPEC_LABEL | Spec term/substring match | "Sound pressure" |
| 8 | TEXT | Default | Everything else |

**No training, no model weights.**  Classification is deterministic from
vocabulary sets and compiled regex patterns.  The type system is the
*genome* — it encodes what a particle *could be* based on its content.

---

## 3. Spatial Sensing (Layer 1b)

Particles may be *promoted* from TEXT to a structural type based on
spatial context.  This is the key innovation: **type emerges from
relative position, not absolute content**.

### 3.1 Column Detection

A vertical cluster of 3+ NUMERIC particles aligned on X defines a
*detected column*:

```
C_j = {p_i : tau_i = NUMERIC, |x_i - mu_j| < theta_x}

|C_j| >= 3
```

Where theta_x is an adaptive tolerance computed from local row spacing:

```
theta_x = clamp(row_spacing / 2, 5, 25)  [px]
```

The X clustering uses agglomerative grouping: particles are sorted by x,
and each is assigned to the nearest cluster within threshold, or seeds a
new cluster.

### 3.2 Header Promotion

A TEXT particle directly above a detected column is promoted to MODEL:

```
If tau_k = TEXT and exists C_j such that:
    |x_k - mu_j| < theta_x   (horizontally aligned)
    y_k < min(y : p in C_j)   (above the column)
    min(y : p in C_j) - y_k < 2 * row_spacing   (close)
Then:
    tau_k <- MODEL
```

### 3.3 Spec-Label Promotion

A TEXT particle to the left of NUMERIC particles on the same row is
promoted to SPEC_LABEL:

```
If tau_k = TEXT and count({p_i : tau_i = NUMERIC, |y_i - y_k| < theta_y, x_i > x_k}) >= 2:
Then:
    tau_k <- SPEC_LABEL
```

The minimum count of 2 is **lateral inhibition**: isolated text-number
pairs (e.g., page numbers) are not promoted.

### 3.4 Section Promotion

TEXT with font size > mean + 2 sigma is promoted to SECTION:

```
If tau_k = TEXT and font_size_k > mu_font + 2 * sigma_font:
Then:
    tau_k <- SECTION
```

### 3.5 Invariant

Sensing *only promotes* — it never changes NUMERIC, UNIT, MODEL, or any
other already-typed particle.  This guarantees monotonic information gain:
information from Layer 1 is preserved, Layer 1b only adds.

---

## 4. The Morphogenetic Field Equation (Layer 2)

The morphogenetic field equation maps NUMERIC values to structural
entities (MODEL, SPEC_LABEL):

```
Phi(i -> j) = W(tau_i, tau_j) * A(i, j) / d(i, j)^alpha
```

### 4.1 Distance Function

Distance is computed in the full 3D document space:

```
d(i, j) = sqrt( (dx / sigma_x)^2 + (dy / sigma_y)^2 + (lambda_z * dz_norm)^2 )
```

Where:
- **dx, dy** are spatial distances in pixels
- **dz_norm** = |z_i - z_j| is the magnitude difference
- **sigma_x** = 30 px (column width scale)
- **sigma_y** = 6 px (row height scale)
- **lambda_z** is auto-calibrated (see 4.4)

### 4.2 Interaction Matrix W

The interaction matrix encodes how strongly two particle types "want"
to be connected:

```
W(NUMERIC, SPEC_LABEL)  = 1.0    — strong row attraction
W(NUMERIC, SIZE_HEADER) = 0.8    — column attraction
W(NUMERIC, MODEL)       = 0.6    — column attraction
W(NUMERIC, KW_HEADER)   = 0.8    — column attraction
W(NUMERIC, UNIT)        = 0.7    — row attraction (units)
W(NUMERIC, NUMERIC)     = 0.3    — weak clustering
W(NUMERIC, TEXT)        = -0.1   — slight repulsion
W(NUMERIC, SECTION)     = 0.0    — neutral
```

### 4.3 Directional Anisotropy A

The alignment factor captures the directional preference of document
layout:

```
A_row(i, j) = exp(-(dy^2) / sigma_y^2) * D_left(i, j)
A_col(i, j) = exp(-(dx^2) / sigma_x^2) * D_above(i, j)
```

Where:
- **D_left** = 1.2 if j is left of i, 0.8 otherwise (specs are left
  of values)
- **D_above** = 1.2 if j is above i, 0.8 otherwise (headers are above
  values)

These directional bonuses encode the universal layout invariant:
**labels are to the left, headers are above**.

### 4.4 lambda_z Auto-Calibration

The z-axis weight is calibrated from the geometry of values on the page:

```
lambda_z = sigma_y / median_z_spread_per_row
```

Logic: NUMERIC particles on the same Y row are values of the same spec
type for different models (e.g., COP model A = 4.0, model B = 4.2).
Their z-spread is small.  lambda_z scales this spread to the Y distance
between rows, making z discriminative:

- If z_spread is small -> lambda high -> z discriminates strongly
- If z_spread is large -> lambda low -> z doesn't interfere
- lambda_z is clamped to [10, 500]

When lambda_z = 0, the field reduces to pure 2D (position only).

### 4.5 Distance Decay: alpha = 0.5

The decay exponent alpha = 0.5 (square root) is deliberately weaker
than gravitational decay (alpha = 2) or Coulomb decay (alpha = 1).

Rationale: document structure is *extended*.  A SPEC_LABEL at 300px
distance is still "the same row" on an A4 page.  Sub-linear decay
allows distant but well-aligned particles to bind — alignment (A)
dominates over distance at large separations, which is the correct
physical behaviour for tabular data.

---

## 5. Universal Boundary Law

For column splitting and row splitting, a single principle applies:

> **A gap is a cell boundary when `gap > avg_element_size * k`.**

### 5.1 Column Boundaries (k_x = 0.3)

Given sorted x-coordinates of particles in a row:

```
gaps = [x_{i+1} - x_i  for i in 0..n-1]
avg_size = mean(width_i  for all particles in row)
threshold = avg_size * k_x

boundary at gap_i  iff  gap_i > threshold
```

With k_x = 0.3, this achieves **66.2% column
exact match** on PubTables-1M without any learned parameters.

### 5.2 Row Boundaries (k_y = 0.05)

For rows, the same principle applies with k_y = 0.05:

```
gaps_y = sorted vertical gaps between consecutive particles in a column
threshold_y = avg_height * k_y
```

k_y << k_x because vertical spacing in tables is typically tighter
relative to element height than horizontal spacing relative to element
width.

### 5.3 The Max-Ratio-Jump Variant

An adaptive alternative replaces the fixed k with the natural break
in the gap distribution:

```
sorted_gaps = sort(gaps)
ratios = [g_{i+1} / g_i  for i in 0..m-1]
threshold = sorted_gaps[argmax(ratios)]
```

The maximum relative jump identifies the natural boundary between
intra-cell spacing and inter-cell spacing without any constant.

Results: +0.2 pp on PubTables-1M (79.7 -> 79.9%), +0.5 pp on
FinTabNet (77.6 -> 78.1%), reducing the cross-domain gap from
2.1 to 1.8 pp.

---

## 6. Cross-Page Merge (Endocrine System)

Multi-page tables are detected by column fingerprinting:

```
fingerprint(page) = sorted([tau_col_1, tau_col_2, ..., tau_col_m])
```

Where tau_col is the dominant type in each detected column.
Consecutive pages with compatible fingerprints (>= 70% overlap in
column types and entity names) are fused.  Lookback window: 3 pages
(to skip intervening pages with different layouts).

---

## 7. Constants Summary

| Symbol | Value | Role |
|--------|-------|------|
| alpha | 0.5 | Distance decay exponent |
| sigma_y | 6 px | Row tolerance |
| sigma_x | 30 px | Column tolerance |
| lambda_z | auto (50 default) | z-axis weight |
| k_x | 0.3 | Column boundary constant |
| k_y | 0.05 | Row boundary constant |
| W | 8x8 matrix | Particle-type interaction |
| D_left | 1.2 / 0.8 | Left directional bonus |
| D_above | 1.2 / 0.8 | Above directional bonus |
| theta_x | clamp(row_spacing/2, 5, 25) | Column detection tolerance |
| min_col_count | 3 | Min particles for column |
| min_spec_pairs | 2 | Min pairs for lateral inhibition |
| font_threshold | mu + 2*sigma | Section promotion |

All constants are invariant across brands and documents.  They were
derived empirically from the first 5 catalogues (Hitachi) and validated
without modification on 46 catalogues across 5 brands (Hitachi, Daikin,
Toshiba, Mitsubishi Electric, Midea) and two academic benchmarks
(PubTables-1M, FinTabNet.c).

---

## 8. Biological Analogies

The naming convention throughout Morph maps computational concepts
to biological processes:

| Computational Concept | Biological Analogy | Module |
|----------------------|-------------------|--------|
| Lexical classification | Gene expression | typify.py |
| Spatial promotion | Cellular differentiation | sense.py |
| Field-based binding | Morphogenetic field | field.py |
| z-axis auto-calibration | Turing concentration gradient | field.py |
| Minimum cluster threshold | Lateral inhibition | sense.py |
| Cross-page fingerprinting | Endocrine signalling | pipeline.py |
| Adaptive tolerance | Thermoregulation | sense.py |
| Early page rejection | Apoptosis (programmed cell death) | pipeline.py |

These are not mere metaphors.  Each analogy maps to a specific
mathematical operation that was *inspired by* the biological process
and shares its key structural property: **local rules producing
global order without central coordination**.

---

## 9. Complexity Analysis

| Operation | Complexity | Bottleneck |
|-----------|-----------|------------|
| Typify (Layer 1) | O(N * P) | N particles, P regex patterns |
| Sense (Layer 1b) | O(N * log N) | Clustering + binary search |
| Field (Layer 2) | O(N * M) | N NUMERIC x M structural |
| Column split | O(N * log N) | Sort + scan per row |
| Row split | O(N * log N) | Sort + scan per column |
| Cross-page merge | O(P * C) | P pages x C columns |

Where N ~ 50-500 particles per page (typical), M ~ 5-50 structural
particles, P ~ 30-80 brand regex patterns, C ~ 3-20 columns.

In practice, the entire pipeline processes **~50 pages/second** on
an i7-10850H CPU with no GPU.

---

*Tacu, E. (2026). Self-organising spatial inference for structured
document parsing: a morphogenetic approach. Unpublished manuscript.*
