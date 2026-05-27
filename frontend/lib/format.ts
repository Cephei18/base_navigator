export function labelize(value?: string | null): string {
  if (!value) return 'Unknown'
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function formatScore(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--'
  return Math.round(value).toString()
}

export function formatDateTime(value?: string | null): string {
  if (!value) return 'Not available'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not available'
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date)
}

export function formatLatency(value?: number): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return '--'
  return `${Math.round(value)}ms`
}

export function formatPercent(numerator?: number, denominator?: number): string {
  if (!numerator || !denominator) return '0%'
  return `${Math.min(100, Math.round((numerator / denominator) * 100))}%`
}
