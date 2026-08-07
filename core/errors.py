class BingXError(Exception):
    """Base exception for BingX."""


class BingXAPIError(BingXError):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class BingXNetworkError(BingXError):
    pass


class ValidationError(BingXError):
    pass