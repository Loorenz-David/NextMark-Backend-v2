from .base import DomainError

class PermissionDenied( DomainError ):
    code = 'forbidden'