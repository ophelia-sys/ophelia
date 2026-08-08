import json
import os
from dataclasses import dataclass, field
from typing import Any

import config
from utils.logger import logger

SUPPORTED_TIMEFRAMES = [
    "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"
]


@dataclass
class TradingSettings:
    ema_fast: int = field(default_factory=lambda: int(getattr(config, "EMA_FAST", 8)))
    ema_slow: int = field(default_factory=lambda: int(getattr(config, "EMA_SLOW", 18)))
    timeframe: str = field(default_factory=lambda: str(getattr(config, "TIMEFRAME", "1m")))
    margin_usdt: float = field(default_factory=lambda: float(getattr(config, "MARGIN_USDT", 10.0)))
    leverage: int = field(default_factory=lambda: int(getattr(config, "LEVERAGE", 20)))
    symbols: list[str] = field(
        default_factory=lambda: list(
            getattr(config, "SUPPORTED_SYMBOLS", ["BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"])
        )
    )
    trade_limit: int | None = None  # None = unlimited
    new_trades_count: int = 0

    # Risk Management Defaults
    sl_mode: str = "PRICE_PERCENT"  # "PRICE_PERCENT" or "FIXED_LOSS"
    sl_value: float = field(default_factory=lambda: float(getattr(config, "INITIAL_STOP_PERCENT", 1.0)))
    tp_mode: str = "PRICE_PERCENT"  # "PRICE_PERCENT" or "FIXED_PROFIT"
    tp_value: float = 2.0
    trailing_activation: float = field(default_factory=lambda: float(getattr(config, "TRAILING_TRIGGER", 1.0)))
    trailing_buffer: float = field(default_factory=lambda: float(getattr(config, "TRAILING_BUFFER", 0.8)))
    exit_plan: list[dict] = field(default_factory=lambda: [{"pct": 100.0, "type": "trailing"}])
    symbol_risk: dict[str, dict] = field(default_factory=dict)

    FILE_PATH = "data/settings.json"

    @classmethod
    def load(cls) -> "TradingSettings":
        settings = cls()
        if os.path.exists(cls.FILE_PATH):
            try:
                with open(cls.FILE_PATH, "r") as f:
                    data = json.load(f)
                if "ema_fast" in data:
                    settings.ema_fast = int(data["ema_fast"])
                if "ema_slow" in data:
                    settings.ema_slow = int(data["ema_slow"])
                if "timeframe" in data:
                    settings.timeframe = str(data["timeframe"])
                if "margin_usdt" in data:
                    settings.margin_usdt = float(data["margin_usdt"])
                if "leverage" in data:
                    settings.leverage = int(data["leverage"])
                if "symbols" in data and isinstance(data["symbols"], list):
                    settings.symbols = [str(s) for s in data["symbols"]]
                if "trade_limit" in data:
                    settings.trade_limit = (
                        int(data["trade_limit"]) if data["trade_limit"] is not None else None
                    )
                if "new_trades_count" in data:
                    settings.new_trades_count = int(data["new_trades_count"])
                if "sl_mode" in data:
                    settings.sl_mode = str(data["sl_mode"]).upper()
                if "sl_value" in data:
                    settings.sl_value = float(data["sl_value"])
                if "tp_mode" in data:
                    settings.tp_mode = str(data["tp_mode"]).upper()
                if "tp_value" in data:
                    settings.tp_value = float(data["tp_value"])
                if "trailing_activation" in data:
                    settings.trailing_activation = float(data["trailing_activation"])
                if "trailing_buffer" in data:
                    settings.trailing_buffer = float(data["trailing_buffer"])
                if "exit_plan" in data and isinstance(data["exit_plan"], list):
                    settings.exit_plan = data["exit_plan"]
                if "symbol_risk" in data and isinstance(data["symbol_risk"], dict):
                    settings.symbol_risk = data["symbol_risk"]
            except Exception as e:
                logger.error(f"Error loading settings from {cls.FILE_PATH}: {e}")
        return settings

    def save(self) -> None:
        os.makedirs("data", exist_ok=True)
        data = {
            "ema_fast": self.ema_fast,
            "ema_slow": self.ema_slow,
            "timeframe": self.timeframe,
            "margin_usdt": self.margin_usdt,
            "leverage": self.leverage,
            "symbols": self.symbols,
            "trade_limit": self.trade_limit,
            "new_trades_count": self.new_trades_count,
            "sl_mode": self.sl_mode,
            "sl_value": self.sl_value,
            "tp_mode": self.tp_mode,
            "tp_value": self.tp_value,
            "trailing_activation": self.trailing_activation,
            "trailing_buffer": self.trailing_buffer,
            "exit_plan": self.exit_plan,
            "symbol_risk": self.symbol_risk,
        }
        try:
            with open(self.FILE_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving settings to {self.FILE_PATH}: {e}")

    def get_risk_config(self, symbol: str | None = None) -> dict:
        base = {
            "sl_mode": self.sl_mode,
            "sl_value": self.sl_value,
            "tp_mode": self.tp_mode,
            "tp_value": self.tp_value,
            "trailing_activation": self.trailing_activation,
            "trailing_buffer": self.trailing_buffer,
            "exit_plan": list(self.exit_plan),
        }
        if symbol:
            sym = str(symbol).upper().strip()
            if sym in self.symbol_risk:
                override = self.symbol_risk[sym]
                for k, v in override.items():
                    base[k] = v
        return base

    # =====================================================
    # VALIDATORS
    # =====================================================

    @staticmethod
    def validate_ema(fast: int, slow: int) -> tuple[bool, str]:
        if not (isinstance(fast, int) and isinstance(slow, int)):
            return False, "EMA periods must be integers."
        if fast <= 0 or slow <= 0:
            return False, "EMA periods must be positive integers."
        if fast >= slow:
            return False, f"EMA fast period ({fast}) must be strictly less than slow period ({slow})."
        return True, ""

    @staticmethod
    def validate_timeframe(tf: str) -> tuple[bool, str]:
        tf = str(tf).lower()
        if tf not in SUPPORTED_TIMEFRAMES:
            return (
                False,
                f"Unsupported timeframe '{tf}'. Supported: {', '.join(SUPPORTED_TIMEFRAMES)}",
            )
        return True, ""

    @staticmethod
    def validate_margin(margin: float) -> tuple[bool, str]:
        try:
            val = float(margin)
        except (ValueError, TypeError):
            return False, "Margin must be a numeric value."
        if val <= 0:
            return False, "Margin must be a positive number."
        if val < 1.0 or val > 1000.0:
            return False, "Margin must be between 1.0 and 1000.0 USDT."
        return True, ""

    @staticmethod
    def validate_leverage(leverage: int) -> tuple[bool, str]:
        try:
            val = int(leverage)
        except (ValueError, TypeError):
            return False, "Leverage must be an integer."
        if val <= 0:
            return False, "Leverage must be a positive integer."
        if val < 1 or val > 100:
            return False, "Leverage must be between 1x and 100x."
        return True, ""

    @staticmethod
    def validate_symbol(symbol: str) -> tuple[bool, str]:
        sym = str(symbol).upper().strip()
        if not sym or "-" not in sym:
            return False, "Symbol must be in format 'BASE-QUOTE' (e.g. BTC-USDT)."
        supported = getattr(config, "SUPPORTED_SYMBOLS", ("BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT"))
        if sym not in supported:
            return False, f"Symbol '{sym}' is not supported by contract configuration. Supported: {', '.join(supported)}"
        return True, ""

    @staticmethod
    def validate_trade_limit(limit_val: Any) -> tuple[bool, str]:
        if limit_val is None or str(limit_val).lower() in ("unlimited", "none", "0"):
            return True, ""
        try:
            val = int(limit_val)
        except (ValueError, TypeError):
            return False, "Trade limit must be a positive integer or 'unlimited'."
        if val <= 0:
            return False, "Trade limit must be greater than 0."
        return True, ""

    @staticmethod
    def validate_sl(mode: str, value: float) -> tuple[bool, str]:
        mode_upper = str(mode).upper().strip()
        if mode_upper in ("PERCENT", "PRICE_PERCENT", "%"):
            mode_norm = "PRICE_PERCENT"
        elif mode_upper in ("FIXED", "FIXED_LOSS", "USDT", "$"):
            mode_norm = "FIXED_LOSS"
        else:
            return False, f"Invalid SL mode '{mode}'. Use 'percent' or 'fixed'."
        try:
            val = float(value)
        except (ValueError, TypeError):
            return False, "SL value must be numeric."
        if val <= 0:
            return False, "SL value must be greater than 0."
        if mode_norm == "PRICE_PERCENT" and val > 50.0:
            return False, "SL percentage cannot exceed 50%."
        return True, ""

    @staticmethod
    def validate_tp(mode: str, value: float) -> tuple[bool, str]:
        mode_upper = str(mode).upper().strip()
        if mode_upper in ("PERCENT", "PRICE_PERCENT", "%"):
            mode_norm = "PRICE_PERCENT"
        elif mode_upper in ("FIXED", "FIXED_PROFIT", "USDT", "$"):
            mode_norm = "FIXED_PROFIT"
        else:
            return False, f"Invalid TP mode '{mode}'. Use 'percent' or 'fixed'."
        try:
            val = float(value)
        except (ValueError, TypeError):
            return False, "TP value must be numeric."
        if val <= 0:
            return False, "TP value must be greater than 0."
        if mode_norm == "PRICE_PERCENT" and val > 500.0:
            return False, "TP percentage cannot exceed 500%."
        return True, ""

    @staticmethod
    def validate_trailing(buffer_pct: float, activation_pct: float) -> tuple[bool, str]:
        try:
            buf = float(buffer_pct)
            act = float(activation_pct)
        except (ValueError, TypeError):
            return False, "Trailing buffer and activation must be numeric values."
        if buf <= 0:
            return False, "Trailing buffer must be greater than 0."
        if act <= 0:
            return False, "Trailing activation must be greater than 0."
        if buf >= 20.0 or act >= 50.0:
            return False, "Trailing parameters exceed safe thresholds."
        return True, ""

    @classmethod
    def parse_exit_plan(cls, text_tokens: list[str]) -> tuple[bool, str, list[dict]]:
        """
        Parses exit plan tokens into structured leg dicts.
        Examples:
            ['25@1.0', '25@2.0', '50@trailing']
            ['50@+1.5%', '50@trailing']
        """
        if not text_tokens:
            return False, "Exit plan tokens cannot be empty.", []

        legs = []
        total_pct = 0.0

        for token in text_tokens:
            token = token.strip()
            if not token:
                continue
            if "@" not in token:
                return False, f"Invalid leg token '{token}'. Expected format 'PCT@TARGET' (e.g. '25@1.0' or '50@trailing').", []
            parts = token.split("@")
            if len(parts) != 2:
                return False, f"Invalid leg token '{token}'. Expected format 'PCT@TARGET'.", []

            pct_str, target_str = parts[0].strip(), parts[1].strip()
            try:
                pct_val = float(pct_str.rstrip("%"))
            except ValueError:
                return False, f"Invalid percentage '{pct_str}' in leg '{token}'.", []

            if pct_val <= 0 or pct_val > 100:
                return False, f"Leg percentage must be > 0 and <= 100 (got {pct_val}%).", []

            target_lower = target_str.lower().rstrip("%")
            if target_lower == "trailing":
                leg_dict = {"pct": pct_val, "type": "trailing"}
            elif target_lower.startswith("sl:"):
                try:
                    sl_val = float(target_lower[3:])
                except ValueError:
                    return False, f"Invalid SL value in leg '{token}'.", []
                leg_dict = {"pct": pct_val, "type": "sl", "target_pct": sl_val}
            else:
                try:
                    tp_val = float(target_lower.lstrip("+"))
                except ValueError:
                    return False, f"Invalid target '{target_str}' in leg '{token}'.", []
                if tp_val <= 0:
                    return False, f"TP target must be > 0 in leg '{token}'.", []
                leg_dict = {"pct": pct_val, "type": "tp", "target_pct": tp_val}

            legs.append(leg_dict)
            total_pct += pct_val

        if abs(total_pct - 100.0) > 1e-4:
            return False, f"Exit plan percentages must sum to exactly 100% (got {total_pct:.1f}%).", []

        return True, "", legs
