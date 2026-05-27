from __future__ import annotations

import hmac
import logging
from typing import Any, cast

from fastapi import FastAPI
from starlette.types import ASGIApp, Receive, Scope, Send

from config import Settings

logger = logging.getLogger(__name__)


class InternalBypassPaymentMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        routes: dict[str, Any],
        server: Any,
        internal_key: str | None,
    ):
        from x402.http.middleware.fastapi import PaymentMiddlewareASGI

        self.app = app
        self.payment_app = PaymentMiddlewareASGI(app, routes=routes, server=server)
        self.internal_key = internal_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http" and self._has_internal_key(scope):
            logger.debug(
                "Bypassing x402 payment with internal key.",
                extra={"path": scope.get("path")},
            )
            await self.app(scope, receive, send)
            return
        try:
            await self.payment_app(scope, receive, send)
        except Exception:
            logger.exception("x402 payment middleware failure.", extra={"path": scope.get("path")})
            raise

    def _has_internal_key(self, scope: Scope) -> bool:
        if not self.internal_key:
            return False
        for name, value in scope.get("headers", []):
            if name == b"x-internal-key":
                return hmac.compare_digest(value.decode("utf-8"), self.internal_key)
        return False


def install_payment_middleware(app: FastAPI, settings: Settings) -> bool:
    if not settings.enable_x402:
        logger.info(
            "x402 payment middleware disabled. Set ENABLE_X402=true to protect paid routes."
        )
        return False
    if not settings.wallet_address:
        logger.warning(
            "ENABLE_X402=true but WALLET_ADDRESS is empty; paid routes are not protected."
        )
        return False

    try:
        from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
        from x402.http.types import RouteConfig
        from x402.mechanisms.evm.exact import ExactEvmServerScheme
        from x402.server import x402ResourceServer
    except ImportError as exc:
        raise RuntimeError(
            'x402 is not installed. Run `python -m pip install -r requirements.txt`.'
        ) from exc

    facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=settings.x402_facilitator_url))
    server = x402ResourceServer(facilitator)
    server.register(settings.x402_network_id, cast(Any, ExactEvmServerScheme()))

    accepts = [
        PaymentOption(
            scheme="exact",
            pay_to=settings.wallet_address,
            price=settings.x402_price_usd,
            network=settings.x402_network_id,
        )
    ]
    premium_accepts = [
        PaymentOption(
            scheme="exact",
            pay_to=settings.wallet_address,
            price=settings.x402_premium_price_usd,
            network=settings.x402_network_id,
        )
    ]
    routes: dict[str, RouteConfig] = {
        "POST /api/governance": RouteConfig(
            accepts=accepts,
            mime_type="application/json",
            description="Base ecosystem governance intelligence.",
        ),
        "POST /api/grants": RouteConfig(
            accepts=accepts,
            mime_type="application/json",
            description="Base ecosystem grants intelligence.",
        ),
        "GET /api/signals/premium": RouteConfig(
            accepts=premium_accepts,
            mime_type="application/json",
            description="Premium Base ecosystem signal intelligence.",
        ),
    }
    app.add_middleware(
        InternalBypassPaymentMiddleware,
        routes=routes,
        server=server,
        internal_key=settings.internal_key,
    )
    logger.info(
        "x402 payment middleware enabled for %s on %s.",
        settings.x402_price_usd,
        settings.x402_network_id,
    )
    return True
