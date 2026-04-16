"""ICME Preflight API client — relevance check, full verification, proof polling."""

import asyncio
import json
import httpx

from src.config import PREFLIGHT_BASE_URL


class PreflightClient:
    """Async client for the ICME Preflight API (https://api.icme.io/v1)."""

    def __init__(self, api_key: str, policy_id: str):
        self.api_key = api_key
        self.policy_id = policy_id
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    # ── Free relevance screening ───────────────────────────────────────────
    async def check_relevance(self, action: str) -> dict:
        """POST /v1/checkRelevance — free screening.
        Returns dict with keys like: relevance, should_check, matched_variables, etc.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{PREFLIGHT_BASE_URL}/checkRelevance",
                headers=self._headers,
                json={
                    "policy_id": self.policy_id,
                    "action": action,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── Full 3-solver consensus check ──────────────────────────────────────
    async def check_action(self, action: str) -> dict:
        """POST /v1/checkIt — full verification (1 credit / $0.01).
        Returns dict with keys like: check_id, result (SAT/UNSAT), detail,
        llm_result, ar_result, z3_result, zk_proof_id, zk_proof_url, etc.
        """
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{PREFLIGHT_BASE_URL}/checkIt",
                headers=self._headers,
                json={
                    "policy_id": self.policy_id,
                    "action": action,
                },
            )
            resp.raise_for_status()
            return resp.json()

    # ── ZK proof polling ───────────────────────────────────────────────────
    async def poll_proof(self, proof_id: str, timeout: int = 120) -> dict:
        """GET /v1/proof/{id} — poll every 5s until proof is ready.
        Returns dict with: proof_id, policy_hash, result, valid, trace_length, etc.
        """
        url = f"{PREFLIGHT_BASE_URL}/proof/{proof_id}"
        deadline = asyncio.get_event_loop().time() + timeout

        async with httpx.AsyncClient(timeout=30) as client:
            while asyncio.get_event_loop().time() < deadline:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    if status in ("ready", "completed", "done") or data.get("valid") is not None:
                        return data
                await asyncio.sleep(5)

        return {"error": "timeout", "proof_id": proof_id}

    # ── Proof verification ─────────────────────────────────────────────────
    async def verify_proof(self, proof_id: str) -> dict:
        """POST /v1/verify — public proof verification.
        Returns dict with: valid, policy_hash, claimed_result, verify_ms, etc.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{PREFLIGHT_BASE_URL}/verify",
                headers=self._headers,
                json={"proof_id": proof_id},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Policy compilation (one-time, used by setup_policy.py) ─────────────
    @staticmethod
    async def compile_policy(api_key: str, policy_text: str) -> str:
        """POST /v1/makeRules — SSE stream, returns policy_id.
        Costs 300 credits (~$3). Parses SSE events until step=done.
        """
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        policy_id = None

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                f"{PREFLIGHT_BASE_URL}/makeRules",
                headers=headers,
                json={"policy": policy_text},
            ) as resp:
                resp.raise_for_status()
                buffer = ""
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data:"):
                            raw = line[len("data:"):].strip()
                            if not raw:
                                continue
                            try:
                                event = json.loads(raw)
                            except json.JSONDecodeError:
                                print(f"  SSE (text): {raw}")
                                continue

                            step = event.get("step", "")
                            print(f"  SSE step: {step}")

                            if "policy_id" in event:
                                policy_id = event["policy_id"]
                            if step == "done":
                                if not policy_id:
                                    policy_id = event.get("policy_id", event.get("id", ""))
                                return policy_id

        if policy_id:
            return policy_id
        raise RuntimeError("SSE stream ended without returning a policy_id")
