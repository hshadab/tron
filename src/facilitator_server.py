"""Local x402 facilitator for Nile testnet.

Handles /verify and /settle endpoints for the demo.
Runs on localhost:8403.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel
from x402.facilitator import X402Facilitator
from x402.mechanisms.facilitator import UptoTronFacilitatorMechanism
from x402.signers.facilitator import TronFacilitatorSigner
from x402.types import PaymentPayload, PaymentRequirements

facilitator = X402Facilitator()


class VerifyRequest(BaseModel):
    paymentPayload: PaymentPayload
    paymentRequirements: PaymentRequirements


class SettleRequest(BaseModel):
    paymentPayload: PaymentPayload
    paymentRequirements: PaymentRequirements


class FeeQuoteRequest(BaseModel):
    accept: PaymentRequirements
    paymentPermitContext: dict | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the facilitator signer and register mechanisms on startup."""
    private_key = os.environ.get("TRON_PRIVATE_KEY", "")
    tron_signer = TronFacilitatorSigner.from_private_key(private_key, network="nile")
    mechanism = UptoTronFacilitatorMechanism(
        signer=tron_signer,
        base_fee=1_000_000,  # 1 TRX equivalent in sun
    )
    facilitator.register(["tron:nile"], mechanism)
    yield


def create_facilitator_app() -> FastAPI:
    """Create the facilitator FastAPI app."""
    app = FastAPI(title="x402 Facilitator (Nile)", lifespan=lifespan)

    @app.get("/supported")
    def supported():
        return facilitator.supported()

    @app.post("/verify")
    async def verify(request: VerifyRequest):
        return await facilitator.verify(request.paymentPayload, request.paymentRequirements)

    @app.post("/settle")
    async def settle(request: SettleRequest):
        return await facilitator.settle(request.paymentPayload, request.paymentRequirements)

    @app.post("/fee/quote")
    async def fee_quote(request: FeeQuoteRequest):
        return await facilitator.fee_quote(request.accept, request.paymentPermitContext)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
