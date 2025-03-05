"""Module for creating merged virtual Python modules that overlay objects from an upper module onto a lower module."""

from __future__ import annotations

import builtins
import importlib.util
import logging
import sys
from contextlib import contextmanager
from importlib.abc import Loader, MetaPathFinder
from types import ModuleType
from typing import Any, Callable

# Set up logger with NullHandler
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class MergedModule(ModuleType):
    """A module that combines attributes from upper and lower modules."""

    def __init__(
        self, name: str, upper_module: ModuleType, lower_module: ModuleType
    ) -> None:
        """Initialize merged module with upper and lower modules.

        Args:
            name: Name of the merged module
            upper_module: Module containing overrides
            lower_module: Base module to enhance
        """
        super().__init__(name)
        self._upper = upper_module
        self._lower = lower_module

    def __getattr__(self, name: str) -> Any:
        """Get an attribute from either upper or lower module.

        Args:
            name: Name of attribute to get

        Returns:
            The attribute value from upper module if it exists, otherwise from lower
        """
        log.debug("Getting attribute '%s' from module '%s'", name, self)
        # Check upper module
        try:
            return getattr(self._upper, name)
        except AttributeError:
            pass
        # Then check lower module
        try:
            return getattr(self._lower, name)
        except AttributeError:
            raise


class MergedModuleLoader(Loader):
    """Loader that creates merged modules combining upper and lower modules."""

    def __init__(
        self,
        merged_name: str,
        upper_name: str,
        lower_name: str,
        finder: MetaPathFinder,
    ) -> None:
        """Initialize the loader with module names and cache.

        Args:
            merged_name: Name of the merged module
            upper_name: Name of the upper module with overrides
            lower_name: Name of the lower base module
            finder: The finder that created this loader
        """
        self.merged_name = merged_name
        self.upper_name = upper_name
        self.lower_name = lower_name
        self.finder = finder

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType:
        """Create a new merged module instance.

        Args:
            spec: Module spec from the import system

        Returns:
            A new merged module combining upper and lower modules
        """
        log.debug("Creating module for spec: %r", spec)
        # If already merged, return from cache
        if spec.name in self.finder.cache:
            return self.finder.cache[spec.name]

        # Import both modules
        try:
            upper_module = importlib.import_module(self.upper_name)
        except ImportError:
            upper_module = ModuleType(self.upper_name)

        # Create a copy of the lower module
        lower_spec = importlib.util.find_spec(self.lower_name)
        lower_module = importlib.util.module_from_spec(lower_spec)

        # Create merged module
        merged = MergedModule(spec.name, upper_module, lower_module)
        merged.__package__ = spec.parent
        merged.__path__ = getattr(lower_module, "__path__", None)

        # Store in cache
        self.finder.cache[spec.name] = merged
        return merged

    @contextmanager
    def hook_imports(
        self,
    ) -> Callable[
        [str, dict[str, Any] | None, dict[str, Any] | None, tuple[str, ...], int],
        ModuleType,
    ]:
        # AI! Add a method docstring
        # Store original import
        original_import = builtins.__import__

        def custom_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> ModuleType:
            log.debug("Importing: %s (fromlist=%r, level=%r)", name, fromlist, level)
            original_name = name
            # Get calling module name
            caller_package = globals.get("__package__", "") if globals else ""
            caller_module = globals.get("__name__", "") if globals else ""

            # Check if we're in the lower module importing from within the lower module
            # If so, redirect the import to the merged module
            if (
                caller_package == self.finder.lower_name
                or caller_module.startswith(self.finder.lower_name + ".")
            ) and (
                name == self.finder.lower_name
                or name.startswith(self.finder.lower_name + ".")
            ):
                name = name.replace(self.finder.lower_name, self.finder.merged_name, 1)
                log.debug("Redirecting import '%s' to '%s'", original_name, name)

            # For relative imports, we need to handle them in the context of their package
            if level > 0 and globals:
                package = globals.get("__package__", "")

                # If import is happening from within lower module
                if package == self.lower_name or package.startswith(
                    self.lower_name + "."
                ):
                    # Calculate the absolute names
                    if level > 1:
                        package_parts = package.split(".")
                        lower_name = ".".join(
                            package_parts[: -level + 1] + ([name] if name else [])
                        )
                    else:
                        lower_name = package + ("." + name if name else "")

                    # Create merged version of the submodule
                    merged_name = self.merged_name + lower_name[len(self.lower_name) :]

                    # Import the merged module
                    result = importlib.import_module(merged_name)

                    # For relative imports, add the module to the caller's namespace
                    # using the local part of the name
                    if name:  # Only if there's a module name (not just dots)
                        local_name = name.split(".")[-1]
                        if globals is not None:
                            globals[local_name] = result

                    return result
                # Handle existing merged module relative imports
                elif package.startswith(self.merged_name):
                    if level > 1:
                        package_parts = package.split(".")
                        name = ".".join(
                            package_parts[: -level + 1] + ([name] if name else [])
                        )
                    else:
                        name = package + ("." + name if name else "")

                    return importlib.import_module(name)

            result = original_import(name, globals, locals, fromlist, level)

            log.debug(
                "Import hook returning module '%s' for import of '%s' (fromlist=%r, level=%r) by '%s'",
                result.__name__,
                original_name,
                fromlist,
                level,
                caller_module,
            )
            return result

        # Install custom import
        builtins.__import__ = custom_import
        yield
        # Restore original import function
        builtins.__import__ = original_import

        return custom_import

    def exec_module(self, module: ModuleType) -> None:
        """Execute a merged module by combining upper and lower modules.

        Args:
            module: The merged module to execute
        """
        log.debug(
            "Executing module: '%s' with upper '%s' and lower '%s'",
            module.__name__,
            self.upper_name,
            self.lower_name,
        )

        #######

        with self.hook_imports():
            # Re-execute lower module with our import hook active
            # - this ensures internal imports go through our hook
            log.debug("Executing '%s'", module._lower.__spec__.name)
            module._lower.__spec__.loader.exec_module(module._lower)
            log.debug("Executed '%s'", module._lower.__spec__.name)

            # Copy attributes from lower first
            for name, value in vars(module._lower).items():
                if not name.startswith("__"):
                    setattr(module, name, value)

            # Then overlay upper module attributes
            for name, value in vars(module._upper).items():
                if not name.startswith("__"):
                    setattr(module, name, value)


class MergedModuleFinder(MetaPathFinder):
    """Finder that creates merged modules combining upper and lower modules."""

    def __init__(
        self,
        merged_name: str,
        upper_name: str,
        lower_name: str,
    ) -> None:
        """Initialize finder with module names.

        Args:
            merged_name: Name of the merged module
            upper_name: Name of the upper module with overrides
            lower_name: Name of the lower base module
        """
        self.merged_name = merged_name
        self.upper_name = upper_name
        self.lower_name = lower_name
        self.cache: dict[str, ModuleType] = {}

    def find_spec(
        self,
        fullname: str,
        path: list[str] | None = None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        """Find and create a module spec for merged modules.

        Args:
            fullname: Full name of the module to find
            path: Search path for the module
            target: Module to use for the spec

        Returns:
            A module spec for the merged module if applicable, None otherwise
        """
        # Only handle imports under our merged namespace
        if fullname != self.merged_name and not fullname.startswith(
            f"{self.merged_name}."
        ):
            return None

        # Calculate corresponding paths in upper and lower modules
        relative_path = fullname[len(self.merged_name) :].lstrip(".")
        upper_fullname = (
            (self.upper_name + "." + relative_path)
            if relative_path
            else self.upper_name
        )
        lower_fullname = (
            (self.lower_name + "." + relative_path)
            if relative_path
            else self.lower_name
        )

        # Create loader
        loader = MergedModuleLoader(
            fullname,
            upper_fullname,
            lower_fullname,
            finder=self,
        )

        # Create a spec for the merged module
        return importlib.util.spec_from_loader(
            fullname,
            loader,
            origin=None,
            is_package=True,  # Allow submodules
        )


def shim(upper: str, lower: str, as_name: str | None = None) -> ModuleType:
    """Create a merged module combining upper and lower modules.

    Args:
        upper: Name of the module containing overrides
        lower: Name of the target module to enhance
        as_name: Optional name for the merged module (defaults to '{lower}_shim')

    Returns:
        A new module that combines both modules, with upper taking precedence
    """
    merged_name = as_name or f"{lower}_shim"

    log.debug(
        "Creating merged module: '%s' with upper '%s' and lower '%s'",
        merged_name,
        upper,
        lower,
    )

    finder = MergedModuleFinder(merged_name, upper, lower)
    sys.meta_path.insert(0, finder)

    # Import the merged module
    merged_module = importlib.import_module(merged_name)
    sys.modules[merged_name] = merged_module

    return merged_module
