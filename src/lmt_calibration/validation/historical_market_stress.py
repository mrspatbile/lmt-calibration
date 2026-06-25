"""Validation for historical market stress scenario JSON libraries."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation

from lmt_calibration.validation.errors import ValidationIssue
from lmt_calibration.validation.field_checks import (
    location as record_location,
)
from lmt_calibration.validation.field_checks import (
    raise_if_issues,
    validate_required_field,
    validate_snake_case,
)

HISTORICAL_LIBRARY_FIELDS = {
    "schema_version",
    "source",
    "scenario_type",
    "notes",
    "scenarios",
}
HISTORICAL_SCENARIO_FIELDS = {
    "test_category",
    "scenario_name",
    "description",
    "period",
    "holding_period_days",
    "shocks",
}
HISTORICAL_STRESS_SHOCK_FIELDS = {"shock", "unit", "description"}
HISTORICAL_FX_SHOCK_FIELDS = {"shock_by_currency", "unit", "description"}
HISTORICAL_SHOCK_GROUPS = {"equity", "interest_rates", "credit_spreads", "fx"}


def validate_historical_market_stress_scenarios_config(
    config: Mapping[str, object],
) -> dict[str, object]:
    """Validate historical market stress scenario JSON before domain object creation."""

    copied_config = dict(config)
    issues: list[ValidationIssue] = []

    unknown_top_level_fields = set(copied_config) - HISTORICAL_LIBRARY_FIELDS
    for field_name in sorted(unknown_top_level_fields):
        issues.append(
            ValidationIssue(
                location="historical_market_stress_scenarios",
                field=field_name,
                message="unknown top-level JSON field",
            )
        )

    for field_name in ("schema_version", "source", "scenario_type", "notes", "scenarios"):
        validate_required_field(
            copied_config, field_name, "historical_market_stress_scenarios", issues
        )

    if copied_config.get("schema_version") != "1.0":
        issues.append(
            ValidationIssue(
                location="historical_market_stress_scenarios",
                field="schema_version",
                message="must be 1.0",
            )
        )
    if copied_config.get("scenario_type") != "historical":
        issues.append(
            ValidationIssue(
                location="historical_market_stress_scenarios",
                field="scenario_type",
                message="must be historical",
            )
        )

    scenarios = copied_config.get("scenarios")
    if not isinstance(scenarios, Mapping) or not scenarios:
        issues.append(
            ValidationIssue(
                location="historical_market_stress_scenarios",
                field="scenarios",
                message="must be a non-empty object",
            )
        )
    else:
        _validate_scenario_entries(scenarios, issues)

    raise_if_issues(issues)
    return copied_config


def _validate_scenario_entries(
    scenarios: Mapping[object, object], issues: list[ValidationIssue]
) -> None:
    for index, (scenario_id, scenario) in enumerate(scenarios.items()):
        location = record_location("historical_market_stress_scenarios.scenarios", index)
        if not isinstance(scenario_id, str):
            issues.append(
                ValidationIssue(location=location, field="scenario_id", message="must be text")
            )
        else:
            validate_snake_case({"scenario_id": scenario_id}, "scenario_id", location, issues)

        if not isinstance(scenario, Mapping):
            issues.append(
                ValidationIssue(location=location, field="record", message="must be an object")
            )
            continue

        scenario_record = dict(scenario)
        unknown_scenario_fields = set(scenario_record) - HISTORICAL_SCENARIO_FIELDS
        for field_name in sorted(unknown_scenario_fields):
            issues.append(
                ValidationIssue(
                    location=location,
                    field=field_name,
                    message="unknown historical scenario field",
                )
            )

        for field_name in HISTORICAL_SCENARIO_FIELDS:
            validate_required_field(scenario_record, field_name, location, issues)

        _validate_positive_integer(scenario_record, "holding_period_days", location, issues)
        shocks = scenario_record.get("shocks")
        if not isinstance(shocks, Mapping) or not shocks:
            issues.append(
                ValidationIssue(location=location, field="shocks", message="must be an object")
            )
            continue
        _validate_shocks(shocks, location, issues)


def _validate_shocks(
    shocks: Mapping[object, object], location: str, issues: list[ValidationIssue]
) -> None:
    shock_group_names = {shock_group for shock_group in shocks if isinstance(shock_group, str)}
    for shock_group in shocks:
        if not isinstance(shock_group, str):
            issues.append(
                ValidationIssue(
                    location=location,
                    field=f"shocks.{shock_group}",
                    message="shock group must be text",
                )
            )
    missing_groups = HISTORICAL_SHOCK_GROUPS - shock_group_names
    unknown_groups = shock_group_names - HISTORICAL_SHOCK_GROUPS

    for shock_group in sorted(missing_groups):
        issues.append(
            ValidationIssue(
                location=location,
                field=f"shocks.{shock_group}",
                message="is required",
            )
        )
    for shock_group in sorted(unknown_groups):
        issues.append(
            ValidationIssue(
                location=location,
                field=f"shocks.{shock_group}",
                message="unknown shock group",
            )
        )

    for shock_group in ("equity", "interest_rates", "credit_spreads"):
        if shock_group in shocks:
            _validate_stress_shock(shock_group, shocks[shock_group], location, issues)
    if "fx" in shocks:
        _validate_fx_shock(shocks["fx"], location, issues)


def _validate_stress_shock(
    shock_group: str,
    shock: object,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    shock_location = f"{location}.shocks.{shock_group}"
    if not isinstance(shock, Mapping):
        issues.append(
            ValidationIssue(location=shock_location, field="record", message="must be an object")
        )
        return

    shock_record = dict(shock)
    _validate_unknown_fields(
        shock_record,
        HISTORICAL_STRESS_SHOCK_FIELDS,
        shock_location,
        "unknown stress shock field",
        issues,
    )
    for field_name in HISTORICAL_STRESS_SHOCK_FIELDS:
        validate_required_field(shock_record, field_name, shock_location, issues)
    _validate_decimal_compatible(shock_record, "shock", shock_location, issues)
    _validate_pct_unit(shock_record, shock_location, issues)


def _validate_fx_shock(shock: object, location: str, issues: list[ValidationIssue]) -> None:
    shock_location = f"{location}.shocks.fx"
    if not isinstance(shock, Mapping):
        issues.append(
            ValidationIssue(location=shock_location, field="record", message="must be an object")
        )
        return

    shock_record = dict(shock)
    _validate_unknown_fields(
        shock_record,
        HISTORICAL_FX_SHOCK_FIELDS,
        shock_location,
        "unknown FX shock field",
        issues,
    )
    for field_name in HISTORICAL_FX_SHOCK_FIELDS:
        validate_required_field(shock_record, field_name, shock_location, issues)
    _validate_pct_unit(shock_record, shock_location, issues)

    shock_by_currency = shock_record.get("shock_by_currency")
    if not isinstance(shock_by_currency, Mapping) or not shock_by_currency:
        issues.append(
            ValidationIssue(
                location=shock_location,
                field="shock_by_currency",
                message="must be a non-empty object",
            )
        )
        return

    for currency, currency_shock in shock_by_currency.items():
        if not isinstance(currency, str) or not _is_uppercase_currency(currency):
            issues.append(
                ValidationIssue(
                    location=shock_location,
                    field=f"shock_by_currency.{currency}",
                    message="currency must be a 3-letter uppercase code",
                )
            )
            continue
        if not _is_decimal_compatible(currency_shock):
            issues.append(
                ValidationIssue(
                    location=shock_location,
                    field=f"shock_by_currency.{currency}",
                    message="must be decimal-compatible",
                )
            )


def _validate_unknown_fields(
    record: Mapping[object, object],
    allowed_fields: set[str],
    location: str,
    message: str,
    issues: list[ValidationIssue],
) -> None:
    field_names = {str(field_name) for field_name in record}
    for field_name in sorted(field_names - allowed_fields):
        issues.append(ValidationIssue(location=location, field=str(field_name), message=message))


def _validate_positive_integer(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    value = record.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        issues.append(
            ValidationIssue(location=location, field=field_name, message="must be integer")
        )
        return
    if value <= 0:
        issues.append(ValidationIssue(location=location, field=field_name, message="must be > 0"))


def _validate_decimal_compatible(
    record: Mapping[str, object],
    field_name: str,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    if not _is_decimal_compatible(record.get(field_name)):
        issues.append(
            ValidationIssue(
                location=location,
                field=field_name,
                message="must be decimal-compatible",
            )
        )


def _validate_pct_unit(
    record: Mapping[str, object],
    location: str,
    issues: list[ValidationIssue],
) -> None:
    if record.get("unit") != "pct":
        issues.append(ValidationIssue(location=location, field="unit", message="must be pct"))


def _is_decimal_compatible(value: object) -> bool:
    if isinstance(value, bool) or value is None:
        return False
    if not isinstance(value, Decimal | int | float | str):
        return False
    if isinstance(value, str) and "%" in value:
        return False
    try:
        Decimal(str(value))
    except (InvalidOperation, ValueError):
        return False
    return True


def _is_uppercase_currency(value: str) -> bool:
    return len(value) == 3 and value.isalpha() and value.isupper()
