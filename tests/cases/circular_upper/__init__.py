"""Overlay package for circular_a."""

from modshim import shim

shim(
    "tests.cases.circular_lower",
    "tests.cases.circular_lower",
    "tests.cases.circular_upper",
)
