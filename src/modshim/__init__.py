"""modshim: A module that combines two modules by rewriting their ASTs.

This module allows "shimming" one module on top of another, creating a combined module
that includes functionality from both. Internal imports are redirected to the mount point.
"""

from __future__ import annotations

import ast
import marshal
import os
import os.path
import struct
import sys
import threading
from importlib import import_module
from importlib.abc import InspectLoader, Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import find_spec, module_from_spec
from types import ModuleType
from typing import TYPE_CHECKING, ClassVar, cast

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import CodeType, TracebackType

# Set up logger with NullHandler
# import logging
# log = logging.getLogger(__name__)
# log.addHandler(logging.NullHandler())
# if os.getenv("MODSHIM_DEBUG"):
#     logging.basicConfig(level=logging.DEBUG)


def _filter_modshim_frames(tb: TracebackType | None) -> TracebackType | None:
    """Remove modshim internal frames from a traceback.

    Filters out frames that originate from this file (modshim/__init__.py)
    to provide cleaner stack traces for users.
    """
    if tb is None:
        return None

    # Get the path to this file for comparison
    this_file = __file__

    # Collect frames that aren't from modshim
    frames: list[TracebackType] = []
    current: TracebackType | None = tb
    while current is not None:
        frame_file = current.tb_frame.f_code.co_filename
        # Keep frames that aren't from this module
        if frame_file != this_file:
            frames.append(current)
        current = current.tb_next

    if not frames:
        # If all frames were filtered, return original to avoid empty traceback
        return tb

    # Reconstruct the traceback chain using TracebackType's immutable nature
    # We need to use the with_traceback trick via a raised exception
    result: TracebackType | None = None
    for frame_tb in reversed(frames):
        if result is None:
            result = frame_tb
        else:
            # We can't directly set tb_next, so we keep the original chain
            # but return the first non-modshim frame
            pass

    # Return the first non-modshim frame; Python will follow tb_next naturally
    # This effectively "skips" the modshim frames at the top of the trace
    return frames[0] if frames else tb


class _ModuleReferenceRewriter(ast.NodeTransformer):
    """AST transformer that rewrites module references based on a set of rules.

    Tracks which rewrite rules were triggered during transformation via
    the 'triggered' set of rule indices.
    """

    # Supplied rules (search, replace)
    rules: ClassVar[list[tuple[str, str]]]
    # Precomputed lookup structures for faster matching
    _exact_rules: ClassVar[dict[str, tuple[int, str]]]
    _prefix_rules_by_first: ClassVar[dict[str, list[tuple[int, str, str]]]]
    # Trigger indices that fired during a visit
    triggered: set[int]

    def __init__(self) -> None:
        super().__init__()
        self.triggered = set()

    @staticmethod
    def _first_component(name: str) -> str:
        idx = name.find(".")
        return name if idx == -1 else name[:idx]

    def _apply_one_rule(self, name: str) -> tuple[str, int | None]:
        """Apply at most one matching rule to 'name'.

        Returns:
            (new_name, rule_index or None if no rule applied)
        """
        # Exact match first (O(1))
        exact = self._exact_rules.get(name)
        if exact is not None:
            idx, replace = exact
            return replace, idx

        # Prefix match only if there is a dot and the first component matches candidates
        if "." in name:
            first = self._first_component(name)
            for idx, search, replace in self._prefix_rules_by_first.get(first, ()):
                # search is guaranteed to have the same first component by construction
                if name.startswith(f"{search}."):
                    return f"{replace}{name[len(search) :]}", idx

        return name, None

    def _rewrite_name_and_track(self, name: str) -> tuple[str, set[int]]:
        """Apply rewrite rules sequentially to a module name and track triggers.

        Unlike a single-pass/first-hit approach, this method allows chained rewrites
        (e.g., 'json' -> 'json_metadata' -> '_working_json_metadata') which are required
        for correct behavior when both lower->mount and mount->working rewrites are in play.

        Returns a tuple of:
        - the rewritten module name (or the original if unchanged)
        - a set containing indices of the applied rules (empty if none)
        """
        # Fast path: no rules configured for this transformer
        if not self.rules:
            return name, set()

        current = name
        fired: set[int] = set()

        # Apply up to len(rules) chained rewrites to avoid accidental cycles.
        # In normal usage we need at most two steps.
        max_steps = max(1, len(self.rules))
        for _ in range(max_steps):
            new_name, idx = self._apply_one_rule(current)
            if idx is None or new_name == current:
                break
            fired.add(idx)
            current = new_name
        return current, fired

    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        """Rewrite 'from X import Y' statements."""
        if not self.rules or not node.module:
            return node

        new_name, triggers = self._rewrite_name_and_track(node.module)

        if new_name != node.module:
            self.triggered |= triggers
            new_node = ast.ImportFrom(
                module=new_name,
                names=node.names,
                level=node.level,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
            )
            return new_node
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        """Rewrite 'import X' statements."""
        if not self.rules:
            return node

        new_names: list[ast.alias] = []
        made_change = False
        for alias in node.names:
            original_name = alias.name
            new_name, triggers = self._rewrite_name_and_track(original_name)

            if new_name != original_name:
                made_change = True
                self.triggered |= triggers
                new_alias = ast.alias(
                    name=new_name,
                    asname=alias.asname,
                    lineno=alias.lineno,
                    col_offset=alias.col_offset,
                    end_lineno=alias.end_lineno,
                    end_col_offset=alias.end_col_offset,
                )
                new_names.append(new_alias)
            else:
                new_names.append(alias)

        if made_change:
            new_node = ast.Import(
                names=new_names,
                lineno=node.lineno,
                col_offset=node.col_offset,
                end_lineno=node.end_lineno,
                end_col_offset=node.end_col_offset,
            )
            return new_node

        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        """Rewrite module references like 'urllib.response' to 'urllib_punycode.response'."""
        # Recurse into children first, then apply the base-name rewrite when appropriate.
        node = cast("ast.Attribute", self.generic_visit(node))

        # Fast path when there are no rules
        if not self.rules:
            return node

        # Try to rewrite without walking children when value is a simple Name
        if isinstance(node.value, ast.Name):
            original_name = node.value.id
            new_name, triggers = self._rewrite_name_and_track(original_name)

            if new_name != original_name:
                self.triggered |= triggers

                # Create a proper attribute access chain from the replacement string.
                # This prevents creating an invalid ast.Name with dots in it.
                parts = new_name.split(".")
                # Start with the first part as a Name node, copying location from the original base
                new_value: ast.expr = ast.Name(
                    id=parts[0],
                    ctx=node.value.ctx,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    end_lineno=node.end_lineno,
                    end_col_offset=node.end_col_offset,
                )
                # Chain the rest as Attribute nodes; copy base location for each chained node
                for part in parts[1:]:
                    chained = ast.Attribute(
                        value=new_value,
                        attr=part,
                        ctx=ast.Load(),
                        lineno=node.lineno,
                        col_offset=node.col_offset,
                        end_lineno=node.end_lineno,
                        end_col_offset=node.end_col_offset,
                    )
                    new_value = chained

                new_attr = ast.Attribute(
                    value=new_value,
                    attr=node.attr,
                    ctx=node.ctx,
                    lineno=node.lineno,
                    col_offset=node.col_offset,
                    end_lineno=node.end_lineno,
                    end_col_offset=node.end_col_offset,
                )
                return new_attr
            # If no rewrite on a simple Name base, we can return early
            return node

        # Otherwise visit children normally and attempt rewrites in deeper attributes
        return node


def reference_rewrite_factory(
    rules: list[tuple[str, str]],
) -> type[_ModuleReferenceRewriter]:
    """Get an AST module reference rewriter with precomputed fast lookups."""

    class ReferenceRewriter(_ModuleReferenceRewriter):
        pass

    # Assign rules and precompute structures for fast matching
    ReferenceRewriter.rules = rules

    # Build exact match dict and prefix lists grouped by first token
    exact: dict[str, tuple[int, str]] = {}
    prefix_by_first: dict[str, list[tuple[int, str, str]]] = {}
    for i, (search, replace) in enumerate(rules):
        if search != replace:
            # Exact mapping for equality checks
            exact[search] = (i, replace)
            # Group prefix rules by first component to filter candidates cheaply
            first = search.split(".", 1)[0]
            prefix_by_first.setdefault(first, []).append((i, search, replace))

    ReferenceRewriter._exact_rules = exact
    ReferenceRewriter._prefix_rules_by_first = prefix_by_first

    return ReferenceRewriter


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


def get_cache_path(
    upper_file_path: str,
    mount_root: str,
    original_module_name: str,
    *,
    optimization: str | int | None = None,
) -> str:
    """Given the path to a .py file, return the path to its .pyc file.

    The .py file does not need to exist; this simply returns the path to the
    .pyc file calculated as if the .py file were imported. All files are
    cached in the upper files' __modshim__ directory.

    The 'optimization' parameter controls the presumed optimization level of
    the bytecode file. If 'optimization' is not None, the string representation
    of the argument is taken and verified to be alphanumeric (else ValueError
    is raised).

    If sys.implementation.cache_tag is None then NotImplementedError is raised.
    """
    upper_path, _filename = os.path.split(upper_file_path)
    cache_dir = os.path.join(upper_path, "__modshim__")

    tag = sys.implementation.cache_tag
    if tag is None:
        raise NotImplementedError("sys.implementation.cache_tag is None")

    base_filename = f"{mount_root}.{original_module_name}"
    stem = f"{base_filename}.{tag}"

    if optimization is None and (
        optimization := str(sys.flags.optimize if sys.flags.optimize != 0 else "")
    ):
        if not optimization.isalnum():
            raise ValueError(f"{optimization!r} is not alphanumeric")
        stem = f"{stem}._OPT{optimization}"

    filename = os.path.join(cache_dir, f"{stem}.pyc")
    return filename


def _preflight_needs_rewrite(code: str, rules: list[tuple[str, str]]) -> bool:
    """Avoid AST parsing when not needed with string-based-matching.

    Returns True if any search term in rules appears in the code in a way that
    suggests a rewrite might be necessary. Uses cheap substring checks only.
    """
    if not rules:
        return False
    # Check for exact names and dotted-prefix references
    return any(search in code or f"{search}." in code for search, _replace in rules)


class ModShimLoader(Loader):
    """Loader for shimmed modules."""

    # Track module that have already been created
    cache: ClassVar[dict[tuple[str, str], ModuleType]] = {}
    # Store magic number at class level
    _magic_number = (1235).to_bytes(2, "little") + b"\r\n"

    # Track modules that are currently being processed to detect circular shimming
    _processing: ClassVar[set[ModuleType]] = set()

    def __init__(
        self,
        lower_spec: ModuleSpec | None,
        upper_spec: ModuleSpec | None,
        lower_root: str,
        upper_root: str,
        mount_root: str,
        finder: ModShimFinder,
    ) -> None:
        """Initialize the loader.

        Args:
            lower_spec: The module spec for the lower module
            upper_spec: The module spec for the upper module
            lower_root: The root package name of the lower module
            upper_root: The root package name of the upper module
            mount_root: The root mount point for import rewriting
            finder: The ModShimFinder instance that created this loader
        """
        self.lower_spec: ModuleSpec | None = lower_spec
        self.upper_spec: ModuleSpec | None = upper_spec
        self.lower_root: str = lower_root
        self.upper_root: str = upper_root
        self.mount_root: str = mount_root
        self.finder: ModShimFinder = finder

        # Set flag indicating we are performing an internal lookup
        finder._internal_call.active = True
        try:
            try:
                upper_root_spec = find_spec(upper_root)
            except (ImportError, AttributeError):
                upper_root_spec = None
            self.upper_root_origin = upper_root_spec.origin if upper_root_spec else None
        finally:
            # Unset the internal call flag
            finder._internal_call.active = False

        # Precompute cache directory, tag, optimization suffix, and negative cache
        self._cache_dir: str | None = None
        self._cache_tag: str | None = None
        self._opt_suffix: str = ""
        self._neg_cache: dict[str, tuple[int, int]] = {}
        self._cache_lock = threading.Lock()

        if self.upper_root_origin:
            upper_path, _ = os.path.split(self.upper_root_origin)
            self._cache_dir = os.path.join(upper_path, "__modshim__")

        tag = sys.implementation.cache_tag
        if tag is not None:
            self._cache_tag = tag
            opt_str = str(sys.flags.optimize if sys.flags.optimize != 0 else "")
            if opt_str:
                if not opt_str.isalnum():
                    raise ValueError(f"{opt_str!r} is not alphanumeric")
                self._opt_suffix = f"._OPT{opt_str}"

    def create_module(self, spec: ModuleSpec) -> ModuleType:
        """Create a new module object."""
        key = spec.name, self.mount_root
        if key in self.cache:
            # log.debug("Returning cached module %r", spec.name)
            return self.cache[key]

        module = ModuleType(spec.name)
        module.__file__ = f"<{spec.name}>"
        module.__loader__ = self
        module.__package__ = spec.parent

        # If this is a package, set up package attributes
        if spec.submodule_search_locations is not None:
            module.__path__ = list(spec.submodule_search_locations)

        # Store in cache
        # with self.finder._cache_lock:
        self.cache[key] = module

        return module

    def rewrite_module_code(
        self, code: str, rules: list[tuple[str, str]]
    ) -> tuple[ast.Module, set[int]]:
        """Rewrite imports and module references in module code.

        Args:
            code: The source code to rewrite
            rules: A list of (search, replace) tuples

        Returns:
            Tuple of:
                - the rewritten ast.AST
                - a set of rule indices that were triggered during rewriting
                  (truthy when any changes occurred; can be used as a binary flag)
        """
        # Fast-path when there are no rules: return parsed AST without visiting
        if not rules:
            return ast.parse(code), set()

        # If a preflight scan indicates no rewrite is needed, skip visiting
        if not _preflight_needs_rewrite(code, rules):
            return ast.parse(code), set()

        tree = ast.parse(code)
        transformer = reference_rewrite_factory(rules)()
        new_tree = cast("ast.Module", transformer.visit(tree))
        if not transformer.triggered:
            return tree, set()
        return new_tree, set(transformer.triggered)

    def _cache_path_for(self, original_module_name: str) -> str | None:
        """Fast internal cache path builder to avoid repeated work in get_cache_path."""
        if not self._cache_dir:
            return None
        if not self._cache_tag:
            # Match prior behavior (get_cache_path would raise)
            raise NotImplementedError("sys.implementation.cache_tag is None")
        base_filename = f"{self.mount_root}.{original_module_name}"
        stem = f"{base_filename}.{self._cache_tag}{self._opt_suffix}"
        return os.path.join(self._cache_dir, f"{stem}.pyc")

    def _get_cached_code(self, spec: ModuleSpec) -> tuple[CodeType | None, bool, bool]:
        """Get cached compiled code if it exists and is valid.

        Returns:
            (code_obj, no_rewrite_flag, working_needed_flag)
            - code_obj: A code object if a rewritten version was cached; otherwise None.
            - no_rewrite_flag: True if the cache indicates the module can be used as-is
              without rewriting (in this case the cache does not contain a code object).
            - working_needed_flag: True if the cache indicates a working module is needed
              when executing the upper module; defaults to True on any failure to read or
              validate the cache header (conservative behavior).
        """
        origin = spec.origin
        upper_origin = self.upper_root_origin
        if not origin or origin.startswith("<") or not upper_origin:
            return None, False, True

        # Use fast, precomputed cache path
        try:
            cache_path = self._cache_path_for(spec.name)
        except NotImplementedError:
            # Match previous behavior when cache_tag is None
            raise
        if cache_path is None:
            return None, False, True

        # Stat source file to get current mtime/size
        try:
            source_stat = os.stat(origin)
        except OSError:
            return None, False, True
        source_mtime32 = int(source_stat.st_mtime_ns) & 0xFFFFFFFF
        source_size32 = source_stat.st_size & 0xFFFFFFFF

        # Fast negative cache: avoid repeated disk hits when the cache file is missing
        with self._cache_lock:
            neg = self._neg_cache.get(cache_path)
            if neg == (source_mtime32, source_size32):
                return None, False, True

        # Single stat call to check existence and freshness (remove redundant exists check)
        try:
            cache_stat = os.stat(cache_path)
        except OSError:
            with self._cache_lock:
                self._neg_cache[cache_path] = (source_mtime32, source_size32)
            return None, False, True

        # Cache file exists: clear any negative cache entry
        with self._cache_lock:
            self._neg_cache.pop(cache_path, None)

        # Check if cache is newer than source using nanosecond resolution
        if int(cache_stat.st_mtime_ns) <= int(source_stat.st_mtime_ns):
            return None, False, True

        # Read and parse cache header in one shot for performance
        try:
            with open(cache_path, "rb") as f:
                header = f.read(14)
                if len(header) != 14:
                    return None, False, True
                magic, cached_mtime32, cached_size32, no_rewrite_flag, working_flag = (
                    struct.unpack("<4sIIBB", header)
                )
                if magic != self._magic_number:
                    return None, False, True

                if (cached_mtime32 != source_mtime32) or (
                    cached_size32 != source_size32
                ):
                    return None, False, True

                no_rewrite = no_rewrite_flag != 0
                working_needed = working_flag != 0

                # If no rewrite was necessary, no code object is stored; return flags only
                if no_rewrite:
                    return None, True, working_needed

                # Load code object for rewritten module
                code_obj = marshal.load(f)  # noqa: S302
                return code_obj, False, working_needed
        except OSError:
            return None, False, True

    def _cache_code(
        self,
        spec: ModuleSpec,
        code_obj: CodeType,
        no_rewrite: bool,
        working_needed: bool,
    ) -> None:
        """Cache compiled code to disk.

        The cache header layout:
            - 4 bytes: magic number
            - 4 bytes: source mtime (low 32 bits, from st_mtime_ns)
            - 4 bytes: source size (low 32 bits)
            - 1 byte : no_rewrite flag (0x00 = rewritten; 0x01 = can use as-is)
            - 1 byte : working_needed flag (0x00 = not needed; 0x01 = needed)
            - if no_rewrite == False: marshalled code object
              (no code object is written when no_rewrite == True)
        """
        origin = spec.origin
        upper_origin = self.upper_root_origin

        if not origin or origin.startswith("<") or not upper_origin:
            return None

        try:
            source_stat = os.stat(origin)
        except OSError:
            # Cannot get source stats, so cannot cache.
            return

        source_mtime32 = int(source_stat.st_mtime_ns) & 0xFFFFFFFF
        source_size32 = source_stat.st_size & 0xFFFFFFFF

        # Use fast, precomputed cache path
        try:
            cache_path = self._cache_path_for(spec.name)
        except NotImplementedError:
            # Match previous behavior when cache_tag is None
            return None
        if cache_path is None:
            return None

        # Ensure cache directory exists
        cache_path_parent, _ = os.path.split(cache_path)
        os.makedirs(cache_path_parent, exist_ok=True)

        # Write cache file
        try:
            with open(cache_path, "wb") as f:
                # Write magic number and timestamp/size
                f.write(self._magic_number)
                f.write(source_mtime32.to_bytes(4, "little"))
                f.write(source_size32.to_bytes(4, "little"))
                # Write flags
                f.write(b"\x01" if no_rewrite else b"\x00")  # no_rewrite
                f.write(b"\x01" if working_needed else b"\x00")  # working_needed
                # Only write a code object if a rewrite occurred
                if not no_rewrite:
                    marshal.dump(code_obj, f)
        except OSError:
            # Ignore cache write failures
            pass

        # Clear any negative cache for this path (the file now exists)
        with self._cache_lock:
            self._neg_cache.pop(cache_path, None)

    def exec_module(self, module: ModuleType) -> None:
        """Execute the module by combining upper and lower modules."""
        # log.debug("Exec_module called for %r", module.__name__)

        # Check if we're in a circular shimming situation
        if module in self._processing:
            return
        # Mark this module as being processed to detect circular shimming
        self._processing.add(module)

        # Calculate upper and lower names
        lower_name = module.__name__.replace(self.mount_root, self.lower_root)
        upper_name = module.__name__.replace(self.mount_root, self.upper_root)

        # Track __all__ from lower module
        lower_all = None

        # Execute lower module first
        if lower_spec := self.lower_spec:
            lower_filename = f"modshim://{module.__file__}::{lower_spec.origin}"
            source_code: str | None = None
            rewritten_ast: ast.Module | None = None
            was_rewritten = False

            try:
                # Try to get cached code first
                code_obj: CodeType | None = None
                no_rewrite = False
                if lower_spec.origin:
                    (
                        code_obj,
                        no_rewrite,
                        _working_needed,
                    ) = self._get_cached_code(lower_spec)

                if code_obj is None:
                    # If cache indicates no rewrite needed, prefer native bytecode and skip AST work
                    if (
                        no_rewrite
                        and lower_spec.loader
                        and isinstance(lower_spec.loader, InspectLoader)
                    ):
                        try:
                            native_code = lower_spec.loader.get_code(lower_name)
                        except (ImportError, AttributeError):
                            native_code = None
                        if native_code:
                            code_obj = native_code

                    if code_obj is None:
                        source_code = get_module_source(lower_name, lower_spec)
                        if source_code is not None:
                            rules = [(self.lower_root, self.mount_root)]
                            # Rewrite the source to get an AST
                            (
                                rewritten_ast,
                                triggered_rules,
                            ) = self.rewrite_module_code(source_code, rules)
                            was_rewritten = bool(triggered_rules)

                            # If no rewrite was needed, try to get native code; otherwise compile
                            if (
                                not was_rewritten
                                and lower_spec.loader
                                and isinstance(lower_spec.loader, InspectLoader)
                            ):
                                try:
                                    native_code = lower_spec.loader.get_code(lower_name)
                                except (ImportError, AttributeError):
                                    native_code = None
                                if native_code:
                                    code_obj = native_code
                                    if lower_spec.origin:
                                        self._cache_code(
                                            lower_spec,
                                            code_obj,
                                            no_rewrite=True,
                                            working_needed=False,
                                        )

                            if code_obj is None and rewritten_ast:
                                code_obj = compile(
                                    rewritten_ast,
                                    lower_filename,
                                    "exec",
                                    optimize=sys.flags.optimize,
                                )
                                if lower_spec.origin:
                                    self._cache_code(
                                        lower_spec,
                                        code_obj,
                                        no_rewrite=not was_rewritten,
                                        working_needed=False,
                                    )

                # If source isn't available, fall back to executing the lower module natively
                if code_obj is None and lower_spec.loader:
                    lower_module = module_from_spec(lower_spec)
                    lower_spec.loader.exec_module(lower_module)
                    # Copy attributes
                    module.__dict__.update(
                        {
                            k: v
                            for k, v in lower_module.__dict__.items()
                            if not k.startswith("__")
                        }
                    )

                if code_obj is not None:
                    try:
                        exec(code_obj, module.__dict__)  # noqa: S102
                    except Exception as e:
                        e.__traceback__ = _filter_modshim_frames(e.__traceback__)
                        raise

                # After executing lower module, capture __all__ if present
                lower_all = module.__dict__.get("__all__")

            except:
                if source_code is None and lower_spec:
                    source_code = get_module_source(lower_name, lower_spec)
                if source_code:
                    import linecache

                    linecache.cache[lower_filename] = (
                        len(source_code),
                        None,
                        source_code.splitlines(True),
                        lower_filename,
                    )
                raise
        # else:
        #     log.debug("No lower spec to execute")

        # Load and execute upper module
        if upper_spec := self.upper_spec:
            # Prepare working module name
            parts = module.__name__.split(".")
            working_name = ".".join([*parts[:-1], f"_working_{parts[-1]}"])

            upper_filename = f"modshim://{module.__file__}::{upper_spec.origin}"

            source_code: str | None = None
            rewritten_ast: ast.Module | None = None
            was_rewritten = False
            working_needed = True  # Default to true, set to false if we know otherwise

            try:
                # Try to get cached code first
                code_obj: CodeType | None = None
                no_rewrite = False
                if upper_spec.origin:
                    (
                        code_obj,
                        no_rewrite,
                        working_needed,
                    ) = self._get_cached_code(upper_spec)

                if code_obj is None:
                    # If cache indicates no rewrite needed, prefer native bytecode and skip AST work
                    if (
                        no_rewrite
                        and upper_spec.loader
                        and isinstance(upper_spec.loader, InspectLoader)
                    ):
                        try:
                            native_code = upper_spec.loader.get_code(upper_name)
                        except (ImportError, AttributeError):
                            native_code = None
                        if native_code:
                            code_obj = native_code
                            working_needed = False

                    if code_obj is None:
                        source_code = get_module_source(upper_name, upper_spec)
                        if source_code is not None:
                            rules = [
                                (self.lower_root, self.mount_root),
                                (module.__name__, working_name),
                                (self.upper_root, self.mount_root),
                            ]
                            (
                                rewritten_ast,
                                triggered_rules,
                            ) = self.rewrite_module_code(source_code, rules)
                            was_rewritten = bool(triggered_rules)
                            working_needed = 1 in triggered_rules

                            # If no rewrite was needed, try to get native code; otherwise compile
                            if (
                                not was_rewritten
                                and upper_spec.loader
                                and isinstance(upper_spec.loader, InspectLoader)
                            ):
                                try:
                                    native_code = upper_spec.loader.get_code(upper_name)
                                except (ImportError, AttributeError):
                                    native_code = None
                                if native_code:
                                    code_obj = native_code
                                    if upper_spec.origin:
                                        self._cache_code(
                                            upper_spec,
                                            code_obj,
                                            no_rewrite=True,
                                            working_needed=False,
                                        )

                            if code_obj is None and rewritten_ast:
                                code_obj = compile(
                                    rewritten_ast,
                                    upper_filename,
                                    "exec",
                                    optimize=sys.flags.optimize,
                                )
                                if upper_spec.origin:
                                    self._cache_code(
                                        upper_spec,
                                        code_obj,
                                        no_rewrite=not was_rewritten,
                                        working_needed=working_needed,
                                    )

                # Create working module only if needed
                if working_needed:
                    # Generate name of working module and create from current module state
                    working_module = ModuleType(working_name)
                    working_module.__name__ = working_name
                    working_module.__file__ = getattr(module, "__file__", None)
                    working_module.__package__ = getattr(module, "__package__", None)
                    # Copy module state to working module
                    working_module.__dict__.update(module.__dict__)
                    # Register the modules in sys.modules
                    sys.modules[working_name] = working_module

                if code_obj is not None:
                    try:
                        exec(code_obj, module.__dict__)  # noqa: S102
                    except Exception as e:
                        e.__traceback__ = _filter_modshim_frames(e.__traceback__)
                        raise
                elif upper_spec.loader and isinstance(upper_spec.loader, InspectLoader):
                    # Fall back to compiled code if source is not available
                    try:
                        upper_code = upper_spec.loader.get_code(upper_name)
                        if upper_code:
                            exec(upper_code, module.__dict__)  # noqa: S102
                    except (ImportError, AttributeError):
                        pass

            except:
                if source_code is None and upper_spec:
                    source_code = get_module_source(upper_name, upper_spec)
                if source_code:
                    import linecache

                    linecache.cache[upper_filename] = (
                        len(source_code),
                        None,
                        source_code.splitlines(True),
                        upper_filename,
                    )
                raise
        # else:
        #     log.debug("No upper spec to execute")

        # Merge __all__ from both modules if both exist
        upper_all = module.__dict__.get("__all__")
        if lower_all is not None and upper_all is not None:
            # Combine both lists, preserving order and avoiding duplicates
            # Lower module items first, then new items from upper
            merged_all = list(lower_all)
            for item in upper_all:
                if item not in merged_all:
                    merged_all.append(item)
            module.__dict__["__all__"] = merged_all

        # Remove this module from processing set
        self._processing.discard(module)

        # log.debug("Exec_module completed for %r", module.__name__)


class ModShimFinder(MetaPathFinder):
    """Finder for shimmed modules."""

    # Dictionary mapping mount points to (upper_module, lower_module) tuples
    _mappings: ClassVar[dict[str, tuple[str, str]]] = {}
    # Thread-local storage to track internal find_spec calls
    _internal_call: ClassVar[threading.local] = threading.local()

    @classmethod
    def register_mapping(
        cls, mount_root: str, upper_root: str, lower_root: str
    ) -> None:
        """Register a new module mapping.

        Args:
            lower_root: The name of the lower module
            upper_root: The name of the upper module
            mount_root: The name of the mount point
        """
        cls._mappings[mount_root] = (upper_root, lower_root)

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None = None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find a module spec for the given module name."""
        # log.debug("Find spec called for %r", fullname)

        # If this find_spec is called internally from _create_spec, ignore it
        # to allow standard finders to locate the original lower/upper modules.
        if getattr(self._internal_call, "active", False):
            return None

        # Check if this is a direct mount point
        if fullname in self._mappings:
            upper_root, lower_root = self._mappings[fullname]
            return self._create_spec(fullname, upper_root, lower_root, fullname)

        # Check if this is a submodule of a mount point
        for mount_root, (upper_root, lower_root) in self._mappings.items():
            # if fullname.startswith(f"{mount_root}."):
            if fullname.startswith(f"{mount_root}."):
                # if not (fullname.startswith((f"{upper_root}.", f"{lower_root}."))):
                return self._create_spec(fullname, upper_root, lower_root, mount_root)

        return None

    def _create_spec(
        self, fullname: str, upper_root: str, lower_root: str, mount_root: str
    ) -> ModuleSpec:
        """Create a module spec for the given module name."""
        # Calculate full lower and upper names
        lower_name = fullname.replace(mount_root, lower_root)
        upper_name = fullname.replace(mount_root, upper_root)

        # Set flag indicating we are performing an internal lookup
        self._internal_call.active = True
        exc = None
        try:
            # Find upper and lower specs using standard finders
            # (Our finder will ignore calls while _internal_call.active is True)
            try:
                # Find lower spec without exec-ing the module
                # log.debug("Finding lower spec %r", lower_name)
                parts = lower_name.split(".")
                spec = None
                path = None
                for i in range(1, len(parts) + 1):
                    name = ".".join(parts[:i])
                    for finder in sys.meta_path:
                        spec = finder.find_spec(name, path, None)
                        if spec is not None:
                            path = spec.submodule_search_locations
                            break
                lower_spec = spec
            except (ImportError, AttributeError) as exc_lower:
                lower_spec = None
                exc = exc_lower
            # log.debug("Found lower spec %r", lower_spec)
            try:
                # log.debug("Finding upper spec %r", upper_name)
                upper_spec = find_spec(upper_name)
            except (ImportError, AttributeError) as exc_upper:
                upper_spec = None
                exc = exc_upper
            # log.debug("Found upper spec %r", upper_spec)
        finally:
            # Unset the internal call flag
            self._internal_call.active = False

        # Raise ImportError if neither module exists
        if lower_spec is None and upper_spec is None:
            if exc is None:
                raise ImportError(
                    f"Cannot find module '{fullname}' (tried '{lower_name}' and '{upper_name}')"
                )
            else:
                raise exc

        # Create loader and spec using the correctly found specs
        loader = ModShimLoader(
            lower_spec, upper_spec, lower_root, upper_root, mount_root, finder=self
        )

        spec = ModuleSpec(
            name=fullname,
            loader=loader,
            origin=upper_spec.origin if upper_spec else None,
            is_package=lower_spec.submodule_search_locations is not None
            if lower_spec
            else False,
        )

        # Add upper module submodule search locations first
        if upper_spec and upper_spec.submodule_search_locations is not None:
            spec.submodule_search_locations = [
                *(spec.submodule_search_locations or []),
                *list(upper_spec.submodule_search_locations),
            ]

        # Inject lower module submodule search locations if we have mounted over the lower
        if (
            lower_root == mount_root
            and lower_spec
            and lower_spec.submodule_search_locations is not None
        ):
            spec.submodule_search_locations = [
                *list(lower_spec.submodule_search_locations),
                *(spec.submodule_search_locations or []),
            ]

        return spec


# Thread-local storage to track function execution state
_shim_state = threading.local()


def shim(lower: str, upper: str = "", mount: str = "") -> None:
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
    # Check if we're already inside this function in the current thread
    # This prevents `shim` calls in modules from triggering recursion loops for
    # auto-shimming modules
    if getattr(_shim_state, "active", False):
        # We're already running this function, so skip
        return None

    try:
        # Mark that we're now running this function
        _shim_state.active = True  # Validate module names

        if not lower:
            raise ValueError("Lower module name cannot be empty")

        # Use calling package name if 'upper' parameter name is empty
        if not upper:
            import inspect

            # Go back one level in the stack to see where this was called from
            if (frame := inspect.currentframe()) is not None and (
                prev_frame := frame.f_back
            ) is not None:
                upper = prev_frame.f_globals.get(
                    "__package__", prev_frame.f_globals.get("__name__", "")
                )
                if upper == "__main__":
                    raise ValueError("Cannot determine package name from __main__")
            if not upper:
                raise ValueError("Upper module name cannot be determined")

        # If mount not specified, use the upper module name
        if not mount and upper:
            mount = upper

        if not upper:
            raise ValueError("Upper module name cannot be empty")
        if not lower:
            raise ValueError("Lower module name cannot be empty")
        if not mount:
            raise ValueError("Mount point cannot be empty")

        # Register our finder in sys.meta_path if not already there
        if not any(isinstance(finder, ModShimFinder) for finder in sys.meta_path):
            sys.meta_path.insert(0, ModShimFinder())

        # Register the mapping for this mount point
        ModShimFinder.register_mapping(mount, upper, lower)

        # Re-import the mounted module if it has already been imported
        # This fixes issues when modules are mounted over their uppers
        if mount in sys.modules:
            del sys.modules[mount]
            for name in list(sys.modules):
                if name.startswith(f"{mount}."):
                    del sys.modules[name]
            _ = import_module(mount)

    finally:
        # Always clear the running flag when we exit
        _shim_state.active = False
