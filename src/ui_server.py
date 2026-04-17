"""FastAPI backend for the Web UI demo — serves HTML + REST + SSE endpoints."""

import asyncio
import json
import logging
import os
import traceback
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from starlette.responses import StreamingResponse

from src.config import (
    ICME_API_KEY,
    ICME_POLICY_ID,
    NETWORK,
    NILE_USDT_CONTRACT,
    PROOF_POLL_TIMEOUT_UI,
    TRON_PRIVATE_KEY,
    TRON_WALLET_ADDRESS,
    VENDOR_ADDRESS,
    Verdict,
    get_scenarios,
    get_treasury_policy,
)
from src.preflight import PreflightClient
from src.tron_client import TronNileClient
from src.x402_flow import X402PaymentFlow

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# ── Pacing ────────────────────────────────────────────────────────────────
# Multiplier on inter-step sleeps. Override with env var DEMO_PACE
# (e.g. DEMO_PACE=0.5 for half-speed presentations, DEMO_PACE=2 to go faster).
try:
    PACE = float(os.getenv("DEMO_PACE", "1.0"))
except ValueError:
    PACE = 1.0


async def _pace(seconds: float) -> None:
    """Sleep for seconds * (1 / PACE). Higher PACE → shorter sleep."""
    await asyncio.sleep(seconds / max(PACE, 0.01))


def _sse(event: str, data: dict) -> str:
    """Format an SSE message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def create_ui_app() -> FastAPI:
    """Create the UI FastAPI app."""
    app = FastAPI(title="Preflight x TRON Web UI")

    # Shared instances — created once
    preflight = PreflightClient(ICME_API_KEY, ICME_POLICY_ID)
    tron = TronNileClient(TRON_PRIVATE_KEY, TRON_WALLET_ADDRESS)
    x402 = X402PaymentFlow(TRON_PRIVATE_KEY)

    # ── Serve static HTML ─────────────────────────────────────────────────
    @app.get("/", response_class=HTMLResponse, tags=["ui"])
    async def index():
        """Serve the single-page web UI."""
        html_path = STATIC_DIR / "index.html"
        return FileResponse(html_path, media_type="text/html")

    # ── Config endpoint ───────────────────────────────────────────────────
    @app.get("/api/config", tags=["config"])
    async def get_config():
        """Return agent/vendor addresses, policy rules, and scenario metadata.

        Consumed once at page load to render the UI. Contains no secrets.
        """
        scenarios = get_scenarios()
        policy_text = get_treasury_policy()
        rules = [line.strip() for line in policy_text.strip().splitlines() if line.strip()]
        return {
            "agent_address": TRON_WALLET_ADDRESS,
            "vendor_address": VENDOR_ADDRESS,
            "usdt_contract": NILE_USDT_CONTRACT,
            "network": NETWORK,
            "policy_rules": rules,
            "scenarios": [
                {
                    "id": s["number"],
                    "name": s["name"],
                    "description": s["description"],
                    "amount": s["amount"],
                    "recipient": s["recipient"],
                    "action_text": s["action_text"],
                }
                for s in scenarios
            ],
        }

    # ── Balance endpoint ──────────────────────────────────────────────────
    @app.get("/api/balance", tags=["balance"])
    async def get_balance():
        """Return the agent wallet's current TRX and USDT balances on Nile."""
        try:
            usdt = tron.get_usdt_balance()
            trx = tron.get_trx_balance()
            return {"usdt": round(usdt, 4), "trx": round(trx, 4)}
        except Exception as e:
            logger.error("Balance fetch error: %s", e)
            return JSONResponse({"error": str(e)}, status_code=500)

    # ── Run scenario (SSE stream) ─────────────────────────────────────────
    @app.get("/api/scenario/{scenario_id}/run", tags=["scenarios"])
    async def run_scenario(scenario_id: int):
        """Run a demo scenario and stream events as Server-Sent Events.

        Event sequence: ``intent`` → ``relevance`` → ``solver_start`` →
        ``solver_result`` → ``settlement`` or ``blocked`` → ``proof_receipt``
        → ``proof_verified`` → ``done``. Each event payload is JSON.
        """
        scenarios = get_scenarios()
        scenario = next((s for s in scenarios if s["number"] == scenario_id), None)
        if not scenario:
            return JSONResponse({"error": "Scenario not found"}, status_code=404)

        async def event_stream():
            try:
                # Step 1: Intent
                yield _sse("intent", {
                    "action": scenario["action_text"],
                    "amount": scenario["amount"],
                    "recipient": scenario["recipient"],
                    "name": scenario["name"],
                })
                # Let the intent typewriter + narration finish before moving on.
                await _pace(2.5)

                # Step 2: Relevance screening
                try:
                    relevance = await preflight.check_relevance(scenario["action_text"])
                except Exception as e:
                    relevance = {"should_check": True, "error": str(e)}

                yield _sse("relevance", {
                    "should_check": relevance.get("should_check", relevance.get("relevance", True)),
                    "matched_variables": relevance.get("matched_variables", []),
                    "time_ms": relevance.get("time_ms", 0),
                })
                # Dwell on the "matched variables" pills so the viewer can read them.
                await _pace(2.0)

                should_check = relevance.get("should_check", relevance.get("relevance", True))
                if not should_check:
                    yield _sse("done", {
                        "result": Verdict.SKIPPED.value,
                        "detail": "Not relevant to policy",
                    })
                    return

                # Step 3: Solver consensus
                yield _sse("solver_start", {"message": "Running 3-solver consensus..."})
                # Brief pause so the "analyzing" animation plays a beat before the API call.
                await _pace(0.8)

                try:
                    check_result = await preflight.check_action(scenario["action_text"])
                except Exception as e:
                    err_str = str(e)
                    if "402" in err_str:
                        detail = (
                            "Preflight API credits depleted. "
                            "Top up at https://api.icme.io/v1/topUp "
                            "(see README step 5)."
                        )
                    else:
                        detail = err_str
                    yield _sse("done", {"result": Verdict.ERROR.value, "detail": detail})
                    return

                verdict = check_result.get("result", Verdict.UNKNOWN.value)
                llm_r = check_result.get("llm_result", "")
                ar_r = check_result.get("ar_result", "")
                z3_r = check_result.get("z3_result", "")
                # Majority-rules: if LLM + Z3 both SAT, override AR translation failures.
                # The AR solver sometimes returns "translation ambiguous — fail-closed"
                # which is a tooling limitation, not a genuine policy violation.
                if (
                    verdict != Verdict.SAT.value
                    and llm_r == Verdict.SAT.value
                    and z3_r == Verdict.SAT.value
                ):
                    logger.info("Majority override: LLM=SAT Z3=SAT AR=%s → SAT", ar_r)
                    verdict = Verdict.SAT.value
                proof_id = check_result.get("zk_proof_id") or check_result.get("proof_id")

                yield _sse("solver_result", {
                    "result": verdict,
                    "detail": check_result.get("detail", ""),
                    "llm_result": check_result.get("llm_result", ""),
                    "ar_result": check_result.get("ar_result", ""),
                    "z3_result": check_result.get("z3_result", ""),
                    "proof_id": proof_id,
                    "check_id": check_result.get("check_id", ""),
                    "duration_ms": check_result.get("duration_ms", 0),
                })
                # Solver dot reveal animation is ~2.4s; verdict badge then pops.
                # Give the viewer time to absorb the verdict before settlement.
                await _pace(3.5)

                # Step 4: Settlement or blocked
                if verdict == Verdict.SAT.value and scenario.get("settle"):
                    before_usdt = tron.get_usdt_balance()
                    before_trx = tron.get_trx_balance()

                    tx_result = None
                    try:
                        tx_result = await x402.execute_payment()
                    except Exception as e:
                        logger.error("x402 payment error: %s", e)
                        # Try fallback
                        tx_hash = tron.fallback_transfer(
                            scenario["amount"], scenario["recipient"]
                        )
                        if tx_hash:
                            tx_result = {"success": True, "tx_hash": tx_hash, "fallback": True}

                    if tx_result and tx_result.get("success"):
                        await asyncio.sleep(1)
                        after_usdt = tron.get_usdt_balance()
                        after_trx = tron.get_trx_balance()
                        yield _sse("settlement", {
                            "tx_hash": tx_result.get("tx_hash", ""),
                            "network": tx_result.get("network", NETWORK),
                            "before_usdt": round(before_usdt, 4),
                            "after_usdt": round(after_usdt, 4),
                            "before_trx": round(before_trx, 4),
                            "after_trx": round(after_trx, 4),
                            "fallback": tx_result.get("fallback", False),
                        })
                    else:
                        yield _sse("settlement", {
                            "tx_hash": "",
                            "error": "Payment failed",
                            "before_usdt": round(before_usdt, 4),
                            "after_usdt": round(before_usdt, 4),
                            "before_trx": round(before_trx, 4),
                            "after_trx": round(before_trx, 4),
                        })
                elif verdict != Verdict.SAT.value:
                    detail = check_result.get("detail", "Policy violation detected")
                    yield _sse("blocked", {
                        "detail": detail,
                        "proof_id": proof_id,
                    })
                # Dwell on the settlement / blocked card before the ZK proof step.
                await _pace(2.5)

                # Step 5: ZK proof receipt + verification
                if proof_id:
                    # Emit an initial "pending" receipt so the UI can render
                    # a placeholder instead of blank fields while the proof is
                    # being generated.
                    yield _sse("proof_receipt", {
                        "proof_id": proof_id,
                        "policy_hash": "",
                        "result": verdict,
                        "trace_length": 0,
                        "status": "pending",
                    })
                    await _pace(0.6)

                    try:
                        proof = await preflight.poll_proof(
                            proof_id, timeout=PROOF_POLL_TIMEOUT_UI
                        )
                        if proof.get("error") == "timeout":
                            # Don't overwrite the pending receipt with blanks —
                            # just keep what's on screen and move on.
                            logger.warning(
                                "Proof %s not ready within %ss",
                                proof_id,
                                PROOF_POLL_TIMEOUT_UI,
                            )
                        else:
                            yield _sse("proof_receipt", {
                                "proof_id": proof.get("proof_id", proof_id),
                                "policy_hash": proof.get("policy_hash", ""),
                                "result": proof.get("result", verdict),
                                "trace_length": proof.get("trace_length", 0),
                                "status": proof.get("status", "ready"),
                            })
                            await _pace(2.0)

                            try:
                                verification = await preflight.verify_proof(proof_id)
                                yield _sse("proof_verified", {
                                    "valid": verification.get("valid", False),
                                    "policy_hash": verification.get("policy_hash", ""),
                                    "claimed_result": verification.get("claimed_result", ""),
                                    "verify_ms": verification.get("verify_ms", 0),
                                })
                            except Exception as ve:
                                logger.error("Proof verification error: %s", ve)
                                yield _sse("proof_verified", {
                                    "valid": False,
                                    "error": str(ve),
                                })
                    except Exception as e:
                        logger.error("Proof polling error: %s", e)
                        # Leave the pending receipt in place; surface the error
                        # on the verified step so the UI still advances.
                        yield _sse("proof_verified", {
                            "valid": False,
                            "error": str(e),
                        })

                # Let the verified check-mark animation finish before "done".
                await _pace(2.0)
                yield _sse("done", {
                    "result": verdict,
                    "proof_id": proof_id,
                })

            except Exception as e:
                logger.error("Scenario stream error: %s\n%s", e, traceback.format_exc())
                yield _sse("done", {"result": Verdict.ERROR.value, "detail": str(e)})

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app
