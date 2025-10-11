"""Upper package for auto-mount testing.

This package automatically shims itself over 'tests.cases.auto_mount_lower'.
"""

from modshim import shim

shim("tests.cases.auto_mount_lower")
