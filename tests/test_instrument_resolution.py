"""Unit and Integration Tests for Canonical Instrument Resolution.

Covers:
- Strict 17-field CanonicalInstrument contract
- Dynamic BingX contract discovery and alias mapping
- Netflix resolution (NFLX -> NCSKNETFLIX2USD-USDT) without hardcoded symbol hacks
- Universal watchlist & commodity resolution (BTC, ETH, SOL, XRP, GOLD, SILVER)
- Segregated asset class validation (CRYPTO vs US_EQUITY vs COMMODITIES)
- Safe error handling on unavailable instruments
"""
import os
import sys
sys.path.insert(0, os.path.abspath("."))

import pytest
from models.instrument import CanonicalInstrument
from control_plane.instruments import InstrumentResolver, InstrumentResolutionError, resolve_instrument


def test_canonical_instrument_model_contract():
    """Verify CanonicalInstrument contains all 17 required attributes."""
    inst = CanonicalInstrument(
        display_symbol="NFLX",
        internal_instrument_id="US_EQUITY:NFLX",
        asset_class="US_EQUITY",
        venue="BINGX",
        venue_product="TRADFI_PERPETUAL",
        venue_symbol="NCSKNETFLIX2USD-USDT",
        quote_currency="USDT",
        order_endpoint="/openApi/swap/v2/trade/order",
        market_data_symbol="NCSKNETFLIX2USD-USDT",
        price_precision=2,
        quantity_precision=4,
        min_order_size=0.0294,
        min_notional=2.0,
        leverage_rules={"max_leverage": 20, "default_leverage": 5},
        trading_status="TRADABLE",
        source="BINGX_REST_CONTRACTS",
        discovery_timestamp=1790890000000,
        last_refreshed=1790890000000
    )
    d = inst.to_dict()
    assert d["display_symbol"] == "NFLX"
    assert d["venue_symbol"] == "NCSKNETFLIX2USD-USDT"
    assert d["price_precision"] == 2
    assert d["quantity_precision"] == 4
    assert d["min_order_size"] == 0.0294

    inst2 = CanonicalInstrument.from_dict(d)
    assert inst2 == inst


def test_netflix_generic_resolution():
    """Verify Netflix resolves to NCSKNETFLIX2USD-USDT from both ticker and name."""
    resolver = InstrumentResolver.get_instance()
    resolver.refresh(force=True)

    # 1. User selects NFLX
    nflx = resolver.resolve("NFLX")
    assert nflx.display_symbol == "NFLX"
    assert nflx.venue_symbol == "NCSKNETFLIX2USD-USDT"
    assert nflx.asset_class == "US_EQUITY"
    assert nflx.venue_product == "TRADFI_PERPETUAL"
    assert nflx.trading_status == "TRADABLE"
    assert nflx.quantity_precision == 4
    assert nflx.min_order_size == 0.0294

    # 2. User searches 'Netflix'
    nflx_alias = resolver.resolve("Netflix")
    assert nflx_alias.venue_symbol == "NCSKNETFLIX2USD-USDT"

    # 3. User passes raw venue symbol
    nflx_raw = resolver.resolve("NCSKNETFLIX2USD-USDT")
    assert nflx_raw.venue_symbol == "NCSKNETFLIX2USD-USDT"


def test_crypto_resolution():
    """Verify crypto symbols resolve to standard perpetual contracts."""
    resolver = InstrumentResolver.get_instance()
    
    btc = resolver.resolve("BTC")
    assert btc.display_symbol == "BTC-USDT"
    assert btc.venue_symbol == "BTC-USDT"
    assert btc.asset_class == "CRYPTO"
    assert btc.venue_product == "STANDARD_PERPETUAL"

    eth = resolver.resolve("ETH-USDT")
    assert eth.display_symbol == "ETH-USDT"
    assert eth.venue_symbol == "ETH-USDT"
    assert eth.asset_class == "CRYPTO"

    sol = resolver.resolve("SOL")
    assert sol.venue_symbol == "SOL-USDT"


def test_commodities_resolution():
    """Verify commodities resolve to dynamic TradFi contracts."""
    resolver = InstrumentResolver.get_instance()

    gold = resolver.resolve("GOLD")
    assert gold.display_symbol == "GOLD"
    assert gold.venue_symbol == "NCCOGOLD2USD-USDT"
    assert gold.asset_class == "COMMODITIES"
    assert gold.venue_product == "TRADFI_PERPETUAL"

    xau = resolver.resolve("XAU")
    assert xau.venue_symbol == "NCCOGOLD2USD-USDT"

    silver = resolver.resolve("SILVER")
    assert silver.display_symbol == "SILVER"
    assert silver.venue_symbol == "NCCOXAG2USD-USDT"
    assert silver.asset_class == "COMMODITIES"


def test_asset_class_segregation():
    """Verify asset class constraints prevent cross-asset pollution."""
    resolver = InstrumentResolver.get_instance()

    # NFLX is US_EQUITY, resolving with asset_class='CRYPTO' must fail
    with pytest.raises(InstrumentResolutionError) as exc:
        resolver.resolve("NFLX", asset_class="CRYPTO")
    assert exc.value.code in ("PRODUCT_NOT_SUPPORTED", "INSTRUMENT_NOT_AVAILABLE")

    # BTC is CRYPTO, resolving with asset_class='US_EQUITY' must fail
    with pytest.raises(InstrumentResolutionError) as exc:
        resolver.resolve("BTC", asset_class="US_EQUITY")
    assert exc.value.code in ("PRODUCT_NOT_SUPPORTED", "INSTRUMENT_NOT_AVAILABLE")


def test_invalid_symbol_error():
    """Verify non-existent symbols fail closed with INSTRUMENT_NOT_AVAILABLE."""
    resolver = InstrumentResolver.get_instance()

    with pytest.raises(InstrumentResolutionError) as exc:
        resolver.resolve("NONEXISTENT_TICKER_123")
    assert exc.value.code == "INSTRUMENT_NOT_AVAILABLE"


def test_cache_invalidation():
    """Verify cache invalidation resets timestamps and re-queries cleanly."""
    resolver = InstrumentResolver.get_instance()
    resolver.refresh()
    assert resolver.is_cache_valid()

    resolver.invalidate_cache()
    assert not resolver.is_cache_valid()

    count = resolver.refresh()
    assert count > 0
    assert resolver.is_cache_valid()
