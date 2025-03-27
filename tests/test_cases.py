"""Various example test cases for modshim."""

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
        import tests.cases.circular_c.layout

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_c.layout` failed"
        ) from exc

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
        import tests.cases.circular_b.layout

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_b.layout` failed"
        ) from exc

    assert hasattr(tests.cases.circular_b.layout.containers, "Container")


def test_circular_import_overmount_auto() -> None:
    """Test circular imports without explicit shimming.
    
    This test verifies that circular dependencies can be resolved 
    automatically without explicitly calling shim() in the test itself.
    The shimming is likely handled in the conftest or module setup.
    """
    try:
        import tests.cases.circular_b.layout

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_b.layout` failed"
        ) from exc

    assert hasattr(tests.cases.circular_b.layout.containers, "Container")
