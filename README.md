# Preflight x TRON: Treasury Guardian Demo

## The Problem

AI agents that can spend money are coming. An agent that can call APIs, book services, or buy compute on your behalf needs a wallet. But a wallet in the hands of an autonomous program is a liability:

- The agent might overspend on a single call.
- A malicious prompt injection could trick it into draining funds to an attacker's address.
- There's no audit trail proving *why* a payment was approved or denied.

Without guardrails, every agent transaction is a trust-me-bro arrangement between you and your code.

## What This Demo Does

This project wires together two protocols to solve that problem on TRON:

1. **ICME Preflight** — a verification service that checks every proposed payment against a formal treasury policy before it executes. Three independent solvers (LLM extraction, automated reasoning, Z3 SMT solver) must unanimously agree the payment is safe. Every decision, approve or deny, is wrapped in a zero-knowledge proof so there's a tamper-proof receipt.

2. **x402** — an HTTP-native payment protocol. A server returns `402 Payment Required` with pricing details. The client signs a payment authorization, retries the request, and the server settles the payment on-chain. No payment pages, no redirects, no manual approval — the agent handles the entire flow programmatically.

The demo runs three scenarios back-to-back on TRON's Nile testnet:

| # | Scenario | Amount | Result | What Happens |
|---|----------|--------|--------|--------------|
| 1 | Legitimate API purchase | 1 USDT | SAT (approved) | Payment settles on-chain via x402 |
| 2 | Budget breach | 5,000 USDT | UNSAT (blocked) | Exceeds per-transaction limit, blocked with ZK proof |
| 3 | Social engineering attack | 500 USDT | UNSAT (blocked) | Urgency language + unknown address, blocked with ZK proof |

All Preflight API calls hit the real production service. All TRON transactions happen on the real Nile testnet. Nothing is mocked.

## How It Works

```
Agent decides to make a payment
         |
         v
  Preflight Relevance Screen (free)
  "Does this action touch any policy variables?"
         |
         v
  3-Solver Consensus Check ($0.01)
  ┌─────────────────────────────────┐
  │  LLM extracts variables         │
  │  Automated Reasoning evaluates   │
  │  Z3 SMT solver verifies          │
  │  All three must agree             │
  └─────────────────────────────────┘
         |                    |
      SAT (safe)         UNSAT (unsafe)
         |                    |
         v                    v
  x402 payment         Transaction blocked
  settles on TRON      ZK proof receipt logged
```

The treasury policy is written in plain English:

- Max 100 USDT per transaction
- Max 500 USDT daily aggregate
- Only approved vendor addresses
- No emotional appeals or urgency language

Preflight compiles this into formal SMT-LIB2 logic once, then evaluates every action against it.

## Why This Matters

**For agent builders:** You get a deterministic policy layer between your agent's intent and its wallet. The agent can reason freely about what to buy; the policy layer decides whether it's actually allowed to. Separation of concerns.

**For treasuries and DAOs:** Every payment decision produces a ZK proof receipt. You can verify after the fact that the policy was enforced correctly without revealing the policy rules themselves. The seller only sees "approved" or "denied."

**For the x402 ecosystem:** This shows that Preflight slots cleanly into the x402 flow as a pre-check. The agent doesn't need to understand the policy — it just asks, gets a yes or no, and proceeds accordingly.

## Requirements

- Python 3.10 - 3.12 (tvm-x402 requires this range)
- An ICME API key ($5 one-time, includes 325 credits)
- TRON Nile testnet wallets (free from faucet)

## Setup

### 1. Install

```bash
cd /home/hshadab/tron
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Generate wallets

```bash
python scripts/setup_wallet.py
```

This creates three wallets (agent, vendor, facilitator) and prints `.env` values to copy.

### 3. Fund wallets on Nile faucet

Go to https://nileex.io/join/getJoinPage and claim tokens:

- **Agent wallet** — needs USDT (for payments) and TRX (for energy/bandwidth)
- **Facilitator wallet** — needs TRX (for gas on settlement transactions)
- **Vendor wallet** — just receives payments, no funding needed

### 4. Get an ICME API key

```bash
curl -X POST https://api.icme.io/v1/createUserCard \
  -H "Content-Type: application/json" \
  -d '{"username": "tron-demo"}'
```

Complete the Stripe checkout ($5, includes 325 credits). Save the API key to `.env`.

### 5. Compile the treasury policy (one-time, 300 credits)

```bash
python scripts/setup_policy.py
```

This streams the policy through Preflight's `/v1/makeRules` endpoint and returns a `policy_id`. Save it to `.env`.

### 6. Approve USDT allowance

```bash
python scripts/approve_allowance.py
```

The agent wallet must approve the x402 PaymentPermit contract to spend its USDT.

### 7. Run the demo

```bash
python run.py
```

This starts a local x402 facilitator and vendor server, then runs all three scenarios with full terminal output.

## Environment Variables

Copy `.env.example` to `.env` and fill in:

| Variable | Description |
|---|---|
| `ICME_API_KEY` | Preflight API key (from step 4) |
| `ICME_POLICY_ID` | Compiled policy ID (from step 5) |
| `TRON_PRIVATE_KEY` | Agent wallet private key, hex (from step 2) |
| `TRON_WALLET_ADDRESS` | Agent wallet address (from step 2) |
| `VENDOR_ADDRESS` | Vendor wallet address (from step 2) |
| `FACILITATOR_PRIVATE_KEY` | Facilitator wallet private key, hex (from step 2) |
| `FACILITATOR_ADDRESS` | Facilitator wallet address (from step 2) |

## Cost

| Item | Cost |
|---|---|
| ICME account setup | $5.00 (includes 325 credits) |
| Policy compilation | 300 credits (one-time) |
| 3 verification checks | 3 credits |
| TRON Nile testnet | Free |
| **Total** | **$5.00** |

After initial setup, each additional demo run costs 3 credits ($0.03). The remaining 22 credits support about 7 more runs.

## Project Structure

```
tron/
├── run.py                      # Entry point
├── pyproject.toml              # Dependencies
├── .env.example                # Env var template
├── scripts/
│   ├── setup_wallet.py         # Generate 3 Nile testnet wallets
│   ├── setup_policy.py         # Compile treasury policy via Preflight
│   └── approve_allowance.py    # Approve USDT spending for x402
└── src/
    ├── config.py               # Constants, env vars, policy text, scenarios
    ├── preflight.py            # ICME Preflight API client
    ├── tron_client.py          # tronpy wrapper for balance checks
    ├── x402_flow.py            # x402 client payment flow (tvm-x402)
    ├── vendor_server.py        # Local x402-protected weather API
    ├── facilitator_server.py   # Local x402 facilitator for Nile
    ├── display.py              # Rich terminal output
    └── demo.py                 # Main orchestrator
```

## Built With

- [ICME Preflight](https://docs.icme.io) — formal verification + ZK proofs for AI agent actions
- [tvm-x402](https://pypi.org/project/tvm-x402/) — x402 payment protocol SDK for TRON
- [tronpy](https://github.com/tronprotocol/tronpy) — Python client for TRON
- [Rich](https://github.com/Textualize/rich) — terminal formatting
