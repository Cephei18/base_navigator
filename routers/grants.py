from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Query

from cache import get_cached, increment_counter, set_cached, set_value
from config import get_settings
from fetchers.gitcoin import fetch_active_grants
from models import GrantsResponse
from synthesis.grants import synthesize_grants

router = APIRouter(tags=["grants"])
logger = logging.getLogger(__name__)


@router.post("/grants", response_model=GrantsResponse)
async def grants_intelligence(refresh: bool = Query(default=False)) -> GrantsResponse:
    settings = get_settings()
    cache_key = "grants:base:v1"

    if not refresh:
        cached = await get_cached(cache_key)
        if cached is not None:
            await increment_counter("stats:queries_served")
            return GrantsResponse.model_validate(cached)

    grants = await fetch_active_grants()
    result = await synthesize_grants(grants)
    payload = GrantsResponse.model_validate(result).model_dump(mode="json")

    await set_cached(cache_key, payload, settings.grants_cache_ttl)
    await set_value("stats:last_grants_update", datetime.now(UTC).isoformat())
    await increment_counter("stats:queries_served")
    logger.info(
        "Grants intelligence generated.",
        extra={"grant_count": len(payload["open_grants"]), "refresh": refresh},
    )
    return GrantsResponse.model_validate(payload)
