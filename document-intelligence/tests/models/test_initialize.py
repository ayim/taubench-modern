from sema4ai.data import DataSource

from sema4ai_docint.models import initialize_database
from sema4ai_docint.models.initialize import _get_missing_views


def test_initialize_database(postgres_datasource: DataSource):
    """Test that we can interact with a UseCase model."""
    # Initialize the database
    initialize_database("postgres", postgres_datasource)

    result = postgres_datasource.native_query(
        """SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"""
    )
    actual = [t["table_name"] for t in result.to_dict_list()]

    assert "data_models" in actual
    assert "document_layouts" in actual
    assert "documents" in actual


def test_get_missing_views():
    views = ["ORDERS_PAYMENTS_ORDERS", "ORDERS_PAYMENTS_PAYMENTS"]
    # If we force=true, then we just return all views and downstream will recreate them.
    actual = _get_missing_views("di_tests", views, force=True)

    assert actual == views
