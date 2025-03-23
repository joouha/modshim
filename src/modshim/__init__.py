"""modshim: A module that combines two modules by rewriting their ASTs.

This module allows "shimming" one module on top of another, creating a combined module
that includes functionality from both. Internal imports are redirected to the mount point.
"""

from __future__ import annotations

import ast
import sys
from importlib.abc import InspectLoader, MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from types import ModuleType
from typing import ClassVar


class ImportRewriter(ast.NodeTransformer):
    """AST transformer that rewrites imports to point to the mount point."""

    def __init__(self, original_module_name: str, mount_point: str) -> None:
        """Initialize the rewriter.

        Args:
            original_module_name: The name of the module being rewritten
            mount_point: The name of the mount point module
        """
        self.original_module_name = original_module_name
        self.mount_point = mount_point
        super().__init__()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        """Rewrite 'from X import Y' statements."""
        # If this is an import from the original module or its submodules,
        # rewrite it to import from the mount point
        if node.module and (
            node.module == self.original_module_name
            or node.module.startswith(f"{self.original_module_name}.")
        ):
            # Replace the original module name with the mount point
            if node.module == self.original_module_name:
                new_module = self.mount_point
            else:
                # Handle submodule imports
                suffix = node.module[len(self.original_module_name) :]
                new_module = f"{self.mount_point}{suffix}"

            return ast.ImportFrom(module=new_module, names=node.names, level=node.level)
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        """Rewrite 'import X' statements."""
        new_names = []
        for name in node.names:
            if name.name == self.original_module_name:
                # Replace the original module name with the mount point
                new_names.append(ast.alias(name=self.mount_point, asname=name.asname))
            elif name.name.startswith(f"{self.original_module_name}."):
                # Handle submodule imports
                suffix = name.name[len(self.original_module_name) :]
                new_name = f"{self.mount_point}{suffix}"
                new_names.append(ast.alias(name=new_name, asname=name.asname))
            else:
                new_names.append(name)

        if new_names:
            return ast.Import(names=new_names)
        return node


def get_module_source(module_name: str, spec: ModuleSpec) -> str | None:
    """Get the source code of a module using its loader.

    Args:
        module_name: Name of the module
        spec: The module's spec

    Returns:
        The source code of the module or None if not available
    """
    if not spec or not spec.loader or not isinstance(spec.loader, InspectLoader):
        return None

    try:
        # Try to get the source directly
        return spec.loader.get_source(module_name)
    except (ImportError, AttributeError):
        return None


def rewrite_module_code(code: str, original_module_name: str, mount_point: str) -> str:
    """Rewrite imports in module code.

    Args:
        code: The source code to rewrite
        original_module_name: The name of the module being rewritten
        mount_point: The name of the mount point module

    Returns:
        Rewritten source code
    """
    tree = ast.parse(code)
    transformer = ImportRewriter(original_module_name, mount_point)
    transformed_tree = transformer.visit(tree)
    ast.fix_missing_locations(transformed_tree)
    return ast.unparse(transformed_tree)


def _load_combined_module(
    upper_module: str | None, lower_module: str | None, target_module: ModuleType
) -> None:
    """Load and combine module content into the target module.

    Args:
        upper_module: The name of the upper module (or None)
        lower_module: The name of the lower module (or None)
        target_module: The target module to load content into
    """
    mount_point = target_module.__name__

    # Load and execute lower module first
    if lower_module:
        try:
            lower_spec = find_spec(lower_module)
            if lower_spec:
                # First try to get the source code
                lower_source = get_module_source(lower_module, lower_spec)

                if lower_source:
                    # Rewrite imports and execute
                    lower_source = rewrite_module_code(
                        lower_source, lower_module, mount_point
                    )
                    exec(
                        f"# Code from {lower_module}\n{lower_source}",
                        target_module.__dict__,
                    )
                elif lower_spec.loader and isinstance(lower_spec.loader, InspectLoader):
                    # Fall back to compiled code if source is not available
                    try:
                        lower_code = lower_spec.loader.get_code(lower_module)
                        if lower_code:
                            exec(lower_code, target_module.__dict__)
                    except (ImportError, AttributeError):
                        pass
        except (ImportError, FileNotFoundError):
            pass

    # Then load and execute upper module
    if upper_module:
        try:
            upper_spec = find_spec(upper_module)
            if upper_spec:
                # First try to get the source code
                upper_source = get_module_source(upper_module, upper_spec)

                if upper_source:
                    # Rewrite imports and execute
                    upper_source = rewrite_module_code(
                        upper_source, lower_module, mount_point
                    )
                    exec(
                        f"# Code from {upper_module}\n{upper_source}",
                        target_module.__dict__,
                    )
                elif upper_spec.loader and isinstance(upper_spec.loader, InspectLoader):
                    # Fall back to compiled code if source is not available
                    try:
                        upper_code = upper_spec.loader.get_code(upper_module)
                        if upper_code:
                            exec(upper_code, target_module.__dict__)
                    except (ImportError, AttributeError):
                        pass
        except (ImportError, FileNotFoundError):
            pass


class ModShimLoader:
    """Loader for shimmed modules."""

    def __init__(self, upper_module: str, lower_module: str):
        """Initialize the loader.

        Args:
            upper_module: The name of the upper module
            lower_module: The name of the lower module
        """
        self.upper_module = upper_module
        self.lower_module = lower_module

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        """Create a new module object."""
        module = ModuleType(spec.name)
        module.__file__ = f"<{spec.name}>"
        module.__loader__ = self
        module.__package__ = spec.parent

        # If this is a package, set up package attributes
        if spec.submodule_search_locations is not None:
            module.__path__ = []

        return module

    def exec_module(self, module: ModuleType) -> None:
        """Execute the module by combining upper and lower modules."""
        upper_name = self.upper_module
        lower_name = self.lower_module

        # For submodules, map the full import path
        if "." in module.__name__:
            suffix = module.__name__.split(".", 1)[1]
            if self.upper_module:
                upper_name = f"{self.upper_module}.{suffix}"
            if self.lower_module:
                lower_name = f"{self.lower_module}.{suffix}"

        # Load the combined module content
        _load_combined_module(upper_name, lower_name, module)


class ModShimFinder(MetaPathFinder):
    """Finder for shimmed modules."""

    # Dictionary mapping mount points to (upper_module, lower_module) tuples
    _mappings: ClassVar[dict[str, tuple[str, str]]] = {}

    @classmethod
    def register_mapping(
        cls, mount_point: str, upper_module: str, lower_module: str
    ) -> None:
        """Register a new module mapping.

        Args:
            mount_point: The name of the mount point
            upper_module: The name of the upper module
            lower_module: The name of the lower module
        """
        cls._mappings[mount_point] = (upper_module, lower_module)

    def find_spec(
        self,
        fullname: str,
        path: list[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find a module spec for the given module name."""
        # Check if this is a direct mount point
        if fullname in self._mappings:
            upper_module, lower_module = self._mappings[fullname]
            # Prevent recursion when mount point is the same as one of the source modules
            if fullname != upper_module and fullname != lower_module:
                return self._create_spec(fullname, upper_module, lower_module)

        # Check if this is a submodule of a mount point
        for mount_point, (upper_module, lower_module) in self._mappings.items():
            if fullname.startswith(f"{mount_point}.") and not (
                fullname.startswith((f"{upper_module}.", f"{lower_module}."))
            ):
                # Prevent recursion when trying to import a submodule that matches
                # the pattern of the source modules
                return self._create_spec(fullname, upper_module, lower_module)

        return None

    def _create_spec(
        self, fullname: str, upper_module: str, lower_module: str
    ) -> ModuleSpec:
        """Create a module spec for the given module name."""
        loader = ModShimLoader(upper_module, lower_module)
        spec = ModuleSpec(fullname, loader)

        # Check if this should be a package - we need to check both the direct module
        # and parent modules for package status
        is_package = False

        # Determine the corresponding module names in the upper and lower modules
        if fullname.startswith(f"{upper_module}.") and upper_module:
            # This is a submodule of the upper module
            relative_name = fullname[len(upper_module) + 1:]
            upper_name = f"{upper_module}.{relative_name}"
            lower_name = f"{lower_module}.{relative_name}" if lower_module else None
        elif fullname.startswith(f"{lower_module}.") and lower_module:
            # This is a submodule of the lower module
            relative_name = fullname[len(lower_module) + 1:]
            upper_name = f"{upper_module}.{relative_name}" if upper_module else None
            lower_name = f"{lower_module}.{relative_name}"
        else:
            # This is the mount point itself
            upper_name = upper_module
            lower_name = lower_module

        # Check if the upper module is a package
        if upper_name:
            try:
                upper_spec = find_spec(upper_name)
                if upper_spec and upper_spec.submodule_search_locations is not None:
                    is_package = True
                    # Use the actual search paths from the upper module if available
                    if not spec.submodule_search_locations:
                        spec.submodule_search_locations = list(upper_spec.submodule_search_locations)
            except (ImportError, AttributeError):
                pass

        # Check if the lower module is a package
        if lower_name and not is_package:  # Only check lower if upper isn't a package
            try:
                lower_spec = find_spec(lower_name)
                if lower_spec and lower_spec.submodule_search_locations is not None:
                    is_package = True
                    # Use the actual search paths from the lower module if available
                    if not spec.submodule_search_locations:
                        spec.submodule_search_locations = list(lower_spec.submodule_search_locations)
            except (ImportError, AttributeError):
                pass

        # If it's a package but we couldn't get search paths, provide an empty list
        if is_package and not spec.submodule_search_locations:
            spec.submodule_search_locations = []

        return spec


def shim(lower: str, upper: str | None = None, mount: str | None = None) -> None:
    """Mount an upper module or package on top of a lower module or package.

    This function sets up import machinery to dynamically combine modules
    from the upper and lower packages when they are imported through
    the mount point.

    Args:
        upper: The name of the upper module or package
        lower: The name of the lower module or package
        mount: The name of the mount point

    Returns:
        The combined module or package
    """
    # Register our finder in sys.meta_path if not already there
    if not any(isinstance(finder, ModShimFinder) for finder in sys.meta_path):
        sys.meta_path.insert(0, ModShimFinder())

    # Register the mapping for this mount point
    ModShimFinder.register_mapping(mount, upper, lower)
