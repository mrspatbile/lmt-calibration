"""Custom validation errors for V1 input checks."""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationIssue:
    """One explicit input validation issue."""

    location: str
    field: str
    message: str

    def format(self) -> str:
        """Return a compact user-facing validation message."""

        return f"{self.location}.{self.field}: {self.message}"


class DataValidationError(ValueError):
    """Raised when external data fails validation before domain object creation."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues: tuple[ValidationIssue, ...] = tuple(issues)
        message = "; ".join(issue.format() for issue in self.issues)
        super().__init__(message)
