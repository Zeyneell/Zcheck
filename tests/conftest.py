import pytest

from zcheck.core import registry


@pytest.fixture(autouse=True)
def clean_registry():
    """Every test starts and ends with an empty registry for isolation."""
    registry.clear()
    yield
    registry.clear()
