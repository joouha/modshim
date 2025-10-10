"""Enhanced JSON module with pretty printing."""

from __future__ import annotations

from typing import Any


def dumps(obj: dict[str, Any], *args: Any, **kwargs: Any) -> str:
    """Serialize obj to a JSON formatted str with consistent formatting.

    Args:
        obj: The object to serialize
        *args: Positional arguments passed to json.dumps
        **kwargs: Keyword arguments passed to json.dumps

    Returns:
        JSON formatted string with consistent indentation
    """
    # Always use consistent formatting
    kwargs["indent"] = 2
    kwargs["sort_keys"] = True

    # Get the dumps from the lower module (a merged module in this case)
    from json_single_quotes import (
        dumps as lower_dumps,  # type: ignore [reportAttributeAccessIssue]
    )

    return lower_dumps(obj, *args, **kwargs)
