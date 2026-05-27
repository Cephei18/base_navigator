from __future__ import annotations

from signals import convergence


import pytest


@pytest.mark.asyncio
async def test_convergence_detects_multi_source():
    e1 = {"event_id": "a1", "title": "Grant XYZ announced", "event_type": "grant", "source": "snapshot"}
    e2 = {"event_id": "b2", "title": "Grant XYZ announced", "event_type": "grant", "source": "farcaster"}
    fp1 = await convergence.add_evidence(e1)
    fp2 = await convergence.add_evidence(e2)
    assert fp1 == fp2
    result = await convergence.evaluate_candidate(fp1)
    assert result is not None
    assert result["event_type"] == "ecosystem_convergence"
    assert "farcaster" in result["sources"]
