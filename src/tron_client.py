"""tronpy wrapper for Nile testnet — balance checks and USDT operations."""

from tronpy import Tron

from src.config import NILE_USDT_CONTRACT, USDT_DECIMALS


class TronNileClient:
    """Read-only TRON Nile client for balance queries."""

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
