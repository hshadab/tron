"""x402 payment flow — client-side, using tvm-x402."""

import httpx
from x402.clients import X402Client, X402HttpClient
from x402.encoding import decode_payment_payload
from x402.mechanisms.client import UptoTronClientMechanism
from x402.signers.client import TronClientSigner
from x402.types import SettleResponse

from src.config import VENDOR_SERVER_URL, X402_PAYMENT_TIMEOUT


class X402PaymentFlow:
    """Executes an x402 payment against a local vendor server on Nile."""

    def __init__(self, private_key: str, network: str = "tron:nile") -> None:
        self.private_key = private_key
        self.network = network
        self._client: X402Client | None = None
        self._signer: TronClientSigner | None = None

    def _ensure_client(self) -> None:
        """Lazy-init the X402Client and signer."""
        if self._client is not None:
            return
        self._signer = TronClientSigner.from_private_key(self.private_key, network="nile")
        self._client = X402Client()
        mechanism = UptoTronClientMechanism(self._signer)
        self._client.register("tron:*", mechanism)

    async def execute_payment(self, vendor_url: str | None = None) -> dict:
        """Execute x402 payment flow:
        1. GET vendor_url -> 402 + PAYMENT-REQUIRED header
        2. SDK auto-signs TIP-712 payment authorization
        3. SDK retries with signed payload
        4. Return settlement result
        """
        self._ensure_client()
        url = vendor_url or f"{VENDOR_SERVER_URL}/weather"

        async with httpx.AsyncClient(timeout=X402_PAYMENT_TIMEOUT) as http_client:
            client = X402HttpClient(http_client, self._client)
            response = await client.get(url)

            result = {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "body": response.json() if response.status_code == 200 else None,
            }

            # Extract settlement details from payment-response header
            payment_response = response.headers.get("payment-response")
            if payment_response:
                settle = decode_payment_payload(payment_response, SettleResponse)
                result["tx_hash"] = getattr(settle, "transaction", None)
                result["network"] = getattr(settle, "network", None)

            return result
