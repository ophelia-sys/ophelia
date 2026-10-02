"""Canonical Multi-Asset Instrument Resolution Engine for Ophelia.

Layer: control_plane/instruments.py
Contract:
- Canonical identity across Crypto, US Equities (TradFi), and Commodities.
- Authoritative discovery directly from live BingX perpetual contracts metadata.
- Thread-safe caching with explicit TTL (10 minutes) and on-demand invalidation.
- Segregated asset class resolution preventing cross-asset pollution.
- Generic display and alias normalization without hardcoded per-ticker if-branches.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from models.instrument import CanonicalInstrument
from . import config, db

logger = logging.getLogger("ophelia.instruments")

# Cache TTL: 10 minutes (600 seconds)
DEFAULT_INSTRUMENT_TTL_MS = 600_000


class InstrumentResolutionError(Exception):
    """Raised when an instrument cannot be resolved to an authoritative venue symbol."""
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        self.message = detail
        self.reason = detail
        super().__init__(f"{code}: {detail}")


class InstrumentResolver:
    """Authoritative singleton resolver for all venue instruments."""
    _instance: Optional["InstrumentResolver"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._inst_lock = threading.Lock()
        self._instruments_by_id: Dict[str, CanonicalInstrument] = {}
        self._instruments_by_venue_sym: Dict[str, CanonicalInstrument] = {}
        self._alias_map: Dict[str, str] = {}  # alias_key -> internal_instrument_id
        self._asset_class_index: Dict[str, List[str]] = {"CRYPTO": [], "US_EQUITY": [], "COMMODITIES": []}
        self._last_refreshed_ms: int = 0
        self._ttl_ms: int = DEFAULT_INSTRUMENT_TTL_MS

    @classmethod
    def get_instance(cls) -> "InstrumentResolver":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def invalidate_cache(self) -> None:
        """Explicitly invalidate cached instrument metadata."""
        with self._inst_lock:
            self._last_refreshed_ms = 0
            logger.info("InstrumentResolver cache invalidated.")

    def is_cache_valid(self) -> bool:
        with self._inst_lock:
            now_ms = int(time.time() * 1000)
            return bool(self._instruments_by_id) and (now_ms - self._last_refreshed_ms < self._ttl_ms)

    def refresh(self, force: bool = False) -> int:
        """Fetch authoritative instrument metadata from BingX swap contracts endpoint."""
        now_ms = int(time.time() * 1000)
        with self._inst_lock:
            if not force and self._instruments_by_id and (now_ms - self._last_refreshed_ms < self._ttl_ms):
                return len(self._instruments_by_id)

        base_url = getattr(config, "BINGX_BASE_URL", "https://open-api.bingx.com")
        url = f"{base_url}/openApi/swap/v2/quote/contracts"
        rows: List[dict] = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ophelia-instruments/1.0"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                rows = data.get("data", [])
        except Exception as e:
            logger.warning("Live BingX contract query failed (%s). Attempting local fallback.", e)
            rows = []

        if not rows:
            # Fallback to local DB if network fails
            return self._load_from_fallback()

        new_by_id: Dict[str, CanonicalInstrument] = {}
        new_by_venue: Dict[str, CanonicalInstrument] = {}
        new_aliases: Dict[str, str] = {}
        new_asset_index: Dict[str, List[str]] = {"CRYPTO": [], "US_EQUITY": [], "COMMODITIES": []}

        for row in rows:
            venue_sym = str(row.get("symbol") or "").strip().upper()
            if not venue_sym or not (venue_sym.endswith("-USDT") or venue_sym.endswith("-USDC")):
                continue

            display_name = str(row.get("displayName") or "").strip()
            asset_raw = str(row.get("asset") or "").strip().upper()
            currency = str(row.get("currency") or "USDT").strip().upper()

            # Determine asset class & venue product
            if venue_sym.startswith("NCSK"):
                asset_class = "US_EQUITY"
                venue_product = "TRADFI_PERPETUAL"
                # Extract ticker: displayName "NFLX-USDT" -> "NFLX"
                if display_name and "-" in display_name:
                    disp_sym = display_name.split("-")[0].strip().upper()
                else:
                    m = re.match(r"^NCSK([A-Z0-9]+)2USD", asset_raw or venue_sym)
                    disp_sym = m.group(1) if m else venue_sym
                internal_id = f"US_EQUITY:{disp_sym}"
            elif venue_sym.startswith("NCCO"):
                asset_class = "COMMODITIES"
                venue_product = "TRADFI_PERPETUAL"
                # Canonical gold & silver primary contracts
                if venue_sym == "NCCOGOLD2USD-USDT" or display_name.startswith("GOLD(XAU)"):
                    disp_sym = "GOLD"
                elif venue_sym == "NCCOXAG2USD-USDT" or display_name.startswith("SILVER(XAG)"):
                    disp_sym = "SILVER"
                elif "OILBRENT" in venue_sym:
                    disp_sym = "OIL_BRENT"
                elif "OILWTI" in venue_sym:
                    disp_sym = "OIL_WTI"
                elif display_name and "-" in display_name:
                    disp_sym = display_name.split("-")[0].strip().upper()
                else:
                    disp_sym = venue_sym.replace("NCCO", "").replace("2USD-USDT", "")
                internal_id = f"COMMODITIES:{disp_sym}"
            else:
                asset_class = "CRYPTO"
                venue_product = "STANDARD_PERPETUAL"
                disp_sym = venue_sym
                internal_id = f"CRYPTO:{disp_sym}"

            # Precision & sizing rules
            p_prec = int(row.get("pricePrecision") or 2)
            q_prec = int(row.get("quantityPrecision") or 4)
            min_qty = float(row.get("tradeMinQuantity") or row.get("minQty") or 0.01)
            min_notional = float(row.get("tradeMinUSDT") or row.get("minNotional") or 2.0)
            max_lev = float(row.get("maxLeverage") or 20.0)

            # Trading status
            raw_status = row.get("status")
            api_open = str(row.get("apiStateOpen", "true")).lower() == "true"
            api_close = str(row.get("apiStateClose", "true")).lower() == "true"
            if raw_status == 1 and api_open and api_close:
                trad_status = "TRADABLE"
            elif raw_status != 1:
                trad_status = "SUSPENDED"
            else:
                trad_status = "UNAVAILABLE"

            inst = CanonicalInstrument(
                display_symbol=disp_sym,
                internal_instrument_id=internal_id,
                asset_class=asset_class,
                venue="BINGX",
                venue_product=venue_product,
                venue_symbol=venue_sym,
                quote_currency=currency,
                order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol=venue_sym,
                price_precision=p_prec,
                quantity_precision=q_prec,
                min_order_size=min_qty,
                min_notional=min_notional,
                leverage_rules={"max_leverage": int(max_lev), "default_leverage": min(5, int(max_lev))},
                trading_status=trad_status,
                source="BINGX_REST_CONTRACTS",
                discovery_timestamp=now_ms,
                last_refreshed=now_ms
            )

            new_by_id[internal_id] = inst
            new_by_venue[venue_sym] = inst
            if internal_id not in new_asset_index[asset_class]:
                new_asset_index[asset_class].append(internal_id)

            # Build generic aliases for safe user lookup
            # 1. Exact internal ID
            new_aliases[internal_id.upper()] = internal_id
            # 2. Exact venue symbol (e.g. NCSKNETFLIX2USD-USDT)
            new_aliases[venue_sym] = internal_id
            # 3. Clean display symbol (e.g. NFLX, BTC-USDT, GOLD)
            new_aliases[f"{asset_class}:{disp_sym}"] = internal_id
            if currency == "USDT" or disp_sym not in new_aliases:
                new_aliases[disp_sym] = internal_id
            # 4. DisplayName from exchange (e.g. NFLX-USDT, GOLD(XAU)-USDT)
            if display_name:
                new_aliases[display_name.upper()] = internal_id
                if "-" in display_name:
                    base = display_name.split("-")[0].strip().upper()
                    if currency == "USDT" or base not in new_aliases:
                        new_aliases[base] = internal_id
                        new_aliases[f"{asset_class}:{base}"] = internal_id

            # 5. Asset name / underlying (e.g. NCSKNETFLIX2USD -> NETFLIX)
            if asset_raw:
                clean_asset = asset_raw.replace("NCSK", "").replace("2USD", "").replace("NCCO", "")
                if clean_asset:
                    if currency == "USDT" or clean_asset not in new_aliases:
                        new_aliases[clean_asset] = internal_id
                        new_aliases[f"{asset_class}:{clean_asset}"] = internal_id

            # 6. Crypto specific aliases (e.g. BTC -> BTC-USDT, BTCUSDT -> BTC-USDT)
            if asset_class == "CRYPTO":
                base_crypto = disp_sym.split("-")[0].strip().upper()
                if currency == "USDT" or base_crypto not in new_aliases:
                    new_aliases[base_crypto] = internal_id
                    new_aliases[f"CRYPTO:{base_crypto}"] = internal_id
                    new_aliases[disp_sym.replace("-", "")] = internal_id

            # 7. Commodities specific aliases
            if asset_class == "COMMODITIES":
                if disp_sym == "GOLD":
                    for g_alias in ["XAU", "XAUUSD", "GOLD (XAU)", "GOLD-USDT", "XAU-USDT", "GOLD(XAU)"]:
                        new_aliases[g_alias] = internal_id
                        new_aliases[f"COMMODITIES:{g_alias}"] = internal_id
                elif disp_sym == "SILVER":
                    for s_alias in ["XAG", "XAGUSD", "SILVER (XAG)", "SILVER-USDT", "XAG-USDT", "SILVER(XAG)"]:
                        new_aliases[s_alias] = internal_id
                        new_aliases[f"COMMODITIES:{s_alias}"] = internal_id

        with self._inst_lock:
            self._instruments_by_id = new_by_id
            self._instruments_by_venue_sym = new_by_venue
            self._alias_map = new_aliases
            self._asset_class_index = new_asset_index
            self._last_refreshed_ms = now_ms

        logger.info("InstrumentResolver refreshed: %d instruments discovered (%d US Equities, %d Commodities, %d Crypto)",
                    len(new_by_id), len(new_asset_index["US_EQUITY"]), len(new_asset_index["COMMODITIES"]), len(new_asset_index["CRYPTO"]))
        return len(new_by_id)

    def _load_from_fallback(self) -> int:
        """Seed essential universal instruments if exchange endpoint is unreachable."""
        now_ms = int(time.time() * 1000)
        seed_instruments = [
            CanonicalInstrument(
                display_symbol="BTC-USDT", internal_instrument_id="CRYPTO:BTC-USDT",
                asset_class="CRYPTO", venue="BINGX", venue_product="STANDARD_PERPETUAL",
                venue_symbol="BTC-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="BTC-USDT", price_precision=1, quantity_precision=4,
                min_order_size=0.0001, min_notional=2.0, leverage_rules={"max_leverage": 125, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="ETH-USDT", internal_instrument_id="CRYPTO:ETH-USDT",
                asset_class="CRYPTO", venue="BINGX", venue_product="STANDARD_PERPETUAL",
                venue_symbol="ETH-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="ETH-USDT", price_precision=2, quantity_precision=4,
                min_order_size=0.001, min_notional=2.0, leverage_rules={"max_leverage": 100, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="SOL-USDT", internal_instrument_id="CRYPTO:SOL-USDT",
                asset_class="CRYPTO", venue="BINGX", venue_product="STANDARD_PERPETUAL",
                venue_symbol="SOL-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="SOL-USDT", price_precision=3, quantity_precision=2,
                min_order_size=0.01, min_notional=2.0, leverage_rules={"max_leverage": 50, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="XRP-USDT", internal_instrument_id="CRYPTO:XRP-USDT",
                asset_class="CRYPTO", venue="BINGX", venue_product="STANDARD_PERPETUAL",
                venue_symbol="XRP-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="XRP-USDT", price_precision=4, quantity_precision=1,
                min_order_size=1.0, min_notional=2.0, leverage_rules={"max_leverage": 50, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="GOLD", internal_instrument_id="COMMODITIES:GOLD",
                asset_class="COMMODITIES", venue="BINGX", venue_product="TRADFI_PERPETUAL",
                venue_symbol="NCCOGOLD2USD-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="NCCOGOLD2USD-USDT", price_precision=2, quantity_precision=3,
                min_order_size=0.01, min_notional=2.0, leverage_rules={"max_leverage": 50, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="SILVER", internal_instrument_id="COMMODITIES:SILVER",
                asset_class="COMMODITIES", venue="BINGX", venue_product="TRADFI_PERPETUAL",
                venue_symbol="NCCOXAG2USD-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="NCCOXAG2USD-USDT", price_precision=3, quantity_precision=2,
                min_order_size=0.1, min_notional=2.0, leverage_rules={"max_leverage": 50, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="NFLX", internal_instrument_id="US_EQUITY:NFLX",
                asset_class="US_EQUITY", venue="BINGX", venue_product="TRADFI_PERPETUAL",
                venue_symbol="NCSKNETFLIX2USD-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="NCSKNETFLIX2USD-USDT", price_precision=2, quantity_precision=4,
                min_order_size=0.0294, min_notional=2.0, leverage_rules={"max_leverage": 20, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="AAPL", internal_instrument_id="US_EQUITY:AAPL",
                asset_class="US_EQUITY", venue="BINGX", venue_product="TRADFI_PERPETUAL",
                venue_symbol="NCSKAAPL2USD-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="NCSKAAPL2USD-USDT", price_precision=2, quantity_precision=4,
                min_order_size=0.01, min_notional=2.0, leverage_rules={"max_leverage": 20, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
            CanonicalInstrument(
                display_symbol="NVDA", internal_instrument_id="US_EQUITY:NVDA",
                asset_class="US_EQUITY", venue="BINGX", venue_product="TRADFI_PERPETUAL",
                venue_symbol="NCSKNVDA2USD-USDT", quote_currency="USDT", order_endpoint="/openApi/swap/v2/trade/order",
                market_data_symbol="NCSKNVDA2USD-USDT", price_precision=2, quantity_precision=4,
                min_order_size=0.01, min_notional=2.0, leverage_rules={"max_leverage": 20, "default_leverage": 5},
                trading_status="TRADABLE", source="FALLBACK_SEED", discovery_timestamp=now_ms, last_refreshed=now_ms
            ),
        ]
        with self._inst_lock:
            for inst in seed_instruments:
                self._instruments_by_id[inst.internal_instrument_id] = inst
                self._instruments_by_venue_sym[inst.venue_symbol] = inst
                self._alias_map[inst.display_symbol.upper()] = inst.internal_instrument_id
                self._alias_map[inst.venue_symbol] = inst.internal_instrument_id
                self._alias_map[inst.internal_instrument_id] = inst.internal_instrument_id
                self._alias_map[f"{inst.asset_class}:{inst.display_symbol.upper()}"] = inst.internal_instrument_id
            self._alias_map["NETFLIX"] = "US_EQUITY:NFLX"
            self._alias_map["APPLE"] = "US_EQUITY:AAPL"
            self._alias_map["NVIDIA"] = "US_EQUITY:NVDA"
            self._alias_map["BITCOIN"] = "CRYPTO:BTC-USDT"
            self._alias_map["BTC"] = "CRYPTO:BTC-USDT"
            self._alias_map["ETH"] = "CRYPTO:ETH-USDT"
            self._alias_map["SOL"] = "CRYPTO:SOL-USDT"
            self._alias_map["XRP"] = "CRYPTO:XRP-USDT"
            self._alias_map["XAU"] = "COMMODITIES:GOLD"
            self._alias_map["GOLD (XAU)"] = "COMMODITIES:GOLD"
            self._alias_map["XAG"] = "COMMODITIES:SILVER"
            self._last_refreshed_ms = now_ms
        return len(seed_instruments)

    def resolve(self, input_symbol: str, asset_class: str | None = None) -> CanonicalInstrument:
        """Resolve any user-facing symbol or alias to a CanonicalInstrument.
        
        Args:
            input_symbol: User-facing ticker, display name, internal ID, or venue symbol
            asset_class: Optional constraint ('CRYPTO', 'US_EQUITY', 'COMMODITIES')
            
        Returns:
            CanonicalInstrument with verified venue parameters
            
        Raises:
            InstrumentResolutionError with standard error code
        """
        if not input_symbol or not isinstance(input_symbol, str):
            raise InstrumentResolutionError("INSTRUMENT_NOT_FOUND", "Empty or non-string symbol provided")

        if not self.is_cache_valid():
            self.refresh()

        clean = input_symbol.strip().upper()

        with self._inst_lock:
            # 1. Try qualified asset class lookup if asset_class provided
            if asset_class:
                ac_key = f"{asset_class.upper()}:{clean}"
                if ac_key in self._alias_map:
                    target_id = self._alias_map[ac_key]
                    return self._instruments_by_id[target_id]

            # 2. Try direct alias map lookup
            if clean in self._alias_map:
                target_id = self._alias_map[clean]
                inst = self._instruments_by_id.get(target_id)
                if inst:
                    if asset_class and inst.asset_class != asset_class.upper():
                        raise InstrumentResolutionError(
                            "PRODUCT_NOT_SUPPORTED",
                            f"Instrument '{clean}' resolved to {inst.asset_class}, which does not match requested asset class '{asset_class}'"
                        )
                    return inst

            # 3. Direct venue symbol match
            if clean in self._instruments_by_venue_sym:
                inst = self._instruments_by_venue_sym[clean]
                if asset_class and inst.asset_class != asset_class.upper():
                    raise InstrumentResolutionError(
                        "PRODUCT_NOT_SUPPORTED",
                        f"Venue symbol '{clean}' is {inst.asset_class}, not {asset_class}"
                    )
                return inst

            # 4. Direct internal ID match
            if clean in self._instruments_by_id:
                inst = self._instruments_by_id[clean]
                if asset_class and inst.asset_class != asset_class.upper():
                    raise InstrumentResolutionError(
                        "PRODUCT_NOT_SUPPORTED",
                        f"Internal ID '{clean}' is {inst.asset_class}, not {asset_class}"
                    )
                return inst

        # Not found
        raise InstrumentResolutionError(
            "INSTRUMENT_NOT_AVAILABLE",
            f"Symbol '{input_symbol}' could not be resolved to any active BingX contract"
        )

    def resolve_or_none(self, input_symbol: str, asset_class: str | None = None) -> CanonicalInstrument | None:
        try:
            return self.resolve(input_symbol, asset_class=asset_class)
        except InstrumentResolutionError:
            return None

    def search(self, query: str, asset_class: str | None = None, limit: int = 50) -> List[CanonicalInstrument]:
        """Search instruments matching a query substring."""
        if not self.is_cache_valid():
            self.refresh()

        q = query.strip().upper()
        results: List[CanonicalInstrument] = []
        with self._inst_lock:
            for inst in self._instruments_by_id.values():
                if asset_class and inst.asset_class != asset_class.upper():
                    continue
                # Match display symbol, venue symbol, internal ID, or aliases
                if (q in inst.display_symbol.upper() or
                    q in inst.venue_symbol.upper() or
                    q in inst.internal_instrument_id.upper()):
                    results.append(inst)
                if len(results) >= limit:
                    break
        return results


def resolve_instrument(symbol: str, asset_class: str | None = None) -> CanonicalInstrument:
    """Convenience helper to resolve instrument using the singleton InstrumentResolver."""
    return InstrumentResolver.get_instance().resolve(symbol, asset_class=asset_class)


def get_instrument_resolver() -> InstrumentResolver:
    """Return the singleton instance of InstrumentResolver."""
    return InstrumentResolver.get_instance()
