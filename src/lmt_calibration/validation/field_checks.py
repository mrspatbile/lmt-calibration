"""Shared validation constants and helper functions."""

from collections.abc import Mapping, Sequence
from decimal import Decimal, InvalidOperation
from typing import cast

from lmt_calibration.domain.investors import ClientClass
from lmt_calibration.domain.positions import AssetGroup, InstrumentSubtype, OptionType
from lmt_calibration.domain.scenarios import LiquidationStrategyType
from lmt_calibration.validation.errors import DataValidationError, ValidationIssue

SNAKE_CASE_ALLOWED_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789_"

SUPPORTED_ASSET_GROUPS = {asset_group.value for asset_group in AssetGroup}
SUPPORTED_INSTRUMENT_SUBTYPES = {subtype.value for subtype in InstrumentSubtype}
SUPPORTED_INSTRUMENT_TYPES = SUPPORTED_INSTRUMENT_SUBTYPES
SUPPORTED_CLIENT_CLASSES = {client_class.value for client_class in ClientClass}
SUPPORTED_OPTION_TYPES = {option_type.value for option_type in OptionType}
SUPPORTED_STRATEGY_TYPES = {strategy_type.value for strategy_type in LiquidationStrategyType}

JSON_TOP_LEVEL_FIELDS = {
    "schema_version",
    "config_type",
    "name",
    "description",
    "strategies",
}
JSON_STRATEGY_FIELDS = {
    "liquidation_strategy_id",
    "version",
    "name",
    "description",
    "strategy_type",
    "cash_buffer_use_rate",
    "preserve_minimum_buffer",
    "weights",
}

CUSTOM_STRATEGY_FIELDS = {
    "strategy_type",
    "cash_buffer_use_rate",
    "preserve_minimum_buffer",
    "weights",
    "custom_weights",
    "liquidation_weight_rate",
    "asset_group",
}

POSITION_REQUIRED_BY_SUBTYPE: dict[str, tuple[str, ...]] = {
    "cash": ("market_value",),
    "listed_equity": ("market_value", "risk_factor_id", "beta"),
    "listed_etf": ("market_value", "risk_factor_id"),
    "government_bond": ("market_value", "risk_factor_id", "duration_years"),
    "corporate_bond": (
        "market_value",
        "risk_factor_id",
        "duration_years",
        "spread_duration_years",
    ),
    "equity_future": (
        "notional_amount",
        "entry_price",
        "delta",
        "underlying_risk_factor_id",
    ),
    "interest_rate_future": (
        "notional_amount",
        "entry_price",
        "delta",
        "underlying_risk_factor_id",
    ),
    "fx_forward": (
        "notional_amount",
        "entry_price",
        "expiry_date",
        "delta",
        "underlying_risk_factor_id",
    ),
    "interest_rate_swap": ("notional_amount", "underlying_risk_factor_id"),
    "reverse_repo": ("market_value", "maturity_days"),
}


def as_records(records: object) -> list[dict[str, object]]:
    """Copy raw records from a mapping, sequence of mappings, or DataFrame."""

    if isinstance(records, Mapping):
        return [dict(records)]

    to_dict = getattr(records, "to_dict", None)
    if callable(to_dict):
        dataframe_records = to_dict(orient="records")
        return [dict(cast(Mapping[str, object], record)) for record in dataframe_records]

    if isinstance(records, Sequence) and not isinstance(records, str):
        return [dict(cast(Mapping[str, object], record)) for record in records]

    raise DataValidationError(
        [
            ValidationIssue(
                location="records", field="input", message="must be a record list or DataFrame"
            )
        ]
    )


def validate_records(
    records: list[dict[str, object]],
    *,
    required_fields: set[str],
    dataset_name: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate common record-shape requirements."""

    if not records:
        issues.append(
            ValidationIssue(location=dataset_name, field="records", message="must not be empty")
        )
        return

    for index, record in enumerate(records):
        record_location = location(dataset_name, index)
        for field_name in sorted(required_fields):
            validate_required_field(record, field_name, record_location, issues)


def validate_required_field(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate that a required field is present and non-empty."""

    if field_name not in record or is_missing(record.get(field_name)):
        issues.append(ValidationIssue(location=location, field=field_name, message="is required"))


def validate_forbidden_fields(
    record: Mapping[str, object],
    forbidden_fields: set[str],
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate that forbidden fields are not present."""

    for field_name in sorted(forbidden_fields.intersection(record.keys())):
        issues.append(
            ValidationIssue(location=location, field=field_name, message="is not allowed here")
        )


def validate_unique_key(
    records: list[dict[str, object]],
    key_fields: tuple[str, ...],
    dataset_name: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate key uniqueness across records."""

    seen: set[tuple[object, ...]] = set()
    for index, record in enumerate(records):
        key = tuple(record.get(field_name) for field_name in key_fields)
        if any(is_missing(value) for value in key):
            continue
        if key in seen:
            issues.append(
                ValidationIssue(
                    location=location(dataset_name, index),
                    field=",".join(key_fields),
                    message="must be unique",
                )
            )
        seen.add(key)


def validate_position_conditional_fields(
    record: Mapping[str, object],
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate conditional position fields by instrument subtype."""

    subtype = record.get("instrument_subtype")
    if not isinstance(subtype, str):
        return

    for field_name in POSITION_REQUIRED_BY_SUBTYPE.get(subtype, ()):
        validate_required_field(record, field_name, location, issues)

    if subtype == "cash":
        validate_exact_decimal(record, "base_haircut_rate", Decimal("0"), location, issues)
        validate_exact_decimal(
            record, "base_liquidity_capacity_rate", Decimal("1"), location, issues
        )
        validate_exact_int(record, "settlement_days", 0, location, issues)

    if subtype == "equity_option":
        for field_name in (
            "notional_amount",
            "strike_price",
            "option_type",
            "expiry_date",
            "delta",
        ):
            validate_required_field(record, field_name, location, issues)
        validate_in_allowed(record, "option_type", SUPPORTED_OPTION_TYPES, location, issues)
        if is_missing(record.get("underlying_position_id")) and is_missing(
            record.get("underlying_risk_factor_id")
        ):
            issues.append(
                ValidationIssue(
                    location=location,
                    field="underlying_position_id",
                    message="or underlying_risk_factor_id is required for equity_option",
                )
            )

    if subtype == "interest_rate_swap" and is_missing(record.get("duration_years")):
        issues.append(
            ValidationIssue(
                location=location,
                field="duration_years",
                message="is required for interest_rate_swap",
            )
        )


def validate_currency(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate ISO-style uppercase currency codes."""

    value = record.get(field_name)
    if isinstance(value, str) and len(value) == 3 and value.isupper():
        return
    issues.append(
        ValidationIssue(
            location=location, field=field_name, message="must be a 3-letter uppercase code"
        )
    )


def validate_in_allowed(
    record: Mapping[str, object],
    field_name: str,
    allowed_values: set[str],
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate that a field value belongs to an allowed set."""

    value = record.get(field_name)
    if is_missing(value):
        return
    if value not in allowed_values:
        allowed = ", ".join(sorted(allowed_values))
        issues.append(
            ValidationIssue(
                location=location, field=field_name, message=f"must be one of {allowed}"
            )
        )


def validate_snake_case(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate snake_case identifier fields."""

    value = record.get(field_name)
    if is_missing(value):
        return
    if not isinstance(value, str) or not is_snake_case(value):
        issues.append(
            ValidationIssue(location=location, field=field_name, message="must use snake_case")
        )


def validate_exactly_one_reference(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate a reference field carries exactly one scalar ID."""

    value = record.get(field_name)
    if is_missing(value):
        return
    if isinstance(value, Sequence) and not isinstance(value, str):
        issues.append(
            ValidationIssue(
                location=location, field=field_name, message="must reference exactly one ID"
            )
        )


def validate_json_decimal_string(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
    *,
    required: bool,
) -> None:
    """Validate a JSON decimal encoded as a string."""

    value = record.get(field_name)
    if is_missing(value):
        if required:
            validate_required_field(record, field_name, location, issues)
        return
    if not isinstance(value, str) or parse_decimal_string(value) is None:
        issues.append(
            ValidationIssue(location=location, field=field_name, message="must be a decimal string")
        )


def validate_decimal(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
    *,
    gt: Decimal | None = None,
    ge: Decimal | None = None,
    le: Decimal | None = None,
) -> None:
    """Validate a Decimal-compatible record value and optional bounds."""

    value = record.get(field_name)
    parsed_value = parse_decimal_value(value)
    if parsed_value is None:
        issues.append(
            ValidationIssue(location=location, field=field_name, message="must be decimal")
        )
        return
    validate_decimal_bounds(parsed_value, field_name, location, issues, gt=gt, ge=ge, le=le)


def validate_optional_decimal(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
    *,
    ge: Decimal | None = None,
) -> None:
    """Validate an optional Decimal-compatible value."""

    if is_missing(record.get(field_name)):
        return
    validate_decimal(record, field_name, location, issues, ge=ge)


def validate_decimal_bounds(
    value: Decimal,
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
    *,
    gt: Decimal | None,
    ge: Decimal | None,
    le: Decimal | None,
) -> None:
    """Validate Decimal bounds."""

    if gt is not None and value <= gt:
        issues.append(
            ValidationIssue(location=location, field=field_name, message=f"must be > {gt}")
        )
    if ge is not None and value < ge:
        issues.append(
            ValidationIssue(location=location, field=field_name, message=f"must be >= {ge}")
        )
    if le is not None and value > le:
        issues.append(
            ValidationIssue(location=location, field=field_name, message=f"must be <= {le}")
        )


def validate_exact_decimal(
    record: Mapping[str, object],
    field_name: str,
    expected_value: Decimal,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate a Decimal-compatible value equals an expected value."""

    parsed_value = parse_decimal_value(record.get(field_name))
    if parsed_value is not None and parsed_value != expected_value:
        issues.append(
            ValidationIssue(
                location=location,
                field=field_name,
                message=f"must be {expected_value}",
            )
        )


def validate_int(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
    *,
    gt: int | None = None,
    ge: int | None = None,
) -> None:
    """Validate an integer value and optional bounds."""

    value = record.get(field_name)
    if not isinstance(value, int):
        issues.append(
            ValidationIssue(location=location, field=field_name, message="must be integer")
        )
        return
    if gt is not None and value <= gt:
        issues.append(
            ValidationIssue(location=location, field=field_name, message=f"must be > {gt}")
        )
    if ge is not None and value < ge:
        issues.append(
            ValidationIssue(location=location, field=field_name, message=f"must be >= {ge}")
        )


def validate_optional_int(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
    *,
    ge: int | None = None,
) -> None:
    """Validate an optional integer value."""

    if is_missing(record.get(field_name)):
        return
    validate_int(record, field_name, location, issues, ge=ge)


def validate_exact_int(
    record: Mapping[str, object],
    field_name: str,
    expected_value: int,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    """Validate an integer value equals an expected value."""

    value = record.get(field_name)
    if isinstance(value, int) and value != expected_value:
        issues.append(
            ValidationIssue(
                location=location, field=field_name, message=f"must be {expected_value}"
            )
        )


def parse_decimal_value(value: object) -> Decimal | None:
    """Parse Decimal-compatible input while rejecting raw percentage strings."""

    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | str):
        if isinstance(value, str) and "%" in value:
            return None
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None


def parse_decimal_string(value: str) -> Decimal | None:
    """Parse a JSON decimal string while rejecting raw percentage strings."""

    if "%" in value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def is_snake_case(value: str) -> bool:
    """Return whether a value is a simple snake_case identifier."""

    if not value or value[0] == "_" or value[-1] == "_" or "__" in value:
        return False
    return all(character in SNAKE_CASE_ALLOWED_CHARS for character in value)


def is_missing(value: object) -> bool:
    """Return whether a raw input value is missing."""

    return value is None or value == ""


def location(dataset_name: str, index: int) -> str:
    """Build a stable record location label."""

    return f"{dataset_name}[{index}]"


def raise_if_issues(issues: list[ValidationIssue]) -> None:
    """Raise a validation error when issues were collected."""

    if issues:
        raise DataValidationError(issues)
