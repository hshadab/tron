"""tronpy wrapper for Nile testnet — balance checks and USDT operations."""

import logging

from tronpy import Tron

from src.config import DEFAULT_FEE_LIMIT_SUN, NILE_USDT_CONTRACT, USDT_DECIMALS

logger = logging.getLogger(__name__)


class TronNileClient:
    """TRON Nile client for balance queries and fallback TRC-20 transfers."""

    def __init__(self, private_key: str, wallet_address: str) -> None:
        self.private_key = private_key
        self.wallet_address = wallet_address
        self.client = Tron(network="nile")
        self._usdt = self.client.get_contract(NILE_USDT_CONTRACT)

    def get_usdt_balance(self, address: str | None = None) -> float:
        """Return TRC-20 USDT balance (human-readable float)."""
        addr = address or self.wallet_address
        raw = self._usdt.functions.balanceOf(addr)
        return raw / (10**USDT_DECIMALS)

    def get_trx_balance(self, address: str | None = None) -> float:
        """Return native TRX balance (human-readable float)."""
        addr = address or self.wallet_address
        raw = self.client.get_account_balance(addr)
        # get_account_balance already returns a float in TRX
        return float(raw)

    def fallback_transfer(self, amount: float, recipient: str) -> str | None:
        """Direct TRC-20 USDT transfer, used when the x402 flow fails.

        Returns the transaction id on success, or ``None`` if the broadcast
        raised. All error details are logged rather than propagated so
        callers can degrade gracefully.
        """
        try:
            from tronpy.keys import PrivateKey

            priv = PrivateKey(bytes.fromhex(self.private_key))
            raw_amount = int(amount * (10**USDT_DECIMALS))

            txn = (
                self._usdt.functions.transfer(recipient, raw_amount)
                .with_owner(self.wallet_address)
                .fee_limit(DEFAULT_FEE_LIMIT_SUN)
                .build()
                .sign(priv)
            )
            result = txn.broadcast()
            return result.get("txid", str(result))
        except Exception as e:
            logger.error("Fallback transfer error: %s", e)
            return None
