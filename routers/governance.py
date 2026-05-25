from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query

from cache import get_cached, increment_counter, set_cached, set_value
from config import get_settings
from fetchers.snapshot import fetch_active_proposals
from models import GovernanceResponse
from synthesis.governance import synthesize_governance

router = APIRouter(tags=["governance"])
logger = logging.getLogger(__name__)


@router.post("/governance", response_model=GovernanceResponse)
async def governance_intelligence(refresh: bool = Query(default=False)) -> GovernanceResponse:
    settings = get_settings()
    cache_key = "governance:base:v1"

    if not refresh:
        cached = await get_cached(cache_key)
        if cached is not None:
            await increment_counter("stats:queries_served")
            return GovernanceResponse.model_validate(cached)

    proposals = await fetch_active_proposals()
    result = await synthesize_governance(proposals)
    payload = GovernanceResponse.model_validate(result).model_dump(mode="json")

    await set_cached(cache_key, payload, settings.governance_cache_ttl)
    await set_value("stats:last_governance_update", datetime.now(UTC).isoformat())
    await increment_counter("stats:queries_served")
    logger.info(
        "Governance intelligence generated.",
        extra={"proposal_count": len(payload["active_proposals"]), "refresh": refresh},
    )
    return GovernanceResponse.model_validate(payload)
