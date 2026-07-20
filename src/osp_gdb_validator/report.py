"""Finding model and report rendering for osp-gdb-validator."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field


SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1}


@dataclass
class Finding:
    code: str            # e.g. D001
    severity: str        # ERROR | WARNING
    layer: str | None
    field: str | None
    fid: int | None      # feature id, when applicable
    message: str
    suggestion: str | None = None


@dataclass
class Report:
    schema_name: str
    schema_version: str
    gdb_path: str
    findings: list[Finding] = field(default_factory=list)
    layers_checked: int = 0
    features_checked: int = 0

    def add(self, *args, **kwargs) -> None:
        self.findings.append(Finding(*args, **kwargs))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "ERROR"]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == "WARNING"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (SEVERITY_ORDER[f.severity], f.layer or "",
                           f.field or "", f.fid if f.fid is not None else -1))

    def to_json(self) -> str:
        return json.dumps({
            "schema_name": self.schema_name,
            "schema_version": self.schema_version,
            "gdb_path": self.gdb_path,
            "layers_checked": self.layers_checked,
            "features_checked": self.features_checked,
            "passed": self.passed,
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
            "findings": [asdict(f) for f in self.sorted_findings()],
        }, indent=2)

    def to_text(self) -> str:
        lines = []
        lines.append(f"osp-gdb-validator — schema {self.schema_name} "
                     f"v{self.schema_version}")
        lines.append(f"GDB: {self.gdb_path}")
        lines.append(f"Layers checked: {self.layers_checked}   "
                     f"Features checked: {self.features_checked}")
        lines.append("-" * 72)
        if not self.findings:
            lines.append("No findings. Geodatabase conforms to schema.")
        for f in self.sorted_findings():
            loc = f.layer or "<gdb>"
            if f.field:
                loc += f".{f.field}"
            if f.fid is not None:
                loc += f" (FID {f.fid})"
            line = f"[{f.severity:7}] {f.code}  {loc}: {f.message}"
            if f.suggestion:
                line += f"  -> {f.suggestion}"
            lines.append(line)
        lines.append("-" * 72)
        verdict = "PASS" if self.passed else "FAIL"
        lines.append(f"RESULT: {verdict}  "
                     f"({len(self.errors)} errors, {len(self.warnings)} warnings)")
        return "\n".join(lines)
