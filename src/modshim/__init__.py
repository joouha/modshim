"""Module for creating merged virtual Python modules that overlay objects from an upper module onto a lower module."""

from __future__ import annotations

import builtins
import inspect
import logging
import os
import sys
import threading
from contextlib import contextmanager
from importlib import import_module
from importlib.abc import Loader
from importlib.util import find_spec, module_from_spec, spec_from_loader
from types import FunctionType, MethodType, ModuleType
from typing import TYPE_CHECKING, Any, Callable, TypeVar

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from importlib.machinery import ModuleSpec

T = TypeVar("T")

# Set up logger with NullHandler
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
if os.getenv("MODSHIM_DEBUG"):
    logging.basicConfig(level=logging.DEBUG)

# Module-level storage for original import
_original_import = builtins.__import__


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

        for attr in ("__package__", "__path__", "__file__", "__cached__"):
            try:
                setattr(self, attr, getattr(self._lower, attr, None))
            except AttributeError:
                pass

    def __getattr__(self, name: str) -> Any:
        """Get an attribute from either upper or lower module.

        Args:
            name: Name of attribute to get

        Returns:
            The attribute value from upper module if it exists, otherwise from lower
        """
        log.debug("Getting attribute '%s' from module '%s'", name, self.__name__)
        try:
            result = super().__getattr__(name)
        except AttributeError:
            pass

        # Check if this is a submodule that might be partially initialized
        full_submodule_name = f"{self.__name__}.{name}"
        if full_submodule_name in sys.modules:
            log.debug("Found partially initialized module '%s'", full_submodule_name)
            return sys.modules[full_submodule_name]

        # Check upper module
        try:
            result = getattr(self._upper, name)
        except AttributeError:
            pass
        # Then check lower module
        try:
            result = getattr(self._lower, name)
        except AttributeError:
            log.debug("No attribute '%s'", name)
            raise

        log.debug(
            "Got attribute '%s' from module '%s': %s", name, self.__name__, result
        )
        return result


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
            key = self.upper_name, self.lower_name, self.merged_name
            if key in self.finder.cache:
                return self.finder.cache[key]

        # Create a copy of the lower module
        lower_spec = find_spec(self.lower_name)
        log.debug("Using lower spec %s for '%s'", lower_spec, self.lower_name)
        if lower_spec is None:
            raise ImportError(f"No module named '{self.lower_name}'")
        lower_module = module_from_spec(lower_spec)

        # Import upper module
        try:
            with MergedModuleFinder._meta_path_lock:
                sys.meta_path.remove(self.finder)
            current_import = builtins.__import__
            try:
                # Restore original built-in import function in case it is hooked
                builtins.__import__ = _original_import
                # Upper module gets executed at this point if it not already imported
                if upper_spec := find_spec(self.upper_name):
                    upper_module = module_from_spec(upper_spec)
                else:
                    upper_module = ModuleType(self.upper_name)
            finally:
                # Restore potentially hooked import function
                builtins.__import__ = current_import
        finally:
            # Restore the finder
            with MergedModuleFinder._meta_path_lock:
                sys.meta_path.insert(0, self.finder)

        # Set upper module package name by modifying lower module package name
        upper_module.__package__ = (
            self.finder.upper_name
            + lower_module.__package__[len(self.finder.lower_name) :]
            if lower_module.__package__
            else None
        )

        # Create merged module
        merged = MergedModule(spec.name, upper_module, lower_module, self.finder)
        merged.__package__ = spec.name
        path_attr = getattr(upper_module, "__path__", None)
        if path_attr is not None:
            merged.__path__ = list(path_attr)

        # Store in cache
        with self.finder._cache_lock:
            self.finder.cache[key] = merged

        return merged

    def _do_import(
        self,
        name: str,
        globals: dict[str, Any] | None,
        locals: dict[str, Any] | None,
        fromlist: tuple[str, ...],
        level: int,
    ) -> ModuleType:
        """Perform the actual import operation."""
        original_name = name
        original_level = level
        # Get calling module name
        caller_package = globals.get("__package__", "") if globals else ""
        caller_module = globals.get("__name__", "") if globals else ""

        log.debug(
            "Importing: %s (fromlist=%r, level=%r) by '%s' of '%s'",
            name,
            fromlist,
            level,
            caller_module,
            caller_package,
        )
        # Check if we're in the upper or lower module importing from within the lower module
        from_layer = caller_module in {
            self.finder.lower_name,
            self.finder.upper_name,
        } or caller_module.startswith(
            (self.finder.lower_name + ".", self.finder.upper_name + ".")
        )

        # Resolve relative imports from the lower module
        if level and from_layer:
            if not caller_package:
                raise ImportError("Relative import with no known parent package")

            package_parts = caller_package.split(".")
            if len(package_parts) < level:
                raise ImportError("Attempted relative import beyond top package")

            # For level=1, use whole package (current directory)
            if level == 1:
                base_package = caller_package
            # For level>1, remove (level-1) parts to go up that many directories
            else:
                base_package = ".".join(package_parts[: -level + 1])

            # Construct absolute name
            name = f"{base_package}.{name}" if name else base_package
            level = 0  # Reset level since we've made it absolute

            log.debug(
                "Resolved relative import '%s' by '%s' to '%s'",
                original_name,
                caller_package,
                name,
            )

        replace = from_layer and (
            name == self.finder.lower_name
            or name.startswith(self.finder.lower_name + ".")
        )
        # if level > 0:
        if replace:
            # name = name.replace(self.finder.lower_name, self.finder.merged_name, 1)
            name = name.replace(self.finder.lower_name, self.finder.merged_name, 1)
            log.debug("Redirecting import '%s' to '%s'", original_name, name)

        # If we're importing the module we're currently creating, return its lower module
        if name == self.merged_name:
            # Get the module from the finder's cache
            key = (self.upper_name, self.lower_name, self.merged_name)
            with self.finder._cache_lock:
                if key in self.finder.cache:
                    return self.finder.cache[key]._lower

        # Perform the import using the original builtin import function
        log.debug(
            "Performing native import of '%s' (fromlist: %s, level: %s)",
            name,
            fromlist,
            level,
        )
        result = _original_import(name, globals, locals, fromlist, level)

        # For relative imports, add the module to the caller's namespace
        if original_name and original_level:
            local_name = name.split(".")[-1]
            if globals is not None:
                globals[local_name] = result

        # If our mount point is a more deeply nested submodule than the lower module,
        # we need to traverse the additional nesting levels of the import result
        if replace:
            lower_name_parts = self.finder.lower_name.split(".")
            merged_name_parts = self.finder.merged_name.split(".")
            if extra_parts := merged_name_parts[
                1 : len(merged_name_parts) - len(lower_name_parts) + 1
            ]:
                current = result
                for part in extra_parts:
                    log.debug("Traversing to '%s' via '%s'", part, current)
                    try:
                        current = getattr(current, part)
                    except AttributeError:
                        break
                result = current

        log.debug(
            "Import hook returning module '%s' for import of '%s' (fromlist=%r, level=%r) by '%s'",
            result,
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
            current_import = builtins.__import__

            def custom_import(
                name: str,
                globals: dict[str, Any] | None = None,
                locals: dict[str, Any] | None = None,
                fromlist: tuple[str, ...] = (),
                level: int = 0,
            ) -> ModuleType:
                with self._global_import_lock:
                    return self._do_import(name, globals, locals, fromlist, level)

            # Set import hook atomically within the lock
            builtins.__import__ = custom_import

            try:
                yield custom_import
            finally:
                builtins.__import__ = current_import

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
            sys.modules[self.lower_name] = module._lower
            # Execute lower module with our import hook active if it has a loader
            if module._lower.__spec__ and module._lower.__spec__.loader:
                log.debug("Executing lower '%s'", module._lower.__spec__.name)
                with self.hook_imports():
                    module._lower.__spec__.loader.exec_module(module._lower)
                log.debug("Executed lower '%s'", module._lower.__spec__.name)

            del sys.modules[self.lower_name]

            # Copy attributes from lower first
            module.__dict__.update(
                {
                    k: v
                    for k, v in module._lower.__dict__.items()
                    if not k.startswith("__")
                }
            )

            # Execute upper module without import hook
            if module._upper.__spec__ and module._upper.__spec__.loader:
                log.debug("Executing upper '%s'", module._upper.__spec__.name)
                module._upper.__spec__.loader.exec_module(module._upper)
                log.debug("Executed upper '%s'", module._upper.__spec__.name)

            # Copy attributes from upper
            module.__dict__.update(
                {
                    k: v
                    for k, v in module._upper.__dict__.items()
                    if not k.startswith("__")
                }
            )

            # Replace globals on any attributes from lower
            for name, value in dict(vars(module)).items():
                if hasattr(value, "__module__") and value.__module__ == self.lower_name:
                    value = patch_globals(value, module.__dict__)
                    setattr(module, name, value)


def patch_globals(value: Any, new_globals: dict[str, Any]) -> Any:
    """Replace an object's function globals to use the provided globals dictionary.

    Args:
        value: Object to patch
        new_globals: Dictionary of globals to use

    Returns:
        Object with updated function globals
    """
    if isinstance(value, FunctionType):
        wrapped = FunctionType(
            value.__code__,
            {**value.__globals__, **new_globals},
            value.__name__,
            value.__defaults__,
            value.__closure__,
        )
        wrapped.__kwdefaults__ = value.__kwdefaults__
        wrapped.__module__ = new_globals.get("__name__", value.__module__)
        return wrapped

    elif isinstance(value, MethodType):
        # Wrap methods
        wrapped_func = patch_globals(value.__func__, new_globals)
        return MethodType(wrapped_func, value.__self__)

    elif isinstance(value, property):
        # Handle properties
        return property(
            fget=patch_globals(value.fget, new_globals) if value.fget else None,
            fset=patch_globals(value.fset, new_globals) if value.fset else None,
            fdel=patch_globals(value.fdel, new_globals) if value.fdel else None,
            doc=value.__doc__,
        )

    elif isinstance(value, type):
        # Exclude subclasses of this class from the new globals in case they were
        # overridden in the overlay - we don't want to replace reference to a class in
        # it's methods with references to a subclass
        new_globals = {
            k: v
            for k, v in new_globals.items()
            if not isinstance(v, type) or not issubclass(v, value)
        }
        # For classes, only wrap their methods
        for name, attr in inspect.getmembers(value):
            # Check method is defined here to prevent wrapping inherited methods if
            # also processing subclasses
            if isinstance(attr, (FunctionType, property)) and name in value.__dict__:
                wrapped = patch_globals(attr, new_globals)
                setattr(value, name, wrapped)
        return value

    else:
        # For other objects, wrap any bound methods
        for name, method in inspect.getmembers(value, predicate=inspect.ismethod):
            if hasattr(method.__func__, "__code__"):  # Only wrap real methods
                wrapped = patch_globals(method.__func__, new_globals)
                try:
                    setattr(value, name, MethodType(wrapped, value))
                except AttributeError:
                    pass  # Skip if attribute can't be set
        return value


class MergedModuleFinder:
    """Finder that creates merged modules combining upper and lower modules."""

    _meta_path_lock = threading.Lock()
    merged_name: str
    upper_name: str
    lower_name: str
    _cache_lock: threading.Lock

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
        self.cache: dict[tuple[str, str, str], ModuleType] = {}
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
                    if name in self.merged_name
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

    def __repr__(self) -> str:
        """Return string representation showing merged module relationships.

        Returns:
            String in format 'MergedModuleFinder(merged = upper -> lower)'
        """
        return f"MergedModuleFinder({self.lower_name} + {self.upper_name} → {self.merged_name})"


def shim(lower: str, upper: str | None = None, mount: str | None = None) -> ModuleType:
    """Create a merged module combining upper and lower modules.

    Args:
        lower: Name of the target module to enhance
        upper: Name of the module containing overrides
        mount: Optional name for the merged module (defaults to '{upper}')

    Returns:
        A new module that combines both modules, with upper taking precedence

    Raises:
        ValueError: If either upper or lower module name is empty
    """
    # Validate module names
    if not lower:
        raise ValueError("Lower module name cannot be empty")

    # Use calling package name if 'upper' parameter name is empty
    if upper is None:
        # Get the caller's frame to find its module
        frame = sys._getframe(1)
        if frame is not None and frame.f_globals is not None:
            upper = frame.f_globals.get("__package__", "")
            if not upper:
                upper = frame.f_globals.get("__name__", "")
                if upper == "__main__":
                    raise ValueError("Cannot determine package name from __main__")
        if not upper:
            raise ValueError("Upper module name cannot be determined")

    if not upper:
        raise ValueError("Upper module name cannot be empty")

    # Use upper name as mount point if no mount point is specified
    merged_name = mount or upper

    # Check if the merged module already exists in sys.modules to avoid creating a new
    # instance
    if merged_name in sys.modules:
        merged_module = sys.modules[merged_name]
        if isinstance(merged_module, MergedModule):
            log.debug("Merged module already exists")
            return merged_module

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

    # Create the merged module
    merged_module = import_module(merged_name)

    # Execute the new merged module (again). This is necessary to ensure attributes
    # defined in the lower module are accessible from the merged module.
    # If the upper is the mount point, it will not be re-executed as the cached
    # module in sys.modules will be used
    if (
        (merged_spec := finder.find_spec(merged_name))
        and (loader := merged_spec.loader)
        and (merged_module := loader.create_module(merged_spec))
    ):
        with MergedModuleFinder._meta_path_lock:
            sys.modules[merged_name] = merged_module
        loader.exec_module(merged_module)

    assert merged_module is not None
    return merged_module
