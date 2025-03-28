"""Various example test cases for modshim."""

from types import ModuleType

from modshim import shim


def test_circular_import() -> None:
    """Test circular imports between modules using a third mount point.

    This test verifies that circular dependencies can be resolved by shimming
    two modules onto a third mount point.
    """
    shim(
        "tests.cases.circular_a",
        "tests.cases.circular_b",
        "tests.cases.circular_c",
    )
    try:
        import tests.cases.circular_c.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_c.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_c, ModuleType)
    assert isinstance(tests.cases.circular_c.layout, ModuleType)
    assert isinstance(tests.cases.circular_c.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_c.layout.containers, "Container")


def test_circular_import_overmount() -> None:
    """Test circular imports by mounting one module onto itself.

    This test verifies that circular dependencies can be resolved by shimming
    one module onto itself, effectively overriding its own implementation.
    """
    shim(
        "tests.cases.circular_a",
        "tests.cases.circular_b",
        "tests.cases.circular_b",
    )
    try:
        import tests.cases.circular_b.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_b.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_b, ModuleType)
    assert isinstance(tests.cases.circular_b.layout, ModuleType)
    assert isinstance(tests.cases.circular_b.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_b.layout.containers, "Container")


def test_circular_import_overmount_auto() -> None:
    """Test circular imports without explicit shimming.

    This test verifies that circular dependencies can be resolved
    automatically without explicitly calling shim() in the test itself.
    The shimming is handled in the module setup.
    """
    try:
        import tests.cases.circular_b.layout  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_b.layout` failed"
        ) from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.circular_b, ModuleType)
    assert isinstance(tests.cases.circular_b.layout, ModuleType)
    assert isinstance(tests.cases.circular_b.layout.containers, ModuleType)
    assert hasattr(tests.cases.circular_b.layout.containers, "Container")


def test_extras_import() -> None:
    """Additional modules in upper are importable."""
    shim("tests.cases.extras_a", "tests.cases.extras_b", "tests.cases.extras_c")

    try:
        import tests.cases.extras_c.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_c.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_c, ModuleType)
    assert isinstance(tests.cases.extras_c.mod, ModuleType)
    assert hasattr(tests.cases.extras_c.mod, "x"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_c.extra  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_c.extra` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_c, ModuleType)
    assert isinstance(tests.cases.extras_c.extra, ModuleType)
    assert hasattr(tests.cases.extras_c.extra, "y"), (
        "Cannot access attribute in extra upper module"
    )


def test_extras_import_overmount() -> None:
    """Additional modules in upper are importable."""
    shim("tests.cases.extras_a", "tests.cases.extras_b", "tests.cases.extras_b")

    try:
        import tests.cases.extras_b.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_b.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_b, ModuleType)
    assert isinstance(tests.cases.extras_b.mod, ModuleType)
    assert hasattr(tests.cases.extras_b.mod, "x"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_b.extra

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_b.extra` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_b, ModuleType)
    assert isinstance(tests.cases.extras_b.extra, ModuleType)
    assert hasattr(tests.cases.extras_b.extra, "y"), (
        "Cannot access attribute in extra upper module"
    )


def test_extras_import_overmount_auto() -> None:
    """Additional modules in upper are importable when automounted over upper."""
    try:
        import tests.cases.extras_b.mod  # pyright: ignore [reportMissingImports]

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_b.mod` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_b, ModuleType)
    assert isinstance(tests.cases.extras_b.mod, ModuleType)
    assert hasattr(tests.cases.extras_b.mod, "x"), (
        "Cannot access attribute in lower module"
    )

    try:
        import tests.cases.extras_b.extra

        assert True
    except ImportError as exc:
        raise AssertionError("Import of `tests.cases.extra_b.extra` failed") from exc

    assert isinstance(tests, ModuleType)
    assert isinstance(tests.cases, ModuleType)
    assert isinstance(tests.cases.extras_b, ModuleType)
    assert isinstance(tests.cases.extras_b.extra, ModuleType)
    assert hasattr(tests.cases.extras_b.extra, "y"), (
        "Cannot access attribute in extra upper module"
    )
