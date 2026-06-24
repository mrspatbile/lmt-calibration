"""Validation for JSON liquidation strategy configuration."""

from collections.abc import Mapping
from decimal import Decimal

from lmt_calibration.validation.errors import ValidationIssue
from lmt_calibration.validation.field_checks import (
    JSON_STRATEGY_FIELDS,
    JSON_TOP_LEVEL_FIELDS,
    SUPPORTED_ASSET_GROUPS,
    SUPPORTED_STRATEGY_TYPES,
    parse_decimal_string,
    raise_if_issues,
    validate_in_allowed,
    validate_json_decimal_string,
    validate_required_field,
    validate_snake_case,
)
from lmt_calibration.validation.field_checks import (
    location as record_location,
)


def validate_liquidation_strategy_config(config: Mapping[str, object]) -> dict[str, object]:
    """Validate JSON liquidation strategy configuration."""

    copied_config = dict(config)
    issues: list[ValidationIssue] = []

    unknown_top_level_fields = set(copied_config) - JSON_TOP_LEVEL_FIELDS
    for field_name in sorted(unknown_top_level_fields):
        issues.append(
            ValidationIssue(
                location="liquidation_strategies",
                field=field_name,
                message="unknown top-level JSON field",
            )
        )

    for field_name in ("schema_version", "config_type", "name", "description"):
        validate_required_field(copied_config, field_name, "liquidation_strategies", issues)

    validate_snake_case(copied_config, "name", "liquidation_strategies", issues)

    if copied_config.get("config_type") != "liquidation_strategies":
        issues.append(
            ValidationIssue(
                location="liquidation_strategies",
                field="config_type",
                message="must be liquidation_strategies",
            )
        )

    strategies = copied_config.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        issues.append(
            ValidationIssue(
                location="liquidation_strategies",
                field="strategies",
                message="must be a non-empty list",
            )
        )
    else:
        _validate_strategy_entries(strategies, issues)

    raise_if_issues(issues)
    return copied_config


def _validate_strategy_entries(strategies: list[object], issues: list[ValidationIssue]) -> None:
    seen_strategy_ids: set[str] = set()
    for index, strategy in enumerate(strategies):
        location = record_location("liquidation_strategies.strategies", index)
        if not isinstance(strategy, Mapping):
            issues.append(
                ValidationIssue(location=location, field="record", message="must be an object")
            )
            continue

        strategy_record = dict(strategy)
        unknown_strategy_fields = set(strategy_record) - JSON_STRATEGY_FIELDS
        for field_name in sorted(unknown_strategy_fields):
            issues.append(
                ValidationIssue(
                    location=location, field=field_name, message="unknown strategy field"
                )
            )

        for field_name in (
            "liquidation_strategy_id",
            "version",
            "name",
            "description",
            "strategy_type",
            "preserve_minimum_buffer",
        ):
            validate_required_field(strategy_record, field_name, location, issues)

        strategy_id = strategy_record.get("liquidation_strategy_id")
        if isinstance(strategy_id, str):
            if strategy_id in seen_strategy_ids:
                issues.append(
                    ValidationIssue(
                        location=location,
                        field="liquidation_strategy_id",
                        message="must be unique",
                    )
                )
            seen_strategy_ids.add(strategy_id)

        validate_snake_case(strategy_record, "liquidation_strategy_id", location, issues)
        validate_snake_case(strategy_record, "name", location, issues)
        validate_in_allowed(
            strategy_record, "strategy_type", SUPPORTED_STRATEGY_TYPES, location, issues
        )
        validate_json_decimal_string(
            strategy_record, "cash_buffer_use_rate", location, issues, required=False
        )

        if "preserve_minimum_buffer" in strategy_record and not isinstance(
            strategy_record.get("preserve_minimum_buffer"),
            bool,
        ):
            issues.append(
                ValidationIssue(
                    location=location,
                    field="preserve_minimum_buffer",
                    message="must be a boolean",
                )
            )

        if strategy_record.get("strategy_type") == "custom_weights":
            _validate_custom_weights(strategy_record, location, issues)


def _validate_custom_weights(
    strategy_record: Mapping[str, object],
    location: str,
    issues: list[ValidationIssue],
) -> None:
    weights = strategy_record.get("weights")
    if not isinstance(weights, Mapping) or not weights:
        issues.append(
            ValidationIssue(
                location=location, field="weights", message="required for custom_weights"
            )
        )
        return

    total_weight = Decimal("0")
    for asset_group, weight in weights.items():
        if not isinstance(asset_group, str) or asset_group not in SUPPORTED_ASSET_GROUPS:
            issues.append(
                ValidationIssue(
                    location=location,
                    field="weights",
                    message=f"unknown asset group {asset_group!r}",
                )
            )
            continue
        if not isinstance(weight, str):
            issues.append(
                ValidationIssue(
                    location=location,
                    field=f"weights.{asset_group}",
                    message="must be a decimal string",
                )
            )
            continue
        parsed_weight = parse_decimal_string(weight)
        if parsed_weight is None:
            issues.append(
                ValidationIssue(
                    location=location,
                    field=f"weights.{asset_group}",
                    message="must be a decimal string",
                )
            )
            continue
        if parsed_weight < Decimal("0") or parsed_weight > Decimal("1"):
            issues.append(
                ValidationIssue(
                    location=location,
                    field=f"weights.{asset_group}",
                    message="must be between 0 and 1",
                )
            )
            continue
        total_weight += parsed_weight

    if total_weight != Decimal("1"):
        issues.append(ValidationIssue(location=location, field="weights", message="must sum to 1"))
