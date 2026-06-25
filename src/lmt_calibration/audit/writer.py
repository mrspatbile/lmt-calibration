"""Audit record writers."""

import json
from pathlib import Path

from lmt_calibration.audit.records import ScenarioAuditRecord


class JsonAuditWriter:
    """Write scenario audit records as JSON files."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def write(self, record: ScenarioAuditRecord) -> Path:
        """Write an audit record and return the generated path."""

        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / f"{record.metadata.run_id}_audit.json"
        output_path.write_text(
            json.dumps(record.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
        return output_path
