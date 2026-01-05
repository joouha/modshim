"""Overrides for global variable in a sub-module."""

from __future__ import annotations

from tests.cases.exec_module_upper.a import Y

Y: str = Y.replace("lower", "upper")
