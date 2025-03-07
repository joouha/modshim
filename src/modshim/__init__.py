"""Module for creating merged virtual Python modules that overlay objects from an upper module onto a lower module."""

from __future__ import annotations

import builtins
import logging
import sys
import threading
from contextlib import contextmanager
from importlib import import_module
from importlib.abc import Loader
from importlib.util import find_spec, module_from_spec, spec_from_loader
from types import ModuleType
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from importlib.machinery import ModuleSpec

# Set up logger with NullHandler
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class MergedModule(ModuleType):
    """A module that combines attributes from upper and lower modules."""

    def __init__(
        self,
        name: str,
        upper_module: ModuleType,
        lower_module: ModuleType,
        finder: MergedModuleFinder,
    ) -> None:
        """Initialize merged module with upper and lower modules.

        Args:
            name: Name of the merged module
            upper_module: Module containing overrides
            lower_module: Base module to enhance
            finder: The finder that created this module
        """
        super().__init__(name)
        self._upper = upper_module
        self._lower = lower_module
        self._finder = finder

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

    # Class-level lock for import operations
    _global_import_lock = threading.RLock()  # Use RLock to allow recursive locking

    def __init__(
        self,
        merged_name: str,
        upper_name: str,
        lower_name: str,
        finder: MergedModuleFinder,
    ) -> None:
        """Initialize the loader with module names and cache.

        Args:
            merged_name: Name of the merged module
            upper_name: Name of the upper module with overrides
            lower_name: Name of the lower base module
            finder: The finder that created this loader
        """
        super().__init__()
        self.merged_name = merged_name
        self.upper_name = upper_name
        self.lower_name = lower_name
        self.finder = finder
        self._original_import = None

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        """Create a new merged module instance.

        Args:
            spec: Module spec from the import system

        Returns:
            A new merged module combining upper and lower modules
        """
        log.debug("Creating module for spec: %r", spec)
        # If already merged, return from cache
        with self.finder._cache_lock:
            if spec.name in self.finder.cache:
                return self.finder.cache[spec.name]

        # Import both modules
        try:
            upper_module = import_module(self.upper_name)
        except ImportError:
            upper_module = ModuleType(self.upper_name)

        # Create a copy of the lower module
        lower_spec = find_spec(self.lower_name)
        if lower_spec is None:
            raise ImportError(f"No module named '{self.lower_name}'")

        lower_module = module_from_spec(lower_spec)

        # Create merged module
        merged = MergedModule(spec.name, upper_module, lower_module, self.finder)
        merged.__package__ = spec.parent
        path_attr = getattr(lower_module, "__path__", None)
        if path_attr is not None:
            merged.__path__ = list(path_attr)

        # Store in cache
        with self.finder._cache_lock:
            self.finder.cache[spec.name] = merged
        return merged

    def _do_import(
        self,
        original_import: Callable,
        name: str,
        globals: dict[str, Any] | None,
        locals: dict[str, Any] | None,
        fromlist: tuple[str, ...],
        level: int,
    ) -> ModuleType:
        """Perform the actual import operation."""
        log.debug("Importing: %s (fromlist=%r, level=%r)", name, fromlist, level)
        original_name = name
        original_level = level
        # Get calling module name
        caller_package = globals.get("__package__", "") if globals else ""
        caller_module = globals.get("__name__", "") if globals else ""

        # Resolve relative imports from the lower module
        if level and (
            caller_package == self.lower_name
            or caller_package.startswith(self.lower_name + ".")
        ):
            # Calculate the absolute names
            name = (
                ".".join(
                    caller_package.split(".")[: -level + 1] + ([name] if name else [])
                )
                if level > 1
                else caller_package + ("." + name if name else "")
            )
            # Reset the level, as name is now resolved
            level = 0

        # Check if we're in the lower module importing from within the lower module
        if (
            caller_package == self.finder.lower_name
            or caller_module.startswith(self.finder.lower_name + ".")
        ) and (
            name == self.finder.lower_name
            or name.startswith(self.finder.lower_name + ".")
        ):
            name = name.replace(self.finder.lower_name, self.finder.merged_name, 1)
            log.debug("Redirecting import '%s' to '%s'", original_name, name)

        result = original_import(name, globals, locals, fromlist, level)

        # For relative imports, add the module to the caller's namespace
        if original_name and original_level:
            local_name = name.split(".")[-1]
            if globals is not None:
                globals[local_name] = result

        log.debug(
            "Import hook returning module '%s' for import of '%s' (fromlist=%r, level=%r) by '%s'",
            result.__name__,
            original_name,
            fromlist,
            level,
            caller_module,
        )
        return result

    @contextmanager
    def hook_imports(
        self,
    ) -> Iterator[
        Callable[
            [str, dict[str, Any] | None, dict[str, Any] | None, tuple[str, ...], int],
            ModuleType,
        ]
    ]:
        """Temporarily install a custom import hook for handling merged modules.

        Thread-safe: Uses global and instance-specific locks to prevent concurrent modifications.

        Yields:
            The custom import function that was temporarily installed.
        """
        with self._global_import_lock:
            if self._original_import is None:
                self._original_import = builtins.__import__

            original_import = self._original_import

            def custom_import(
                name: str,
                globals: dict[str, Any] | None = None,
                locals: dict[str, Any] | None = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ) -> ModuleType:
                with self._global_import_lock:
                    return self._do_import(
                        original_import, name, globals, locals, fromlist, level
                    )

            # Set import hook atomically within the lock
            builtins.__import__ = custom_import

            try:
                yield custom_import
            finally:
                if self._original_import is not None:
                    builtins.__import__ = self._original_import
                    self._original_import = None

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

        # Use global lock for entire module execution
        with self._global_import_lock:
            with self.hook_imports():
                # Re-execute lower module with our import hook active if it has a loader
                if module._lower.__spec__ and module._lower.__spec__.loader:
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


class MergedModuleFinder:
    """Finder that creates merged modules combining upper and lower modules."""

    _meta_path_lock = threading.Lock()
    merged_name: str
    upper_name: str
    lower_name: str
    cache: dict[str, ModuleType]
    _cache_lock: threading.Lock

    def cleanup(self) -> None:
        """Clean up this finder and its associated modules.

        Removes the finder from sys.meta_path, clears its cache,
        and removes associated modules from sys.modules.
        """
        try:
            # Remove finder from sys.meta_path if it's still there
            with self._meta_path_lock:
                if self in sys.meta_path:
                    sys.meta_path.remove(self)
                    self.cache.clear()

                # Remove all associated modules from sys.modules
                # This includes both the main module and any submodules
                modules_to_remove = [
                    name
                    for name in sys.modules
                    if name == self.merged_name
                    or name.startswith(f"{self.merged_name}.")
                ]
                for name in modules_to_remove:
                    try:
                        del sys.modules[name]
                    except KeyError:
                        # Module already removed
                        pass

        except (ImportError, AttributeError):
            # Only catch specific errors that might occur during shutdown
            if not sys.is_finalizing():
                raise

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
        self._cache_lock = threading.Lock()

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
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
        return spec_from_loader(
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

    Raises:
        ValueError: If either upper or lower module name is empty
    """
    # Validate module names
    if not upper:
        raise ValueError("Upper module name cannot be empty")
    if not lower:
        raise ValueError("Lower module name cannot be empty")

    merged_name = as_name or f"{lower}_shim"

    log.debug(
        "Creating merged module: '%s' with upper '%s' and lower '%s'",
        merged_name,
        upper,
        lower,
    )

    finder = MergedModuleFinder(merged_name, upper, lower)

    with MergedModuleFinder._meta_path_lock:
        # Remove any existing finder for this merged module
        sys.meta_path = [
            f
            for f in sys.meta_path
            if not (isinstance(f, MergedModuleFinder) and f.merged_name == merged_name)
        ]
        sys.meta_path.insert(0, finder)

    # Import the merged module
    merged_module = import_module(merged_name)

    with MergedModuleFinder._meta_path_lock:
        sys.modules[merged_name] = merged_module

    return merged_module
