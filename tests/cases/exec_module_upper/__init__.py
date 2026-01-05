"""Overlay package for executing a module."""

from modshim import shim

shim(
    "tests.cases.exec_module_lower",
    "tests.cases.exec_module_upper",
    "tests.cases.exec_module_upper",
)
