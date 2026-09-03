from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Evidence:
    kind: str
    path: str
    line: int | None
    anchor: str
    strength: str = "static"


@dataclass
class Parameter:
    name: str
    accessors: list[str] = field(default_factory=list)
    defaults: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Route:
    route_id: str
    scheme: str | None
    host: str
    path: str
    handler: str | None = None
    visibility: str | None = None
    capability: str = "unknown"
    parameters: dict[str, Parameter] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    source: str = "annotation"
    confidence: str = "static-confirmed"

    @property
    def template(self) -> str | None:
        if not self.scheme:
            return None
        suffix = f"/{self.path}" if self.path else ""
        return f"{self.scheme}://{self.host}{suffix}"


@dataclass
class DynamicTest:
    platform: str
    url: str
    outcome: str
    observed: dict[str, str]
    notes: str = ""
    tested_at: str = ""


@dataclass
class AppReport:
    query_name: str
    app_name: str | None = None
    platform: str | None = None
    package_id: str | None = None
    version_name: str | None = None
    version_code: str | None = None
    artifact_path: str | None = None
    artifact_sha256: str | None = None
    schemes: list[str] = field(default_factory=list)
    routes: list[Route] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    dynamic_tests: list[DynamicTest] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

