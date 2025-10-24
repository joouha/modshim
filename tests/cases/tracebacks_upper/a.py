"""A module that intentionally raises an error during import for testing."""

from tests.cases.tracebacks_lower import other as other

raise RuntimeError("boom during upper import")
