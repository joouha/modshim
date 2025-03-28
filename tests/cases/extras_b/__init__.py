"""Overlay package for extras_a."""

from modshim import shim

shim(
    "tests.cases.extras_a",
    "tests.cases.extras_b",
    "tests.cases.extras_b",
)
