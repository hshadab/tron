"""Approve USDT allowance for the x402 PaymentPermit contract on Nile.

The agent wallet must approve USDT spending to the PaymentPermit contract
before the x402 payment flow can work.

Usage: python scripts/approve_allowance.py
"""

import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from tronpy import Tron
from tronpy.keys import PrivateKey

from src.config import (
    NILE_USDT_CONTRACT,
    PAYMENT_PERMIT_ADDRESS,
    TRON_PRIVATE_KEY,
    TRON_WALLET_ADDRESS,
    USDT_DECIMALS,
)


def main():
    if not TRON_PRIVATE_KEY or not TRON_WALLET_ADDRESS:
        print("Error: TRON_PRIVATE_KEY and TRON_WALLET_ADDRESS must be set in .env")
        sys.exit(1)

    print("=" * 60)
    print("  Approve USDT Allowance for x402 PaymentPermit")
    print("=" * 60)
    print()
    print(f"Agent wallet:          {TRON_WALLET_ADDRESS}")
    print(f"USDT contract:         {NILE_USDT_CONTRACT}")
    print(f"PaymentPermit spender: {PAYMENT_PERMIT_ADDRESS}")
    print()

    client = Tron(network="nile")
    priv = PrivateKey(bytes.fromhex(TRON_PRIVATE_KEY))
    contract = client.get_contract(NILE_USDT_CONTRACT)

    # Approve max uint256 allowance (standard pattern)
    max_allowance = 2**256 - 1

    print("Sending approve transaction...")
    txn = (
        contract.functions.approve(PAYMENT_PERMIT_ADDRESS, max_allowance)
        .with_owner(TRON_WALLET_ADDRESS)
        .fee_limit(100_000_000)
        .build()
        .sign(priv)
    )
    result = txn.broadcast()
    tx_id = result.get("txid", str(result))

    print()
    print(f"Transaction broadcast: {tx_id}")
    print()

    # Wait and check result
    print("Waiting for confirmation...")
    import time
    time.sleep(5)

    try:
        info = client.get_transaction_info(tx_id)
        receipt = info.get("receipt", {})
        if receipt.get("result") == "SUCCESS" or info.get("id"):
            print("[OK] Allowance approved successfully.")
        else:
            print(f"[WARN] Transaction result: {receipt}")
    except Exception:
        print(f"[INFO] Check transaction on Nile explorer:")
        print(f"  https://nile.tronscan.org/#/transaction/{tx_id}")

    print()
    print("The agent wallet can now make x402 payments via the PaymentPermit contract.")


if __name__ == "__main__":
    main()
