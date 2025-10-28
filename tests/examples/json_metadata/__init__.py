"""Enhanced JSON module with metadata injection."""

from json import dumps as original_dumps
from typing import Any


def dumps(obj: dict[str, Any], *args: Any, **kwargs: Any) -> str:
    """Serialize obj to a JSON formatted str with added metadata.

    Args:
        obj: The object to serialize
        *args: Positional arguments passed to json.dumps
        **kwargs: Keyword arguments passed to json.dumps

    Returns:
        JSON formatted string with metadata added
    """
    # Add a metadata field to all JSON output
    if isinstance(obj, dict):
        obj = obj.copy()
        obj["_metadata"] = {"timestamp": "2024-01-01"}
    return original_dumps(obj, *args, **kwargs)
