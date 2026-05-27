from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from cache import get_value, set_value, increment_counter

logger = logging.getLogger(__name__)

INDEX_KEY = "convergence:candidates_index"
CANDIDATE_KEY = "convergence:candidate:{fingerprint}"


def _normalize_event_for_fingerprint(event: Dict[str, Any]) -> Dict[str, Any]:
    # choose stable fields: title, event_type, normalized target id, source
    return {
        "title": (event.get("title") or "").strip().lower(),
        "event_type": (event.get("event_type") or "").strip().lower(),
        "target": str(event.get("target") or event.get("proposal_id") or "").strip().lower(),
    }


def fingerprint_event(event: Dict[str, Any]) -> str:
    normalized = _normalize_event_for_fingerprint(event)
    payload = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


async def add_evidence(event: Dict[str, Any]) -> str:
    """Add an evidence event to a candidate fingerprint and return fingerprint."""
    fp = fingerprint_event(event)
    key = CANDIDATE_KEY.format(fingerprint=fp)
    current = await get_value(key) or []
    if not isinstance(current, list):
        current = []
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": event.get("source"),
        "event": {k: event.get(k) for k in ("event_id", "title", "event_type")},
    }
    current.append(entry)
    await set_value(key, current)
    # add to index
    idx = await get_value(INDEX_KEY) or []
    if fp not in idx:
        idx.append(fp)
        await set_value(INDEX_KEY, idx)
    await increment_counter("convergence:evidence_added")
    return fp


async def evaluate_candidate(fingerprint: str) -> Dict[str, Any] | None:
    key = CANDIDATE_KEY.format(fingerprint=fingerprint)
    entries = await get_value(key) or []
    if not isinstance(entries, list) or len(entries) < 2:
        return None
    sources = sorted({e.get("source") for e in entries if e.get("source")})
    if len(sources) < 2:
        return None
    # simple convergence score: unique_sources * sqrt(total_evidence)
    score = len(sources) * (len(entries) ** 0.5)
    if score < 2.0:
        return None
    event = {
        "event_type": "ecosystem_convergence",
        "narrative_id": f"narr_{fingerprint}",
        "contributing_signals": entries,
        "sources": sources,
        "convergence_score": round(score, 3),
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }
    await increment_counter("convergence:detected")
    return event
