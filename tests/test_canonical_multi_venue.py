"""Unit tests for Authoritative Canonical Multi-Venue Instrument Architecture.

Layer: tests/test_canonical_multi_venue.py
"""
import pytest
from models.instrument import CanonicalInstrument, MappingStatus
from control_plane.instruments import (
    InstrumentResolver,
    InstrumentResolutionError,
    resolve_instrument,
    get_instrument_resolver,
)


def test_canonical_instrument_model_dual_venue():
    data = {
        "canonical_instrument_id": "CRYPTO:BTC-USDT",
        "asset": "BTC",
        "quote_currency": "USDT",
        "asset_class": "CRYPTO",
        "display_symbol": "BTC-USDT",
        "internal_instrument_id": "CRYPTO:BTC-USDT",
        "venue": "MULTI_VENUE",
        "binance_symbol": "BTCUSDT",
        "binance_precision": 1,
        "binance_min_quantity": 0.001,
        "binance_min_notional": 5.0,
        "bingx_symbol": "BTC-USDT",
        "bingx_precision": 1,
        "bingx_min_quantity": 0.0001,
        "bingx_min_notional": 2.0,
        "mapping_status": MappingStatus.TRADABLE_BOTH.value,
        "trading_status": "TRADABLE",
    }
    inst = CanonicalInstrument.from_dict(data)
    assert inst.canonical_instrument_id == "CRYPTO:BTC-USDT"
    assert inst.binance_symbol == "BTCUSDT"
    assert inst.bingx_symbol == "BTC-USDT"
    assert inst.mapping_status == "TRADABLE_BOTH"
    assert inst.binance_min_notional == 5.0
    assert inst.bingx_min_notional == 2.0

    d = inst.to_dict()
    assert d["binance_symbol"] == "BTCUSDT"
    assert d["bingx_symbol"] == "BTC-USDT"
    assert d["mapping_status"] == "TRADABLE_BOTH"


def test_instrument_resolver_dual_venue_crypto():
    resolver = InstrumentResolver.get_instance()
    resolver.refresh(force=True)

    # 1. Resolve by clean ticker
    inst_btc = resolver.resolve("BTC")
    assert inst_btc.canonical_instrument_id == "CRYPTO:BTC-USDT"
    assert inst_btc.binance_symbol == "BTCUSDT"
    assert inst_btc.bingx_symbol == "BTC-USDT"
    assert inst_btc.mapping_status == MappingStatus.TRADABLE_BOTH.value

    # 2. Resolve by Binance symbol
    inst_bn = resolver.resolve("BTCUSDT")
    assert inst_bn.canonical_instrument_id == "CRYPTO:BTC-USDT"

    # 3. Resolve by BingX symbol
    inst_bx = resolver.resolve("BTC-USDT")
    assert inst_bx.canonical_instrument_id == "CRYPTO:BTC-USDT"

    # 4. Check ETH and SOL
    inst_eth = resolver.resolve("ETH")
    assert inst_eth.binance_symbol == "ETHUSDT"
    assert inst_eth.bingx_symbol == "ETH-USDT"

    inst_sol = resolver.resolve("SOL")
    assert inst_sol.binance_symbol == "SOLUSDT"
    assert inst_sol.bingx_symbol == "SOL-USDT"


def test_instrument_resolver_tradfi_isolation():
    resolver = InstrumentResolver.get_instance()
    
    # TradFi equity on BingX only
    inst_nflx = resolver.resolve("NFLX")
    assert inst_nflx.asset_class == "US_EQUITY"
    assert inst_nflx.bingx_symbol == "NCSKNETFLIX2USD-USDT"
    assert inst_nflx.mapping_status == MappingStatus.BINGX_ONLY.value
    assert inst_nflx.binance_symbol == ""


def test_instrument_resolver_commodities_gold():
    resolver = InstrumentResolver.get_instance()
    inst_gold = resolver.resolve("GOLD")
    assert inst_gold.asset_class == "COMMODITIES"
    assert inst_gold.bingx_symbol == "NCCOGOLD2USD-USDT"

    inst_xau = resolver.resolve("XAU")
    assert inst_xau.canonical_instrument_id == inst_gold.canonical_instrument_id


def test_cross_asset_pollution_prevention():
    resolver = InstrumentResolver.get_instance()
    with pytest.raises(InstrumentResolutionError) as exc_info:
        resolver.resolve("BTC", asset_class="US_EQUITY")
    assert "PRODUCT_NOT_SUPPORTED" in str(exc_info.value)


def test_resolver_lookup_helpers():
    resolver = InstrumentResolver.get_instance()
    assert resolver.get_binance_symbol("BTC") == "BTCUSDT"
    assert resolver.get_bingx_symbol("BTC") == "BTC-USDT"

    both = resolver.list_cross_venue_instruments(MappingStatus.TRADABLE_BOTH.value)
    assert len(both) > 0
    symbols = [i.binance_symbol for i in both]
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "SOLUSDT" in symbols
