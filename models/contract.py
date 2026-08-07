from dataclasses import dataclass


@dataclass(slots=True)
class Contract:
    """
    Represents a BingX perpetual futures contract.
    """

    symbol: str

    base_asset: str

    quote_asset: str

    status: str

    price_precision: int

    quantity_precision: int

    min_quantity: float

    min_notional: float | None = None

    max_leverage: int | None = None

    contract_size: float | None = None

    # =====================================================
    # DESERIALIZATION
    # =====================================================

    @classmethod
    def from_api(cls, data: dict) -> "Contract":
        """
        Convert BingX contract response into Contract model.
        """

        return cls(

            symbol=data["symbol"],

            base_asset=data.get(
                "baseAsset",
                ""
            ),

            quote_asset=data.get(
                "quoteAsset",
                "USDT"
            ),

            status=data.get(
                "status",
                "UNKNOWN"
            ),

            price_precision=int(
                data.get(
                    "pricePrecision",
                    0
                )
            ),

            quantity_precision=int(
                data.get(
                    "quantityPrecision",
                    0
                )
            ),

            min_quantity=float(
                data.get(
                    "tradeMinQuantity",
                    0
                )
            ),

            min_notional=(
                float(data["tradeMinUSDT"])
                if data.get("tradeMinUSDT")
                else None
            ),

            max_leverage=(
                int(float(data["maxLongLeverage"]))
                if data.get("maxLongLeverage")
                else None
            ),

            contract_size=(
                float(data["contractSize"])
                if data.get("contractSize")
                else None
            ),
        )

    # =====================================================
    # HELPERS
    # =====================================================

    def round_price(
        self,
        price: float,
    ) -> float:
        """
        Round price to exchange precision.
        """

        return round(
            price,
            self.price_precision,
        )

    def round_quantity(
        self,
        quantity: float,
    ) -> float:
        """
        Round quantity to exchange precision.
        """

        return round(
            quantity,
            self.quantity_precision,
        )

    def validate_quantity(
        self,
        quantity: float,
    ) -> bool:
        """
        Check if quantity satisfies minimum trade size.
        """

        return quantity >= self.min_quantity

    def validate_notional(
        self,
        price: float,
        quantity: float,
    ) -> bool:
        """
        Check minimum order value.
        """

        if self.min_notional is None:
            return True

        return (
            price * quantity
        ) >= self.min_notional

    @property
    def tick_size(self) -> float:
        """
        Minimum price increment.
        """

        return 10 ** (-self.price_precision)

    @property
    def step_size(self) -> float:
        """
        Minimum quantity increment.
        """

        return 10 ** (-self.quantity_precision)