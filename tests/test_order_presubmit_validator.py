"""Deterministic tests for pre-submit parameter validation and symbol normalization.

Reproduces Image 4 execution failure:
- bingx code 109400: Invalid parameters, err:side: This field is required. symbol: This field must end with -USDT or -USDC.
Proves that:
1. Malformed symbols (e.g. SOLUSDT) are rejected locally by pre-submit validator.
2. Centralized symbols resolver restores canonical hyphenation (SOL-USDT).
3. Pre-submit validator validates side, positionSide, quantity, and clientOrderId.
4. Client fail-closed behavior operates without network calls or placing real orders.
"""
import pytest
from control_plane import bingx_client, symbols
from control_plane.bingx_client import OrderValidationError


def test_reproduce_and_reject_malformed_symbol():
    """Reproduce exact Image 4 error: symbol must end with -USDT or -USDC."""
    # Attempting to submit SOLUSDT (stripped hyphen) must be rejected locally
    with pytest.raises(OrderValidationError) as exc_info:
        bingx_client.validate_order_params("SOLUSDT", side="BUY", position_side="LONG", quantity=0.1, client_order_id="oph-1")
    assert "must end with -USDT or -USDC" in str(exc_info.value)

    # Empty symbol
    with pytest.raises(OrderValidationError):
        bingx_client.validate_order_params("", side="BUY", position_side="LONG", quantity=0.1)

    # Invalid symbol without suffix
    with pytest.raises(OrderValidationError):
        bingx_client.validate_order_params("BTC", side="BUY", position_side="LONG", quantity=0.1)


def test_accept_canonical_hyphenated_symbols():
    """Canonical hyphenated symbols must pass validation cleanly."""
    valid_symbols = ["SOL-USDT", "BTC-USDT", "ETH-USDT", "XRP-USDT", "BTC-USDC"]
    for s in valid_symbols:
        res = bingx_client.validate_order_params(s, side="BUY", position_side="LONG", quantity=0.5, client_order_id="oph-test-123")
        assert res == s


def test_validate_side_and_positionside():
    """Verify side and positionSide validation."""
    # Invalid side
    with pytest.raises(OrderValidationError) as exc:
        bingx_client.validate_order_params("SOL-USDT", side="INVALID", position_side="LONG", quantity=1.0)
    assert "must be BUY or SELL" in str(exc.value)

    # Missing side
    with pytest.raises(OrderValidationError):
        bingx_client.validate_order_params("SOL-USDT", side="", position_side="LONG", quantity=1.0)

    # Invalid positionSide
    with pytest.raises(OrderValidationError) as exc:
        bingx_client.validate_order_params("SOL-USDT", side="BUY", position_side="UPWARD", quantity=1.0)
    assert "Must be LONG, SHORT, or BOTH" in str(exc.value)


def test_validate_quantity():
    """Verify non-positive quantity is rejected."""
    with pytest.raises(OrderValidationError) as exc:
        bingx_client.validate_order_params("SOL-USDT", side="BUY", position_side="LONG", quantity=0.0)
    assert "Must be positive float" in str(exc.value)

    with pytest.raises(OrderValidationError):
        bingx_client.validate_order_params("SOL-USDT", side="BUY", position_side="LONG", quantity=-1.5)


def test_centralized_symbol_resolver():
    """Verify SymbolResolver normalizes non-hyphenated or messy inputs to canonical BingX format."""
    assert symbols.to_bingx_symbol("SOL-USDT") == "SOL-USDT"
    assert symbols.to_bingx_symbol("sol-usdt") == "SOL-USDT"
    assert symbols.to_bingx_symbol("SOLUSDT") == "SOL-USDT"
    assert symbols.to_bingx_symbol("btcusdt") == "BTC-USDT"
    assert symbols.to_bingx_symbol("ETHUSDC") == "ETH-USDC"

    # Gold dynamic resolution returns contract ending in -USDT or -USDC
    gold_res = symbols.to_bingx_symbol("GOLD (XAU)")
    assert gold_res.endswith("-USDT") or gold_res.endswith("-USDC")
    assert "GOLD" in gold_res or "XAU" in gold_res


def test_client_local_presubmit_gate_blocks_network():
    """Verify Client.market_order and Client.set_leverage fail before any network request."""
    # Constructed with dummy keys, allow_trade=True to verify pre-submit validator triggers before network
    client = bingx_client.Client("dummy_key", "dummy_secret", allow_trade=True)

    # Submitting malformed symbol must throw OrderValidationError locally without network call
    with pytest.raises(OrderValidationError):
        client.market_order("SOLUSDT", "BUY", "LONG", 0.5, "oph-test-1")

    with pytest.raises(OrderValidationError):
        client.set_leverage("SOLUSDT", 20)

    # Submitting invalid side must throw OrderValidationError locally
    with pytest.raises(OrderValidationError):
        client.market_order("SOL-USDT", "HOLD", "LONG", 0.5, "oph-test-1")
