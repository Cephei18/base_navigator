from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from config import get_settings
from observability import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    if not settings.neynar_api_key or not settings.farcaster_signer_uuid:
        logger.info("Skipping Farcaster post: NEYNAR_API_KEY or FARCASTER_SIGNER_UUID is missing.")
        return

    headers = {"X-Internal-Key": settings.internal_key} if settings.internal_key else {}
    async with httpx.AsyncClient(timeout=30) as client:
        governance = await _fetch_json(
            client,
            f"{settings.public_base_url}/api/governance",
            headers,
        )
        grants = await _fetch_json(client, f"{settings.public_base_url}/api/grants", headers)
        cast = _format_cast(governance, grants, settings.public_base_url)
        response = await client.post(
            "https://api.neynar.com/v2/farcaster/cast",
            headers={"api_key": settings.neynar_api_key},
            json={"signer_uuid": settings.farcaster_signer_uuid, "text": cast},
        )
        response.raise_for_status()
        logger.info("Posted Farcaster daily update.")


async def _fetch_json(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    response = await client.post(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


def _format_cast(governance: dict[str, Any], grants: dict[str, Any], public_url: str) -> str:
    today = datetime.now(UTC).strftime("%b %d")
    proposals = governance.get("active_proposals", [])
    urgent = governance.get("urgent_count", 0)
    open_grants = grants.get("open_grants", [])
    text = (
        f"Base Governance Update - {today}\n\n"
        f"{len(proposals)} active proposals monitored\n"
        f"{urgent} urgent governance deadlines\n"
        f"{len(open_grants)} Base grants tracked\n\n"
        f"Full details: {public_url}\n"
        "/base /build"
    )
    return text[:320]


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        logger.warning("Farcaster daily job failed: %s", exc)
