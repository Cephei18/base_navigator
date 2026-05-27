"""Inject a synthetic high-severity governance signal and validate end-to-end flows.

Usage: python -m scripts.inject_test_signal

This script is for PRE-DEPLOYMENT validation only. It performs best-effort
checks without bringing up an HTTP server: uses library functions directly.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pprint import pprint

from config import get_settings

from signals.scorer import build_signal
from signals.reasoner import enrich_signal, reason_about_signal
from signals.store import save_signal_with_result, get_signals
from signals.timeline import get_ticks, compute_momentum
from signals.convergence import add_evidence, evaluate_candidate
from cache import get_client, get_value

logger = logging.getLogger("inject_test_signal")


def make_synthetic_governance_event() -> dict:
    now = datetime.now(UTC)
    event = {
        "event_id": f"inject_test_{int(now.timestamp())}",
        "event_type": "governance_proposal",
        "source": "snapshot",
        "protocol": "Base",
        "title": "Proposal: emergency treasury allocation to support protocol security",
        "source_url": "https://snapshot.org/#/space/proposal/0xdeadbeef",
        # deterministic scoring inputs to push score above 70
        "vote_swing_pct": 25.0,
        "hours_until_deadline": 2,
        "estimated_treasury_impact_usd": 2_500_000,
        "quorum_at_risk": True,
        "for_vs_against_swing": True,
        "governance_activity_score": 18.0,
        "is_new_proposal": True,
    }
    return event


async def run_injection():
    settings = get_settings()
    print("PRE-DEPLOY VALIDATION: inject_test_signal")
    print("Settings: ", {"redis": bool(settings.redis_url), "gemini": bool(settings.gemini_api_key)})

    event = make_synthetic_governance_event()
    print("Synthetic event:")
    pprint(event)

    # Score
    scored = build_signal(event)
    print("Scored urgency:", scored.urgency_score, "severity:", scored.severity)
    if scored.urgency_score < 70:
        print("FAIL: synthetic event did not reach critical threshold (>=70)")
        return 1

    # Enrich (best-effort)
    print("Attempting enrichment (best-effort)…")
    try:
        enriched = await enrich_signal(scored.model_dump(mode="json"))
        llm = enriched.get("llm_enrichment")
        print("Enrichment status:", bool(llm))
    except Exception as exc:
        print("Enrichment raised exception (expected if GEMINI not configured):", exc)
        llm = None

    # Save signal
    print("Saving signal to store…")
    saved = await save_signal_with_result(scored.model_dump(mode="json"))
    print("Saved result:", saved)

    # Verify signals API backend (library) returns the signal
    signals = await get_signals(50)
    found = next((s for s in signals if s.get("event_id") == scored.event_id), None)
    print("Signal present in feed:", bool(found))

    # Timeline ticks
    ticks = await get_ticks(scored.event_id)
    print("Timeline ticks count for event_id:", len(ticks))
    mom = await compute_momentum(scored.event_id)
    print("Momentum:")
    pprint(mom)

    # Convergence: add a fake Farcaster evidence and evaluate
    print("Adding second-source evidence for convergence test…")
    farc_event = {**event, "event_id": f"farc_{event['event_id']}", "source": "farcaster"}
    fp1 = await add_evidence(event)
    fp2 = await add_evidence(farc_event)
    assert fp1 == fp2
    conv = await evaluate_candidate(fp1)
    print("Convergence detected:", conv is not None)
    if conv:
        pprint(conv)

    # Redis keys and basic checks
    client = await get_client()
    if client is not None:
        print("Connected to Redis; checking some keys…")
        # list a few keys
        keys = await client.keys("*")
        print("Redis key sample count:", len(keys))
    else:
        print("Redis not configured — using in-memory fallback; ensure persistence test later.")

    # Final verdict
    ok = bool(found and (scored.urgency_score >= 70))
    print("FINAL RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 2


def main():
    code = asyncio.run(run_injection())
    return code


if __name__ == "__main__":
    raise SystemExit(main())
