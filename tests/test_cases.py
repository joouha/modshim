"""Various example test cases for modshim."""

from types import ModuleType

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
    assert hasattr(tests.cases.extras_mount.extra, "y"), (
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
    assert hasattr(tests.cases.extras_upper.extra, "y"), (
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
    assert hasattr(tests.cases.extras_upper.extra, "y"), (
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
