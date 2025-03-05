"""Module for creating merged virtual Python modules that overlay objects from an upper module onto a lower module."""

from __future__ import annotations

import builtins
import logging
import importlib.util

# Set up logger with NullHandler
log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())
import sys
import types
from importlib.abc import Loader, MetaPathFinder
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping


class MergedModule(types.ModuleType):
    """A module that combines attributes from upper and lower modules."""

    def __init__(
        self, name: str, upper_module: types.ModuleType, lower_module: types.ModuleType
    ) -> None:
        super().__init__(name)
        self._upper = upper_module
        self._lower = lower_module
        self._lower_dict: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        log.debug("Getting attribute '%s' from %s", name, self)
        # First check if this is a submodule path
        full_lower_name = f"{self._lower.__name__}.{name}"
        if full_lower_name in sys.modules:
            # Return the merged version if it exists
            merged_name = f"{self.__name__}.{name}"
            if merged_name in sys.modules:
                return sys.modules[merged_name]
            # Otherwise return the original submodule
            return sys.modules[full_lower_name]

        # Then check upper module
        try:
            val = getattr(self._upper, name)
            return val
        except AttributeError:
            pass

        # Then check lower module
        try:
            value = getattr(self._lower, name)
            if isinstance(value, types.ModuleType):
                # If this is a submodule of the lower module, redirect to merged version
                if value.__name__.startswith(self._lower.__name__ + "."):
                    merged_name = (
                        self.__name__ + value.__name__[len(self._lower.__name__) :]
                    )
                    if merged_name in sys.modules:
                        return sys.modules[merged_name]
                return value
            # If this is an import from the lower module, we need to redirect it
            if isinstance(value, type) and value.__module__ == self._lower.__name__:
                # Check if we already have this class in our merged module
                if hasattr(self, value.__name__):
                    return getattr(self, value.__name__)
            return value
        except AttributeError as e:
            raise


class MergedModuleLoader(Loader):
    """Loader that creates merged modules combining upper and lower modules."""

    def __init__(
        self,
        merged_name: str,
        upper_name: str,
        lower_name: str,
        finder: MetaPathFinder,
        cache: Mapping[str, types.ModuleType],
    ) -> None:
        self.merged_name = merged_name
        self.upper_name = upper_name
        self.lower_name = lower_name
        self.finder = finder
        self.cache = cache

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        log.debug("Creating module for spec: %r", spec)
        # If already merged, return from cache
        if spec.name in self.cache:
            return self.cache[spec.name]

        # Import both modules
        try:
            upper_module = importlib.import_module(self.upper_name)
        except ImportError:
            upper_module = types.ModuleType(self.upper_name)

        # Create a copy of the lower module
        lower_spec = importlib.util.find_spec(self.lower_name)
        lower_module = importlib.util.module_from_spec(lower_spec)

        # Create merged module
        merged = MergedModule(spec.name, upper_module, lower_module)
        merged.__package__ = spec.parent
        merged.__path__ = getattr(lower_module, "__path__", None)

        # Store in cache
        self.cache[spec.name] = merged
        return merged

    def exec_module(self, module: types.ModuleType) -> None:
        log.debug("Executing module: %s", module.__name__)
        log.debug("Upper module path: %s", self.upper_name)
        log.debug("Lower module path: %s", self.lower_name)
        log.debug(
            "Lower module contents before: %s",
            [x for x in dir(module._lower) if not x.startswith("__")],
        )
        log.debug(
            "Upper module contents: %s",
            [x for x in dir(module._upper) if not x.startswith("__")],
        )

        # Store original import
        original_import = builtins.__import__

        def custom_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> types.ModuleType:
            log.debug("Importing: %s (fromlist=%r, level=%r)", name, fromlist, level)
            original_name = name
            # Get calling module name
            caller_package = globals.get("__package__", "") if globals else ""
            caller_module = globals.get("__name__", "") if globals else ""

            # Check if we're anywhere in the lower module hierarchy
            if (caller_package == self.finder.lower_name) or caller_module.startswith(
                self.finder.lower_name + "."
            ):
                if (name == self.finder.lower_name) or name.startswith(
                    self.finder.lower_name + "."
                ):
                    name = name.replace(
                        self.finder.lower_name, self.finder.merged_name, 1
                    )

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

            # For absolute imports, check if we're importing from the target module
            result = None
            if name == self.lower_name or name.startswith(self.lower_name + "."):
                # Redirect to merged module
                merged_name = self.merged_name + name[len(self.lower_name) :]
                result = importlib.import_module(merged_name)
            # Handle imports from within the target package
            elif globals and globals.get("__package__") == self.lower_name:
                if name.startswith(self.lower_name + "."):
                    # This is an internal package import, redirect it
                    merged_name = self.merged_name + name[len(self.lower_name) :]
                    result = importlib.import_module(merged_name)

            if result is None:
                result = original_import(name, globals, locals, fromlist, level)

            # setattr(caller_module, original_name, result)

            log.debug(
                "Import returning module '%s' for import of '%s' (fromlist=%r, level=%r) by '%s'",
                result.__name__,
                original_name,
                fromlist,
                level,
                caller_module,
            )
            return result

        #######

        try:
            # Install custom import
            builtins.__import__ = custom_import

            # Re-import lower module with our import hook active
            # This ensures internal imports go through our hook
            log.debug("Reloading '%s'", module._lower.__spec__.name)
            # importlib.reload(module._lower)
            module._lower.__spec__.loader.exec_module(module._lower)
            log.debug("Reloaded '%s'", module._lower.__spec__.name)

            # Copy attributes from lower first
            for name, value in vars(module._lower).items():
                if not name.startswith("_"):
                    # if (
                    #     isinstance(value, type)
                    #     and not isinstance(value, type(object))  # Skip built-in types
                    #     and not hasattr(value, "__slots__")
                    # ):  # Skip types with slots
                    #     # Create redirected class with updated references
                    #     try:
                    #         value = create_redirected_class(value, module)
                    #     except TypeError:
                    #         # If we can't create redirected class, use original value
                    #         pass
                    if isinstance(value, types.FunctionType):
                        # Create new function with merged module's globals
                        new_globals = dict(value.__globals__)
                        new_globals["__name__"] = module.__name__
                        new_globals["__package__"] = module.__package__

                        # Update module references to point to merged versions
                        for k, v in new_globals.items():
                            if isinstance(v, types.ModuleType):
                                if v.__name__ == self.lower_name:
                                    new_globals[k] = module
                                elif v.__name__.startswith(self.lower_name + "."):
                                    merged_name = (
                                        self.merged_name
                                        + v.__name__[len(self.lower_name) :]
                                    )
                                    new_globals[k] = sys.modules.get(merged_name)

                        value = types.FunctionType(
                            value.__code__,
                            new_globals,
                            value.__name__,
                            value.__defaults__,
                            value.__closure__,
                        )
                    setattr(module, name, value)

            # Then overlay upper module attributes
            for name, value in vars(module._upper).items():
                if not name.startswith("_"):
                    setattr(module, name, value)

            # Store original module's dict for import redirection
            module._lower_dict = dict(module._lower.__dict__)

        finally:
            # Restore original import
            log.debug(
                "Exec'd module ('%s') contents after: %s",
                module.__spec__.name,
                [x for x in dir(module._lower) if not x.startswith("__")],
            )
            builtins.__import__ = original_import


class MergedModuleFinder(MetaPathFinder):
    """Finder that creates merged modules combining upper and lower modules."""

    def __init__(
        self,
        merged_name: str,
        upper_name: str,
        lower_name: str,
    ) -> None:
        self.merged_name = merged_name
        self.upper_name = upper_name
        self.lower_name = lower_name
        self.cache: dict[str, types.ModuleType] = {}

    def find_spec(
        self,
        fullname: str,
        path: list[str] | None = None,
        target: types.ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
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
            cache=self.cache,
        )

        # Create a spec for the merged module
        return importlib.util.spec_from_loader(
            fullname,
            loader,
            origin=None,
            is_package=True,  # Allow submodules
        )


def shim(upper: str, lower: str, as_name: str | None = None) -> types.ModuleType:
    """Create a merged module combining upper and lower modules.

    Args:
        upper: Name of the module containing overrides
        lower: Name of the target module to enhance
        as_name: Optional name for the merged module (defaults to '{lower}_shim')

    Returns:
        A new module that combines both modules, with upper taking precedence
    """
    merged_name = as_name or f"{lower}_shim"

    log.debug("Creating merged module: %s", merged_name)
    log.debug("Upper module: %s", upper)
    log.debug("Lower module: %s", lower)

    finder = MergedModuleFinder(merged_name, upper, lower)
    sys.meta_path.insert(0, finder)

    # Import the merged module
    merged_module = importlib.import_module(merged_name)
    sys.modules[merged_name] = merged_module
    log.debug(
        "Merged module contents: %s",
        [x for x in dir(merged_module) if not x.startswith("__")],
    )

    return merged_module
