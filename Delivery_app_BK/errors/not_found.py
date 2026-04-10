from .base import DomainError

class NotFound( DomainError ):
    code = "not_found"