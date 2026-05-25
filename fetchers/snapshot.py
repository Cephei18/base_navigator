from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from config import get_settings

logger = logging.getLogger(__name__)

SNAPSHOT_QUERY = """
query ActiveBaseProposals($spaces: [String], $first: Int) {
  proposals(
    first: $first,
    skip: 0,
    where: { space_in: $spaces, state: "active" },
    orderBy: "end",
    orderDirection: asc
  ) {
    id
    title
    body
    choices
    space { id name }
    start
    end
    state
    scores
    scores_total
    votes
    quorum
  }
}
"""


async def fetch_active_proposals(first: int = 20) -> list[dict[str, Any]]:
    settings = get_settings()
    payload = {
        "query": SNAPSHOT_QUERY,
        "variables": {"spaces": settings.snapshot_spaces, "first": first},
    }

    for attempt in range(2):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(settings.snapshot_graphql_url, json=payload)
                response.raise_for_status()
                data = response.json()
            break
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Snapshot fetch failed.",
                extra={"attempt": attempt + 1, "error": f"{type(exc).__name__}: {exc}"},
            )
            if attempt == 0:
                await asyncio.sleep(1)
                continue
            return []

    if data.get("errors"):
        logger.warning("Snapshot GraphQL errors.", extra={"errors": data["errors"]})
        return []

    proposals = data.get("data", {}).get("proposals", [])
    if not isinstance(proposals, list):
        return []
    parsed = [proposal for proposal in proposals if isinstance(proposal, dict)]
    logger.info("Snapshot fetch complete.", extra={"proposal_count": len(parsed)})
    return parsed
