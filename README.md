# Base Navigator

Base Navigator is a FastAPI service that monitors Base ecosystem governance, grants activity, and Farcaster social momentum, scores meaningful changes deterministically, selectively enriches high-value signals, and serves a precomputed intelligence feed for builders, agents, and internal automation.

The current product is intentionally small: a scheduled signal pipeline, feed-oriented APIs, one public health endpoint, Redis-backed operational memory with in-memory fallback, selective Gemini enrichment, structured request logging, rate limiting, Docker deployment files, and an optional Farcaster daily post script.

## What It Does

- Tracks active governance proposals from configured Snapshot spaces.
- Tracks Base ecosystem grant opportunities from Gitcoin and Base Batches.
- Tracks high-signal Farcaster activity from Neynar without ingesting the full social firehose.
- Scores meaningful changes deterministically before any LLM enrichment.
- Uses Gemini only for high-value pre-scored signal enrichment.
- Publishes only critical or selected high-value signals back through a controlled distribution layer.
- Serves precomputed signals from Redis when available, or process memory when Redis is unavailable.
- Protects intelligence endpoints with optional x402 payment middleware.
- Exposes health, degraded-mode, request-count, and estimated revenue information.

## API

### Health

```bash
curl http://localhost:8000/health
```

Returns runtime status, cache backend, Redis status, rate-limit backend, Gemini/x402 configuration state, request counters, and estimated USDC revenue.

### Signal Feed

```bash
curl http://localhost:8000/api/signals
```

Returns the latest precomputed ecosystem signals. This endpoint does not fetch upstream data and does not call Gemini:

```json
{
  "source": "precomputed",
  "category": "all",
  "signals_count": 0,
  "quiet_period": true,
  "message": "No high-priority ecosystem signals detected.",
  "severity_summary": {},
  "signals": []
}
```

Premium signal feed:

```bash
curl http://localhost:8000/api/signals/premium
```

When x402 is enabled, `/api/signals/premium` is protected at `X402_PREMIUM_PRICE_USD` and returns richer signal payloads, including score components and raw event context for future premium dashboards.

### Governance Intelligence

```bash
curl -X POST http://localhost:8000/api/governance
```

Returns governance-related precomputed signals:

```json
{
  "source": "precomputed",
  "category": "governance",
  "signals_count": 0,
  "quiet_period": true,
  "message": "No high-priority ecosystem signals detected.",
  "signals": []
}
```

Live fallback is disabled by default. To temporarily allow the legacy live fetch and synthesis path only when the feed is empty:

```env
ALLOW_LIVE_FALLBACK=true
```

### Grants Intelligence

```bash
curl -X POST http://localhost:8000/api/grants
```

Returns grants/funding-related precomputed signals:

```json
{
  "source": "precomputed",
  "category": "grants",
  "signals_count": 0,
  "quiet_period": true,
  "message": "No high-priority ecosystem signals detected.",
  "signals": []
}
```

### Social Intelligence

```bash
curl -X POST http://localhost:8000/api/social
```

Returns Farcaster-derived ecosystem attention signals, including governance acceleration, launch traction, and funding visibility.

## Architecture

```text
Client or agent
  |
  v
RequestContextMiddleware
  - request id
  - structured JSON logs
  - request counters
  |
  v
CORS middleware
  |
  v
RateLimitMiddleware
  - Redis-backed when Redis is connected
  - memory fallback when Redis is unavailable
  - stricter bucket for refresh=true
  |
  v
x402 payment middleware
  - optional
  - protects POST /api/governance, POST /api/grants, and GET /api/signals/premium
  - supports X-Internal-Key bypass for trusted automation
  |
  v
FastAPI router
  |
  +-- Redis signal feed read
  +-- category filtering
  +-- quiet-period response
  +-- optional live fallback only when ALLOW_LIVE_FALLBACK=true
  +-- response validation

Background scheduler
  |
  +-- upstream fetchers
  +-- diff detection
  +-- Farcaster channel/search ingestion via Neynar
  +-- deterministic social normalization
  +-- deterministic scoring
  +-- selective Gemini enrichment
  +-- high-signal distribution control
  +-- Redis signal feed write
```

## Project Structure

```text
.
├── main.py                  # FastAPI app assembly and middleware registration
├── config.py                # Environment-driven Settings object
├── cache.py                 # Redis cache, counters, health state, memory fallback
├── payments.py              # x402 middleware and internal bypass
├── rate_limit.py            # Redis or memory-backed rate limiting
├── observability.py         # JSON logging and request IDs
├── errors.py                # Standard JSON error handlers
├── models.py                # Pydantic API response models
├── routers/
│   ├── governance.py        # POST /api/governance
│   ├── grants.py            # POST /api/grants
│   ├── health.py            # GET /health
│   ├── signals.py           # GET /api/signals and premium feed
│   └── social.py            # POST /api/social for Farcaster signals
├── fetchers/
│   ├── snapshot.py          # Snapshot GraphQL fetcher
│   ├── gitcoin.py           # Gitcoin GraphQL and Base Batches fetchers
│   └── neynar.py            # Farcaster channel/search fetcher via Neynar
├── signals/
│   ├── reasoner.py          # Selective Gemini enrichment and fallback logic
│   ├── scorer.py            # Deterministic scoring rules and severity mapping
│   ├── store.py             # Redis-backed signal storage and cooldown memory
│   ├── feed.py              # Public signal feed shaping and filtering
│   ├── social.py            # Farcaster normalization and momentum event extraction
│   └── distribution.py      # Controlled signal publication and cooldowns
├── frontend/                # Next.js intelligence terminal UI
│   ├── app/                 # App Router entry, layout, and shell page
│   ├── components/          # Feed, metric, status, and signal cards
│   ├── lib/                 # API client and formatting helpers
│   └── types/               # Shared TypeScript response types
├── synthesis/
│   ├── common.py            # Gemini JSON helper
│   ├── governance.py        # Governance prompt and fallback
│   └── grants.py            # Grants prompt and fallback
├── scripts/
│   ├── farcaster_daily.py   # Optional Neynar/Farcaster daily post script
│   ├── test_payment.py      # x402 paid-client smoke test
│   └── validate_docker.py   # Local Docker validation helper
└── tests/                   # Unit and optional live integration tests
```

## Setup

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Copy the example environment file:

```powershell
copy .env.example .env
```

Run the API:

```powershell
.\.venv\Scripts\python -m uvicorn main:app --reload --port 8000
```

Open:

```text
http://localhost:8000/health
```

## Configuration

Important environment variables:

```env
APP_ENV=development
LOG_LEVEL=INFO
ALLOWED_ORIGINS=*
REDIS_URL=redis://localhost:6379

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

ENABLE_X402=false
WALLET_ADDRESS=
X402_PRICE_USD=$0.01
X402_NETWORK_ID=eip155:84532
X402_FACILITATOR_URL=https://x402.org/facilitator
INTERNAL_KEY=

SNAPSHOT_GRAPHQL_URL=https://hub.snapshot.org/graphql
GITCOIN_GRAPHQL_URL=https://grants-stack-indexer-v2.gitcoin.co/graphql
BASE_BATCHES_URL=https://basebatches.xyz

NEYNAR_API_KEY=
FARCASTER_SIGNER_UUID=
NEYNAR_API_BASE_URL=https://api.neynar.com
FARCASTER_CHANNEL_IDS=base
FARCASTER_SEARCH_QUERIES=Base,Base DAO,Base governance,Base grant,Base launch
FARCASTER_POLL_LIMIT=25
FARCASTER_LOOKBACK_MINUTES=240
FARCASTER_DISTRIBUTION_COOLDOWN_SECONDS=21600
PUBLIC_BASE_URL=http://localhost:8000
```

Never commit `.env`. It is ignored by `.gitignore`.

## Caching And Fallbacks

Base Navigator uses Redis when `REDIS_URL` is configured and reachable. If Redis is missing or fails, the app continues with an in-memory fallback for:

- cached intelligence responses
- request counters
- health metadata
- rate-limit windows

Gemini synthesis is also fault-tolerant. If the Gemini API key is missing, the API fails, or the model returns invalid JSON, the service logs the issue and returns deterministic fallback output that still matches the Pydantic response schema.

## x402 Payments

Local development defaults to unpaid endpoints:

```env
ENABLE_X402=false
```

To protect paid endpoints:

```env
ENABLE_X402=true
WALLET_ADDRESS=0xYourReceivingWallet
X402_PRICE_USD=$0.01
X402_PREMIUM_PRICE_USD=$0.05
X402_NETWORK_ID=eip155:84532
```

Protected endpoints:

- `POST /api/governance`
- `POST /api/grants`
- `GET /api/signals/premium`

Trusted internal jobs can bypass x402 by sending:

```text
X-Internal-Key: <INTERNAL_KEY>
```

Revenue shown in `/health` is currently estimated from served query count and configured price. It is not verified on-chain accounting yet.

## Rate Limiting

Rate limiting is enabled by default:

```env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PUBLIC_REQUESTS=120
RATE_LIMIT_PUBLIC_WINDOW_SECONDS=60
RATE_LIMIT_REFRESH_REQUESTS=10
RATE_LIMIT_REFRESH_WINDOW_SECONDS=60
TRUST_PROXY_HEADERS=true
```

Requests with `refresh=true` use the stricter refresh bucket because they bypass cached data and trigger external API work.

## Request Tracing And Logs

Every response includes `X-Request-ID`. If the caller supplies one, the service preserves it. Logs are JSON-formatted and include the request ID, route, subsystem, status code, duration, and relevant error context.

Example:

```bash
curl -H "X-Request-ID: local-debug-1" http://localhost:8000/health
```

## Tests

Install development dependencies:

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

Run unit tests:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Run linting:

```powershell
.\.venv\Scripts\python -m ruff check .
```

Optional live integration tests are skipped unless explicitly enabled:

```powershell
$env:RUN_REDIS_INTEGRATION_TESTS="true"
$env:RUN_GEMINI_INTEGRATION_TESTS="true"
$env:RUN_SNAPSHOT_INTEGRATION_TESTS="true"
$env:RUN_X402_INTEGRATION_TESTS="true"
.\.venv\Scripts\python -m pytest tests\integration -q
```

## Farcaster Daily Post

The API runtime does not schedule Farcaster posts by itself. The optional script can be run manually or from Railway cron:

```powershell
.\.venv\Scripts\python scripts\farcaster_daily.py
```

Required variables:

```env
PUBLIC_BASE_URL=https://your-service.example
INTERNAL_KEY=long-random-secret
NEYNAR_API_KEY=...
FARCASTER_SIGNER_UUID=...
```

## Docker

Build locally:

```bash
docker build -t base-navigator .
```

Run locally:

```bash
docker run --rm -p 8000:8000 --env-file .env base-navigator
```

Validation helper:

```powershell
.\.venv\Scripts\python scripts\validate_docker.py
```

## Railway Deployment

This repository includes:

- `Dockerfile`
- `railway.json`
- `/health` healthcheck path

Recommended production variables:

```env
APP_ENV=production
ALLOWED_ORIGINS=https://your-frontend.example
REDIS_URL=redis://...
GEMINI_API_KEY=...
ENABLE_X402=true
WALLET_ADDRESS=0xYourReceivingWallet
X402_PREMIUM_PRICE_USD=$0.05
ALLOW_LIVE_FALLBACK=false
SOURCE_STALE_HOURS=24
INTERNAL_KEY=long-random-secret
PUBLIC_BASE_URL=https://your-service.example
```

Attach Redis in Railway, add the environment variables, and deploy from GitHub.

### Scheduler Safety

The in-process APScheduler poller must run in a single API worker. The Docker command pins `uvicorn` to `--workers 1` so Railway runs one scheduler loop per deployed service instance.

If you scale horizontally later, move polling to a separate worker/cron service or add Redis leader election before increasing API replicas. Running multiple API workers without leader election can duplicate polls, signals, and Gemini enrichment attempts.

## Current Reality Check

Working now:

- FastAPI app boots.
- Health endpoint reports runtime state.
- Redis cache and memory fallback paths exist.
- Scheduled polling, deterministic signal scoring, and selective Gemini enrichment exist.
- Public and premium signal feed APIs serve precomputed intelligence.
- x402 middleware can require payment on protected routes.
- Rate limiting and request IDs are tested.
- Docker and Railway config files exist.

Still incomplete:

- Verified on-chain payment settlement and revenue accounting.
- Automated Farcaster scheduling.
- Neynar posting tests.
- Full production observability beyond structured logs.
- Hard production guarantees around third-party upstream availability.

## License

No license has been selected yet.
