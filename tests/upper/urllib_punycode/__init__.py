"""Enhanced urllib with automatic punycode-to-unicode conversion."""

from __future__ import annotations

from modshim import overlay

overlay = overlay("urllib")
