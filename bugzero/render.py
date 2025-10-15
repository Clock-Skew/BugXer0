"""Output helpers for CLI rendering."""

from __future__ import annotations

import json
import sys
from typing import Iterable, TextIO

from .types import SearchResult


def render_results(
    results: Iterable[SearchResult],
    *,
    mode: str = "table",
    stream: TextIO = sys.stdout,
) -> None:
    results = list(results)
    if mode == "json":
        json.dump([_result_to_dict(item) for item in results], stream, indent=2)
        stream.write("\n")
        return

    if not results:
        stream.write("No matches found.\n")
        return

    for item in results:
        stream.write(f"{item.repository} :: {item.path} (score {item.score:.2f})\n")
        stream.write(f"  {item.url}\n")
        if item.snippet:
            snippet = item.snippet.replace("\n", "\n  ")
            stream.write(f"  Snippet:\n  {snippet}\n")
        stream.write("\n")


def _result_to_dict(result: SearchResult) -> dict:
    return {
        "repository": result.repository,
        "path": result.path,
        "url": result.url,
        "score": result.score,
        "snippet": result.snippet,
    }


def serialize_results(results: Iterable[SearchResult]) -> list[dict]:
    return [_result_to_dict(item) for item in results]

