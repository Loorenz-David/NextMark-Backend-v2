from .base import DomainError


class TokenInvalidError(DomainError):
    code = "token_invalid"

    def __init__(self):
        super().__init__("Form link is not valid.")


class TokenExpiredError(DomainError):
    code = "token_expired"

    def __init__(self):
        super().__init__("Form link has expired.")


class TokenAlreadyUsedError(DomainError):
    code = "token_already_used"

    def __init__(self):
        super().__init__("Form has already been submitted.")
