"""
Domain-specific configurations for Morph.

Each domain module defines vocabulary, patterns, and behavior for a specific
type of document (HVAC catalogs, scientific papers, financial reports, etc.).
"""

from .base import DomainConfig
from .hvac import HVAC
from .scientific import SCIENTIFIC
from .financial import FINANCIAL
from .universal import UNIVERSAL

__all__ = [
    'DomainConfig',
    'HVAC',
    'SCIENTIFIC',
    'FINANCIAL',
    'UNIVERSAL',
]
