class Endpoint:

    # ==============================
    # MARKET
    # ==============================

    CONTRACTS = "/openApi/swap/v2/quote/contracts"

    PRICE = "/openApi/swap/v2/quote/price"

    TICKER = "/openApi/swap/v2/quote/ticker"

    BOOK_TICKER = "/openApi/swap/v2/quote/bookTicker"

    PREMIUM_INDEX = "/openApi/swap/v2/quote/premiumIndex"

    OPEN_INTEREST = "/openApi/swap/v2/quote/openInterest"

    KLINES = "/openApi/swap/v3/quote/klines"

    # ==============================
    # ACCOUNT
    # ==============================

    BALANCE = "/openApi/swap/v3/user/balance"

    POSITIONS = "/openApi/swap/v2/user/positions"

    # ==============================
    # LEVERAGE
    # ==============================

    LEVERAGE = "/openApi/swap/v2/trade/leverage"

    MARGIN_MODE = "/openApi/swap/v2/trade/marginType"

    POSITION_MODE = "/openApi/swap/v1/positionSide/dual"

    # ==============================
    # ORDERS
    # ==============================

    ORDER = "/openApi/swap/v2/trade/order"

    OPEN_ORDERS = "/openApi/swap/v2/trade/openOrders"

    ALL_OPEN_ORDERS = "/openApi/swap/v2/trade/allOpenOrders"

    ORDER_HISTORY = "/openApi/swap/v2/trade/allOrders"

    TRADE_HISTORY = "/openApi/swap/v2/trade/allFillOrders"

    # ==============================
    # POSITION
    # ==============================

    CLOSE_ALL_POSITIONS = "/openApi/swap/v2/trade/closeAllPositions"

    CLOSE_POSITION = "/openApi/swap/v1/trade/closePosition"

    # ==============================
    # MODIFY
    # ==============================

    AMEND_ORDER = "/openApi/swap/v1/trade/amend"