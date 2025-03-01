
"""Module for creating merged virtual Python modules that overlay objects from an upper module onto a lower module."""

import builtins
import importlib.util
import sys
import types
from importlib.abc import Loader, MetaPathFinder
from typing import Any, Mapping


def create_redirected_class(orig_class: type, merged_module: types.ModuleType) -> type:
    """Creates a new class with redirected base classes and updated method references.
    
    Args:
        orig_class: The original class to redirect
        merged_module: The merged module containing redirected references
        
    Returns:
        A new class with updated bases and method references
    """
    # Create new class with updated bases
    bases = []
    for base in orig_class.__bases__:
        if base.__module__ == merged_module._lower.__name__:
            redirected_base = getattr(merged_module, base.__name__)
            bases.append(redirected_base)
        else:
            bases.append(base)
            
    # Create new class with updated namespace
    namespace = dict(orig_class.__dict__)
    
    # Update any class-level references to lower module
    for key, value in namespace.items():
        if isinstance(value, types.FunctionType):
            # Update method globals like we do for functions
            new_globals = dict(value.__globals__)
            new_globals["__name__"] = merged_module.__name__
            new_globals["__package__"] = merged_module.__package__
            
            # Redirect module references
            for k, v in new_globals.items():
                if isinstance(v, types.ModuleType):
                    if v.__name__ == merged_module._lower.__name__:
                        new_globals[k] = merged_module
                    elif v.__name__.startswith(merged_module._lower.__name__ + "."):
                        merged_name = merged_module.__name__ + v.__name__[len(merged_module._lower.__name__):]
                        new_globals[k] = sys.modules.get(merged_name)
                        
            namespace[key] = types.FunctionType(
                value.__code__,
                new_globals,
                value.__name__,
                value.__defaults__,
                value.__closure__,
            )
            
    return type(orig_class.__name__, tuple(bases), namespace)


class MergedModule(types.ModuleType):
    """A module that combines attributes from upper and lower modules."""

    def __init__(self, name: str, upper_module: types.ModuleType, lower_module: types.ModuleType) -> None:
        super().__init__(name)
        self._upper = upper_module
        self._lower = lower_module
        self._lower_dict: dict[str, Any] = {}

    def __getattr__(self, name: str) -> Any:
        # First check upper module
        try:
            return getattr(self._upper, name)
        except AttributeError:
            pass

        # Then check lower module
        try:
            value = getattr(self._lower, name)

            # If this is an import from the lower module, we need to redirect it
            if isinstance(value, type) and value.__module__ == self._lower.__name__:
                # Check if we already have this class in our merged module
                if hasattr(self, value.__name__):
                    return getattr(self, value.__name__)

            return value
        except AttributeError:
            raise


class MergedModuleLoader(Loader):
    """Loader that creates merged modules combining upper and lower modules."""

    def __init__(
        self,
        merged_name: str,
        upper_name: str,
        lower_name: str,
        cache: Mapping[str, types.ModuleType],
    ) -> None:
        self.merged_name = merged_name
        self.upper_name = upper_name
        self.lower_name = lower_name
        self.cache = cache

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> types.ModuleType:
        # If already merged, return from cache
        if spec.name in self.cache:
            return self.cache[spec.name]

        # Import both modules
        try:
            upper_module = importlib.import_module(self.upper_name)
        except ImportError:
            upper_module = types.ModuleType(self.upper_name)

        lower_module = importlib.import_module(self.lower_name)

        # Create merged module
        merged = MergedModule(spec.name, upper_module, lower_module)
        merged.__package__ = spec.parent
        merged.__path__ = getattr(lower_module, "__path__", None)

        # Store in cache
        self.cache[spec.name] = merged
        return merged

    def exec_module(self, module: types.ModuleType) -> None:
        # Store original import
        original_import = builtins.__import__

        def custom_import(
            name: str,
            globals: dict[str, Any] | None = None,
            locals: dict[str, Any] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> types.ModuleType:
            # Handle relative imports within the merged module namespace
            if level > 0 and globals:
                package = globals.get("__package__", "")
                
                # If this is an import from the lower module
                if package == self.lower_name or package.startswith(self.lower_name + "."):
                    # Map it to our merged namespace
                    merged_package = self.merged_name + package[len(self.lower_name):]
                    
                    if level > 1:
                        package_parts = merged_package.split(".")
                        merged_name = ".".join(package_parts[:-level+1] + ([name] if name else []))
                    else:
                        merged_name = merged_package + ("." + name if name else "")
                        
                    # Import through our merged module system
                    return importlib.import_module(merged_name)
                    
                # Handle existing merged module relative imports
                elif package.startswith(self.merged_name):
                    if level > 1:
                        package_parts = package.split(".")
                        name = ".".join(package_parts[:-level+1] + ([name] if name else []))
                    else:
                        name = package + ("." + name if name else "")
                        
                    return importlib.import_module(name)

            # For absolute imports, check if we're importing from the target module
            if name == self.lower_name or name.startswith(self.lower_name + "."):
                # Redirect to merged module
                merged_name = self.merged_name + name[len(self.lower_name):]
                return importlib.import_module(merged_name)

            # Otherwise use normal import
            return original_import(name, globals, locals, fromlist, level)

        try:
            # Install custom import
            builtins.__import__ = custom_import

            # Copy attributes from lower first
            for name, value in vars(module._lower).items():
                if not name.startswith("_"):
                    if (isinstance(value, type) and 
                        not isinstance(value, type(object)) and  # Skip built-in types
                        not hasattr(value, '__slots__')):  # Skip types with slots
                        # Create redirected class with updated references
                        try:
                            value = create_redirected_class(value, module)
                        except TypeError:
                            # If we can't create redirected class, use original value
                            pass
                    elif isinstance(value, types.FunctionType):
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
                                    merged_name = self.merged_name + v.__name__[len(self.lower_name) :]
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
            builtins.__import__ = original_import


class MergedModuleFinder(MetaPathFinder):
    """Finder that creates merged modules combining upper and lower modules."""

    def __init__(self, merged_name: str, upper_name: str, lower_name: str) -> None:
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
        if not fullname.startswith(self.merged_name):
            return None

        # Calculate corresponding paths in upper and lower modules
        relative_path = fullname[len(self.merged_name) :].lstrip(".")
        upper_fullname = (self.upper_name + relative_path) if relative_path else self.upper_name
        lower_fullname = (self.lower_name + relative_path) if relative_path else self.lower_name

        # Create loader
        loader = MergedModuleLoader(fullname, upper_fullname, lower_fullname, self.cache)

        # Create a spec for the merged module
        return importlib.util.spec_from_loader(
            fullname,
            loader,
            origin=None,
            is_package=True  # Allow submodules
        )


def merge(upper: str, lower: str, as_name: str | None = None) -> types.ModuleType:
    """Create a merged module combining upper and lower modules.

    Args:
        upper: Name of the module containing overrides
        lower: Name of the target module to enhance
        as_name: Optional name for the merged module (defaults to merged_{lower})

    Returns:
        A new module that combines both modules, with upper taking precedence
    """
    merged_name = as_name or f"merged_{lower}"
    finder = MergedModuleFinder(merged_name, upper, lower)
    sys.meta_path.insert(0, finder)
    return importlib.import_module(merged_name)
