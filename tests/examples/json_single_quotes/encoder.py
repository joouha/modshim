"""JSON encoder that uses single quotes instead of double quotes for string values.

This module provides a custom JSON encoder that outputs strings with single quotes,
while maintaining full compatibility with the standard json.encoder functionality.
"""

from json.encoder import (
    encode_basestring as og_encode_basestring,
)
from json.encoder import encode_basestring_ascii as og_encode_basestring_ascii


def encode_basestring(s: str) -> str:
    """Encode a string with single quotes."""
    return "'" + og_encode_basestring(s)[1:-1] + "'"


def encode_basestring_ascii(s: str) -> str:
    """Encode a string as ASCII with single quotes."""
    return "'" + og_encode_basestring_ascii(s)[1:-1] + "'"
