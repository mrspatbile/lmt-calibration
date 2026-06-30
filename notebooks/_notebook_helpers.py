"""Display helpers for educational notebooks."""

from decimal import Decimal

from lmt_calibration.domain import LiquidationResult

ZERO = Decimal("0")


def money(value: Decimal | int | float | None) -> str:
    """Format a money-like value for display."""

    if value is None:
        return ""
    return f"{Decimal(value):,.2f}"


def rate(value: Decimal | int | float | None) -> str:
    """Format a decimal rate for display."""

    if value is None:
        return ""
    return f"{Decimal(value) * Decimal('100'):.2f}%"


def days(value: int | None) -> str:
    """Format optional day counts for display."""

    if value is None:
        return ""
    return str(value)


def yes_no(value: bool) -> str:
    """Format booleans as reviewer-friendly labels."""

    return "yes" if value else "no"


def print_profile(profile: dict[str, object]) -> None:
    """Print a compact right-aligned key/value profile."""

    if not profile:
        return

    key_width = max(len(str(key)) for key in profile) + 2
    value_width = max(len(str(value)) for value in profile.values())

    for key, value in profile.items():
        label = f"{key}:"
        print(f"{label:>{key_width}} {str(value):>{value_width}}")


def gross_sales(result: LiquidationResult) -> Decimal:
    """Return total gross sales from a liquidation result."""

    return sum((asset.gross_sale_amount for asset in result.assets_liquidated), ZERO)
