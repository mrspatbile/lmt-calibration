"""CSV loaders for V1 sample input files."""

import csv
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

from lmt_calibration.domain import (
    AssetPosition,
    FundSnapshot,
    InvestorClassProfile,
    LiquidityStress,
    LmtParameters,
    MarketStress,
    RedemptionScenario,
    ScenarioDefinition,
)
from lmt_calibration.validation import (
    DataValidationError,
    ValidationIssue,
    validate_fund_records,
    validate_investor_class_records,
    validate_liquidity_stress_records,
    validate_lmt_parameter_records,
    validate_market_stress_records,
    validate_position_records,
    validate_redemption_scenario_records,
    validate_scenario_definition_records,
)

RecordValidator = Callable[[object], list[dict[str, object]]]


def load_funds_csv(path: Path) -> list[FundSnapshot]:
    """Load validated fund snapshots from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="funds",
        validator=validate_fund_records,
        integer_fields={"redemption_notice_days", "redemption_settlement_days"},
    )
    return [FundSnapshot.model_validate(record) for record in records]


def load_positions_csv(path: Path) -> list[AssetPosition]:
    """Load validated asset positions from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="positions",
        validator=validate_position_records,
        integer_fields={"settlement_days", "maturity_days"},
    )
    return [AssetPosition.model_validate(record) for record in records]


def load_investor_classes_csv(path: Path) -> list[InvestorClassProfile]:
    """Load validated investor class profiles from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="investor_classes",
        validator=validate_investor_class_records,
        integer_fields={"notice_days", "settlement_days"},
    )
    return [InvestorClassProfile.model_validate(record) for record in records]


def load_redemption_scenarios_csv(path: Path) -> list[RedemptionScenario]:
    """Load validated reusable redemption scenarios from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="redemption_scenarios",
        validator=validate_redemption_scenario_records,
        integer_fields=set(),
    )
    return [RedemptionScenario.model_validate(record) for record in records]


def load_market_stresses_csv(path: Path) -> list[MarketStress]:
    """Load validated reusable market stresses from a CSV file."""

    records = _read_csv_records(path)
    _normalize_blank_cells(records)
    _convert_decimal_fields(
        records,
        "market_stresses",
        {
            "market_shock_rate",
            "bid_ask_spread_rate",
            "transaction_cost_rate",
            "market_impact_rate",
            "participation_rate",
            "liquidity_haircut_rate",
        },
    )
    records = validate_market_stress_records(records)
    return [MarketStress.model_validate(record) for record in records]


def load_liquidity_stresses_csv(path: Path) -> list[LiquidityStress]:
    """Load validated reusable liquidity stresses from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="liquidity_stresses",
        validator=validate_liquidity_stress_records,
        integer_fields={"stress_horizon_days"},
    )
    return [LiquidityStress.model_validate(record) for record in records]


def load_scenario_definitions_csv(path: Path) -> list[ScenarioDefinition]:
    """Load validated scenario definitions from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="scenario_definitions",
        validator=validate_scenario_definition_records,
        integer_fields=set(),
    )
    return [ScenarioDefinition.model_validate(record) for record in records]


def load_lmt_parameters_csv(path: Path) -> list[LmtParameters]:
    """Load validated LMT parameter sets from a CSV file."""

    records = _load_validated_csv(
        path,
        dataset_name="lmt_parameters",
        validator=validate_lmt_parameter_records,
        integer_fields=set(),
    )
    return [LmtParameters.model_validate(record) for record in records]


def _load_validated_csv(
    path: Path,
    *,
    dataset_name: str,
    validator: RecordValidator,
    integer_fields: set[str],
) -> list[dict[str, object]]:
    records = _read_csv_records(path)
    _normalize_blank_cells(records)
    _convert_integer_fields(records, dataset_name, integer_fields)
    return validator(records)


def _read_csv_records(path: Path) -> list[dict[str, object]]:
    try:
        with path.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file, strict=True)
            records = [dict(row) for row in reader]
    except FileNotFoundError as error:
        raise _file_validation_error(path, "file not found") from error
    except PermissionError as error:
        raise _file_validation_error(path, "file is not readable") from error
    except UnicodeDecodeError as error:
        raise _file_validation_error(path, "file is not valid UTF-8") from error
    except csv.Error as error:
        raise _file_validation_error(path, f"malformed CSV: {error}") from error
    except OSError as error:
        raise _file_validation_error(path, f"could not read file: {error}") from error

    for index, record in enumerate(records):
        if None in record:
            raise DataValidationError(
                [
                    ValidationIssue(
                        location=f"{path}[{index}]",
                        field="file",
                        message="malformed CSV: row has more fields than headers",
                    )
                ]
            )

    return records


def _normalize_blank_cells(records: list[dict[str, object]]) -> None:
    for record in records:
        for field_name, value in record.items():
            if value == "":
                record[field_name] = None


def _convert_integer_fields(
    records: list[dict[str, object]],
    dataset_name: str,
    integer_fields: set[str],
) -> None:
    issues: list[ValidationIssue] = []
    for index, record in enumerate(records):
        for field_name in sorted(integer_fields):
            value = record.get(field_name)
            if value is None or value == "":
                continue
            if isinstance(value, int):
                continue
            if isinstance(value, str):
                try:
                    record[field_name] = int(value)
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            location=f"{dataset_name}[{index}]",
                            field=field_name,
                            message="must be integer",
                        )
                    )
                continue
            issues.append(
                ValidationIssue(
                    location=f"{dataset_name}[{index}]",
                    field=field_name,
                    message="must be integer",
                )
            )

    if issues:
        raise DataValidationError(issues)


def _convert_decimal_fields(
    records: list[dict[str, object]],
    dataset_name: str,
    decimal_fields: set[str],
) -> None:
    issues: list[ValidationIssue] = []
    for index, record in enumerate(records):
        for field_name in sorted(decimal_fields):
            value = record.get(field_name)
            if value is None or value == "":
                continue
            if isinstance(value, Decimal):
                continue
            if isinstance(value, str):
                try:
                    record[field_name] = Decimal(value)
                except Exception:
                    issues.append(
                        ValidationIssue(
                            location=f"{dataset_name}[{index}]",
                            field=field_name,
                            message="must be decimal",
                        )
                    )
                continue
            issues.append(
                ValidationIssue(
                    location=f"{dataset_name}[{index}]",
                    field=field_name,
                    message="must be decimal",
                )
            )

    if issues:
        raise DataValidationError(issues)


def _file_validation_error(path: Path, reason: str) -> DataValidationError:
    return DataValidationError([ValidationIssue(location=str(path), field="file", message=reason)])
