"""Main orchestrator — runs all 3 scenarios sequentially."""

import asyncio
import os
import signal
import sys
import multiprocessing
import time

import uvicorn
from rich.console import Console

from src.config import (
    ICME_API_KEY,
    ICME_POLICY_ID,
    TRON_PRIVATE_KEY,
    TRON_WALLET_ADDRESS,
    VENDOR_ADDRESS,
    FACILITATOR_PRIVATE_KEY,
    VENDOR_SERVER_PORT,
    FACILITATOR_SERVER_PORT,
    VENDOR_SERVER_URL,
    get_scenarios,
)
from src.preflight import PreflightClient
from src.tron_client import TronNileClient
from src.x402_flow import X402PaymentFlow
from src.display import DemoDisplay

console = Console()


def _check_env():
    """Validate required environment variables."""
    missing = []
    for var in ("ICME_API_KEY", "ICME_POLICY_ID", "TRON_PRIVATE_KEY",
                "TRON_WALLET_ADDRESS", "VENDOR_ADDRESS",
                "FACILITATOR_PRIVATE_KEY"):
        if not os.getenv(var):
            missing.append(var)
    if missing:
        console.print(f"[bold red]Missing env vars: {', '.join(missing)}[/bold red]")
        console.print("Copy .env.example to .env and fill in the values.")
        console.print("See README.md for setup instructions.")
        sys.exit(1)


def _run_facilitator():
    """Run the facilitator server in a subprocess."""
    # Set env var so TronFacilitatorSigner picks up the facilitator key
    os.environ["TRON_PRIVATE_KEY"] = FACILITATOR_PRIVATE_KEY
    from src.facilitator_server import create_facilitator_app
    app = create_facilitator_app()
    uvicorn.run(app, host="127.0.0.1", port=FACILITATOR_SERVER_PORT, log_level="warning")


def _run_vendor():
    """Run the vendor server in a subprocess."""
    from src.vendor_server import create_vendor_app
    app = create_vendor_app()
    uvicorn.run(app, host="127.0.0.1", port=VENDOR_SERVER_PORT, log_level="warning")


def _start_servers() -> tuple[multiprocessing.Process, multiprocessing.Process]:
    """Start facilitator and vendor servers as background processes."""
    console.print("  [dim]Starting local x402 facilitator server...[/dim]")
    facilitator_proc = multiprocessing.Process(target=_run_facilitator, daemon=True)
    facilitator_proc.start()

    console.print("  [dim]Starting local x402 vendor server...[/dim]")
    vendor_proc = multiprocessing.Process(target=_run_vendor, daemon=True)
    vendor_proc.start()

    # Give servers time to start
    time.sleep(3)
    console.print("  [dim]Servers started.[/dim]")
    return facilitator_proc, vendor_proc


async def _run_scenario(
    scenario: dict,
    display: DemoDisplay,
    preflight: PreflightClient,
    tron: TronNileClient,
    x402: X402PaymentFlow,
) -> dict:
    """Run a single scenario and return its result."""
    display.scenario_header(scenario["number"], scenario["name"], scenario["description"])

    result_record = {
        "number": scenario["number"],
        "name": scenario["name"],
        "expected": scenario["expected_result"],
        "actual": None,
        "proof_id": None,
    }

    # Step 1: Agent "decides" to make a payment
    display.agent_thinking(scenario["action_text"])

    # Step 2: Preflight relevance screening (free)
    display.info("Running Preflight relevance screening...")
    try:
        relevance = await preflight.check_relevance(scenario["action_text"])
    except Exception as e:
        display.error(f"Relevance check failed: {e}")
        relevance = {"should_check": True, "error": str(e)}

    display.preflight_screening(relevance)

    should_check = relevance.get("should_check", relevance.get("relevance", True))
    if not should_check:
        display.skipped("Action not relevant to treasury policy")
        result_record["actual"] = "SKIPPED"
        return result_record

    # Step 3: Full 3-solver consensus check ($0.01)
    display.info("Running full 3-solver consensus verification...")
    try:
        check_result = await preflight.check_action(scenario["action_text"])
    except Exception as e:
        display.error(f"Consensus check failed: {e}")
        result_record["actual"] = "ERROR"
        return result_record

    display.solver_consensus(check_result)

    verdict = check_result.get("result", "UNKNOWN")
    result_record["actual"] = verdict
    proof_id = check_result.get("zk_proof_id") or check_result.get("proof_id")
    result_record["proof_id"] = proof_id

    if verdict == "SAT" and scenario.get("settle"):
        # Step 4a: Execute x402 payment on Nile
        display.info("Executing x402 payment on Nile testnet...")
        before_bal = tron.get_usdt_balance()

        try:
            tx = await x402.execute_payment()
            if tx.get("success"):
                display.settlement_result(tx)
            else:
                display.error(f"x402 payment returned status {tx.get('status_code')}")
                display.info("Attempting direct TRC-20 fallback transfer...")
                tx_hash = _fallback_transfer(tron, scenario["amount"], scenario["recipient"])
                if tx_hash:
                    display.settlement_fallback(tx_hash, scenario["amount"], scenario["recipient"])
                else:
                    display.error("Fallback transfer also failed")
        except Exception as e:
            display.error(f"x402 payment failed: {e}")
            display.info("Attempting direct TRC-20 fallback transfer...")
            tx_hash = _fallback_transfer(tron, scenario["amount"], scenario["recipient"])
            if tx_hash:
                display.settlement_fallback(tx_hash, scenario["amount"], scenario["recipient"])
            else:
                display.error("Fallback transfer also failed")

        # Wait for on-chain confirmation
        await asyncio.sleep(3)
        after_bal = tron.get_usdt_balance()
        display.balance_check(before_bal, after_bal)

    elif verdict != "SAT":
        # Step 4b: Blocked — show proof
        detail = check_result.get("detail", "Policy violation detected")
        display.blocked_result(detail, proof_id)

    # Step 5: Poll and verify ZK proof
    if proof_id:
        display.info("Polling for ZK proof receipt...")
        try:
            proof = await preflight.poll_proof(proof_id)
            display.proof_receipt(proof)

            if proof.get("proof_id") and not proof.get("error"):
                display.info("Verifying ZK proof...")
                verification = await preflight.verify_proof(proof_id)
                display.proof_verification(verification)
        except Exception as e:
            display.error(f"Proof polling/verification failed: {e}")

    return result_record


def _fallback_transfer(tron: TronNileClient, amount: float, recipient: str) -> str | None:
    """Direct TRC-20 USDT transfer as fallback when x402 flow fails."""
    try:
        from tronpy.keys import PrivateKey
        from src.config import NILE_USDT_CONTRACT, USDT_DECIMALS

        priv = PrivateKey(bytes.fromhex(tron.private_key))
        contract = tron.client.get_contract(NILE_USDT_CONTRACT)
        raw_amount = int(amount * (10 ** USDT_DECIMALS))

        txn = (
            contract.functions.transfer(recipient, raw_amount)
            .with_owner(tron.wallet_address)
            .fee_limit(100_000_000)
            .build()
            .sign(priv)
        )
        result = txn.broadcast()
        return result.get("txid", str(result))
    except Exception as e:
        console.print(f"  [dim]Fallback error: {e}[/dim]")
        return None


async def run_demo():
    """Run all 3 scenarios sequentially."""
    _check_env()

    display = DemoDisplay()
    display.intro_banner()

    # Start local x402 servers
    facilitator_proc, vendor_proc = _start_servers()

    try:
        preflight = PreflightClient(ICME_API_KEY, ICME_POLICY_ID)
        tron = TronNileClient(TRON_PRIVATE_KEY, TRON_WALLET_ADDRESS)
        x402 = X402PaymentFlow(TRON_PRIVATE_KEY)

        # Show initial balances
        display.info(f"Agent wallet: {TRON_WALLET_ADDRESS}")
        display.info(f"Vendor wallet: {VENDOR_ADDRESS}")
        try:
            agent_bal = tron.get_usdt_balance()
            agent_trx = tron.get_trx_balance()
            display.info(f"Agent USDT balance: {agent_bal:.4f}")
            display.info(f"Agent TRX balance:  {agent_trx:.4f}")
        except Exception as e:
            display.error(f"Could not fetch balances: {e}")

        scenarios = get_scenarios()
        results = []

        for scenario in scenarios:
            result = await _run_scenario(scenario, display, preflight, tron, x402)
            results.append(result)

        display.summary_table(results)

    finally:
        # Cleanup servers
        if facilitator_proc.is_alive():
            facilitator_proc.terminate()
        if vendor_proc.is_alive():
            vendor_proc.terminate()
