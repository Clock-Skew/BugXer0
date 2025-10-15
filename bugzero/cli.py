"""Command-line interface for BugZero v2."""

from __future__ import annotations

import argparse
import json
import sys
from getpass import getpass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from .config import delete_token, resolve_token, store_token, token_status
from .github import GitHubAPIError, GitHubSearchClient
from .queries import delete_query, get_query_specs, list_queries, save_query
from .render import render_results, serialize_results
from .types import QuerySpec, Qualifier


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bugzero", description="BugZero GitHub search CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_search_parser(subparsers)
    _add_sweep_parser(subparsers)
    _add_queries_parser(subparsers)
    _add_token_parser(subparsers)

    return parser


def _add_search_parser(subparsers: argparse._SubParsersAction) -> None:
    search = subparsers.add_parser("search", help="Run a direct GitHub code search")
    source = search.add_mutually_exclusive_group(required=True)
    source.add_argument("-q", "--query", help="Search query string")
    source.add_argument("--query-file", help="File containing the search query")
    search.add_argument(
        "--split-lines",
        action="store_true",
        help="Treat each non-empty line as an individual query",
    )
    search.add_argument(
        "-Q",
        "--qualifier",
        action="append",
        default=[],
        metavar="key=value",
        help="Add GitHub search qualifier (may be repeated)",
    )
    search.add_argument("--per-page", type=int, default=30, help="Items per API page (default: 30)")
    search.add_argument("--pages", type=int, default=1, help="Number of pages to fetch")
    search.add_argument("--output", choices=["table", "json"], default="table")
    search.add_argument("--token", help="Explicit GitHub token")
    search.set_defaults(func=_handle_search)


def _add_sweep_parser(subparsers: argparse._SubParsersAction) -> None:
    sweep = subparsers.add_parser("sweep", help="Run saved queries in sequence")
    sweep.add_argument("names", nargs="*", help="Specific query names to run (default: all)")
    sweep.add_argument(
        "-Q",
        "--qualifier",
        action="append",
        default=[],
        metavar="key=value",
        help="Extra qualifiers applied to every query",
    )
    sweep.add_argument("--per-page", type=int, default=30)
    sweep.add_argument("--pages", type=int, default=1)
    sweep.add_argument("--output", choices=["table", "json"], default="table")
    sweep.add_argument("--token", help="Explicit GitHub token")
    sweep.set_defaults(func=_handle_sweep)


def _add_queries_parser(subparsers: argparse._SubParsersAction) -> None:
    queries = subparsers.add_parser("queries", help="Manage saved queries")
    queries_sub = queries.add_subparsers(dest="subcommand", required=True)

    add_cmd = queries_sub.add_parser("add", help="Add or update a saved query")
    add_cmd.add_argument("name", help="Name for the saved query")
    source = add_cmd.add_mutually_exclusive_group(required=True)
    source.add_argument("-q", "--query", help="Query string")
    source.add_argument("--query-file", help="File containing the query")
    add_cmd.add_argument(
        "-Q",
        "--qualifier",
        action="append",
        default=[],
        metavar="key=value",
        help="Qualifiers stored with the query",
    )
    add_cmd.set_defaults(func=_handle_query_add)

    remove_cmd = queries_sub.add_parser("remove", help="Delete a saved query")
    remove_cmd.add_argument("names", nargs="+", help="Query names to remove")
    remove_cmd.set_defaults(func=_handle_query_remove)

    list_cmd = queries_sub.add_parser("list", help="List saved queries")
    list_cmd.set_defaults(func=_handle_query_list)


def _add_token_parser(subparsers: argparse._SubParsersAction) -> None:
    token = subparsers.add_parser("token", help="Manage GitHub tokens")
    token_sub = token.add_subparsers(dest="subcommand", required=True)

    set_cmd = token_sub.add_parser("set", help="Store a GitHub token in the config file")
    set_cmd.add_argument("--token", help="Token value (omit to be prompted securely)")
    set_cmd.set_defaults(func=_handle_token_set)

    clear_cmd = token_sub.add_parser("clear", help="Remove stored token")
    clear_cmd.set_defaults(func=_handle_token_clear)

    info_cmd = token_sub.add_parser("info", help="Show token sourcing details")
    info_cmd.set_defaults(func=_handle_token_info)


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except GitHubAPIError as exc:
        print(f"GitHub API error: {exc}", file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _handle_search(args: argparse.Namespace) -> int:
    qualifiers = _parse_qualifiers(args.qualifier)
    query_texts = _collect_query_texts(args.query, args.query_file)
    specs = _build_specs(query_texts, qualifiers, args.split_lines)
    if not specs:
        raise RuntimeError("No queries to execute")
    token = resolve_token(explicit=args.token)
    client = GitHubSearchClient(token)

    if args.output == "json":
        payload = []
        for spec in specs:
            results = client.search_code(
                spec, per_page=args.per_page, pages=args.pages
            )
            payload.append(
                {
                    "query": spec.build(),
                    "results": serialize_results(results),
                }
            )
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    for idx, spec in enumerate(specs, start=1):
        if len(specs) > 1:
            sys.stdout.write(f"=== Query {idx}: {spec.build()}\n")
        results = client.search_code(spec, per_page=args.per_page, pages=args.pages)
        render_results(results, mode=args.output)
    return 0


def _handle_sweep(args: argparse.Namespace) -> int:
    qualifiers = _parse_qualifiers(args.qualifier)
    specs = get_query_specs(args.names or None)
    if not specs:
        raise RuntimeError("No saved queries found")
    token = resolve_token(explicit=args.token)
    client = GitHubSearchClient(token)

    if args.output == "json":
        payload = []
        for name, spec in specs:
            merged = QuerySpec(spec.query, tuple(spec.qualifiers) + qualifiers)
            results = client.search_code(
                merged, per_page=args.per_page, pages=args.pages
            )
            payload.append(
                {
                    "name": name,
                    "query": merged.build(),
                    "results": serialize_results(results),
                }
            )
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    for name, spec in specs:
        merged = QuerySpec(spec.query, tuple(spec.qualifiers) + qualifiers)
        sys.stdout.write(f"=== {name}: {merged.build()}\n")
        results = client.search_code(merged, per_page=args.per_page, pages=args.pages)
        render_results(results, mode=args.output)
    return 0


def _handle_query_add(args: argparse.Namespace) -> int:
    qualifiers = dict(_parse_qualifiers(args.qualifier))
    query_texts = _collect_query_texts(args.query, args.query_file)
    query_text = "\n".join(query_texts).strip()
    if not query_text:
        raise RuntimeError("Query text is empty")
    save_query(args.name, query_text, qualifiers)
    print(f"Saved query '{args.name}'")
    return 0


def _handle_query_remove(args: argparse.Namespace) -> int:
    removed = 0
    for name in args.names:
        if delete_query(name):
            print(f"Removed query '{name}'")
            removed += 1
        else:
            print(f"Query '{name}' not found", file=sys.stderr)
    if removed == 0:
        return 1
    return 0


def _handle_query_list(_: argparse.Namespace) -> int:
    names = list_queries()
    if not names:
        print("No saved queries.")
        return 0
    for name in names:
        print(name)
    return 0


def _handle_token_set(args: argparse.Namespace) -> int:
    token = args.token or getpass("GitHub token: ")
    path = store_token(token)
    print(f"Token stored at {path}")
    return 0


def _handle_token_clear(_: argparse.Namespace) -> int:
    delete_token()
    print("Stored token cleared.")
    return 0


def _handle_token_info(_: argparse.Namespace) -> int:
    status = token_status()
    if status["env"]:
        print("Token available via GITHUB_TOKEN environment variable.")
    if status["config_path"]:
        print(f"Token stored at {status['config_path']}")
    if not status["env"] and not status["config_path"]:
        print("No token sources found.")
    return 0


def _parse_qualifiers(raw: Sequence[str]) -> Tuple[Qualifier, ...]:
    qualifiers: List[Qualifier] = []
    for entry in raw:
        if "=" in entry:
            key, value = entry.split("=", 1)
        else:
            key, value = entry, ""
        key = key.strip()
        if not key:
            continue
        qualifiers.append((key, value.strip()))
    return tuple(qualifiers)


def _collect_query_texts(*sources: str | None) -> List[str]:
    texts: List[str] = []
    if sources[0]:
        texts.append(str(sources[0]))
    file_path = sources[1]
    if file_path:
        path = Path(file_path)
        texts.append(path.read_text(encoding="utf-8"))
    return texts


def _build_specs(
    query_texts: Sequence[str],
    qualifiers: Tuple[Qualifier, ...],
    split_lines: bool,
) -> List[QuerySpec]:
    specs: List[QuerySpec] = []
    if split_lines:
        for text in query_texts:
            for line in text.splitlines():
                stripped = line.strip()
                if stripped:
                    specs.append(QuerySpec(stripped, qualifiers))
    else:
        merged = "\n".join(query_texts).strip()
        if merged:
            specs.append(QuerySpec(merged, qualifiers))
    return specs


if __name__ == "__main__":
    sys.exit(main())
