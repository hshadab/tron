"""Tests for src.preflight module."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.config import PROOF_POLL_INTERVAL_SECONDS, PROOF_POLL_TIMEOUT_CLI
from src.preflight import PreflightClient


@pytest.fixture
def client():
    return PreflightClient(api_key="test-key", policy_id="test-policy-id")


def test_client_init(client):
    assert client.api_key == "test-key"
    assert client.policy_id == "test-policy-id"
    assert client._headers["X-API-Key"] == "test-key"


def test_client_headers_have_content_type(client):
    assert client._headers["Content-Type"] == "application/json"


def test_poll_constants():
    assert PROOF_POLL_INTERVAL_SECONDS > 0
    assert PROOF_POLL_TIMEOUT_CLI > 0
    assert PROOF_POLL_TIMEOUT_CLI > PROOF_POLL_INTERVAL_SECONDS


@pytest.mark.asyncio
async def test_check_relevance_calls_api(client):
    mock_response = httpx.Response(
        200,
        json={"should_check": True, "matched_variables": ["amount"]},
        request=httpx.Request("POST", "https://api.icme.io/v1/checkRelevance"),
    )
    with patch("src.preflight.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        result = await client.check_relevance("Pay 1 USDT")
        assert result["should_check"] is True
        mock_http.post.assert_called_once()


@pytest.mark.asyncio
async def test_check_action_calls_api(client):
    mock_response = httpx.Response(
        200,
        json={"result": "SAT", "check_id": "abc123"},
        request=httpx.Request("POST", "https://api.icme.io/v1/checkIt"),
    )
    with patch("src.preflight.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        result = await client.check_action("Pay 1 USDT")
        assert result["result"] == "SAT"


@pytest.mark.asyncio
async def test_verify_proof_calls_api(client):
    mock_response = httpx.Response(
        200,
        json={"valid": True, "policy_hash": "abc"},
        request=httpx.Request("POST", "https://api.icme.io/v1/verify"),
    )
    with patch("src.preflight.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        result = await client.verify_proof("proof-123")
        assert result["valid"] is True


@pytest.mark.asyncio
async def test_poll_proof_returns_timeout_on_expired(client):
    mock_response = httpx.Response(
        200,
        json={"status": "pending"},
        request=httpx.Request("GET", "https://api.icme.io/v1/proof/test"),
    )
    with patch("src.preflight.httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.get.return_value = mock_response
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_http

        result = await client.poll_proof("test", timeout=0)
        assert result["error"] == "timeout"
