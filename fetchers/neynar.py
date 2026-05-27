from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)
_last_neynar_fetch_ok: bool | None = None


async def fetch_social_casts(*, limit: int | None = None, after: datetime | None = None) -> list[dict[str, Any]]:
    global _last_neynar_fetch_ok
    settings = get_settings()
    if not settings.neynar_api_key:
        _last_neynar_fetch_ok = None
        logger.info("Skipping Farcaster fetch because NEYNAR_API_KEY is missing.")
        return []

    current_limit = max(1, min(limit or settings.farcaster_poll_limit, 100))
    fetched_casts: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    any_success = False
    after_clause = f" after:{after.date().isoformat()}" if after is not None else ""

    async with httpx.AsyncClient(timeout=20) as client:
        if settings.farcaster_channel_ids:
            channel_payload = await _fetch_channel_feed(
                client,
                api_key=settings.neynar_api_key,
                api_base_url=settings.neynar_api_base_url,
                channel_ids=settings.farcaster_channel_ids,
                limit=current_limit,
            )
            if channel_payload is not None:
                any_success = True
                _extend_casts(fetched_casts, seen_hashes, channel_payload)

        for query in settings.farcaster_search_queries:
            search_payload = await _fetch_search_casts(
                client,
                api_key=settings.neynar_api_key,
                api_base_url=settings.neynar_api_base_url,
                query=f"{query}{after_clause}".strip(),
                limit=current_limit,
            )
            if search_payload is not None:
                any_success = True
                _extend_casts(fetched_casts, seen_hashes, search_payload)

        for author_fid in settings.farcaster_author_fids:
            author_payload = await _fetch_search_casts(
                client,
                api_key=settings.neynar_api_key,
                api_base_url=settings.neynar_api_base_url,
                query=f"Base{after_clause}".strip(),
                limit=current_limit,
                author_fid=author_fid,
            )
            if author_payload is not None:
                any_success = True
                _extend_casts(fetched_casts, seen_hashes, author_payload)

    _last_neynar_fetch_ok = any_success
    logger.info(
        "Farcaster fetch complete.",
        extra={"casts_found": len(fetched_casts), "fetch_ok": any_success},
    )
    return fetched_casts


def neynar_fetch_ok() -> bool | None:
    return _last_neynar_fetch_ok


async def _fetch_channel_feed(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    api_base_url: str,
    channel_ids: list[str],
    limit: int,
) -> list[dict[str, Any]] | None:
    url = f"{api_base_url.rstrip('/')}/v2/farcaster/feed/channels/"
    try:
        response = await client.get(
            url,
            headers={"x-api-key": api_key},
            params={"channel_ids": ",".join(channel_ids), "limit": limit},
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Farcaster channel feed fetch failed.",
            extra={"error": f"{type(exc).__name__}: {exc}"},
        )
        return None

    casts = data.get("casts") if isinstance(data, dict) else None
    return [cast for cast in casts if isinstance(cast, dict)] if isinstance(casts, list) else []


async def _fetch_search_casts(
    client: httpx.AsyncClient,
    *,
    api_key: str,
    api_base_url: str,
    query: str,
    limit: int,
    author_fid: int | None = None,
) -> list[dict[str, Any]] | None:
    url = f"{api_base_url.rstrip('/')}/v2/farcaster/cast/search/"
    params: dict[str, Any] = {
        "q": query,
        "mode": "literal",
        "sort_type": "desc_chron",
        "limit": limit,
    }
    if author_fid is not None:
        params["author_fid"] = author_fid

    try:
        response = await client.get(url, headers={"x-api-key": api_key}, params=params)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "Farcaster cast search failed.",
            extra={"query": query, "error": f"{type(exc).__name__}: {exc}"},
        )
        return None

    if not isinstance(data, dict):
        return []
    result = data.get("result")
    casts = result.get("casts") if isinstance(result, dict) else None
    return [cast for cast in casts if isinstance(cast, dict)] if isinstance(casts, list) else []


def _extend_casts(
    destination: list[dict[str, Any]],
    seen_hashes: set[str],
    casts: list[dict[str, Any]],
) -> None:
    for cast in casts:
        cast_hash = str(cast.get("hash") or cast.get("cast_hash") or "")
        if not cast_hash or cast_hash in seen_hashes:
            continue
        seen_hashes.add(cast_hash)
        destination.append(cast)
