"""Core dataclasses and typing helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence, Tuple

Qualifier = Tuple[str, str]


@dataclass(slots=True)
class QuerySpec:
    """Represents a single GitHub code search query."""

    query: str
    qualifiers: Sequence[Qualifier] = field(default_factory=tuple)

    def build(self) -> str:
        parts: List[str] = []
        query_text = " ".join(self.query.split())
        if query_text:
            parts.append(query_text)
        for qualifier, value in self.qualifiers:
            qualifier = qualifier.strip()
            value = value.strip()
            if not qualifier:
                continue
            token = qualifier if not value else f"{qualifier}:{value}"
            parts.append(token)
        return " ".join(parts)


@dataclass(slots=True)
class SearchResult:
    """Normalized representation of a GitHub search hit."""

    repository: str
    path: str
    url: str
    score: float
    snippet: str | None = None


def merge_qualifiers(*groups: Iterable[Qualifier]) -> Tuple[Qualifier, ...]:
    """Flatten several qualifier iterables into a tuple, preserving order."""
    combined: List[Qualifier] = []
    for group in groups:
        combined.extend(group)
    return tuple(combined)
