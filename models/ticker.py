from dataclasses import dataclass


@dataclass(slots=True)
class Ticker:
    """
    Represents the latest market ticker for a futures contract.
    """

    symbol: str

    last_price: float

    mark_price: float

    index_price: float

    bid_price: float

    ask_price: float

    high_price: float

    low_price: float

    volume: float

    quote_volume: float

    price_change_percent: float

    funding_rate: float = 0.0

    open_interest: float = 0.0

    # =====================================================
    # DESERIALIZATION
    # =====================================================

    @classmethod
    def from_api(cls, data: dict) -> "Ticker":
        """
        Convert BingX ticker response into a Ticker model.
        """

        return cls(

            symbol=data["symbol"],

            last_price=float(
                data.get("lastPrice", 0)
            ),

            mark_price=float(
                data.get(
                    "markPrice",
                    data.get("lastPrice", 0)
                )
            ),

            index_price=float(
                data.get(
                    "indexPrice",
                    data.get("lastPrice", 0)
                )
            ),

            bid_price=float(
                data.get(
                    "bidPrice",
                    0
                )
            ),

            ask_price=float(
                data.get(
                    "askPrice",
                    0
                )
            ),

            high_price=float(
                data.get(
                    "highPrice",
                    0
                )
            ),

            low_price=float(
                data.get(
                    "lowPrice",
                    0
                )
            ),

            volume=float(
                data.get(
                    "volume",
                    0
                )
            ),

            quote_volume=float(
                data.get(
                    "quoteVolume",
                    0
                )
            ),

            price_change_percent=float(
                data.get(
                    "priceChangePercent",
                    0
                )
            ),

            funding_rate=float(
                data.get(
                    "fundingRate",
                    0
                )
            ),

            open_interest=float(
                data.get(
                    "openInterest",
                    0
                )
            ),
        )

    # =====================================================
    # HELPERS
    # =====================================================

    @property
    def spread(self) -> float:
        """
        Bid/Ask spread.
        """
        return self.ask_price - self.bid_price

    @property
    def spread_percent(self) -> float:
        """
        Bid/Ask spread as a percentage.
        """
        if self.last_price <= 0:
            return 0.0

        return (self.spread / self.last_price) * 100

    @property
    def mid_price(self) -> float:
        """
        Midpoint between bid and ask.
        """
        if self.bid_price == 0 or self.ask_price == 0:
            return self.last_price

        return (self.bid_price + self.ask_price) / 2

    @property
    def is_bullish(self) -> bool:
        return self.price_change_percent > 0

    @property
    def is_bearish(self) -> bool:
        return self.price_change_percent < 0