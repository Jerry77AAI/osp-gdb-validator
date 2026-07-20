"""Schema definition loading for osp-gdb-validator.

A schema is a YAML document declaring the expected shape of a file
geodatabase: layers (feature classes), fields, and attribute domains.
See schemas/fttx_demo_schema.yaml for the reference format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_FIELD_TYPES = {"String", "Integer", "Real", "Date"}
VALID_GEOMETRIES = {"Point", "LineString", "Polygon", "MultiPoint",
                    "MultiLineString", "MultiPolygon"}


class SchemaError(ValueError):
    """Raised when a schema document is malformed."""


@dataclass
class Domain:
    name: str
    kind: str                       # "coded" | "range"
    field_type: str                 # String | Integer | Real
    codes: dict = field(default_factory=dict)   # coded: {code: description}
    min: float | None = None        # range
    max: float | None = None        # range


@dataclass
class FieldSpec:
    name: str
    type: str
    length: int | None = None
    required: bool = False
    unique: bool = False
    domain: str | None = None


@dataclass
class LayerSpec:
    name: str
    geometry: str
    fields: list[FieldSpec] = field(default_factory=list)

    def field_by_name(self, name: str) -> FieldSpec | None:
        for f in self.fields:
            if f.name == name:
                return f
        return None


@dataclass
class Schema:
    schema_name: str
    version: str
    crs: str | None
    domains: dict[str, Domain]
    layers: dict[str, LayerSpec]


def load_schema(path: str | Path) -> Schema:
    """Load and structurally validate a schema YAML file."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict):
        raise SchemaError(f"{path}: schema root must be a mapping")

    for key in ("schema_name", "version", "layers"):
        if key not in raw:
            raise SchemaError(f"{path}: missing required key '{key}'")

    domains: dict[str, Domain] = {}
    for dname, d in (raw.get("domains") or {}).items():
        kind = d.get("kind")
        if kind not in ("coded", "range"):
            raise SchemaError(f"domain '{dname}': kind must be coded|range")
        ftype = d.get("field_type", "String")
        if ftype not in VALID_FIELD_TYPES:
            raise SchemaError(f"domain '{dname}': bad field_type '{ftype}'")
        if kind == "coded":
            codes = d.get("codes")
            if not isinstance(codes, dict) or not codes:
                raise SchemaError(f"domain '{dname}': coded domain needs codes")
            domains[dname] = Domain(dname, kind, ftype, codes=codes)
        else:
            if d.get("min") is None or d.get("max") is None:
                raise SchemaError(f"domain '{dname}': range domain needs min+max")
            domains[dname] = Domain(dname, kind, ftype,
                                    min=float(d["min"]), max=float(d["max"]))

    layers: dict[str, LayerSpec] = {}
    for lname, l in raw["layers"].items():
        geom = l.get("geometry")
        if geom not in VALID_GEOMETRIES:
            raise SchemaError(f"layer '{lname}': bad geometry '{geom}'")
        fields = []
        for f in l.get("fields", []):
            if "name" not in f or "type" not in f:
                raise SchemaError(f"layer '{lname}': field needs name+type: {f}")
            if f["type"] not in VALID_FIELD_TYPES:
                raise SchemaError(
                    f"layer '{lname}.{f['name']}': bad type '{f['type']}'")
            dom = f.get("domain")
            if dom is not None and dom not in domains:
                raise SchemaError(
                    f"layer '{lname}.{f['name']}': unknown domain '{dom}'")
            fields.append(FieldSpec(
                name=f["name"], type=f["type"], length=f.get("length"),
                required=bool(f.get("required", False)),
                unique=bool(f.get("unique", False)), domain=dom))
        layers[lname] = LayerSpec(name=lname, geometry=geom, fields=fields)

    return Schema(
        schema_name=raw["schema_name"],
        version=str(raw["version"]),
        crs=raw.get("crs"),
        domains=domains,
        layers=layers,
    )
