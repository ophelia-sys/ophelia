"""Authoritative Canonical Multi-Venue Instrument Identity Model.

Layer: models/instrument.py
Strict Contract:
- Strongly typed immutable domain model representing canonical instrument identity across
  Crypto, US Equities (TradFi), and Commodities.
- Separates Primary Market Intelligence Venue (BINANCE USD-M) from Execution Venue (BINGX SWAP).
- Preserves full precision, sizing, and leverage rules discovered directly from venue metadata.
- Explicit mapping states: UNRESOLVED, RESOLVED, TRADABLE_BOTH, BINANCE_ONLY, BINGX_ONLY, MISMATCH, STALE, INVALID.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MappingStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"
    TRADABLE_BOTH = "TRADABLE_BOTH"
    BINANCE_ONLY = "BINANCE_ONLY"
    BINGX_ONLY = "BINGX_ONLY"
    MISMATCH = "MISMATCH"
    STALE = "STALE"
    INVALID = "INVALID"


@dataclass(slots=True)
class CanonicalInstrument:
    # 1. Authoritative Canonical Core
    canonical_instrument_id: str
    asset: str
    quote_currency: str
    asset_class: str

    # 2. Existing / Display Compatibility Fields
    display_symbol: str
    internal_instrument_id: str
    venue: str
    venue_product: str
    venue_symbol: str
    order_endpoint: str
    market_data_symbol: str
    price_precision: int
    quantity_precision: int
    min_order_size: float
    min_notional: float
    leverage_rules: Dict[str, Any]
    trading_status: str
    source: str
    discovery_timestamp: int
    last_refreshed: int

    # 3. Binance USD-M Market Intelligence Attributes
    binance_symbol: str = ""
    binance_product: str = "USDM_PERPETUAL"
    binance_contract_type: str = "PERPETUAL"
    binance_status: str = "TRADING"
    binance_precision: int = 2
    binance_min_quantity: float = 0.001
    binance_min_notional: float = 5.0
    binance_discovery_timestamp: int = 0

    # 4. BingX Execution Venue Attributes
    bingx_symbol: str = ""
    bingx_product: str = "STANDARD_PERPETUAL"
    bingx_status: str = "TRADABLE"
    bingx_precision: int = 2
    bingx_min_quantity: float = 0.001
    bingx_min_notional: float = 2.0
    bingx_discovery_timestamp: int = 0

    # 5. Shared Cross-Venue Mapping Attributes
    canonical_status: str = "ACTIVE"
    mapping_status: str = MappingStatus.UNRESOLVED.value
    mapping_source: str = "DYNAMIC_DISCOVERY"
    mapping_confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalInstrument":
        internal_id = str(data.get("internal_instrument_id") or data.get("canonical_instrument_id") or "")
        display = str(data.get("display_symbol") or internal_id or "")
        asset = str(data.get("asset") or display.split("-")[0].replace("USDT", "") or "BTC")
        quote = str(data.get("quote_currency") or "USDT")
        asset_class = str(data.get("asset_class") or "CRYPTO")
        
        # Determine venue mapping status if provided or deduce
        mapping_status = str(data.get("mapping_status") or "")
        binance_sym = str(data.get("binance_symbol") or "")
        bingx_sym = str(data.get("bingx_symbol") or data.get("venue_symbol") or "")
        if not mapping_status:
            if binance_sym and bingx_sym:
                mapping_status = MappingStatus.TRADABLE_BOTH.value
            elif binance_sym:
                mapping_status = MappingStatus.BINANCE_ONLY.value
            elif bingx_sym:
                mapping_status = MappingStatus.BINGX_ONLY.value
            else:
                mapping_status = MappingStatus.UNRESOLVED.value

        return cls(
            canonical_instrument_id=internal_id,
            asset=asset,
            quote_currency=quote,
            asset_class=asset_class,
            display_symbol=display,
            internal_instrument_id=internal_id,
            venue=str(data.get("venue") or "MULTI_VENUE"),
            venue_product=str(data.get("venue_product") or "PERPETUAL_SWAP"),
            venue_symbol=bingx_sym or str(data.get("venue_symbol") or ""),
            order_endpoint=str(data.get("order_endpoint") or "/openApi/swap/v2/trade/order"),
            market_data_symbol=binance_sym or str(data.get("market_data_symbol") or bingx_sym or ""),
            price_precision=int(data.get("price_precision") or data.get("bingx_precision") or 2),
            quantity_precision=int(data.get("quantity_precision") or 4),
            min_order_size=float(data.get("min_order_size") or data.get("bingx_min_quantity") or 0.001),
            min_notional=float(data.get("min_notional") or data.get("bingx_min_notional") or 2.0),
            leverage_rules=dict(data.get("leverage_rules") or {"max_leverage": 20, "default_leverage": 5}),
            trading_status=str(data.get("trading_status") or "TRADABLE"),
            source=str(data.get("source") or "MULTI_VENUE_DISCOVERY"),
            discovery_timestamp=int(data.get("discovery_timestamp") or 0),
            last_refreshed=int(data.get("last_refreshed") or 0),
            binance_symbol=binance_sym,
            binance_product=str(data.get("binance_product") or "USDM_PERPETUAL"),
            binance_contract_type=str(data.get("binance_contract_type") or "PERPETUAL"),
            binance_status=str(data.get("binance_status") or "TRADING"),
            binance_precision=int(data.get("binance_precision") or data.get("price_precision") or 2),
            binance_min_quantity=float(data.get("binance_min_quantity") or 0.001),
            binance_min_notional=float(data.get("binance_min_notional") or 5.0),
            binance_discovery_timestamp=int(data.get("binance_discovery_timestamp") or 0),
            bingx_symbol=bingx_sym,
            bingx_product=str(data.get("bingx_product") or "STANDARD_PERPETUAL"),
            bingx_status=str(data.get("bingx_status") or "TRADABLE"),
            bingx_precision=int(data.get("bingx_precision") or data.get("price_precision") or 2),
            bingx_min_quantity=float(data.get("bingx_min_quantity") or data.get("min_order_size") or 0.001),
            bingx_min_notional=float(data.get("bingx_min_notional") or data.get("min_notional") or 2.0),
            bingx_discovery_timestamp=int(data.get("bingx_discovery_timestamp") or 0),
            canonical_status=str(data.get("canonical_status") or "ACTIVE"),
            mapping_status=mapping_status,
            mapping_source=str(data.get("mapping_source") or "DYNAMIC_DISCOVERY"),
            mapping_confidence=float(data.get("mapping_confidence") or 1.0),
        )
