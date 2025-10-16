class ZaloChatBotException(Exception):
    def __init__(self, message: str, error_code: str | None = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ZaloAPIException(ZaloChatBotException):
    def __init__(self, message: str, status_code: int | None = None, error_code: str | None = None):
        self.status_code = status_code
        super().__init__(message, error_code)


class DatabaseException(ZaloChatBotException):
    pass


class ValidationException(ZaloChatBotException):
    def __init__(self, message: str, field_name: str | None = None, error_code: str | None = None):
        self.field_name = field_name
        super().__init__(message, error_code)