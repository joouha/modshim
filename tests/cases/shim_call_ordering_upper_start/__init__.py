"""Upper package with shim() call at the start."""

from modshim import shim

shim("tests.cases.shim_call_ordering_lower")

# Some other code to ensure the module does more than just shim
some_var = "start"
