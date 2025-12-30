"""Various example test cases for modshim."""

import os
import traceback
from types import ModuleType

import pytest

from modshim import shim


def test_circular_import() -> None:
    """Test circular imports between modules using a third mount point.

    This test verifies that circular dependencies can be resolved by shimming
    two modules onto a third mount point.
    """
    shim(
        "tests.cases.circular_lower",
        "tests.cases.circular_upper",
        "tests.cases.circular_mount",
    )
    try:
        import tests.cases.circular_mount.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_mount.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_mount, ModuleType)
    assert isinstance(tests.cases.circular_mount.layout, ModuleType)
    assert isinstance(tests.cases.circular_mount.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_mount.layout.containers, "Container")


def test_circular_import_overmount() -> None:
    """Test circular imports by mounting one module onto itself.

    This test verifies that circular dependencies can be resolved by shimming
    one module onto itself, effectively overriding its own implementation.
    """
    shim(
        "tests.cases.circular_lower",
        "tests.cases.circular_upper",
        "tests.cases.circular_upper",
    )
    try:
        import tests.cases.circular_upper.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_upper.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_upper, ModuleType)
    assert isinstance(tests.cases.circular_upper.layout, ModuleType)
    assert isinstance(tests.cases.circular_upper.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_upper.layout.containers, "Container")


def test_circular_import_overmount_lower() -> None:
    """Test circular imports by mounting the shimmed module over the lower module.

    This test verifies that circular dependencies can be resolved when the mount
    point is the lower module itself.
    """
    shim(
        "tests.cases.circular_lower",
        "tests.cases.circular_upper",
        "tests.cases.circular_lower",
    )
    try:
        import tests.cases.circular_lower.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_lower.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_lower, ModuleType)
    assert isinstance(tests.cases.circular_lower.layout, ModuleType)
    assert isinstance(tests.cases.circular_lower.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_lower.layout.containers, "Container")


def test_circular_import_overmount_auto() -> None:
    """Test circular imports without explicit shimming.

    This test verifies that circular dependencies can be resolved
    automatically without explicitly calling shim() in the test itself.
    The shimming is handled in the module setup.
    """
    try:
        import tests.cases.circular_upper.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_upper.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_upper, ModuleType)
    assert isinstance(tests.cases.circular_upper.layout, ModuleType)
    assert isinstance(tests.cases.circular_upper.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_upper.layout.containers, "Container")


def test_extras_import() -> None:
    """Additional modules in upper are importable."""
    shim(
        "tests.cases.extras_lower",
        "tests.cases.extras_upper",
        "tests.cases.extras_mount",
    )

    try:
        import tests.cases.extras_mount.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_mount.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_mount, ModuleType)
    assert isinstance(tests.cases.extras_mount.mod, ModuleType)
    assert hasattr(tests.cases.extras_mount.mod, "x"), (
        "Cannot access attribute in lower module"
    )
    assert hasattr(tests.cases.extras_mount.mod, "y"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_mount.extra  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.extra_mount.extra` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_mount, ModuleType)
    assert isinstance(tests.cases.extras_mount.extra, ModuleType)
    assert hasattr(tests.cases.extras_mount.extra, "z"), (
        "Cannot access attribute in extra upper module"
    )


def test_extras_import_overmount() -> None:
    """Additional modules in upper are importable."""
    shim(
        "tests.cases.extras_lower",
        "tests.cases.extras_upper",
        "tests.cases.extras_upper",
    )

    try:
        import tests.cases.extras_upper.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_upper.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_upper, ModuleType)
    assert isinstance(tests.cases.extras_upper.mod, ModuleType)
    assert hasattr(tests.cases.extras_upper.mod, "x"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_upper.extra

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.extra_upper.extra` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_upper, ModuleType)
    assert isinstance(tests.cases.extras_upper.extra, ModuleType)
    assert hasattr(tests.cases.extras_upper.extra, "z"), (
        "Cannot access attribute in extra upper module"
    )


def test_extras_import_overmount_lower() -> None:
    """Additional modules in upper are importable when mounting over the lower module."""
    shim(
        "tests.cases.extras_lower",
        "tests.cases.extras_upper",
        "tests.cases.extras_lower",
    )

    try:
        import tests.cases.extras_lower.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extras_lower.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_lower, ModuleType)
    assert isinstance(tests.cases.extras_lower.mod, ModuleType)
    assert hasattr(tests.cases.extras_lower.mod, "x"), (
        "Cannot access attribute in lower module"
    )
    assert hasattr(tests.cases.extras_lower.mod, "y"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_lower.extra  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.extras_lower.extra` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_lower, ModuleType)
    assert isinstance(tests.cases.extras_lower.extra, ModuleType)
    assert hasattr(tests.cases.extras_lower.extra, "z"), (
        "Cannot access attribute in extra upper module"
    )


def test_extras_import_overmount_auto() -> None:
    """Additional modules in upper are importable when automounted over upper."""
    try:
        import tests.cases.extras_upper.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_upper.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_upper, ModuleType)
    assert isinstance(tests.cases.extras_upper.mod, ModuleType)
    assert hasattr(tests.cases.extras_upper.mod, "x"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_upper.extra

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.extra_upper.extra` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_upper, ModuleType)
    assert isinstance(tests.cases.extras_upper.extra, ModuleType)
    assert hasattr(tests.cases.extras_upper.extra, "z"), (
        "Cannot access attribute in extra upper module"
    )


def test_auto_shim_from_upper() -> None:
    """Test calling shim() with only the 'lower' argument from the upper package."""
    # The shim is called inside tests.cases.auto_mount_upper's __init__.py
    # When we import it, it should shim itself over auto_mount_lower
    try:
        # Import a module from the lower package, through the upper package mount
        import tests.cases.auto_mount_upper.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.auto_mount_upper.mod` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.auto_mount_upper, ModuleType)
    assert isinstance(tests.cases.auto_mount_upper.mod, ModuleType)
    assert hasattr(tests.cases.auto_mount_upper.mod, "x"), (
        "Cannot access attribute in lower module"
    )
    assert tests.cases.auto_mount_upper.mod.x == 11

    try:
        # Import an extra module from the upper package
        import tests.cases.auto_mount_upper.extra

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.auto_mount_upper.extra` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.auto_mount_upper, ModuleType)
    assert isinstance(tests.cases.auto_mount_upper.extra, ModuleType)
    assert hasattr(tests.cases.auto_mount_upper.extra, "y"), (
        "Cannot access attribute in extra upper module"
    )


def test_shim_call_at_start() -> None:
    """Test auto-shimming when shim() is called at the start of the upper module."""
    # Importing the upper module triggers the auto-shim.
    # The mount point becomes tests.cases.shim_call_ordering_upper_start
    try:
        # Import a module from the lower package, through the upper package mount
        import tests.cases.shim_call_ordering_upper_start.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.shim_call_ordering_upper_start.mod` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.shim_call_ordering_upper_start, ModuleType)
    assert isinstance(tests.cases.shim_call_ordering_upper_start.mod, ModuleType)
    assert hasattr(tests.cases.shim_call_ordering_upper_start.mod, "x")
    assert tests.cases.shim_call_ordering_upper_start.mod.x == 100

    try:
        # Import an extra module from the upper package
        import tests.cases.shim_call_ordering_upper_start.extra  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.shim_call_ordering_upper_start.extra` failed"
        ) from exc

    assert isinstance(tests.cases.shim_call_ordering_upper_start.extra, ModuleType)
    assert hasattr(tests.cases.shim_call_ordering_upper_start.extra, "y")
    assert tests.cases.shim_call_ordering_upper_start.extra.y == 200
    assert tests.cases.shim_call_ordering_upper_start.some_var == "start"


def test_shim_call_at_end() -> None:
    """Test auto-shimming when shim() is called at the end of the upper module."""
    # Importing the upper module triggers the auto-shim.
    # The mount point becomes tests.cases.shim_call_ordering_upper_end
    try:
        # Import a module from the lower package, through the upper package mount
        import tests.cases.shim_call_ordering_upper_end.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.shim_call_ordering_upper_end.mod` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.shim_call_ordering_upper_end, ModuleType)
    assert isinstance(tests.cases.shim_call_ordering_upper_end.mod, ModuleType)
    assert hasattr(tests.cases.shim_call_ordering_upper_end.mod, "x")
    assert tests.cases.shim_call_ordering_upper_end.mod.x == 100

    try:
        # Import an extra module from the upper package
        import tests.cases.shim_call_ordering_upper_end.extra  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.shim_call_ordering_upper_end.extra` failed"
        ) from exc

    assert isinstance(tests.cases.shim_call_ordering_upper_end.extra, ModuleType)
    assert hasattr(tests.cases.shim_call_ordering_upper_end.extra, "y")
    assert tests.cases.shim_call_ordering_upper_end.extra.y == 200
    assert tests.cases.shim_call_ordering_upper_end.some_var == "end"


def test_stack_trace_lines_for_upper_import_error() -> None:
    """Verify that tracebacks for errors in the upper module are correct."""
    # Mount upper on lower
    shim(
        lower="tests.cases.tracebacks_lower",
        upper="tests.cases.tracebacks_upper",
        mount="mount_point",
    )

    with pytest.raises(RuntimeError) as excinfo:
        import mount_point.a as a  # pyright: ignore [reportMissingImports  # noqa: F401

    # Inspect traceback frames
    frames = traceback.extract_tb(excinfo.value.__traceback__)
    # Find the frame that corresponds to the upper module (should be the raising line)
    target = None
    for f in frames:
        if (
            f.filename.startswith("modshim://")
            and os.path.join("tracebacks_upper", "a.py") in f.filename
        ):
            target = f
            break

    assert target is not None, f"No upper frame found in traceback: {frames}"
    # The raise is on line 5 of the file
    assert target.lineno == 5
    assert target.line is not None
    assert target.line.strip() == 'raise RuntimeError("boom during upper import")'


def test_stack_trace_lines_for_lower_import_error() -> None:
    """Verify that tracebacks for errors in the lower module are correct."""
    shim(
        lower="tests.cases.tracebacks_lower",
        upper="tests.cases.tracebacks_upper",
        mount="mount_point",
    )

    with pytest.raises(RuntimeError) as excinfo:
        import mount_point.b as b  # pyright: ignore [reportMissingImports  # noqa: F401

    frames = traceback.extract_tb(excinfo.value.__traceback__)
    target = None
    for f in frames:
        if (
            f.filename.startswith("modshim://")
            and os.path.join("tracebacks_lower", "b.py") in f.filename
        ):
            target = f
            break

    assert target is not None, f"No lower frame found in traceback: {frames}"
    assert target.lineno == 5
    assert target.line is not None
    assert target.line.strip() == 'raise RuntimeError("boom during lower import")'


def test_star_import_from_mount_point() -> None:
    """Test that star imports from a shimmed mount point bring in expected names."""
    shim(
        "tests.cases.extras_lower",
        "tests.cases.extras_upper",
        "tests.cases.extras_mount",
    )

    namespace: dict[str, object] = {}
    exec("from tests.cases.extras_mount.mod import *", namespace)  # noqa: S102

    assert "x" in namespace
    assert namespace["x"] == 1
    assert "y" in namespace
    assert namespace["y"] == 2


def test_star_import_from_upper() -> None:
    """Test that star imports from an overmounted upper module bring in expected names."""
    shim(
        "tests.cases.extras_lower",
        "tests.cases.extras_upper",
        "tests.cases.extras_upper",
    )

    namespace: dict[str, object] = {}
    exec("from tests.cases.extras_upper.mod import *", namespace)  # noqa: S102

    assert "x" in namespace
    assert namespace["x"] == 1
    assert "y" in namespace
    assert namespace["y"] == 2


def test_star_import_extra_module_from_upper() -> None:
    """Test that star imports from an extra module in upper bring in its names."""
    shim(
        "tests.cases.extras_lower",
        "tests.cases.extras_upper",
        "tests.cases.extras_upper",
    )

    namespace: dict[str, object] = {}
    exec("from tests.cases.extras_upper.extra import *", namespace)  # noqa: S102

    assert "z" in namespace
    assert namespace["z"] == 1


def test_star_import_auto_mount_upper() -> None:
    """Test star imports when upper auto-mounts itself over lower."""
    namespace: dict[str, object] = {}
    exec("from tests.cases.auto_mount_upper.mod import *", namespace)  # noqa: S102

    assert "x" in namespace
    assert namespace["x"] == 11

    namespace_extra: dict[str, object] = {}
    exec("from tests.cases.auto_mount_upper.extra import *", namespace_extra)  # noqa: S102

    assert "y" in namespace_extra
    assert namespace_extra["y"] == 20


def test_all_merged_from_both() -> None:
    """Test that __all__ is correctly merged from both lower and upper modules."""
    shim(
        "tests.cases.all_lower",
        "tests.cases.all_upper",
        "tests.cases.all_mount",
    )

    import tests.cases.all_mount.mod  # pyright: ignore [reportMissingImports]

    # Verify __all__ exists and contains items from both modules
    assert hasattr(tests.cases.all_mount.mod, "__all__")
    all_list = tests.cases.all_mount.mod.__all__

    # Should contain items from lower first: ["x", "y"]
    # Then new items from upper: ["a", "b"]
    # "y" appears in both, so should only appear once (from lower position)
    assert all_list == ["x", "y", "a", "b"]

    # Verify all the expected attributes exist
    assert tests.cases.all_mount.mod.x == 1
    assert tests.cases.all_mount.mod.y == 22  # Upper overrides lower
    assert tests.cases.all_mount.mod.z == 3  # From lower but not in __all__
    assert tests.cases.all_mount.mod.a == 10
    assert tests.cases.all_mount.mod.b == 20


def test_all_star_import_merged() -> None:
    """Test that star imports respect the merged __all__."""
    shim(
        "tests.cases.all_lower",
        "tests.cases.all_upper",
        "tests.cases.all_mount",
    )

    namespace: dict[str, object] = {}
    exec("from tests.cases.all_mount.mod import *", namespace)  # noqa: S102

    # Should include items in merged __all__
    assert "x" in namespace
    assert namespace["x"] == 1
    assert "y" in namespace
    assert namespace["y"] == 22  # Upper value
    assert "a" in namespace
    assert namespace["a"] == 10
    assert "b" in namespace
    assert namespace["b"] == 20

    # Should NOT include items not in __all__
    assert "z" not in namespace  # From lower but not in __all__
    assert "_private" not in namespace  # Private variable


def test_all_only_lower_has_all() -> None:
    """Test __all__ when only the lower module defines it."""
    shim(
        "tests.cases.all_lower_only",
        "tests.cases.all_upper_only",
        "tests.cases.all_mount_lower_only",
    )

    import tests.cases.all_mount_lower_only.mod  # pyright: ignore [reportMissingImports]

    # Should only have __all__ from lower since upper doesn't define it
    assert hasattr(tests.cases.all_mount_lower_only.mod, "__all__")
    all_list = tests.cases.all_mount_lower_only.mod.__all__
    assert all_list == ["x", "y"]


def test_all_only_upper_has_all() -> None:
    """Test __all__ when only the upper module defines it."""
    shim(
        "tests.cases.all_upper_only",
        "tests.cases.all_lower_only",
        "tests.cases.all_mount_upper_only",
    )

    import tests.cases.all_mount_upper_only.mod  # pyright: ignore [reportMissingImports]

    # Should only have __all__ from upper (which is actually lower in this reversed shim)
    assert hasattr(tests.cases.all_mount_upper_only.mod, "__all__")
    all_list = tests.cases.all_mount_upper_only.mod.__all__
    assert all_list == ["x", "y"]


def test_all_merged_overmount() -> None:
    """Test __all__ merging when overmounting (mount == upper)."""
    shim(
        "tests.cases.all_lower",
        "tests.cases.all_upper",
        "tests.cases.all_upper",
    )

    import tests.cases.all_upper.mod  # pyright: ignore [reportMissingImports]

    # Should have merged __all__
    assert hasattr(tests.cases.all_upper.mod, "__all__")
    all_list = tests.cases.all_upper.mod.__all__
    assert all_list == ["x", "y", "a", "b"]

    # Test star import
    namespace: dict[str, object] = {}
    exec("from tests.cases.all_upper.mod import *", namespace)  # noqa: S102

    assert "x" in namespace
    assert "y" in namespace
    assert "a" in namespace
    assert "b" in namespace
    assert "z" not in namespace
    assert "_private" not in namespace


def test_upper_only_submodule_with_relative_import() -> None:
    """Test that upper modules can use relative imports to import upper-only submodules."""
    shim(
        "tests.cases.relative_import_lower",
        "tests.cases.relative_import_upper",
        "tests.cases.relative_import_mount",
    )

    # This should work: the upper's __init__.py does a relative import of .extra
    # which should resolve to tests.cases.relative_import_mount.extra
    # and the finder should find tests.cases.relative_import_upper.extra
    import tests.cases.relative_import_mount  # pyright: ignore [reportMissingImports]

    assert hasattr(tests.cases.relative_import_mount, "something")
    assert tests.cases.relative_import_mount.something == 42


def test_modshim_frames_filtered_from_traceback() -> None:
    """Test that modshim internal frames are filtered from exception tracebacks."""
    shim(
        lower="tests.cases.tracebacks_lower",
        upper="tests.cases.tracebacks_upper",
        mount="mount_point_filter_test",
    )

    with pytest.raises(RuntimeError) as excinfo:
        import mount_point_filter_test.a  # pyright: ignore [reportMissingImports]  # noqa: F401

    # Extract all frames from the traceback
    frames = traceback.extract_tb(excinfo.value.__traceback__)

    # Verify no frames come from modshim/__init__.py
    modshim_frames = [
        f
        for f in frames
        if "modshim" in f.filename
        and f.filename.endswith("__init__.py")
        and "tests"
        not in f.filename  # Exclude test files that might have "modshim" in path
    ]

    assert len(modshim_frames) == 0, (
        f"Expected no modshim internal frames in traceback, but found: "
        f"{[(f.filename, f.name, f.lineno) for f in modshim_frames]}"
    )

    # Verify the traceback still contains the actual error location
    error_frames = [
        f for f in frames if "tracebacks_upper" in f.filename and "a.py" in f.filename
    ]
    assert len(error_frames) >= 1, (
        "Expected at least one frame from the upper module where the error occurred"
    )


def test_modshim_frames_filtered_lower_module_error() -> None:
    """Test that modshim frames are filtered when error occurs in lower module."""
    shim(
        lower="tests.cases.tracebacks_lower",
        upper="tests.cases.tracebacks_upper",
        mount="mount_point_filter_test_lower",
    )

    with pytest.raises(RuntimeError) as excinfo:
        import mount_point_filter_test_lower.b  # pyright: ignore [reportMissingImports]  # noqa: F401

    frames = traceback.extract_tb(excinfo.value.__traceback__)

    # Verify no frames come from modshim/__init__.py
    modshim_frames = [
        f
        for f in frames
        if "modshim" in f.filename
        and f.filename.endswith("__init__.py")
        and "tests" not in f.filename
    ]

    assert len(modshim_frames) == 0, (
        f"Expected no modshim internal frames in traceback, but found: "
        f"{[(f.filename, f.name, f.lineno) for f in modshim_frames]}"
    )

    # Verify the traceback contains the actual error location in lower module
    error_frames = [
        f for f in frames if "tracebacks_lower" in f.filename and "b.py" in f.filename
    ]
    assert len(error_frames) >= 1, (
        "Expected at least one frame from the lower module where the error occurred"
    )


def test_traceback_preserves_user_frames() -> None:
    """Test that user code frames are preserved while modshim frames are filtered."""
    shim(
        lower="tests.cases.tracebacks_lower",
        upper="tests.cases.tracebacks_upper",
        mount="mount_point_preserve_test",
    )

    with pytest.raises(RuntimeError) as excinfo:
        import mount_point_preserve_test.a  # pyright: ignore [reportMissingImports]  # noqa: F401

    frames = traceback.extract_tb(excinfo.value.__traceback__)

    # The traceback should have at least the test frame and the error frame
    assert len(frames) >= 1, "Traceback should not be empty"

    # Verify we can still see the actual error source
    frame_files = [f.filename for f in frames]
    has_error_source = any(
        "tracebacks_upper" in f or "tracebacks_lower" in f for f in frame_files
    )
    assert has_error_source, (
        f"Traceback should contain the error source file, got: {frame_files}"
    )
