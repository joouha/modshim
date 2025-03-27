"""Various example test cases for modshim."""

from modshim import shim

# AI! Add docstrings to all test function


def test_circular_import() -> None:
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
    try:
        import tests.cases.circular_b.layout

        assert True
    except ImportError as exc:
        raise AssertionError(
            "Import of `tests.cases.circular_b.layout` failed"
        ) from exc

    assert hasattr(tests.cases.circular_b.layout.containers, "Container")
