"""GitHub API utilities."""

from __future__ import annotations

import time
from typing import Iterable, List, Sequence

import requests

from .types import QuerySpec, SearchResult

DEFAULT_BASE_URL = "https://api.github.com"
SEARCH_ENDPOINT = "/search/code"
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3


class GitHubAPIError(RuntimeError):
    """Represents a non-success response from the GitHub API."""


class GitHubSearchClient:
    """Thin client around the GitHub code search endpoint."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        user_agent: str = "BugZero/0.1",
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3.text-match+json",
                "User-Agent": user_agent,
            }
        )

    def search_code(
        self,
        query: QuerySpec,
        *,
        per_page: int = 30,
        pages: int = 1,
        text_matches: bool = True,
    ) -> List[SearchResult]:
        """Execute the given query and return a list of normalized results."""
        headers = {}
        if text_matches:
            headers["Accept"] = "application/vnd.github.v3.text-match+json"

        results: List[SearchResult] = []
        for page in range(1, pages + 1):
            params = {
                "q": query.build(),
                "per_page": per_page,
                "page": page,
            }
            payload = self._request_with_retry(params, extra_headers=headers)
            items = payload.get("items", [])
            results.extend(_parse_items(items))
            if len(items) < per_page:
                break
        return results

    def _request_with_retry(self, params: dict, extra_headers: dict[str, str]) -> dict:
        for attempt in range(1, MAX_RETRIES + 1):
            response = self.session.get(
                f"{self.base_url}{SEARCH_ENDPOINT}",
                params=params,
                headers=extra_headers,
                timeout=DEFAULT_TIMEOUT,
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code == 403 and _is_rate_limited(response):
                wait_seconds = _retry_after(response, attempt)
                time.sleep(wait_seconds)
                continue
            if response.status_code == 401:
                raise GitHubAPIError("GitHub rejected the token (401 Unauthorized)")
            message = _extract_error_message(response)
            raise GitHubAPIError(
                f"GitHub API error {response.status_code}: {message}"
            )
        raise GitHubAPIError("Retry limit exceeded while calling GitHub API")


def _parse_items(items: Iterable[dict]) -> List[SearchResult]:
    parsed: List[SearchResult] = []
    for item in items:
        repo = item.get("repository", {})
        text_matches = item.get("text_matches") or []
        snippet = text_matches[0].get("fragment") if text_matches else None
        parsed.append(
            SearchResult(
                repository=repo.get("full_name", "unknown/repo"),
                path=item.get("path", ""),
                url=item.get("html_url", ""),
                score=item.get("score") or 0.0,
                snippet=snippet,
            )
        )
    return parsed


def _is_rate_limited(response: requests.Response) -> bool:
    if "rate limit" in response.text.lower():
        return True
    remaining = response.headers.get("X-RateLimit-Remaining")
    return remaining == "0"


def _retry_after(response: requests.Response, attempt: int) -> float:
    reset_header = response.headers.get("X-RateLimit-Reset")
    if reset_header:
        try:
            reset_time = int(reset_header)
            return max(reset_time - time.time(), 1)
        except ValueError:
            pass
    return min(2 ** attempt, 60.0)


def _extract_error_message(response: requests.Response) -> str:
    try:
        payload = response.json()
        return payload.get("message", response.text)
    except ValueError:
        return response.text

