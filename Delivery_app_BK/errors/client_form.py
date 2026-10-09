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

    def __init__(self, team_id: int | None = None):
        super().__init__("Form has already been submitted.")
        # The token was genuine, so the team is known and the "already
        # submitted" response may still carry the team's public redirect.
        self.team_id = team_id
        self.extra: dict = {}
