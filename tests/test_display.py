"""Tests for src.display module."""

from src.display import DemoDisplay


def test_display_instantiates():
    display = DemoDisplay()
    assert display is not None


def test_display_methods_exist():
    display = DemoDisplay()
    assert callable(display.intro_banner)
    assert callable(display.scenario_header)
    assert callable(display.agent_thinking)
    assert callable(display.preflight_screening)
    assert callable(display.solver_consensus)
    assert callable(display.settlement_result)
    assert callable(display.settlement_fallback)
    assert callable(display.blocked_result)
    assert callable(display.proof_receipt)
    assert callable(display.proof_verification)
    assert callable(display.balance_check)
    assert callable(display.skipped)
    assert callable(display.info)
    assert callable(display.error)
    assert callable(display.summary_table)
