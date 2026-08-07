from dataclasses import dataclass


@dataclass(slots=True)
class Balance:
    """
    Represents the BingX Futures account balance.
    """

    asset: str

    balance: float

    equity: float

    available_margin: float

    used_margin: float

    unrealized_pnl: float

    # =====================================================
    # DESERIALIZATION
    # =====================================================

    @classmethod
    def from_api(cls, data: dict) -> "Balance":
        """
        Convert BingX balance response into Balance model.

        This method supports both current and future
        BingX balance payload formats.
        """

        return cls(

            asset=data.get(
                "asset",
                data.get("currency", "USDT")
            ),

            balance=float(
                data.get(
                    "balance",
                    data.get("walletBalance", 0)
                )
            ),

            equity=float(
                data.get(
                    "equity",
                    data.get("balance", 0)
                )
            ),

            available_margin=float(
                data.get(
                    "availableMargin",
                    data.get("availableBalance", 0)
                )
            ),

            used_margin=float(
                data.get(
                    "usedMargin",
                    data.get("positionMargin", 0)
                )
            ),

            unrealized_pnl=float(
                data.get(
                    "unrealizedProfit",
                    data.get("unrealizedPnL", 0)
                )
            ),
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def margin_used_percent(self) -> float:

        if self.equity <= 0:
            return 0.0

        return (
            self.used_margin
            / self.equity
        ) * 100

    @property
    def free_margin_percent(self) -> float:

        if self.equity <= 0:
            return 0.0

        return (
            self.available_margin
            / self.equity
        ) * 100

    @property
    def has_available_margin(self) -> bool:
        return self.available_margin > 0

    @property
    def total_pnl(self) -> float:
        return self.unrealized_pnl