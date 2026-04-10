from .base import DomainError

class ValidationFailed( DomainError ):
    code = "bad_request"