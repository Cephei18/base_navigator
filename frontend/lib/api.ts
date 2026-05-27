import type { FeedCategory, HealthResponse, Signal, SignalFeedResponse } from '@/types/api'

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: 'no-store',
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers || {})
    }
  })

  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(`${response.status} ${response.statusText}${detail ? `: ${detail}` : ''}`)
  }

  return response.json() as Promise<T>
}

export function getFeed(category: FeedCategory): Promise<SignalFeedResponse> {
  if (category === 'signals') {
    return requestJson<SignalFeedResponse>('/api/signals?limit=10')
  }

  if (category === 'social') {
    return requestJson<SignalFeedResponse>('/api/social', {
      method: 'POST'
    }).catch(async (error) => {
      if (error instanceof Error && error.message.startsWith('402 ')) {
        const publicFeed = await requestJson<SignalFeedResponse>('/api/signals?limit=50')
        return filterPublicFeed(publicFeed, category)
      }
      throw error
    })
  }

  return requestJson<SignalFeedResponse>(`/api/${category}`, {
    method: 'POST'
  }).catch(async (error) => {
    if (error instanceof Error && error.message.startsWith('402 ')) {
      const publicFeed = await requestJson<SignalFeedResponse>('/api/signals?limit=50')
      return filterPublicFeed(publicFeed, category)
    }
    throw error
  })
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health')
}

function filterPublicFeed(feed: SignalFeedResponse, category: Exclude<FeedCategory, 'signals'>): SignalFeedResponse {
  const signals = feed.signals.filter((signal) => signalMatchesCategory(signal, category))
  const severitySummary = signals.reduce<Record<string, number>>((summary, signal) => {
    const severity = String(signal.severity || 'unknown')
    summary[severity] = (summary[severity] || 0) + 1
    return summary
  }, {})

  return {
    ...feed,
    category,
    signals,
    signals_count: signals.length,
    quiet_period: signals.length === 0,
    message: signals.length ? 'Precomputed signals returned.' : 'No high-priority ecosystem signals detected.',
    severity_summary: severitySummary,
    live_fallback: {
      reason: 'category_endpoint_payment_required',
      filtered_from: '/api/signals'
    }
  }
}

function signalMatchesCategory(signal: Signal, category: Exclude<FeedCategory, 'signals'>): boolean {
  const source = String(signal.source || '').toLowerCase()
  const eventType = String(signal.event_type || '').toLowerCase()
  const protocol = String(signal.protocol || '').toLowerCase()
  const title = String(signal.title || '').toLowerCase()
  const haystack = `${source} ${eventType} ${protocol} ${title}`

  if (category === 'governance') {
    return source === 'snapshot' || ['governance', 'proposal', 'vote', 'quorum', 'snapshot', 'dao'].some((term) => haystack.includes(term))
  }

  if (category === 'social') {
    return source === 'farcaster' || eventType.includes('social')
  }

  return (
    ['gitcoin', 'base_batches'].includes(source) ||
    ['grant', 'grants', 'fund', 'funding', 'round', 'builder', 'builders', 'batches', 'gitcoin'].some((term) => haystack.includes(term))
  )
}
