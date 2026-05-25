from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import get_settings

logger = logging.getLogger(__name__)

GITCOIN_ROUNDS_QUERY = """
query BaseRounds($chainId: Int!) {
  rounds(
    first: 20,
    where: { chainId: { _eq: $chainId } },
    orderBy: { applicationsEndTime: asc }
  ) {
    id
    chainId
    roundMetadata
    applicationsStartTime
    applicationsEndTime
    donationsStartTime
    donationsEndTime
    matchingFundsAvailable
    matchingCap
    roundType
    strategyName
  }
}
"""

GITCOIN_ROUNDS_FALLBACK_QUERY = """
query BaseRoundsFallback {
  rounds(first: 20, chainId: 8453) {
    id
    chainId
    roundMetadata
    applicationsStartTime
    applicationsEndTime
    donationsStartTime
    donationsEndTime
    matchingFundsAvailable
  }
}
"""


async def fetch_active_grants() -> list[dict[str, Any]]:
    settings = get_settings()
    rounds = await _fetch_gitcoin_rounds(settings.gitcoin_graphql_url)
    base_batches = await _fetch_base_batches(settings.base_batches_url)
    return [*rounds, *base_batches]


async def _fetch_gitcoin_rounds(url: str) -> list[dict[str, Any]]:
    payloads = [
        {"query": GITCOIN_ROUNDS_QUERY, "variables": {"chainId": 8453}},
        {"query": GITCOIN_ROUNDS_FALLBACK_QUERY},
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        for payload in payloads:
            data: dict[str, Any] = {}
            for attempt in range(2):
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                    break
                except (httpx.HTTPError, ValueError) as exc:
                    logger.warning(
                        "Gitcoin fetch failed.",
                        extra={"attempt": attempt + 1, "error": f"{type(exc).__name__}: {exc}"},
                    )
                    if attempt == 0:
                        await asyncio.sleep(1)
                        continue

            if data.get("errors"):
                logger.info("Gitcoin query variant failed.", extra={"errors": data["errors"]})
                continue
            rounds = data.get("data", {}).get("rounds", [])
            if isinstance(rounds, list):
                parsed = [
                    {"source": "gitcoin", **round}
                    for round in rounds
                    if isinstance(round, dict)
                ]
                logger.info("Gitcoin fetch complete.", extra={"round_count": len(parsed)})
                return parsed
    return []


async def _fetch_base_batches(url: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.info(
            "Base Batches fetch failed.",
            extra={"error": f"{type(exc).__name__}: {exc}"},
        )
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "Base Batches"
    description_tag = soup.find("meta", attrs={"name": "description"})
    description = (
        description_tag.get("content", "").strip()
        if description_tag and description_tag.get("content")
        else "Base ecosystem builder program."
    )
    logger.info("Base Batches fetch complete.")
    return [
        {
            "source": "base_batches",
            "name": title,
            "operator": "Base",
            "amount": "See program page",
            "deadline": None,
            "apply_url": url,
            "description": description,
        }
    ]
