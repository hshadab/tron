"""Approve USDT allowance for the x402 PaymentPermit contract on Nile.

The agent wallet must approve USDT spending to the PaymentPermit contract
before the x402 payment flow can work.

Usage: python scripts/approve_allowance.py
"""

import logging
import os
import sys
import time

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from tronpy import Tron
from tronpy.keys import PrivateKey

from scripts.utils import print_header
from src.config import (
    DEFAULT_FEE_LIMIT_SUN,
    MAX_UINT256,
    NILE_USDT_CONTRACT,
    PAYMENT_PERMIT_ADDRESS,
    TRON_PRIVATE_KEY,
    TRON_WALLET_ADDRESS,
    TX_CONFIRM_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


def main() -> None:
    if not TRON_PRIVATE_KEY or not TRON_WALLET_ADDRESS:
        print("Error: TRON_PRIVATE_KEY and TRON_WALLET_ADDRESS must be set in .env")
        sys.exit(1)

    print_header("Approve USDT Allowance for x402 PaymentPermit")
    print(f"Agent wallet:          {TRON_WALLET_ADDRESS}")
    print(f"USDT contract:         {NILE_USDT_CONTRACT}")
    print(f"PaymentPermit spender: {PAYMENT_PERMIT_ADDRESS}")
    print()

    client = Tron(network="nile")
    priv = PrivateKey(bytes.fromhex(TRON_PRIVATE_KEY))
    contract = client.get_contract(NILE_USDT_CONTRACT)

    print("Sending approve transaction...")
    txn = (
        contract.functions.approve(PAYMENT_PERMIT_ADDRESS, MAX_UINT256)
        .with_owner(TRON_WALLET_ADDRESS)
        .fee_limit(DEFAULT_FEE_LIMIT_SUN)
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
    time.sleep(TX_CONFIRM_DELAY_SECONDS)

    try:
        info = client.get_transaction_info(tx_id)
        receipt = info.get("receipt", {})
        if receipt.get("result") == "SUCCESS" or info.get("id"):
            print("[OK] Allowance approved successfully.")
        else:
            print(f"[WARN] Transaction result: {receipt}")
    except Exception as e:
        logger.warning("Could not fetch transaction info: %s", e)
        print("[INFO] Check transaction on Nile explorer:")
        print(f"  https://nile.tronscan.org/#/transaction/{tx_id}")

    print()
    print("The agent wallet can now make x402 payments via the PaymentPermit contract.")


if __name__ == "__main__":
    main()
