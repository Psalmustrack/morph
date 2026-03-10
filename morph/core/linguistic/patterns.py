"""
Pattern Recognition Module - Universal linguistic patterns

This module detects universal patterns in text particles, independent of domain.
Patterns are geometric/structural, not semantic.

Examples of universal patterns:
- "XX-YY" → CODE_WITH_DASH (works for FXFA-25A, ISO-9001, etc)
- "xx(y)" → UNIT_WITH_PARENTHESIS (works for kg(m), dB(A), etc)
- "Xxx Yyy Zzz" → TITLE_CASE_PHRASE (works for any language)
- "XXX" → ALL_CAPS_CODE (works for any acronym/code)
"""

import re
import string
from typing import Dict, Any


def analyze_format(text: str) -> Dict[str, Any]:
    """
    Analyze the structural format of a text string.

    Returns universal format features, not domain-specific semantics.

    Args:
        text: Input text to analyze

    Returns:
        Dictionary with format features:
        - has_uppercase: Contains uppercase letters
        - has_lowercase: Contains lowercase letters
        - has_digits: Contains digits
        - has_punctuation: Contains punctuation
        - starts_uppercase: Starts with uppercase
        - all_uppercase: All letters are uppercase
        - length: Character count
        - word_count: Number of words
        - pattern: Recognized pattern type
    """
    if not text:
        return {
            'has_uppercase': False,
            'has_lowercase': False,
            'has_digits': False,
            'has_punctuation': False,
            'starts_uppercase': False,
            'all_uppercase': False,
            'length': 0,
            'word_count': 0,
            'pattern': 'EMPTY'
        }

    # Basic character analysis
    has_uppercase = any(c.isupper() for c in text)
    has_lowercase = any(c.islower() for c in text)
    has_digits = any(c.isdigit() for c in text)
    has_punctuation = any(c in string.punctuation for c in text)

    # Structure analysis
    starts_uppercase = text[0].isupper() if text else False
    letters_only = ''.join(c for c in text if c.isalpha())
    all_uppercase = letters_only.isupper() if letters_only else False

    # Word analysis
    words = text.split()
    word_count = len(words)

    # Pattern classification
    pattern = classify_pattern(text)

    return {
        'has_uppercase': has_uppercase,
        'has_lowercase': has_lowercase,
        'has_digits': has_digits,
        'has_punctuation': has_punctuation,
        'starts_uppercase': starts_uppercase,
        'all_uppercase': all_uppercase,
        'length': len(text),
        'word_count': word_count,
        'pattern': pattern
    }


def classify_pattern(text: str) -> str:
    """
    Classify text into universal structural patterns.

    These patterns are geometric/syntactic, not semantic.
    They work across domains and languages.

    Args:
        text: Input text

    Returns:
        Pattern type (string)
    """
    # Pattern: CODE-NUMBER-LETTER (e.g., FXFA-25A, ISO-9001)
    if re.match(r'^[A-Z]+-\d+[A-Z]?$', text):
        return 'CODE_WITH_DASH'

    # Pattern: LETTER-CODE-NUMBER (e.g., RAS-2HVRC3)
    if re.match(r'^[A-Z]+-[A-Z0-9]+$', text):
        return 'CODE_WITH_DASH'

    # Pattern: text(content) - typically units or notes (e.g., kg(m), dB(A))
    if re.match(r'^[a-z]+\([^)]+\)$', text, re.IGNORECASE):
        return 'UNIT_WITH_PARENTHESIS'

    # Pattern: single letter/number codes (e.g., R32, R410A, B12)
    if re.match(r'^[A-Z]\d+[A-Z]?$', text):
        return 'ALPHANUMERIC_CODE'

    # Pattern: dimensions XXxYYxZZ (e.g., 629x898x365)
    if re.match(r'^\d+x\d+x\d+$', text):
        return 'DIMENSIONS_3D'

    # Pattern: range XX-YY or XX/YY (e.g., 30/20, 90-115)
    if re.match(r'^\d+[-/]\d+$', text):
        return 'NUMERIC_RANGE'

    # Pattern: voltage/frequency (e.g., 1~230V 50Hz)
    if re.match(r'^\d+~\d+V \d+Hz$', text):
        return 'ELECTRICAL_SPEC'

    # Pattern: fraction format (e.g., 1/4-1/2, 3/8-5/8)
    if re.match(r'^\d+/\d+-\d+/\d+$', text):
        return 'FRACTION_RANGE'

    # Pattern: Title Case Phrase (multiple words, first letter caps)
    words = text.split()
    if len(words) >= 2 and all(w[0].isupper() if w else False for w in words):
        return 'TITLE_CASE_PHRASE'

    # Pattern: lowercase phrase (multiple words, all lowercase)
    if len(words) >= 2 and text.islower():
        return 'LOWERCASE_PHRASE'

    # Pattern: ALL CAPS (acronym or emphasis)
    letters_only = ''.join(c for c in text if c.isalpha())
    if letters_only and letters_only.isupper() and len(text) <= 10:
        return 'ALL_CAPS_CODE'

    # Pattern: pure numeric
    if text.replace(',', '.').replace('.', '').isdigit():
        return 'NUMERIC'

    # Pattern: numeric with comma (e.g., 1,3 or 5,6)
    if re.match(r'^\d+,\d+$', text):
        return 'NUMERIC_DECIMAL'

    return 'UNKNOWN'


def is_likely_unit(text: str) -> bool:
    """
    Check if text is likely a unit of measurement (universal check).

    Args:
        text: Input text

    Returns:
        True if likely a unit
    """
    fmt = analyze_format(text)

    # Units are typically short and contain parentheses
    if fmt['pattern'] == 'UNIT_WITH_PARENTHESIS':
        return True

    # Or single short words with specific chars
    if fmt['length'] <= 6 and fmt['has_punctuation']:
        return True

    return False


def is_likely_header(text: str) -> bool:
    """
    Check if text is likely a table header (universal check).

    Args:
        text: Input text

    Returns:
        True if likely a header
    """
    fmt = analyze_format(text)

    # Headers are typically:
    # - Multi-word phrases
    # - Title case
    # - Longer than 15 characters

    if fmt['pattern'] == 'TITLE_CASE_PHRASE' and fmt['length'] >= 15:
        return True

    if fmt['word_count'] >= 3 and fmt['starts_uppercase']:
        return True

    return False


def is_likely_value(text: str) -> bool:
    """
    Check if text is likely a data value (universal check).

    Args:
        text: Input text

    Returns:
        True if likely a value
    """
    fmt = analyze_format(text)

    # Values are typically:
    # - Numeric
    # - Short codes
    # - Single words

    if fmt['pattern'] in ['NUMERIC', 'NUMERIC_DECIMAL', 'ALPHANUMERIC_CODE']:
        return True

    if fmt['length'] <= 10 and fmt['word_count'] == 1:
        return True

    return False
