"""Core validation engine: file geodatabase vs schema definition.

Check codes
-----------
L001  expected layer missing from GDB                     ERROR
L002  unexpected layer present in GDB                     WARNING
L003  layer geometry type mismatch                        ERROR
L004  layer CRS mismatch                                  ERROR
F001  expected field missing from layer                   ERROR
F002  field data type mismatch                            ERROR
F003  string field width differs from schema              WARNING
F004  unexpected field present in layer                   WARNING
R001  required field is null/empty                        ERROR
U001  duplicate value in unique field                     ERROR
D001  value not in coded domain (typo detection)          ERROR
D002  numeric value outside range domain                  ERROR
G001  feature has missing/empty geometry                  ERROR

The full check list above is enumerated in CHECKS; the engine iterates the
schema, never a hand-maintained subset (acceptance-gate discipline).
"""

from __future__ import annotations

import difflib
from collections import defaultdict
from pathlib import Path

from osgeo import ogr, osr

from .report import Report
from .schema import Schema, load_schema

ogr.UseExceptions()
osr.UseExceptions()

CHECKS = {
    "L001": "expected layer missing",
    "L002": "unexpected layer present",
    "L003": "geometry type mismatch",
    "L004": "layer CRS mismatch",
    "F001": "expected field missing",
    "F002": "field type mismatch",
    "F003": "string width differs",
    "F004": "unexpected field present",
    "R001": "required field null/empty",
    "U001": "duplicate unique value",
    "D001": "value not in coded domain",
    "D002": "value outside range domain",
    "G001": "missing/empty geometry",
}

# OGR field type -> schema type
_OGR_TYPE_MAP = {
    ogr.OFTString: "String",
    ogr.OFTInteger: "Integer",
    ogr.OFTInteger64: "Integer",
    ogr.OFTReal: "Real",
    ogr.OFTDate: "Date",
    ogr.OFTDateTime: "Date",
}

# Internal layers OpenFileGDB may expose that are never schema targets
_SYSTEM_LAYER_PREFIXES = ("GDB_", "T_1_")


def _flatten_geom_name(gtype: int) -> str:
    name = ogr.GeometryTypeToName(ogr.GT_Flatten(gtype))
    return name.replace(" ", "").replace("3D", "")


def _geom_matches(expected: str, actual: int) -> bool:
    """FileGDB promotes Line->MultiLineString and Polygon->MultiPolygon;
    accept the Multi* form of the declared type."""
    actual_name = _flatten_geom_name(actual)
    if actual_name.lower() == expected.lower():
        return True
    return actual_name.lower() == f"multi{expected}".lower()


def _crs_id(srs: osr.SpatialReference | None) -> str | None:
    if srs is None:
        return None
    auth = srs.GetAuthorityName(None)
    code = srs.GetAuthorityCode(None)
    if auth and code:
        return f"{auth}:{code}"
    return srs.GetName()


def _is_empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _suggest(value: str, codes) -> str | None:
    matches = difflib.get_close_matches(
        str(value).upper(), [str(c).upper() for c in codes], n=1, cutoff=0.6)
    if matches:
        return f"did you mean '{matches[0]}'?"
    return None


def validate(gdb_path: str | Path, schema: Schema | str | Path) -> Report:
    """Validate a file geodatabase against a schema definition."""
    if not isinstance(schema, Schema):
        schema = load_schema(schema)

    gdb_path = str(gdb_path)
    ds = ogr.Open(gdb_path, 0)
    if ds is None:
        raise IOError(f"Cannot open geodatabase: {gdb_path}")

    report = Report(schema_name=schema.schema_name,
                    schema_version=schema.version, gdb_path=gdb_path)

    present = {}
    for i in range(ds.GetLayerCount()):
        lyr = ds.GetLayerByIndex(i)
        name = lyr.GetName()
        if name.startswith(_SYSTEM_LAYER_PREFIXES):
            continue
        present[name] = lyr

    # L002 — unexpected layers
    for name in present:
        if name not in schema.layers:
            report.add("L002", "WARNING", name, None, None,
                       "layer present in GDB but not in schema")

    for lname, lspec in schema.layers.items():
        # L001 — missing layer
        if lname not in present:
            report.add("L001", "ERROR", lname, None, None,
                       "expected layer missing from GDB")
            continue

        lyr = present[lname]
        report.layers_checked += 1
        defn = lyr.GetLayerDefn()

        # L003 — geometry type
        if not _geom_matches(lspec.geometry, defn.GetGeomType()):
            report.add("L003", "ERROR", lname, None, None,
                       f"geometry is {_flatten_geom_name(defn.GetGeomType())}, "
                       f"schema expects {lspec.geometry}")

        # L004 — CRS
        if schema.crs:
            actual_crs = _crs_id(lyr.GetSpatialRef())
            if actual_crs != schema.crs:
                report.add("L004", "ERROR", lname, None, None,
                           f"CRS is {actual_crs or 'undefined'}, "
                           f"schema expects {schema.crs}")

        # Field-level structure
        gdb_fields = {}
        for i in range(defn.GetFieldCount()):
            fd = defn.GetFieldDefn(i)
            gdb_fields[fd.GetName()] = fd

        for fspec in lspec.fields:
            if fspec.name not in gdb_fields:
                report.add("F001", "ERROR", lname, fspec.name, None,
                           "expected field missing from layer")
                continue
            fd = gdb_fields[fspec.name]
            actual_type = _OGR_TYPE_MAP.get(fd.GetType(), f"OGR:{fd.GetType()}")
            if actual_type != fspec.type:
                report.add("F002", "ERROR", lname, fspec.name, None,
                           f"type is {actual_type}, schema expects {fspec.type}")
            elif fspec.type == "String" and fspec.length:
                width = fd.GetWidth()
                if width and width != fspec.length:
                    report.add("F003", "WARNING", lname, fspec.name, None,
                               f"width is {width}, schema declares {fspec.length}")

        expected_names = {f.name for f in lspec.fields}
        for name in gdb_fields:
            if name not in expected_names and name.upper() not in (
                    "OBJECTID", "SHAPE_LENGTH", "SHAPE_AREA"):
                report.add("F004", "WARNING", lname, name, None,
                           "field present in layer but not in schema")

        # Feature-level checks
        checkable = [f for f in lspec.fields if f.name in gdb_fields]
        unique_seen: dict[str, dict] = defaultdict(dict)

        lyr.ResetReading()
        for feat in lyr:
            fid = feat.GetFID()
            report.features_checked += 1

            # G001 — geometry present
            geom = feat.GetGeometryRef()
            if geom is None or geom.IsEmpty():
                report.add("G001", "ERROR", lname, None, fid,
                           "feature has missing or empty geometry")

            for fspec in checkable:
                idx = feat.GetFieldIndex(fspec.name)
                is_set = feat.IsFieldSetAndNotNull(idx)
                value = feat.GetField(idx) if is_set else None

                # R001 — required
                if fspec.required and _is_empty(value):
                    report.add("R001", "ERROR", lname, fspec.name, fid,
                               "required field is null/empty")
                    continue
                if _is_empty(value):
                    continue

                # U001 — unique
                if fspec.unique:
                    if value in unique_seen[fspec.name]:
                        first = unique_seen[fspec.name][value]
                        report.add("U001", "ERROR", lname, fspec.name, fid,
                                   f"duplicate value '{value}' "
                                   f"(first seen at FID {first})")
                    else:
                        unique_seen[fspec.name][value] = fid

                # D001/D002 — domains
                if fspec.domain:
                    dom = schema.domains[fspec.domain]
                    if dom.kind == "coded":
                        codes = dom.codes
                        if dom.field_type in ("Integer", "Real"):
                            ok = any(_num_eq(value, c) for c in codes)
                        else:
                            ok = str(value) in {str(c) for c in codes}
                        if not ok:
                            suggestion = None
                            if dom.field_type == "String":
                                suggestion = _suggest(value, codes)
                            report.add(
                                "D001", "ERROR", lname, fspec.name, fid,
                                f"value '{value}' not in domain "
                                f"{fspec.domain} {sorted(map(str, codes))}",
                                suggestion=suggestion)
                    else:  # range
                        try:
                            num = float(value)
                        except (TypeError, ValueError):
                            num = None
                        if num is None or num < dom.min or num > dom.max:
                            report.add(
                                "D002", "ERROR", lname, fspec.name, fid,
                                f"value '{value}' outside range domain "
                                f"{fspec.domain} [{dom.min}..{dom.max}]")

    ds = None
    return report


def _num_eq(value, code) -> bool:
    try:
        return float(value) == float(code)
    except (TypeError, ValueError):
        return False
