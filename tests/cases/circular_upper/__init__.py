"""Overlay package for circular_a."""

from modshim import shim

shim(
    "tests.cases.circular_a",
    "tests.cases.circular_b",
    "tests.cases.circular_b",
)
