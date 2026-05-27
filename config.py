from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _network_id() -> str:
    raw = os.getenv("X402_NETWORK_ID") or os.getenv("NETWORK_ID") or "eip155:84532"
    aliases = {
        "base-sepolia": "eip155:84532",
        "base": "eip155:8453",
    }
    return aliases.get(raw, raw)


def _csv_env(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


def _environment() -> str:
    return (os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or "development").strip().lower()


def _allowed_origins(environment: str) -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS")
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    if environment in {"production", "prod"}:
        return []
    return ["*"]


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    log_level: str
    port: int
    allowed_origins: list[str]
    trust_proxy_headers: bool
    redis_url: str | None
    rate_limit_enabled: bool
    rate_limit_public_requests: int
    rate_limit_public_window_seconds: int
    rate_limit_refresh_requests: int
    rate_limit_refresh_window_seconds: int
    governance_cache_ttl: int
    grants_cache_ttl: int
    allow_live_fallback: bool
    source_stale_hours: int
    gemini_api_key: str | None
    gemini_model: str
    enable_x402: bool
    wallet_address: str | None
    x402_price_usd: str
    x402_premium_price_usd: str
    x402_network_id: str
    x402_facilitator_url: str
    internal_key: str | None
    snapshot_graphql_url: str
    snapshot_spaces: list[str]
    gitcoin_graphql_url: str
    base_batches_url: str
    neynar_api_key: str | None
    farcaster_signer_uuid: str | None
    public_base_url: str


@lru_cache
def get_settings() -> Settings:
    load_dotenv()
    environment = _environment()
    return Settings(
        app_name="Base Navigator",
        app_version="0.1.0",
        environment=environment,
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        port=_int_env("PORT", 8000),
        allowed_origins=_allowed_origins(environment),
        trust_proxy_headers=_bool_env("TRUST_PROXY_HEADERS", True),
        redis_url=os.getenv("REDIS_URL") or None,
        rate_limit_enabled=_bool_env("RATE_LIMIT_ENABLED", True),
        rate_limit_public_requests=_int_env("RATE_LIMIT_PUBLIC_REQUESTS", 120),
        rate_limit_public_window_seconds=_int_env("RATE_LIMIT_PUBLIC_WINDOW_SECONDS", 60),
        rate_limit_refresh_requests=_int_env("RATE_LIMIT_REFRESH_REQUESTS", 10),
        rate_limit_refresh_window_seconds=_int_env("RATE_LIMIT_REFRESH_WINDOW_SECONDS", 60),
        governance_cache_ttl=_int_env("GOVERNANCE_CACHE_TTL", 300),
        grants_cache_ttl=_int_env("GRANTS_CACHE_TTL", 3600),
        allow_live_fallback=_bool_env("ALLOW_LIVE_FALLBACK", False),
        source_stale_hours=_int_env("SOURCE_STALE_HOURS", 24),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        enable_x402=_bool_env("ENABLE_X402", False),
        wallet_address=os.getenv("WALLET_ADDRESS") or None,
        x402_price_usd=os.getenv("X402_PRICE_USD", "$0.01"),
        x402_premium_price_usd=os.getenv("X402_PREMIUM_PRICE_USD", "$0.05"),
        x402_network_id=_network_id(),
        x402_facilitator_url=os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator"),
        internal_key=os.getenv("INTERNAL_KEY") or None,
        snapshot_graphql_url=os.getenv("SNAPSHOT_GRAPHQL_URL", "https://hub.snapshot.org/graphql"),
        snapshot_spaces=_csv_env(
            "SNAPSHOT_SPACES",
            [
                "aerodrome.eth",
                "uniswapgovernance.eth",
                "aave.eth",
                "compound-governance.eth",
                "gitcoindao.eth",
                "ens.eth",
            ],
        ),
        gitcoin_graphql_url=os.getenv(
            "GITCOIN_GRAPHQL_URL", "https://grants-stack-indexer-v2.gitcoin.co/graphql"
        ),
        base_batches_url=os.getenv("BASE_BATCHES_URL", "https://basebatches.xyz"),
        neynar_api_key=os.getenv("NEYNAR_API_KEY") or None,
        farcaster_signer_uuid=os.getenv("FARCASTER_SIGNER_UUID") or None,
        public_base_url=os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/"),
    )
