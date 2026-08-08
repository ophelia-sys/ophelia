"""
=====================================================
ACCOUNT BALANCE MODEL
=====================================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class Balance:
    """
    Strongly typed BingX account balance model.
    """

    asset: str
    wallet_balance: float
    available_balance: float
    margin_balance: float
    unrealized_pnl: float
    realized_pnl: float
    equity: float
    frozen_balance: float
    cross_wallet_balance: float
    cross_unrealized_pnl: float
    update_time: int

    @classmethod
    def from_api(cls, data: dict[str, Any]) -> "Balance":
        """
        Build a Balance object from a BingX API response.
        """

        return cls(
            asset=str(
                data.get("asset")
                or data.get("currency")
                or "USDT"
            ),
            wallet_balance=float(data.get("balance", data.get("walletBalance", 0))),
            available_balance=float(
                data.get("availableMargin", data.get("availableBalance", 0))
            ),
            margin_balance=float(
                data.get("marginBalance", data.get("equity", 0))
            ),
            unrealized_pnl=float(
                data.get("unrealizedProfit", data.get("unrealizedPnL", 0))
            ),
            realized_pnl=float(
                data.get("realizedProfit", data.get("realizedPnL", 0))
            ),
            equity=float(data.get("equity", data.get("marginBalance", 0))),
            frozen_balance=float(
                data.get("frozenBalance", data.get("frozenMargin", 0))
            ),
            cross_wallet_balance=float(
                data.get("crossWalletBalance", 0)
            ),
            cross_unrealized_pnl=float(
                data.get("crossUnrealizedPnL", 0)
            ),
            update_time=int(data.get("updateTime", 0)),
        )