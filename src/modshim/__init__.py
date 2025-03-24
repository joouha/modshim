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


class ModuleReferenceRewriter(ast.NodeTransformer):
    """AST transformer that rewrites module references to point to the mount point."""

    def __init__(self, original_root_package: str, mount_point: str) -> None:
        """Initialize the rewriter.

        Args:
            original_root_package: The root package name of the module being rewritten
            mount_point: The name of the mount point module
        """
        self.original_root_package = original_root_package
        self.mount_point = mount_point
        super().__init__()

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        """Rewrite 'from X import Y' statements."""
        # If this is an import from the original module or its submodules,
        # rewrite it to import from the mount point
        if node.module and (
            node.module == self.original_root_package
            or node.module.startswith(f"{self.original_root_package}.")
        ):
            # Replace the original module name with the mount point
            if node.module == self.original_root_package:
                new_module = self.mount_point
            else:
                # Handle submodule imports
                suffix = node.module[len(self.original_root_package) :]
                new_module = f"{self.mount_point}{suffix}"

            print(node.module, "->", new_module)
            return ast.ImportFrom(module=new_module, names=node.names, level=node.level)
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        """Rewrite 'import X' statements."""
        new_names = []
        for name in node.names:
            if name.name == self.original_root_package:
                # Replace the original module name with the mount point
                new_names.append(ast.alias(name=self.mount_point, asname=name.asname))
            elif name.name.startswith(f"{self.original_root_package}."):
                # Handle submodule imports
                suffix = name.name[len(self.original_root_package) :]
                new_name = f"{self.mount_point}{suffix}"
                new_names.append(ast.alias(name=new_name, asname=name.asname))
            else:
                new_names.append(name)

        if new_names:
            return ast.Import(names=new_names)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """Rewrite module references like 'urllib.response' to 'urllib_punycode.response'."""
        # First visit any child nodes
        node = self.generic_visit(node)
        
        # Check if this is a reference to the original module
        if isinstance(node.value, ast.Name) and node.value.id == self.original_root_package:
            # Replace the module name with the mount point
            return ast.Attribute(
                value=ast.Name(id=self.mount_point, ctx=node.value.ctx),
                attr=node.attr,
                ctx=node.ctx
            )
        
        # Check for nested attributes like urllib.parse.urlparse
        if isinstance(node.value, ast.Attribute):
            # Build the full attribute chain to check if it starts with the original module
            attrs = []
            current = node
            while isinstance(current, ast.Attribute):
                attrs.insert(0, current.attr)
                current = current.value
            
            # If the base is the original module name, rewrite the entire chain
            if isinstance(current, ast.Name) and current.id == self.original_root_package:
                # Start with the mount point as the base
                result = ast.Name(id=self.mount_point, ctx=current.ctx)
                
                # Rebuild the attribute chain
                for attr in attrs:
                    result = ast.Attribute(value=result, attr=attr, ctx=node.ctx)
                
                return result
        
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


def rewrite_module_code(code: str, original_root_package: str, mount_point: str) -> str:
    """Rewrite imports and module references in module code.

    Args:
        code: The source code to rewrite
        original_root_package: The root package name of the module being rewritten
        mount_point: The name of the mount point module

    Returns:
        Rewritten source code
    """
    tree = ast.parse(code)
    
    # Use the new transformer that handles both imports and module references
    transformer = ModuleReferenceRewriter(original_root_package, mount_point)
    transformed_tree = transformer.visit(tree)
    ast.fix_missing_locations(transformed_tree)
    
    return ast.unparse(transformed_tree)


class ModShimLoader:
    """Loader for shimmed modules."""

    def __init__(self, upper_module: str, lower_module: str, root_mount_point: str):
        """Initialize the loader.

        Args:
            upper_module: The name of the upper module
            lower_module: The name of the lower module
            root_mount_point: The root mount point for import rewriting
        """
        self.upper_module = upper_module
        self.lower_module = lower_module
        self.root_mount_point = root_mount_point

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
        self._load_combined_module(upper_name, lower_name, module)

    def _load_combined_module(
        self,
        upper_module: str | None,
        lower_module: str | None,
        target_module: ModuleType,
    ) -> None:
        """Load and combine module content into the target module.

        Args:
            upper_module: The name of the upper module (or None)
            lower_module: The name of the lower module (or None)
            target_module: The target module to load content into
        """
        # Get the root package names from ModShimFinder._mappings
        if self.root_mount_point in ModShimFinder._mappings:
            upper_root, lower_root = ModShimFinder._mappings[self.root_mount_point]
        else:
            # This should never happen, but just in case
            upper_root = self.upper_module
            lower_root = self.lower_module

        # Load and execute lower module first
        if lower_module:
            try:
                lower_spec = find_spec(lower_module)
                if lower_spec:
                    # First try to get the source code
                    lower_source = get_module_source(lower_module, lower_spec)

                    if lower_source:
                        # Rewrite imports using the root package name
                        lower_source = rewrite_module_code(
                            lower_source, lower_root, self.root_mount_point
                        )
                        try:
                            exec(
                                f"# Code from {lower_module}\n{lower_source}",
                                target_module.__dict__,
                            )
                        except Exception:
                            for i, line in enumerate(lower_source.splitlines()):
                                print(i, repr(line))
                            raise
                    elif lower_spec.loader and isinstance(
                        lower_spec.loader, InspectLoader
                    ):
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
                        # Rewrite imports using the root package name
                        upper_source = rewrite_module_code(
                            upper_source, lower_root, self.root_mount_point
                        )
                        exec(
                            f"# Code from {upper_module}\n{upper_source}",
                            target_module.__dict__,
                        )
                    elif upper_spec.loader and isinstance(
                        upper_spec.loader, InspectLoader
                    ):
                        # Fall back to compiled code if source is not available
                        try:
                            upper_code = upper_spec.loader.get_code(upper_module)
                            if upper_code:
                                exec(upper_code, target_module.__dict__)
                        except (ImportError, AttributeError):
                            pass
            except (ImportError, FileNotFoundError):
                pass


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
                return self._create_spec(fullname, upper_module, lower_module, fullname)
        # Check if this is a submodule of a mount point
        for mount_point, (upper_module, lower_module) in self._mappings.items():
            # Prevent recursion when trying to import a submodule that matches
            # the pattern of the source modules
            if fullname.startswith(f"{mount_point}.") and not (
                fullname.startswith((f"{upper_module}.", f"{lower_module}."))
            ):
                return self._create_spec(
                    fullname, upper_module, lower_module, mount_point
                )
        return None

    def _create_spec(
        self, fullname: str, upper_module: str, lower_module: str, root_mount_point: str
    ) -> ModuleSpec:
        """Create a module spec for the given module name."""
        loader = ModShimLoader(upper_module, lower_module, root_mount_point)
        spec = ModuleSpec(fullname, loader)

        # Add lower module submodule search locations
        try:
            lower_spec = find_spec(lower_module)
            if lower_spec and lower_spec.submodule_search_locations is not None:
                spec.submodule_search_locations = [
                    *(spec.submodule_search_locations or []),
                    *list(lower_spec.submodule_search_locations),
                ]
        except (ImportError, AttributeError):
            pass

        # Add upper module submodule search locations
        try:
            upper_spec = find_spec(upper_module)
            if upper_spec and upper_spec.submodule_search_locations is not None:
                spec.submodule_search_locations = [
                    *(spec.submodule_search_locations or []),
                    *list(upper_spec.submodule_search_locations),
                ]
        except (ImportError, AttributeError):
            pass

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
