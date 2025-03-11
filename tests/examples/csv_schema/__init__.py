"""Enhanced csv with schema validation and type conversion."""

from __future__ import annotations

import csv as original_csv
from datetime import datetime
from typing import Any, Callable


class Schema:
    """CSV column schema definition."""

    def __init__(self, **fields: type | Callable[[str], Any]) -> None:
        """Initialize schema with field definitions.

        Args:
            **fields: Mapping of field names to their type converters
        """
        self.fields = fields

    def validate_and_convert(self, row: dict[str, str]) -> dict[str, Any]:
        """Validate and convert row according to schema."""
        result = {}
        for field, converter in self.fields.items():
            if field not in row:
                raise ValueError(f"Missing required field: {field}")
            try:
                if converter == datetime:
                    # Try common date formats
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                        try:
                            result[field] = datetime.strptime(row[field], fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        raise ValueError(f"Invalid date format: {row[field]}")
                else:
                    result[field] = converter(row[field])
            except ValueError as e:
                raise ValueError(
                    f"Invalid value for {field}: {row[field]}\n{e!s}"
                ) from None
        return result


class DictReader(original_csv.DictReader):
    """Enhanced DictReader with schema validation."""

    def __init__(self, f: Any, schema: Schema | None = None, **kwargs: Any) -> None:
        """Initialize DictReader with optional schema validation.

        Args:
            f: A file-like object to read from
            schema: Optional Schema instance for validation and conversion
            **kwargs: Keyword arguments passed to csv.DictReader
        """
        super().__init__(f, **kwargs)
        self.schema = schema

    def __next__(self) -> dict[str, Any]:
        """Get next row with validation and conversion."""
        row = super().__next__()
        if self.schema:
            return self.schema.validate_and_convert(row)
        return row
