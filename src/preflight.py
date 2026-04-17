"""ICME Preflight API client — relevance check, full verification, proof polling."""

import json
import logging
import time
from typing import TypedDict

import httpx

from src.config import PREFLIGHT_BASE_URL

logger = logging.getLogger(__name__)

PROOF_POLL_INTERVAL_SECONDS = 1
PROOF_POLL_TIMEOUT_SECONDS = 120


class RelevanceResult(TypedDict, total=False):
    relevance: bool
    should_check: bool
    matched_variables: list[str]
    time_ms: int
    error: str


class ConsensusResult(TypedDict, total=False):
    check_id: str
    result: str  # "SAT" | "UNSAT"
    detail: str
    llm_result: str
    ar_result: str
    z3_result: str
    zk_proof_id: str
    zk_proof_url: str
    verification_time_ms: int
    duration_ms: int


class ProofResult(TypedDict, total=False):
    proof_id: str
    policy_hash: str
    result: str
    valid: bool
    trace_length: int
    created_at: str
    status: str
    error: str


class VerificationResult(TypedDict, total=False):
    valid: bool
    policy_hash: str
    claimed_result: str
    verify_ms: int


class PreflightClient:
    """Async client for the ICME Preflight API (https://api.icme.io/v1)."""

    def __init__(self, api_key: str, policy_id: str) -> None:
        self.api_key = api_key
        self.policy_id = policy_id
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    # ── SSE helper ─────────────────────────────────────────────────────────
    @staticmethod
    async def _post_sse_or_json(
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
        payload: dict,
    ) -> dict:
        """POST to an endpoint that may return JSON or an SSE stream.
        If SSE, parse events and return the final 'done' event.
        """
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()

        # SSE response — parse data lines to find the final event
        done_event: dict | None = None
        for line in resp.text.splitlines():
            data = line[len("data:") :].strip() if line.startswith("data:") else line.strip()
            if not data or not data.startswith("{"):
                continue
            try:
                parsed = json.loads(data)
                if parsed.get("step") == "done" or parsed.get("result"):
                    done_event = parsed
            except json.JSONDecodeError:
                continue

        if done_event is None:
            raise RuntimeError(f"SSE stream from {url} ended without a result event")
        return done_event

    # ── Free relevance screening ───────────────────────────────────────────
    async def check_relevance(self, action: str) -> RelevanceResult:
        """POST /v1/checkRelevance — free screening.
        Returns dict with keys like: relevance, should_check, matched_variables, etc.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            return await self._post_sse_or_json(
                client,
                f"{PREFLIGHT_BASE_URL}/checkRelevance",
                self._headers,
                {"policy_id": self.policy_id, "action": action},
            )

    # ── Full 3-solver consensus check ──────────────────────────────────────
    async def check_action(self, action: str) -> ConsensusResult:
        """POST /v1/checkIt — full verification (1 credit / $0.01).
        Returns dict with keys like: check_id, result (SAT/UNSAT), detail,
        llm_result, ar_result, z3_result, zk_proof_id, zk_proof_url, etc.
        """
        async with httpx.AsyncClient(timeout=120) as client:
            return await self._post_sse_or_json(
                client,
                f"{PREFLIGHT_BASE_URL}/checkIt",
                self._headers,
                {"policy_id": self.policy_id, "action": action},
            )

    # ── ZK proof polling ───────────────────────────────────────────────────
    async def poll_proof(
        self,
        proof_id: str,
        timeout: int = PROOF_POLL_TIMEOUT_SECONDS,
    ) -> ProofResult:
        """GET /v1/proof/{id} — poll every 5s until proof is ready.
        Returns dict with: proof_id, policy_hash, result, valid, trace_length, etc.
        """
        import asyncio

        url = f"{PREFLIGHT_BASE_URL}/proof/{proof_id}"
        deadline = time.monotonic() + timeout

        async with httpx.AsyncClient(timeout=30) as client:
            while time.monotonic() < deadline:
                resp = await client.get(url, headers=self._headers)
                if resp.status_code == 200:
                    data = resp.json()
                    status = data.get("status", "")
                    if status in ("ready", "completed", "done") or data.get("valid") is not None:
                        return data
                await asyncio.sleep(PROOF_POLL_INTERVAL_SECONDS)

        return {"error": "timeout", "proof_id": proof_id}

    # ── Proof verification ─────────────────────────────────────────────────
    async def verify_proof(self, proof_id: str) -> VerificationResult:
        """POST /v1/verifyProof — public proof verification (no API key needed).
        Returns dict with: valid, policy_hash, claimed_result, verify_ms, etc.
        """
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{PREFLIGHT_BASE_URL}/verifyProof",
                headers={"Content-Type": "application/json"},
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
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        policy_id = None

        async with (
            httpx.AsyncClient(timeout=300) as client,
            client.stream(
                "POST",
                f"{PREFLIGHT_BASE_URL}/makeRules",
                headers=headers,
                json={"policy": policy_text},
            ) as resp,
        ):
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
                        raw = line[len("data:") :].strip()
                        if not raw:
                            continue
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            logger.debug("SSE (text): %s", raw)
                            continue

                        step = event.get("step", "")
                        logger.debug("SSE step: %s", step)

                        if "policy_id" in event:
                            policy_id = event["policy_id"]
                        if step == "done":
                            if not policy_id:
                                policy_id = event.get("policy_id", event.get("id", ""))
                            return policy_id

        if policy_id:
            return policy_id
        raise RuntimeError("SSE stream ended without returning a policy_id")
