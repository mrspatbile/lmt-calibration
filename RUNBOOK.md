# RUNBOOK.md

## Environment

Use `uv` for project dependency management.

Create or update the project environment:

```bash
uv sync
```

`uv sync` reads `pyproject.toml` and `uv.lock`, creates `.venv` if needed, and installs the project dependencies.

Do not install project dependencies with `pip` unless there is a specific reason.

## Dependency management

Add runtime dependencies:

```bash
uv add <package>
```

Example:

```bash
uv add pandas
```

Add development dependencies:

```bash
uv add --dev <package>
```

Examples:

```bash
uv add --dev pytest
uv add --dev ruff
uv add --dev mypy
uv add --dev pre-commit
```

## Code quality

Check linting:

```bash
uv run ruff check src tests
```

Auto-fix what Ruff can fix:

```bash
uv run ruff check --fix src tests
```

Check formatting:

```bash
uv run ruff format --check src tests
```

Fix formatting:

```bash
uv run ruff format src tests
```

Type check:

```bash
uv run mypy src
```

## Tests

Run all tests:

```bash
uv run pytest tests/
```

Run tests with coverage:

```bash
uv run pytest tests/ -v --cov=src --cov-report=term-missing
```

## Project checks

Before asking for review, run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest tests/
```

For changes involving methodology, validation, or audit records, also review:

```text
ARCHITECTURE.md
docs/METHODOLOGY.md
docs/DATA_CONVENTIONS.md
docs/AUDIT_TRAIL.md
```

## Pre-commit

Install the Git pre-commit hook once per repository:

```bash
uv run pre-commit install
```

Run all pre-commit hooks manually:

```bash
uv run pre-commit run --all-files
```

The pre-commit hook currently runs:

```text
ruff-check
ruff-format
```

Do not add slow checks such as the full test suite to pre-commit unless there is a clear reason.

## Git workflow

Check current state:

```bash
git status
```

Stage changes:

```bash
git add <file>
```

Commit changes:

```bash
git commit -m "clear commit message"
```

Pre-commit runs automatically before the commit is created.

## Common Ruff errors

* `F401` unused import: remove the import
* `F841` assigned but unused variable: remove the variable
* `I001` import order: run `uv run ruff check --fix src tests`

## Sample data

Sample data for this project should be synthetic but realistic.

Expected sample data files:

```text
data/sample/funds.csv
data/sample/positions.csv
data/sample/investor_classes.csv
data/sample/redemption_scenarios.csv
data/sample/lmt_parameters.csv
data/sample/liquidation_strategies.json
```

Sample data must cover:

* one synthetic fund snapshot
* cash
* listed equities
* listed ETFs
* reverse repo exposure
* repo financing exposure
* retail investors
* institutional investors
* platform investors
* funds of funds
* seed capital
* redemption stress scenarios
* liquidation strategy configuration
* LMT parameter sets

Do not use placeholder names such as `Asset A`, `Entity B`, or `Fund 1`.

<!--
Future sample-data generator command:

```bash
uv run python scripts/generate_sample_data.py
```
-->

<!--
## Streamlit app

Run the local application:

```bash
uv run streamlit run app/streamlit_app.py
```
-->

<!--
## Docker

Build the application image:

```bash
docker build -t lmt-calibration .
```

Run the application container:

```bash
docker run --rm -p 8501:8501 lmt-calibration
```
-->

## Common commands

```bash
uv sync
uv run ruff check src tests
uv run ruff check --fix src tests
uv run ruff format src tests
uv run mypy src
uv run pytest tests/
uv run pre-commit run --all-files
```

## Notes

* `pyproject.toml` defines project dependencies and tool settings.
* `uv.lock` records the exact package versions installed by uv.
* `.venv` contains the project environment.
* `uv run` executes commands inside the project environment.
* `uv add` updates dependencies and the lock file.
* `uv sync` recreates or updates the environment from the lock file.

### Addendum: Register project Jupyter kernel

If `ipykernel` is already installed in the project environment:

uv run python3 -m ipykernel install --user --name lmt-calibration --display-name "lmt-calibration"

If `ipykernel` is not installed:

uv add --dev ipykernel
uv run python3 -m ipykernel install --user --name lmt-calibration --display-name "lmt-calibration"

Then reload VS Code and select the `lmt-calibration` kernel in the notebook picker.

