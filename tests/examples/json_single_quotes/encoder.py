"""JSON encoder that uses single quotes instead of double quotes for string values.

This module provides a custom JSON encoder that outputs strings with single quotes,
while maintaining full compatibility with the standard json.encoder functionality.
"""

from collections.abc import Iterator
from json.encoder import (
    INFINITY,
    _make_iterencode,  # type: ignore [reportAttributeAccessIssue]
)
from json.encoder import JSONEncoder as OgJSONEncoder
from json.encoder import (
    encode_basestring as og_encode_basestring,
)
from json.encoder import encode_basestring_ascii as og_encode_basestring_ascii
from typing import Callable


def encode_basestring(s: str) -> str:
    """Encode a string with single quotes."""
    return "'" + og_encode_basestring(s)[1:-1] + "'"


def encode_basestring_ascii(s: str) -> str:
    """Encode a string as ASCII with single quotes."""
    return "'" + og_encode_basestring_ascii(s)[1:-1] + "'"


class JSONEncoder(OgJSONEncoder):
    """JSON encoder that uses single quotes for strings."""

    def iterencode(self, o: object, _one_shot: bool = False) -> Iterator[str]:
        """Encode the given object and yield each string representation as available."""
        if self.check_circular:
            markers = {}
        else:
            markers = None
        if self.ensure_ascii:
            _encoder = encode_basestring_ascii
        else:
            _encoder = encode_basestring

        def floatstr(
            o: float,
            allow_nan: bool = self.allow_nan,
            _repr: Callable[[float], str] = float.__repr__,
            _inf: float = INFINITY,
            _neginf: float = -INFINITY,
        ) -> str:
            if o != o:
                text = "NaN"
            elif o == _inf:
                text = "Infinity"
            elif o == _neginf:
                text = "-Infinity"
            else:
                return _repr(o)

            if not allow_nan:
                raise ValueError(
                    "Out of range float values are not JSON compliant: " + repr(o)
                )

            return text

        if self.indent is None or isinstance(self.indent, str):
            indent = self.indent
        else:
            indent = " " * self.indent
        _iterencode = _make_iterencode(
            markers,
            self.default,
            _encoder,
            indent,
            floatstr,
            self.key_separator,
            self.item_separator,
            self.sort_keys,
            self.skipkeys,
            _one_shot,
        )
        return _iterencode(o, 0)
