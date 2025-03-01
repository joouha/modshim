"""Module overlay system for Python."""
from __future__ import annotations

import sys
from importlib.abc import MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import spec_from_file_location
from pathlib import Path
from types import ModuleType
from typing import Any

# Registry of overlays: lower module -> (upper module, merge module)
_overlays: dict[str, tuple[str, str]] = {}

def register(*, lower: str, upper: str, merge: str) -> None:
    """Register an overlay configuration.
    
    Args:
        lower: The base module to be overlaid (e.g. "json")
        upper: The overlay module path (e.g. "upper.json_single_quotes") 
        merge: The name to use for the merged result (e.g. "json_single_quotes")
    """
    _overlays[lower] = (upper, merge)

class ModshimFinder(MetaPathFinder):
    """Import hook that handles overlay modules."""
    
    def find_spec(
        self,
        fullname: str,
        path: list[str] | None,
        target: Any = None,
    ) -> ModuleSpec | None:
        """Find and create module spec for overlay modules."""
        # Check if this is a registered overlay
        for lower, (upper, merge) in _overlays.items():
            if fullname == merge:
                # Load the lower (base) module
                base_module = __import__(lower)
                
                # Load the upper (overlay) module
                overlay_module = __import__(upper)
                for part in upper.split(".")[1:]:
                    overlay_module = getattr(overlay_module, part)
                
                # Create merged module
                merged = ModuleType(merge)
                merged.__dict__.update(base_module.__dict__)
                merged.__dict__.update(overlay_module.__dict__)
                
                # Add to sys.modules
                sys.modules[merge] = merged
                
                # Create a dummy spec
                return ModuleSpec(
                    name=merge,
                    loader=None,
                    origin="modshim virtual module",
                )
        return None

# Install the import hook
sys.meta_path.insert(0, ModshimFinder())
