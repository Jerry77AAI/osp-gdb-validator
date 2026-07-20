# osp-gdb-validator

**Schema QC for OSP / FTTx file geodatabases — no Esri license required.**

Reads an Esri file geodatabase with GDAL's open-source OpenFileGDB driver and
validates it against a YAML schema definition: layers, geometry types, CRS,
fields, data types, coded and range domains, required values, unique IDs —
with fuzzy typo detection that tells you `'AERL'` probably means `'AER'`.

Built by Jerry Stevens (Director Engineering · AI Engineer · OSP Veteran, 30
years of outside-plant design and construction) with Claude as AI engineering
partner. First artifact in a series of clean-room OSP automation skills —
see [docs/CLEAN_ROOM.md](docs/CLEAN_ROOM.md) for the provenance statement,
written before the first line of code.

## Why

In OSP engineering, the geodatabase *is* the design. A misspelled domain code,
a duplicated pole ID, or a cable attributed with a fiber count that doesn't
exist will surface later as make-ready rework, failed AGOL syncs, rejected
permits, or construction billed against the wrong units. Attribute QC is
tedious, unambiguous, and rule-driven — exactly the work that should be
automated so engineers review findings instead of hunting for them.

Deterministic Python does the checking; nothing here needs an LLM or an
ArcGIS license to run. That makes it free to run on every commit.

## Quick start

```bash
# GDAL bindings from your platform (Ubuntu shown; conda/OSGeo4W also work)
sudo apt-get install -y gdal-bin python3-gdal python3-yaml

# Build the synthetic FTTx demo geodatabases (clean + dirty)
python3 tools/build_sample_gdb.py data

# Validate
PYTHONPATH=src python3 -m osp_gdb_validator.cli \
    data/fttx_demo_dirty.gdb -s schemas/fttx_demo_schema.yaml
```

Output for the intentionally-broken demo GDB:

```
osp-gdb-validator — schema FTTx_Demo v1.0.0
GDB: data/fttx_demo_dirty.gdb
Layers checked: 5   Features checked: 22
------------------------------------------------------------------------
[ERROR  ] D001  FiberCable.CABLE_TYPE (FID 3): value 'AERL' not in domain CableType ['AER', 'BUR', 'UND']  -> did you mean 'AER'?
[ERROR  ] D001  FiberCable.FIBER_COUNT (FID 4): value '47' not in domain FiberCount ['12', '144', '24', '288', '48', '96']
[ERROR  ] G001  ServiceLocation (FID 4): feature has missing or empty geometry
[ERROR  ] R001  ServiceLocation.ADDRESS (FID 2): required field is null/empty
[ERROR  ] D001  SpliceClosure.STATUS (FID 2): value 'ASBILT' not in domain ConstructionStatus ['ASBUILT', 'CONST', 'PERM', 'PLAN']  -> did you mean 'ASBUILT'?
[ERROR  ] F002  SpliceClosure.TRAY_CAPACITY: type is Real, schema expects Integer
[ERROR  ] D002  StructurePole.HEIGHT_FT (FID 3): value '150.0' outside range domain PoleHeightFt [20.0..125.0]
[ERROR  ] U001  StructurePole.POLE_ID (FID 5): duplicate value 'PL-3001' (first seen at FID 1)
[ERROR  ] F001  UndergroundStructure.SIZE_CODE: expected field missing from layer
[WARNING] F004  FiberCable.TEMP_NOTE: field present in layer but not in schema
[WARNING] L002  RedlineNotes: layer present in GDB but not in schema
------------------------------------------------------------------------
RESULT: FAIL  (9 errors, 2 warnings)
```

Exit code 0 on PASS, 1 on FAIL — drop it straight into CI or a pre-submit
hook. `--json report.json` writes the full machine-readable report.

## Checks

| Code | Severity | Check |
|------|----------|-------|
| L001 | ERROR | expected layer missing from GDB |
| L002 | WARNING | unexpected layer present |
| L003 | ERROR | geometry type mismatch |
| L004 | ERROR | layer CRS mismatch |
| F001 | ERROR | expected field missing |
| F002 | ERROR | field data type mismatch |
| F003 | WARNING | string field width differs |
| F004 | WARNING | unexpected field present |
| R001 | ERROR | required field null/empty |
| U001 | ERROR | duplicate value in unique field |
| D001 | ERROR | value not in coded domain (+ typo suggestion) |
| D002 | ERROR | numeric value outside range domain |
| G001 | ERROR | missing/empty geometry |

## Schema definition format

Schemas are plain YAML — versionable, diffable, reviewable in a PR:

```yaml
schema_name: FTTx_Demo
version: "1.0.0"
crs: "EPSG:4326"

domains:
  CableType:
    kind: coded
    field_type: String
    codes: {AER: Aerial, UND: Underground (conduit), BUR: Direct buried}
  PoleHeightFt:
    kind: range
    field_type: Real
    min: 20
    max: 125

layers:
  FiberCable:
    geometry: LineString
    fields:
      - {name: CABLE_ID, type: String, length: 32, required: true, unique: true}
      - {name: CABLE_TYPE, type: String, length: 8, required: true, domain: CableType}
```

The bundled [`schemas/fttx_demo_schema.yaml`](schemas/fttx_demo_schema.yaml)
models a small FTTx network: fiber cables, splice closures, poles (with
make-ready status), underground structures, and service locations. To QC your
own geodatabase, write a schema that mirrors your organization's data
dictionary and point the CLI at it.

## Python API

```python
from osp_gdb_validator import validate

report = validate("my_design.gdb", "my_schema.yaml")
print(report.to_text())
if not report.passed:
    for f in report.errors:
        print(f.code, f.layer, f.field, f.message)
```

## Sample data

`tools/build_sample_gdb.py` generates two synthetic geodatabases: a clean one
that passes, and a dirty one with 11 seeded defects covering the check matrix
above. Every ID, address, coordinate, and attribute is fabricated (see
[docs/CLEAN_ROOM.md](docs/CLEAN_ROOM.md)). The test suite asserts that every
seeded defect is detected and that the clean GDB yields zero false positives.

## Roadmap

This is skill 1 of a planned series of OSP fiber design/construction
automations: schema comparison against ArcGIS Online feature services, BOM
generation from validated GDBs, permit drawing prep, and splice schematic
generation. Same principles throughout: deterministic Python core,
license-free where possible, clean-room data, CI-proven.

## License

MIT — see [LICENSE](LICENSE).
