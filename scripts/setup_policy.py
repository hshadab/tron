"""Compile treasury policy via Preflight /v1/makeRules.

Costs 300 credits (~$3.00). Run once, save policy_id to .env.
Requires ICME_API_KEY in .env.

Usage: python scripts/setup_policy.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from scripts.utils import print_header
from src.config import ICME_API_KEY, TREASURY_POLICY
from src.preflight import PreflightClient


async def main() -> None:
    if not ICME_API_KEY:
        print("Error: ICME_API_KEY not set in .env")
        print("Get one at: POST https://api.icme.io/v1/createUserCard")
        sys.exit(1)

    print_header("Compile Treasury Policy via Preflight /v1/makeRules")
    print("Policy text:")
    print("-" * 40)
    print(TREASURY_POLICY)
    print("-" * 40)
    print()
    print("This costs 300 credits (~$3.00). Proceeding...")
    print()

    try:
        policy_id = await PreflightClient.compile_policy(ICME_API_KEY, TREASURY_POLICY)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

    print()
    print_header("Policy compiled successfully!")
    print(f"Policy ID: {policy_id}")
    print()
    print("Add this to your .env file:")
    print(f"  ICME_POLICY_ID={policy_id}")


if __name__ == "__main__":
    asyncio.run(main())
