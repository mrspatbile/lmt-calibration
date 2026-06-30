"""Small V1 validation rules for raw input records and JSON config.

These functions validate external inputs before domain object creation. They
return copied records or configuration dictionaries and never instantiate domain
models, load files, or perform business calculations.
"""

from decimal import Decimal

from lmt_calibration.validation.errors import ValidationIssue
from lmt_calibration.validation.field_checks import (
    CUSTOM_STRATEGY_FIELDS,
    SUPPORTED_ASSET_GROUPS,
    SUPPORTED_CLIENT_CLASSES,
    SUPPORTED_INSTRUMENT_SUBTYPES,
    SUPPORTED_INSTRUMENT_TYPES,
    as_records,
    raise_if_issues,
    validate_currency,
    validate_decimal,
    validate_exactly_one_reference,
    validate_forbidden_fields,
    validate_in_allowed,
    validate_int,
    validate_optional_decimal,
    validate_optional_int,
    validate_position_conditional_fields,
    validate_records,
    validate_snake_case,
    validate_unique_key,
)
from lmt_calibration.validation.field_checks import (
    location as record_location,
)
from lmt_calibration.validation.liquidation_config import validate_liquidation_strategy_config

__all__ = [
    "validate_fund_records",
    "validate_investor_class_records",
    "validate_liquidation_strategy_config",
    "validate_liquidity_stress_records",
    "validate_lmt_parameter_records",
    "validate_market_stress_records",
    "validate_position_records",
    "validate_redemption_scenario_records",
    "validate_scenario_definition_records",
]


def validate_fund_records(records: object) -> list[dict[str, object]]:
    """Validate raw fund snapshot records."""

    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    validate_records(
        copied_records,
        required_fields={
            "fund_id",
            "as_of_date",
            "fund_name",
            "base_currency",
            "nav",
            "dealing_frequency",
            "redemption_notice_days",
            "redemption_settlement_days",
        },
        dataset_name="funds",
        issues=issues,
    )
    validate_unique_key(copied_records, ("fund_id", "as_of_date"), "funds", issues)

    for index, record in enumerate(copied_records):
        location = record_location("funds", index)
        validate_currency(record, "base_currency", location, issues)
        validate_decimal(record, "nav", location, issues, gt=Decimal("0"))
        validate_int(record, "redemption_notice_days", location, issues, ge=0)
        validate_int(record, "redemption_settlement_days", location, issues, ge=0)

    raise_if_issues(issues)
    return copied_records


def validate_position_records(records: object) -> list[dict[str, object]]:
    """Validate raw position records, including conditional subtype fields."""

    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    validate_records(
        copied_records,
        required_fields={
            "position_id",
            "fund_id",
            "as_of_date",
            "asset_group",
            "instrument_type",
            "instrument_subtype",
            "instrument_name",
            "currency",
            "base_haircut_rate",
            "base_liquidity_capacity_rate",
            "settlement_days",
        },
        dataset_name="positions",
        issues=issues,
    )
    validate_unique_key(
        copied_records, ("fund_id", "as_of_date", "position_id"), "positions", issues
    )

    for index, record in enumerate(copied_records):
        location = record_location("positions", index)
        validate_in_allowed(record, "asset_group", SUPPORTED_ASSET_GROUPS, location, issues)
        validate_in_allowed(record, "instrument_type", SUPPORTED_INSTRUMENT_TYPES, location, issues)
        validate_in_allowed(
            record,
            "instrument_subtype",
            SUPPORTED_INSTRUMENT_SUBTYPES,
            location,
            issues,
        )
        validate_currency(record, "currency", location, issues)
        validate_optional_decimal(record, "market_value", location, issues, ge=Decimal("0"))
        validate_optional_decimal(record, "notional_amount", location, issues, ge=Decimal("0"))
        validate_optional_decimal(record, "beta", location, issues)
        validate_optional_decimal(record, "duration_years", location, issues)
        validate_optional_decimal(record, "spread_duration_years", location, issues)
        validate_optional_decimal(record, "delta", location, issues)
        validate_optional_decimal(record, "entry_price", location, issues, ge=Decimal("0"))
        validate_optional_decimal(record, "strike_price", location, issues, ge=Decimal("0"))
        validate_decimal(
            record, "base_haircut_rate", location, issues, ge=Decimal("0"), le=Decimal("1")
        )
        validate_decimal(
            record,
            "base_liquidity_capacity_rate",
            location,
            issues,
            ge=Decimal("0"),
            le=Decimal("1"),
        )
        validate_int(record, "settlement_days", location, issues, ge=0)
        validate_optional_int(record, "maturity_days", location, issues, ge=0)
        validate_position_conditional_fields(record, location, issues)

    raise_if_issues(issues)
    return copied_records


def validate_investor_class_records(records: object) -> list[dict[str, object]]:
    """Validate raw investor class records."""

    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    validate_records(
        copied_records,
        required_fields={
            "fund_id",
            "as_of_date",
            "client_class",
            "nav_share_rate",
            "base_redemption_rate",
            "stress_redemption_rate",
            "concentration_factor",
            "notice_days",
            "settlement_days",
        },
        dataset_name="investor_classes",
        issues=issues,
    )

    for index, record in enumerate(copied_records):
        location = record_location("investor_classes", index)
        validate_in_allowed(record, "client_class", SUPPORTED_CLIENT_CLASSES, location, issues)
        for field_name in ("nav_share_rate", "base_redemption_rate", "stress_redemption_rate"):
            validate_decimal(record, field_name, location, issues, ge=Decimal("0"), le=Decimal("1"))
        validate_decimal(record, "concentration_factor", location, issues, gt=Decimal("0"))
        validate_int(record, "notice_days", location, issues, ge=0)
        validate_int(record, "settlement_days", location, issues, ge=0)

    raise_if_issues(issues)
    return copied_records


def validate_redemption_scenario_records(records: object) -> list[dict[str, object]]:
    """Validate reusable liability-side redemption scenario records."""

    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    validate_records(
        copied_records,
        required_fields={
            "redemption_scenario_id",
            "version",
            "name",
            "description",
            "redemption_multiplier",
        },
        dataset_name="redemption_scenarios",
        issues=issues,
    )
    validate_unique_key(copied_records, ("redemption_scenario_id",), "redemption_scenarios", issues)

    forbidden_fields = {
        "fund_id",
        "as_of_date",
        "market_stress_id",
        "liquidity_stress_id",
        "liquidation_strategy_id",
        "lmt_parameter_set_id",
    }
    for index, record in enumerate(copied_records):
        location = record_location("redemption_scenarios", index)
        validate_forbidden_fields(record, forbidden_fields, location, issues)
        validate_snake_case(record, "redemption_scenario_id", location, issues)
        validate_snake_case(record, "name", location, issues)
        validate_decimal(record, "redemption_multiplier", location, issues, gt=Decimal("0"))

    raise_if_issues(issues)
    return copied_records


def validate_market_stress_records(records: object) -> list[dict[str, object]]:
    """Validate reusable market stress records."""

    copied_records = _validate_versioned_assumption_records(
        records,
        id_field="market_stress_id",
        dataset_name="market_stresses",
    )
    issues: list[ValidationIssue] = []
    for index, record in enumerate(copied_records):
        location = record_location("market_stresses", index)
        validate_forbidden_fields(record, {"fund_id", "as_of_date"}, location, issues)
        validate_decimal(
            record, "market_shock_rate", location, issues, ge=Decimal("-1"), le=Decimal("1")
        )
    raise_if_issues(issues)
    return copied_records


def validate_liquidity_stress_records(records: object) -> list[dict[str, object]]:
    """Validate reusable asset-group liquidity and execution assumptions."""

    copied_records = _validate_versioned_assumption_records(
        records,
        id_field="liquidity_stress_id",
        dataset_name="liquidity_stresses",
    )
    issues: list[ValidationIssue] = []
    for index, record in enumerate(copied_records):
        location = record_location("liquidity_stresses", index)
        validate_forbidden_fields(record, {"fund_id", "as_of_date"}, location, issues)
        validate_int(record, "stress_horizon_days", location, issues, gt=0)
        # execution_assumptions_by_asset_group is validated by Pydantic model
    raise_if_issues(issues)
    return copied_records


def validate_scenario_definition_records(records: object) -> list[dict[str, object]]:
    """Validate scenario definitions without resolving referenced IDs."""

    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    required_fields = {
        "scenario_id",
        "fund_id",
        "as_of_date",
        "redemption_scenario_id",
        "market_stress_id",
        "liquidity_stress_id",
        "liquidation_strategy_id",
        "lmt_parameter_set_id",
    }
    validate_records(
        copied_records,
        required_fields=required_fields,
        dataset_name="scenario_definitions",
        issues=issues,
    )
    validate_unique_key(copied_records, ("scenario_id",), "scenario_definitions", issues)

    for index, record in enumerate(copied_records):
        location = record_location("scenario_definitions", index)
        validate_forbidden_fields(record, CUSTOM_STRATEGY_FIELDS, location, issues)
        validate_snake_case(record, "scenario_id", location, issues)
        for field_name in (
            "redemption_scenario_id",
            "market_stress_id",
            "liquidity_stress_id",
            "liquidation_strategy_id",
            "lmt_parameter_set_id",
        ):
            validate_exactly_one_reference(record, field_name, location, issues)

    raise_if_issues(issues)
    return copied_records


def validate_lmt_parameter_records(records: object) -> list[dict[str, object]]:
    """Validate raw LMT parameter records."""

    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    validate_records(
        copied_records,
        required_fields={
            "fund_id",
            "as_of_date",
            "parameter_set_id",
            "swing_threshold_rate",
            "max_swing_factor_rate",
            "gate_threshold_rate",
            "minimum_buffer_rate",
        },
        dataset_name="lmt_parameters",
        issues=issues,
    )
    validate_unique_key(
        copied_records, ("fund_id", "as_of_date", "parameter_set_id"), "lmt_parameters", issues
    )

    for index, record in enumerate(copied_records):
        location = record_location("lmt_parameters", index)
        for field_name in (
            "swing_threshold_rate",
            "max_swing_factor_rate",
            "gate_threshold_rate",
            "minimum_buffer_rate",
        ):
            validate_decimal(record, field_name, location, issues, ge=Decimal("0"), le=Decimal("1"))

    raise_if_issues(issues)
    return copied_records


def _validate_versioned_assumption_records(
    records: object,
    *,
    id_field: str,
    dataset_name: str,
) -> list[dict[str, object]]:
    copied_records = as_records(records)
    issues: list[ValidationIssue] = []
    validate_records(
        copied_records,
        required_fields={
            id_field,
            "version",
            "name",
            "description",
            *_stress_value_fields(id_field),
        },
        dataset_name=dataset_name,
        issues=issues,
    )
    validate_unique_key(copied_records, (id_field,), dataset_name, issues)
    for index, record in enumerate(copied_records):
        location = record_location(dataset_name, index)
        validate_snake_case(record, id_field, location, issues)
        validate_snake_case(record, "name", location, issues)
    raise_if_issues(issues)
    return copied_records


def _stress_value_fields(id_field: str) -> set[str]:
    if id_field == "market_stress_id":
        return {"market_shock_rate"}
    if id_field == "liquidity_stress_id":
        return {"stress_horizon_days"}
    return set()
