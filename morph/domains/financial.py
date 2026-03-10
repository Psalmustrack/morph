"""
Financial domain configuration.

Vocabulary and patterns for financial reports, balance sheets, income statements,
earnings reports, and financial analyses.
"""

from .base import DomainConfig


FINANCIAL = DomainConfig(
    name="financial",

    # No model codes in financial documents
    model_patterns=[],
    size_patterns=[],

    # Financial vocabulary
    spec_terms={
        # Income statement
        'revenue', 'income', 'sales', 'earnings',
        'profit', 'loss', 'margin', 'ebitda', 'ebit',
        'operating', 'gross', 'net',
        # Balance sheet
        'assets', 'liabilities', 'equity', 'capital',
        'cash', 'debt', 'inventory', 'receivables',
        'payables', 'goodwill', 'depreciation',
        'current', 'non-current', 'short-term', 'long-term',
        # Cash flow
        'inflow', 'outflow', 'financing', 'investing',
        'dividend', 'capex', 'opex',
        # Metrics
        'ratio', 'return', 'roe', 'roa', 'roi',
        'eps', 'pe', 'multiple', 'valuation',
        'growth', 'yield', 'turnover',
        # Time periods
        'q1', 'q2', 'q3', 'q4', 'fy', 'ytd',
        'quarter', 'annual', 'fiscal', 'period',
        # General
        'total', 'subtotal', 'consolidated',
        'adjusted', 'reported', 'pro forma',
    },

    spec_substrings={
        'balance sheet', 'income statement', 'cash flow',
        'shareholder', 'stockholder', 'equity',
        'operating income', 'net income',
        'earnings per share', 'return on',
    },

    section_terms={
        'consolidated', 'statements', 'notes',
        'summary', 'highlights', 'overview',
        'financial position', 'results',
    },

    unit_set={
        # Currencies
        '$', '€', '£', '¥', 'usd', 'eur', 'gbp', 'jpy',
        # Scales
        'm', 'b', 'k', 'million', 'billion', 'thousand',
        'mn', 'bn', 'tn',
        # Ratios
        '%', 'x', 'per share', 'eps',
        # Other
        'shares', 'units',
    },

    exclude_patterns=[
        r'^page\s+\d+',
        r'^see\s+note',
        r'^\d{4}$',  # Just year numbers
    ],

    use_fuzzy=True,
    require_models=False,  # No MODEL particles needed
)
