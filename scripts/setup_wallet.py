"""Generate three Nile testnet wallets: agent, vendor, facilitator.

Prints addresses and instructions to fund them on the Nile faucet.
Run once, then copy the output to .env.

Usage: python scripts/setup_wallet.py
"""

from tronpy.keys import PrivateKey

from scripts.utils import print_header


def generate_wallet(label: str) -> dict:
    """Generate a random TRON wallet."""
    priv = PrivateKey.random()
    addr = priv.public_key.to_base58check_address()
    return {
        "label": label,
        "private_key": priv.hex(),
        "address": addr,
    }


def main() -> None:
    print_header("TRON Nile Testnet Wallet Generator")

    wallets = [
        generate_wallet("Agent"),
        generate_wallet("Vendor"),
        generate_wallet("Facilitator"),
    ]

    # Print .env format
    print("# ── Copy the following into your .env file ──")
    print()

    agent = wallets[0]
    print(f"TRON_PRIVATE_KEY={agent['private_key']}")
    print(f"TRON_WALLET_ADDRESS={agent['address']}")
    print()

    vendor = wallets[1]
    print(f"VENDOR_ADDRESS={vendor['address']}")
    print()

    facilitator = wallets[2]
    print(f"FACILITATOR_PRIVATE_KEY={facilitator['private_key']}")
    print(f"FACILITATOR_ADDRESS={facilitator['address']}")
    print()

    # Funding instructions
    print_header("FUNDING INSTRUCTIONS")
    print("Visit the Nile faucet to claim test tokens:")
    print("  https://nileex.io/join/getJoinPage")
    print()
    print("Fund each wallet with TRX (and USDT for the agent):")
    print()

    for w in wallets:
        print(f"  {w['label']}: {w['address']}")

    print()
    print("Required balances:")
    print("  Agent       — needs USDT (for payments) + TRX (for energy/bandwidth)")
    print("  Vendor      — just receives payments, no funding needed")
    print("  Facilitator — needs TRX (for gas on x402 settlement)")
    print()
    print("After funding, run:  python scripts/approve_allowance.py")


if __name__ == "__main__":
    main()
