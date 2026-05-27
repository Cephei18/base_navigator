from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Query

from cache import increment_counter
from models import SignalFeedResponse
from signals.feed import build_signal_feed

router = APIRouter(tags=["signals"])
logger = logging.getLogger(__name__)


@router.get("/signals", response_model=SignalFeedResponse)
async def signal_feed(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SignalFeedResponse:
    payload = await build_signal_feed(limit=limit, premium=False)
    await increment_counter("stats:signals_public_reads")
    logger.info(
        "Public signal feed served.",
        extra={"signals_count": payload["signals_count"], "quiet_period": payload["quiet_period"]},
    )
    return SignalFeedResponse.model_validate(payload)


@router.get("/signals/premium", response_model=SignalFeedResponse)
async def premium_signal_feed(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> SignalFeedResponse:
    payload = await build_signal_feed(limit=limit, premium=True)
    await increment_counter("stats:queries_served")
    await increment_counter("stats:signals_premium_reads")
    logger.info(
        "Premium signal feed served.",
        extra={"signals_count": payload["signals_count"], "quiet_period": payload["quiet_period"]},
    )
    return SignalFeedResponse.model_validate(payload)
