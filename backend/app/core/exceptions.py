"""Domain-level exceptions. Services and repositories raise these; the API
layer (see app/main.py exception handlers) maps them to HTTP responses.
Keeping this mapping in one place means services never import fastapi.
"""


class DomainError(Exception):
    """Base class for all domain-level errors."""


class NotFoundError(DomainError):
    def __init__(self, entity: str, entity_id: str):
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} {entity_id} not found")


class ValidationError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ProviderError(DomainError):
    """Raised by FinancialDataProvider implementations on upstream failure."""
