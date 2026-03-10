"""
Scientific domain configuration.

Vocabulary and patterns for scientific research papers, medical studies,
clinical trials, and academic publications.
"""

from .base import DomainConfig


SCIENTIFIC = DomainConfig(
    name="scientific",

    # No model codes in scientific papers
    model_patterns=[],
    size_patterns=[],

    # Scientific vocabulary
    spec_terms={
        # Study participants
        'cases', 'controls', 'subjects', 'participants', 'patients',
        'cohort', 'sample', 'population', 'group',
        # Demographics
        'age', 'years', 'gender', 'male', 'female', 'sex',
        'race', 'ethnicity', 'african-american', 'caucasian',
        'birth', 'maternal', 'paternal', 'gestational',
        # Statistics
        'mean', 'median', 'sd', 'se', 'ci', 'range', 'iqr',
        'p-value', 'p', 'odds', 'ratio', 'or', 'hr', 'rr',
        'correlation', 'regression', 'variance', 'deviation',
        # Study design
        'treatment', 'control', 'placebo', 'intervention',
        'baseline', 'follow-up', 'outcome', 'endpoint',
        'randomized', 'blinded', 'trial', 'study',
        # Measurements
        'total', 'n', 'percentage', 'percent', 'frequency',
        'prevalence', 'incidence', 'risk', 'rate',
        # Medical
        'diagnosis', 'disease', 'condition', 'symptom',
        'treatment', 'therapy', 'medication', 'dose',
        'adverse', 'event', 'complication',
    },

    spec_substrings={
        'african-american', 'caucasian', 'hispanic', 'asian',
        'birth order', 'maternal age', 'gestational',
        'confidence interval', 'standard deviation',
        'follow-up', 'baseline', 'end-point',
    },

    section_terms={
        'methods', 'results', 'discussion', 'conclusions',
        'table', 'figure', 'supplementary', 'appendix',
        'introduction', 'background', 'objectives',
        'materials', 'procedures', 'analysis',
        'findings', 'interpretation', 'limitations',
    },

    unit_set={
        '%', 'years', 'months', 'days', 'weeks',
        'kg', 'g', 'mg', 'μg', 'ng',
        'l', 'ml', 'μl',
        'cm', 'mm', 'm',
        'mmol', 'μmol', 'nmol',
        'iu', 'u',
        'n', 'total',
    },

    exclude_patterns=[
        r'^\(\d+\)$',  # Note references like (1), (2)
        r'^[A-Z]{2,}$',  # All-caps abbreviations (keep as TEXT)
        r'^p\s*[<>=]',  # P-values (keep as TEXT or parse separately)
    ],

    use_fuzzy=True,
    require_models=False,  # No MODEL particles needed for scientific tables
)
