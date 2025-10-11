"""Upper package with shim() call at the end."""

from modshim import shim

# Some other code to ensure the module does more than just shim
some_var = "end"

shim("tests.cases.shim_call_ordering_lower")
