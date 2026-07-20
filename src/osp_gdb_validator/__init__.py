"""osp-gdb-validator — schema QC for OSP/FTTx file geodatabases.

Clean-room, license-free (GDAL OpenFileGDB) validation of file GDBs against
YAML schema definitions: layers, fields, types, domains, uniqueness, typos.
"""

from .schema import load_schema, Schema, SchemaError
from .validator import validate, CHECKS
from .report import Report, Finding

__version__ = "0.1.0"
__all__ = ["load_schema", "Schema", "SchemaError", "validate", "CHECKS",
           "Report", "Finding"]
