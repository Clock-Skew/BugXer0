"""Saved query management."""

from __future__ import annotations

import json
from collections import OrderedDict
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

from .config import DEFAULT_CONFIG_PATH
from .types import QuerySpec, Qualifier

QUERIES_FILENAME = "queries.json"


def _default_queries_path() -> Path:
    return DEFAULT_CONFIG_PATH.with_name(QUERIES_FILENAME)


def _read_queries(path: Path) -> OrderedDict[str, dict]:
    if not path.exists():
        return OrderedDict()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    items = payload.get("queries")
    if not isinstance(items, list):
        return OrderedDict()
    ordered: OrderedDict[str, dict] = OrderedDict()
    for entry in items:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            continue
        ordered[name] = {
            "query": str(entry.get("query") or ""),
            "qualifiers": entry.get("qualifiers") or {},
        }
    return ordered


def _write_queries(path: Path, items: OrderedDict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "queries": [
            {"name": name, **data} for name, data in items.items()
        ]
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def list_queries(*, path: Optional[Path] = None) -> List[str]:
    data = _read_queries(path or _default_queries_path())
    return list(data.keys())


def get_query_specs(
    names: Optional[Iterable[str]] = None,
    *,
    path: Optional[Path] = None,
) -> List[Tuple[str, QuerySpec]]:
    data = _read_queries(path or _default_queries_path())
    if names is None:
        selected = data.items()
    else:
        desired = [name.strip() for name in names if name.strip()]
        selected = [(name, data[name]) for name in desired if name in data]
    specs: List[Tuple[str, QuerySpec]] = []
    for name, entry in selected:
        qualifiers_map = entry.get("qualifiers") or {}
        qualifiers: List[Qualifier] = [
            (str(key), str(value)) for key, value in qualifiers_map.items()
        ]
        specs.append((name, QuerySpec(entry.get("query", ""), qualifiers)))
    return specs


def save_query(
    name: str,
    query: str,
    qualifiers: Optional[dict[str, str]] = None,
    *,
    path: Optional[Path] = None,
) -> None:
    path = path or _default_queries_path()
    data = _read_queries(path)
    data[name] = {
        "query": query,
        "qualifiers": qualifiers or {},
    }
    _write_queries(path, data)


def delete_query(name: str, *, path: Optional[Path] = None) -> bool:
    path = path or _default_queries_path()
    data = _read_queries(path)
    if name not in data:
        return False
    del data[name]
    _write_queries(path, data)
    return True

