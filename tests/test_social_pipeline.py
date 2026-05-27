from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import cache
from fetchers import neynar
from signals.distribution import publish_signal, should_publish_signal
from signals.social import normalize_social_casts


def _cast(**overrides):
    cast = {
        'hash': 'cast-1',
        'text': 'Base governance vote is accelerating and Base DAO builders are paying attention.',
        'timestamp': datetime(2026, 5, 26, 12, 0, tzinfo=UTC).isoformat(),
        'author': {
            'fid': 101,
            'username': 'builderone',
            'display_name': 'Builder One',
            'follower_count': 1200,
            'score': 0.91,
            'verified_accounts': [{'platform': 'x', 'username': 'builderone'}],
        },
        'reactions': {'likes_count': 18, 'recasts_count': 4},
        'replies': {'count': 3},
        'channel': {'id': 'base', 'name': 'Base'},
    }
    cast.update(overrides)
    return cast


async def test_normalize_social_casts_builds_topic_events():
    casts = [
        _cast(),
        _cast(
            hash='cast-2',
            text='Base launch traction keeps rising and the ecosystem is watching closely.',
            author={
                'fid': 202,
                'username': 'launchwatch',
                'display_name': 'Launch Watch',
                'follower_count': 800,
                'score': 0.86,
                'verified_accounts': [{'platform': 'x', 'username': 'launchwatch'}],
            },
            reactions={'likes_count': 12, 'recasts_count': 2},
            replies={'count': 2},
        ),
    ]

    events = await normalize_social_casts(casts, now=datetime(2026, 5, 26, 16, 0, tzinfo=UTC), window_minutes=240)

    event_types = {event['event_type'] for event in events}
    assert 'social_momentum' in event_types
    assert 'social_governance_momentum' in event_types
    assert 'social_launch_momentum' in event_types
    assert all(event['source'] == 'farcaster' for event in events)
    assert any(event['mention_velocity'] > 0 for event in events)
    assert any(event['verified_actor_count'] > 0 for event in events)


async def test_publish_signal_applies_cooldown():
    signal = {
        'event_id': 'social-alert-1',
        'event_type': 'social_governance_momentum',
        'source': 'farcaster',
        'protocol': 'Base',
        'title': 'Base governance vote swings rapidly',
        'severity': 'critical',
        'urgency_score': 82,
        'store_as_major_signal': True,
        'notify_users': True,
    }
    now = datetime(2026, 5, 26, 16, 0, tzinfo=UTC)

    first = await publish_signal(signal, now=now)
    second = await publish_signal(signal, now=now + timedelta(minutes=5))

    assert first.published is True
    assert first.external_posted is False
    assert second.published is False
    assert second.reason == 'cooldown_suppressed'
    assert await cache.get_counter('stats:signals_distributed') == 1
    assert await cache.get_counter('stats:distribution_cooldown_suppressions') == 1


async def test_publish_signal_skips_ineligible_signal():
    signal = {
        'event_id': 'social-alert-2',
        'event_type': 'social_momentum',
        'source': 'farcaster',
        'protocol': 'Base',
        'title': 'Small chat pulse',
        'severity': 'low',
        'urgency_score': 12,
    }

    result = await publish_signal(signal, now=datetime(2026, 5, 26, 16, 0, tzinfo=UTC))

    assert result.published is False
    assert result.reason == 'not_eligible'
    assert should_publish_signal(signal) is False
    assert await cache.get_counter('stats:distribution_skips') == 1


async def test_fetch_social_casts_handles_api_failure(monkeypatch):
    settings = SimpleNamespace(
        neynar_api_key='test-key',
        farcaster_poll_limit=10,
        neynar_api_base_url='https://api.neynar.com',
        farcaster_channel_ids=['base'],
        farcaster_search_queries=['Base'],
        farcaster_author_fids=[],
    )

    async def fake_fetch_channel_feed(*args, **kwargs):
        return None

    async def fake_fetch_search_casts(*args, **kwargs):
        return None

    monkeypatch.setattr(neynar, 'get_settings', lambda: settings)
    monkeypatch.setattr(neynar, '_fetch_channel_feed', fake_fetch_channel_feed)
    monkeypatch.setattr(neynar, '_fetch_search_casts', fake_fetch_search_casts)

    casts = await neynar.fetch_social_casts(limit=5)

    assert casts == []
    assert neynar.neynar_fetch_ok() is False
