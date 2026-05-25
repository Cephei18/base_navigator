# Base Navigator

Base Navigator is a FastAPI service that turns raw Base ecosystem governance and grants signals into structured JSON intelligence for builders, agents, and internal automation.

The current product is intentionally small: two paid-ready intelligence endpoints, one public health endpoint, Redis caching with in-memory fallback, Gemini synthesis with deterministic fallback, structured request logging, rate limiting, Docker deployment files, and an optional Farcaster daily post script.

## What It Does

- Tracks active governance proposals from configured Snapshot spaces.
- Tracks Base ecosystem grant opportunities from Gitcoin and Base Batches.
- Uses Gemini to synthesize raw upstream data into concise developer-friendly JSON.
- Falls back to deterministic summaries when Gemini or upstream services fail.
- Caches responses in Redis when available, or process memory when Redis is unavailable.
- Protects intelligence endpoints with optional x402 payment middleware.
- Exposes health, degraded-mode, request-count, and estimated revenue information.

## API

### Health

```bash
curl http://localhost:8000/health
```

Returns runtime status, cache backend, Redis status, rate-limit backend, Gemini/x402 configuration state, request counters, and estimated USDC revenue.

### Governance Intelligence

```bash
curl -X POST http://localhost:8000/api/governance
```

Returns active governance proposal summaries:

```json
{
  "as_of": "2026-05-25T18:17:54.492886+00:00",
  "active_proposals": [],
  "urgent_count": 0,
  "summary_for_agents": "No active monitored Base ecosystem governance proposals were found."
}
```

Force a fresh upstream fetch and synthesis pass:

```bash
curl -X POST "http://localhost:8000/api/governance?refresh=true"
```

### Grants Intelligence

```bash
curl -X POST http://localhost:8000/api/grants
```

Returns open grants and urgent deadlines:

```json
{
  "as_of": "2026-05-25T18:18:01.338643+00:00",
  "open_grants": [
    {
      "name": "Base Batches 2026",
      "operator": "Base",
      "amount": "See program page",
      "deadline": null,
      "urgency": "low",
      "eligibility": ["Builds in or benefits the Base ecosystem"],
      "apply_url": "https://basebatches.xyz",
      "tldr": "A program designed to help builders kickstart their business."
    }
  ],
  "urgent_deadlines": [],
  "pro_tip": "Prioritize grants with live application windows and prepare a concise builder traction summary."
}
```

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
  - protects POST /api/governance and POST /api/grants
  - supports X-Internal-Key bypass for trusted automation
  |
  v
FastAPI router
  |
  +-- cache lookup
  +-- upstream fetchers
  +-- Gemini synthesis
  +-- deterministic fallback
  +-- response validation
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
│   └── health.py            # GET /health
├── fetchers/
│   ├── snapshot.py          # Snapshot GraphQL fetcher
│   └── gitcoin.py           # Gitcoin GraphQL and Base Batches fetchers
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
X402_NETWORK_ID=eip155:84532
```

Protected endpoints:

- `POST /api/governance`
- `POST /api/grants`

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
INTERNAL_KEY=long-random-secret
PUBLIC_BASE_URL=https://your-service.example
```

Attach Redis in Railway, add the environment variables, and deploy from GitHub.

## Current Reality Check

Working now:

- FastAPI app boots.
- Health endpoint reports runtime state.
- Redis cache and memory fallback paths exist.
- Gemini synthesis is implemented with deterministic fallback.
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
