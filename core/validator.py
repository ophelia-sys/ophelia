from core.errors import OrderRejected

from core.enums import OrderType
from models.order_request import OrderRequest


class Validator:
    """
    Validates OrderRequest objects before they are
    submitted to the BingX API.

    All validation failures raise OrderRejected.
    """

    @staticmethod
    def validate(request: OrderRequest) -> None:

        Validator._validate_symbol(request)

        Validator._validate_quantity(request)

        Validator._validate_price(request)

        Validator._validate_stop_price(request)

        Validator._validate_trailing(request)

        Validator._validate_close_position(request)

    # =====================================================
    # SYMBOL
    # =====================================================

    @staticmethod
    def _validate_symbol(
        request: OrderRequest,
    ) -> None:

        if not request.symbol:
            raise OrderRejected(
                "Symbol is required."
            )

        if "-" not in request.symbol:
            raise OrderRejected(
                "Invalid BingX symbol format. Example: BTC-USDT"
            )

    # =====================================================
    # QUANTITY
    # =====================================================

    @staticmethod
    def _validate_quantity(
        request: OrderRequest,
    ) -> None:

        if request.close_position:
            return

        if (
            request.quantity is None
            and request.quote_order_qty is None
        ):
            raise OrderRejected(
                "Quantity is required."
            )

        if (
            request.quantity is not None
            and request.quantity <= 0
        ):
            raise OrderRejected(
                "Quantity must be greater than zero."
            )

        if (
            request.quote_order_qty is not None
            and request.quote_order_qty <= 0
        ):
            raise OrderRejected(
                "Quote quantity must be greater than zero."
            )

    # =====================================================
    # PRICE
    # =====================================================

    @staticmethod
    def _validate_price(
        request: OrderRequest,
    ) -> None:

        if request.order_type in (

            OrderType.LIMIT,

            OrderType.STOP,

            OrderType.TAKE_PROFIT,

            OrderType.TRIGGER_LIMIT,

        ):

            if request.price is None:

                raise OrderRejected(
                    "Price is required."
                )

            if request.price <= 0:

                raise OrderRejected(
                    "Price must be positive."
                )

        elif request.order_type == OrderType.MARKET:

            if request.price is not None:

                raise OrderRejected(
                    "Market order cannot have price."
                )

    # =====================================================
    # STOP PRICE
    # =====================================================

    @staticmethod
    def _validate_stop_price(
        request: OrderRequest,
    ) -> None:

        if request.order_type in (

            OrderType.STOP,

            OrderType.STOP_MARKET,

            OrderType.TAKE_PROFIT,

            OrderType.TAKE_PROFIT_MARKET,

            OrderType.TRIGGER_MARKET,

            OrderType.TRIGGER_LIMIT,

        ):

            if request.stop_price is None:

                raise OrderRejected(
                    "stopPrice is required."
                )

            if request.stop_price <= 0:

                raise OrderRejected(
                    "stopPrice must be positive."
                )

    # =====================================================
    # TRAILING
    # =====================================================

    @staticmethod
    def _validate_trailing(
        request: OrderRequest,
    ) -> None:

        if request.order_type not in (

            OrderType.TRAILING_STOP_MARKET,

            OrderType.TRAILING_TP_SL,

        ):

            return

        if (

            request.price is None

            and request.price_rate is None

        ):

            raise OrderRejected(

                "Trailing order requires "

                "price or priceRate."

            )

        if (

            request.price_rate is not None

            and (

                request.price_rate <= 0

                or request.price_rate > 1

            )

        ):

            raise OrderRejected(

                "priceRate must be between "

                "0 and 1."

            )

    # =====================================================
    # CLOSE POSITION
    # =====================================================

    @staticmethod
    def _validate_close_position(
        request: OrderRequest,
    ) -> None:

        if not request.close_position:
            return

        if request.quantity is not None:

            raise OrderRejected(

                "closePosition cannot be "

                "used with quantity."

            )