"""Tests for src.config module."""

from src.config import (
    DEFAULT_FEE_LIMIT_SUN,
    MAX_UINT256,
    NILE_USDT_CONTRACT,
    PAYMENT_PERMIT_ADDRESS,
    PREFLIGHT_BASE_URL,
    SERVER_STARTUP_DELAY_SECONDS,
    TX_CONFIRM_DELAY_SECONDS,
    USDT_DECIMALS,
    get_scenarios,
)


def test_constants_are_reasonable():
    assert USDT_DECIMALS == 6
    assert DEFAULT_FEE_LIMIT_SUN == 100_000_000
    assert MAX_UINT256 == 2**256 - 1
    assert SERVER_STARTUP_DELAY_SECONDS > 0
    assert TX_CONFIRM_DELAY_SECONDS > 0


def test_contract_addresses_are_tron_format():
    assert NILE_USDT_CONTRACT.startswith("T")
    assert PAYMENT_PERMIT_ADDRESS.startswith("T")


def test_preflight_base_url():
    assert PREFLIGHT_BASE_URL.startswith("https://")
    assert "/v1" in PREFLIGHT_BASE_URL


def test_get_scenarios_returns_three():
    scenarios = get_scenarios()
    assert len(scenarios) == 3


def test_scenarios_have_required_keys():
    required_keys = {
        "number",
        "name",
        "description",
        "action_text",
        "amount",
        "recipient",
        "expected_result",
        "settle",
    }
    for scenario in get_scenarios():
        missing = required_keys - scenario.keys()
        assert not missing, f"Scenario {scenario.get('number')} missing keys: {missing}"


def test_scenario_expected_results():
    scenarios = get_scenarios()
    assert scenarios[0]["expected_result"] == "SAT"
    assert scenarios[1]["expected_result"] == "UNSAT"
    assert scenarios[2]["expected_result"] == "UNSAT"


def test_scenario_amounts_positive():
    for scenario in get_scenarios():
        assert scenario["amount"] > 0
