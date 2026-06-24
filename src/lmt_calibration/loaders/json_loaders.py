"""JSON loaders for V1 sample configuration files."""

import json
from pathlib import Path

from lmt_calibration.domain import LiquidationStrategyConfig
from lmt_calibration.validation import (
    DataValidationError,
    ValidationIssue,
    validate_liquidation_strategy_config,
)


def load_liquidation_strategies_json(path: Path) -> list[LiquidationStrategyConfig]:
    """Load validated liquidation strategy configurations from JSON."""

    config = _read_json_config(path)
    validated_config = validate_liquidation_strategy_config(config)
    strategies = validated_config["strategies"]
    if not isinstance(strategies, list):
        raise DataValidationError(
            [
                ValidationIssue(
                    location=str(path),
                    field="strategies",
                    message="must be a list",
                )
            ]
        )
    return [LiquidationStrategyConfig.model_validate(strategy) for strategy in strategies]


def _read_json_config(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8") as file:
            config = json.load(file)
    except FileNotFoundError as error:
        raise _file_validation_error(path, "file not found") from error
    except PermissionError as error:
        raise _file_validation_error(path, "file is not readable") from error
    except UnicodeDecodeError as error:
        raise _file_validation_error(path, "file is not valid UTF-8") from error
    except json.JSONDecodeError as error:
        raise _file_validation_error(path, f"malformed JSON: {error.msg}") from error
    except OSError as error:
        raise _file_validation_error(path, f"could not read file: {error}") from error

    if not isinstance(config, dict):
        raise DataValidationError(
            [
                ValidationIssue(
                    location=str(path),
                    field="file",
                    message="JSON root must be an object",
                )
            ]
        )
    return config


def _file_validation_error(path: Path, reason: str) -> DataValidationError:
    return DataValidationError([ValidationIssue(location=str(path), field="file", message=reason)])
