"""Authoritative Canonical Instrument Identity Model.

Layer: models/instrument.py
Strict Contract:
- Strongly typed immutable domain model representing canonical instrument identity across
  Crypto, US Equities (TradFi), and Commodities.
- Separates user-facing display concepts from authoritative exchange venue execution identities.
- Preserves full precision, sizing, and leverage rules discovered directly from venue metadata.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class CanonicalInstrument:
    display_symbol: str
    internal_instrument_id: str
    asset_class: str
    venue: str
    venue_product: str
    venue_symbol: str
    quote_currency: str
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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CanonicalInstrument":
        return cls(
            display_symbol=str(data.get("display_symbol") or ""),
            internal_instrument_id=str(data.get("internal_instrument_id") or ""),
            asset_class=str(data.get("asset_class") or "CRYPTO"),
            venue=str(data.get("venue") or "BINGX"),
            venue_product=str(data.get("venue_product") or "STANDARD_PERPETUAL"),
            venue_symbol=str(data.get("venue_symbol") or ""),
            quote_currency=str(data.get("quote_currency") or "USDT"),
            order_endpoint=str(data.get("order_endpoint") or "/openApi/swap/v2/trade/order"),
            market_data_symbol=str(data.get("market_data_symbol") or data.get("venue_symbol") or ""),
            price_precision=int(data.get("price_precision") or 2),
            quantity_precision=int(data.get("quantity_precision") or 4),
            min_order_size=float(data.get("min_order_size") or 0.01),
            min_notional=float(data.get("min_notional") or 2.0),
            leverage_rules=dict(data.get("leverage_rules") or {"max_leverage": 20, "default_leverage": 5}),
            trading_status=str(data.get("trading_status") or "TRADABLE"),
            source=str(data.get("source") or "BINGX_REST_CONTRACTS"),
            discovery_timestamp=int(data.get("discovery_timestamp") or 0),
            last_refreshed=int(data.get("last_refreshed") or 0),
        )
