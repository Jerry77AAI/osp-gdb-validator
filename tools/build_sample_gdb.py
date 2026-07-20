"""Build synthetic FTTx sample geodatabases (clean-room demo data).

Creates two file GDBs with GDAL's OpenFileGDB driver (no Esri license):

  data/fttx_demo_clean.gdb  — conforms to schemas/fttx_demo_schema.yaml
  data/fttx_demo_dirty.gdb  — same network with SEEDED DEFECTS (below)

All coordinates are a fabricated demo grid near 45.00N, 92.00W; every ID,
address, and attribute is invented. See docs/CLEAN_ROOM.md.

Seeded defects in the dirty GDB (each maps to a validator check):
  D001  FiberCable FC-1003 CABLE_TYPE 'AERL' (typo for 'AER')
  D001  FiberCable FC-1004 FIBER_COUNT 47 (not a valid count)
  D001  SpliceClosure SC-2002 STATUS 'ASBILT' (typo for 'ASBUILT')
  D002  StructurePole PL-3003 HEIGHT_FT 150.0 (out of range 20..125)
  R001  ServiceLocation SL-5002 ADDRESS null
  U001  StructurePole PL-3001 duplicated
  F001  UndergroundStructure missing SIZE_CODE field
  F002  SpliceClosure TRAY_CAPACITY created as Real (schema: Integer)
  F004  FiberCable extra field TEMP_NOTE
  L002  extra layer 'RedlineNotes' not in schema
  G001  ServiceLocation SL-5004 has null geometry

Usage:  python tools/build_sample_gdb.py [output_dir]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from osgeo import ogr, osr

ogr.UseExceptions()
osr.UseExceptions()

BASE_LON, BASE_LAT = -92.00, 45.00   # fabricated demo grid
STEP = 0.001                          # ~100 m spacing


def _srs() -> osr.SpatialReference:
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    return srs


def _pt(i: int, row: int = 0):
    g = ogr.Geometry(ogr.wkbPoint)
    g.AddPoint_2D(BASE_LON + i * STEP, BASE_LAT + row * STEP)
    return g


def _line(i: int):
    g = ogr.Geometry(ogr.wkbLineString)
    g.AddPoint_2D(BASE_LON + i * STEP, BASE_LAT)
    g.AddPoint_2D(BASE_LON + (i + 1) * STEP, BASE_LAT)
    return g


FIELD_TYPES = {
    "String": ogr.OFTString,
    "Integer": ogr.OFTInteger,
    "Real": ogr.OFTReal,
    "Date": ogr.OFTDate,
}


def _make_layer(ds, name, geom_type, fields):
    lyr = ds.CreateLayer(name, srs=_srs(), geom_type=geom_type)
    for fname, ftype, width in fields:
        fd = ogr.FieldDefn(fname, FIELD_TYPES[ftype])
        if width:
            fd.SetWidth(width)
        lyr.CreateField(fd)
    return lyr


def _add(lyr, geom, **attrs):
    feat = ogr.Feature(lyr.GetLayerDefn())
    if geom is not None:
        feat.SetGeometry(geom)
    for k, v in attrs.items():
        if v is not None:
            feat.SetField(k, v)
    lyr.CreateFeature(feat)
    feat = None


def build(out_dir: Path, dirty: bool) -> Path:
    name = "fttx_demo_dirty.gdb" if dirty else "fttx_demo_clean.gdb"
    path = out_dir / name
    if path.exists():
        shutil.rmtree(path)

    drv = ogr.GetDriverByName("OpenFileGDB")
    ds = drv.CreateDataSource(str(path))

    # ---- FiberCable -------------------------------------------------
    fields = [("CABLE_ID", "String", 32), ("CABLE_TYPE", "String", 8),
              ("FIBER_COUNT", "Integer", None), ("STATUS", "String", 16),
              ("LENGTH_FT", "Real", None), ("INSTALL_DATE", "Date", None)]
    if dirty:
        fields.append(("TEMP_NOTE", "String", 64))          # F004
    lyr = _make_layer(ds, "FiberCable", ogr.wkbLineString, fields)
    cables = [
        ("FC-1001", "AER", 144, "ASBUILT", 328.0, "2026-05-11"),
        ("FC-1002", "UND", 288, "CONST", 512.5, None),
        ("FC-1003", "AERL" if dirty else "AER", 48, "PLAN", 297.0, None),   # D001
        ("FC-1004", "BUR", 47 if dirty else 48, "PERM", 1204.0, None),      # D001
        ("FC-1005", "AER", 24, "ASBUILT", 260.3, "2026-06-02"),
        ("FC-1006", "UND", 96, "CONST", 845.9, None),
    ]
    for i, (cid, ctype, cnt, status, ln, dt) in enumerate(cables):
        _add(lyr, _line(i), CABLE_ID=cid, CABLE_TYPE=ctype, FIBER_COUNT=cnt,
             STATUS=status, LENGTH_FT=ln, INSTALL_DATE=dt,
             **({"TEMP_NOTE": "wip"} if dirty else {}))

    # ---- SpliceClosure ----------------------------------------------
    tray_type = "Real" if dirty else "Integer"              # F002
    lyr = _make_layer(ds, "SpliceClosure", ogr.wkbPoint,
                      [("CLOSURE_ID", "String", 32),
                       ("CLOSURE_TYPE", "String", 8),
                       ("STATUS", "String", 16),
                       ("TRAY_CAPACITY", tray_type, None)])
    closures = [
        ("SC-2001", "AER", "ASBUILT", 12),
        ("SC-2002", "PED", "ASBILT" if dirty else "ASBUILT", 24),  # D001
        ("SC-2003", "VLT", "CONST", 12),
        ("SC-2004", "AER", "PLAN", None),
    ]
    for i, (cid, ctype, status, cap) in enumerate(closures):
        _add(lyr, _pt(i, row=1), CLOSURE_ID=cid, CLOSURE_TYPE=ctype,
             STATUS=status, TRAY_CAPACITY=cap)

    # ---- StructurePole ----------------------------------------------
    lyr = _make_layer(ds, "StructurePole", ogr.wkbPoint,
                      [("POLE_ID", "String", 32), ("OWNER", "String", 64),
                       ("POLE_CLASS", "Integer", None),
                       ("HEIGHT_FT", "Real", None),
                       ("MR_STATUS", "String", 8)])
    poles = [
        ("PL-3001", "Demo Power Co-op", 4, 40.0, "COMP"),
        ("PL-3002", "Demo Power Co-op", 3, 45.0, "REQ"),
        ("PL-3003", "Demo Telephone Co", 5,
         150.0 if dirty else 35.0, "NA"),                   # D002
        ("PL-3004", "Demo Power Co-op", 4, 40.0, "COMP"),
    ]
    if dirty:
        poles.append(("PL-3001", "Demo Power Co-op", 4, 40.0, "COMP"))  # U001
    for i, (pid, owner, pclass, h, mr) in enumerate(poles):
        _add(lyr, _pt(i, row=2), POLE_ID=pid, OWNER=owner, POLE_CLASS=pclass,
             HEIGHT_FT=h, MR_STATUS=mr)

    # ---- UndergroundStructure ---------------------------------------
    ug_fields = [("STRUCT_ID", "String", 32), ("STRUCT_TYPE", "String", 8)]
    if not dirty:
        ug_fields.append(("SIZE_CODE", "String", 16))       # F001 when absent
    lyr = _make_layer(ds, "UndergroundStructure", ogr.wkbPoint, ug_fields)
    structs = [("US-4001", "HH", "24x36"), ("US-4002", "VLT", "48x48"),
               ("US-4003", "MH", "60x60")]
    for i, (sid, stype, size) in enumerate(structs):
        attrs = {"STRUCT_ID": sid, "STRUCT_TYPE": stype}
        if not dirty:
            attrs["SIZE_CODE"] = size
        _add(lyr, _pt(i, row=3), **attrs)

    # ---- ServiceLocation --------------------------------------------
    lyr = _make_layer(ds, "ServiceLocation", ogr.wkbPoint,
                      [("LOC_ID", "String", 32), ("ADDRESS", "String", 128),
                       ("SERV_STATUS", "String", 16),
                       ("DROP_TYPE", "String", 8)])
    locs = [
        ("SL-5001", "101 Demo Grid Rd", "CONNECTED", "AER"),
        ("SL-5002", None if dirty else "103 Demo Grid Rd",
         "DROPPED", "AER"),                                 # R001
        ("SL-5003", "105 Demo Grid Rd", "PLANNED", None),
        ("SL-5004", "107 Demo Grid Rd", "PLANNED", "UND"),  # G001 (null geom)
    ]
    for i, (lid, addr, status, drop) in enumerate(locs):
        geom = None if (dirty and lid == "SL-5004") else _pt(i, row=4)
        _add(lyr, geom, LOC_ID=lid, ADDRESS=addr, SERV_STATUS=status,
             DROP_TYPE=drop)

    # ---- Extra layer (dirty only) -----------------------------------
    if dirty:                                               # L002
        lyr = _make_layer(ds, "RedlineNotes", ogr.wkbPoint,
                          [("NOTE", "String", 64)])
        _add(lyr, _pt(0, row=5), NOTE="field redline — resolve before asbuilt")

    ds = None
    return path


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    out_dir.mkdir(parents=True, exist_ok=True)
    clean = build(out_dir, dirty=False)
    dirty = build(out_dir, dirty=True)
    print(f"built: {clean}")
    print(f"built: {dirty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
