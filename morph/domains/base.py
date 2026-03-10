"""
Base domain configuration class.
"""

from dataclasses import dataclass, field
from typing import List, Set, Optional
import re


@dataclass
class DomainConfig:
    """Base domain configuration for Morph extraction.

    A domain defines:
    - Patterns for entity detection (model codes, size headers)
    - Vocabulary for spec/section recognition
    - Unit sets
    - Behavior flags (fuzzy matching, model requirements)

    Attributes:
        name: Domain identifier (e.g., "hvac", "scientific")
        model_patterns: Regex patterns for MODEL entity detection
        size_patterns: Regex patterns for SIZE_HEADER detection
        spec_terms: Vocabulary for SPEC_LABEL detection
        spec_substrings: Substrings for SPEC_LABEL detection
        section_terms: Vocabulary for SECTION detection
        unit_set: Set of recognized units of measurement
        exclude_patterns: Patterns to exclude from processing
        use_fuzzy: Enable fuzzy matching for typo tolerance
        require_models: Whether extract_page needs MODEL particles
    """

    name: str

    # Patterns (will be compiled to regex)
    model_patterns: List[str] = field(default_factory=list)
    size_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)

    # Vocabulary sets
    spec_terms: Set[str] = field(default_factory=set)
    spec_substrings: Set[str] = field(default_factory=set)
    section_terms: Set[str] = field(default_factory=set)
    unit_set: Set[str] = field(default_factory=set)

    # Behavior flags
    use_fuzzy: bool = True
    require_models: bool = True

    # Compiled patterns (filled by compile_patterns())
    _model_patterns_compiled: Optional[List[re.Pattern]] = field(default=None, repr=False, init=False)
    _size_patterns_compiled: Optional[List[re.Pattern]] = field(default=None, repr=False, init=False)
    _exclude_patterns_compiled: Optional[List[re.Pattern]] = field(default=None, repr=False, init=False)

    def __post_init__(self):
        """Compile regex patterns after initialization."""
        self.compile_patterns()

    def compile_patterns(self):
        """Compile string patterns to regex objects."""
        if self.model_patterns:
            self._model_patterns_compiled = [re.compile(p) for p in self.model_patterns]
        else:
            self._model_patterns_compiled = []

        if self.size_patterns:
            self._size_patterns_compiled = [re.compile(p) for p in self.size_patterns]
        else:
            self._size_patterns_compiled = []

        if self.exclude_patterns:
            self._exclude_patterns_compiled = [re.compile(p) for p in self.exclude_patterns]
        else:
            self._exclude_patterns_compiled = []

    def get_model_patterns(self) -> List[re.Pattern]:
        """Get compiled model patterns."""
        return self._model_patterns_compiled or []

    def get_size_patterns(self) -> List[re.Pattern]:
        """Get compiled size patterns."""
        return self._size_patterns_compiled or []

    def get_exclude_patterns(self) -> List[re.Pattern]:
        """Get compiled exclude patterns."""
        return self._exclude_patterns_compiled or []

    def copy(self):
        """Create a copy of this domain config for modification."""
        import copy
        return copy.deepcopy(self)
