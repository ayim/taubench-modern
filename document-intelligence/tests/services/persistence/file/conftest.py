import pytest


@pytest.fixture(autouse=True)
def clean_tables():
    """Override the global autouse `clean_tables` fixture for this test subtree.

    The repository-wide document-intelligence test suite bootstraps external datasources
    (MindsDB) via an autouse fixture, which is not needed for these unit tests.
    """

    # Intentionally no-op.
    return None
