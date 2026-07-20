"""End-to-end tests: build synthetic GDBs, validate, assert every check fires.

Self-check contract (written before the implementation was accepted):
  correct IF: clean GDB -> PASS with zero findings;
              dirty GDB -> FAIL and EVERY seeded defect code is flagged
              at the expected layer/field;
  wrong IF:   any seeded defect goes undetected, or the clean GDB
              produces any finding (false positive).
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from osp_gdb_validator import load_schema, validate, CHECKS  # noqa: E402
import build_sample_gdb  # noqa: E402

SCHEMA = REPO / "schemas" / "fttx_demo_schema.yaml"


@pytest.fixture(scope="session")
def gdbs(tmp_path_factory):
    out = tmp_path_factory.mktemp("data")
    clean = build_sample_gdb.build(out, dirty=False)
    dirty = build_sample_gdb.build(out, dirty=True)
    return clean, dirty


def test_schema_loads():
    schema = load_schema(SCHEMA)
    assert schema.schema_name == "FTTx_Demo"
    assert len(schema.layers) == 5
    assert "CableType" in schema.domains


def test_clean_gdb_passes(gdbs):
    clean, _ = gdbs
    report = validate(clean, SCHEMA)
    assert report.passed, report.to_text()
    assert report.findings == [], "clean GDB must produce zero findings"
    assert report.layers_checked == 5
    assert report.features_checked > 0


# (code, layer, field) triples that MUST be present for the dirty GDB.
EXPECTED_DIRTY = [
    ("D001", "FiberCable", "CABLE_TYPE"),
    ("D001", "FiberCable", "FIBER_COUNT"),
    ("D001", "SpliceClosure", "STATUS"),
    ("D002", "StructurePole", "HEIGHT_FT"),
    ("R001", "ServiceLocation", "ADDRESS"),
    ("U001", "StructurePole", "POLE_ID"),
    ("F001", "UndergroundStructure", "SIZE_CODE"),
    ("F002", "SpliceClosure", "TRAY_CAPACITY"),
    ("F004", "FiberCable", "TEMP_NOTE"),
    ("L002", "RedlineNotes", None),
    ("G001", "ServiceLocation", None),
]


def test_dirty_gdb_fails(gdbs):
    _, dirty = gdbs
    report = validate(dirty, SCHEMA)
    assert not report.passed


@pytest.mark.parametrize("code,layer,field", EXPECTED_DIRTY)
def test_every_seeded_defect_detected(gdbs, code, layer, field):
    _, dirty = gdbs
    report = validate(dirty, SCHEMA)
    hits = [f for f in report.findings
            if f.code == code and f.layer == layer and f.field == field]
    assert hits, (f"seeded defect not detected: {code} on "
                  f"{layer}.{field or '<layer>'}\n{report.to_text()}")


def test_no_unexpected_error_codes(gdbs):
    """Every finding on the dirty GDB must correspond to a seeded defect."""
    _, dirty = gdbs
    report = validate(dirty, SCHEMA)
    expected = {(c, l, f) for c, l, f in EXPECTED_DIRTY}
    actual = {(f.code, f.layer, f.field) for f in report.findings}
    assert actual == expected, f"unexpected findings: {actual - expected}"


def test_typo_suggestion_present(gdbs):
    _, dirty = gdbs
    report = validate(dirty, SCHEMA)
    typo = [f for f in report.findings
            if f.code == "D001" and f.field == "CABLE_TYPE"][0]
    assert typo.suggestion and "AER" in typo.suggestion


def test_all_documented_checks_have_codes():
    assert set(CHECKS) == {"L001", "L002", "L003", "L004", "F001", "F002",
                           "F003", "F004", "R001", "U001", "D001", "D002",
                           "G001"}


def test_cli_exit_codes(gdbs, tmp_path):
    clean, dirty = gdbs
    env_path = f"{REPO / 'src'}"
    r = subprocess.run(
        [sys.executable, "-m", "osp_gdb_validator.cli", str(clean),
         "-s", str(SCHEMA)],
        env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        [sys.executable, "-m", "osp_gdb_validator.cli", str(dirty),
         "-s", str(SCHEMA), "--json", str(tmp_path / "rep.json")],
        env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True)
    assert r.returncode == 1
    assert (tmp_path / "rep.json").exists()
