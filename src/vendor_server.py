"""Local x402-protected FastAPI vendor server for the demo.

Serves a weather API endpoint that requires 1 USDT via x402 on Nile.
Runs on localhost:8402.
"""

from fastapi import FastAPI, Request
from x402.facilitator import FacilitatorClient
from x402.fastapi import x402_protected
from x402.server import X402Server

from src.config import FACILITATOR_SERVER_URL, VENDOR_ADDRESS


def create_vendor_app() -> FastAPI:
    """Create the vendor FastAPI app."""
    app = FastAPI(title="Weather API Vendor (x402)")

    server = X402Server(auto_register_tron=True)
    facilitator = FacilitatorClient(base_url=FACILITATOR_SERVER_URL)
    server.add_facilitator(facilitator)

    @app.get("/weather", tags=["vendor"])
    @x402_protected(
        server=server,
        price="1 USDT",
        network="tron:nile",
        pay_to=VENDOR_ADDRESS,
    )
    async def get_weather(request: Request):
        """x402-protected weather endpoint (1 USDT). Returns mock data once paid."""
        return {
            "temperature": 72,
            "condition": "sunny",
            "city": "Geneva",
            "source": "x402-weather-api",
        }

    @app.get("/health", tags=["health"])
    async def health():
        """Liveness probe."""
        return {"status": "ok"}

    return app
