"""
Integration tests using testcontainers to verify view generation with a real database.
"""

import json
import uuid

from conftest import VIEWS_SAMPLE_SCHEMA, load_document
from sema4ai.data import DataSource

from sema4ai_docint.models.initialize import initialize_database
from sema4ai_docint.views import ViewGenerator


def clear_tables(ds: DataSource):
    """Setup database with test data for views tests."""
    for table in ["data_models", "document_layouts", "documents"]:
        ds.native_query(f"TRUNCATE TABLE {table} CASCADE")


def setup_db_views(ds: DataSource, sample_document: dict) -> str:
    """Setup database with test data for views tests."""
    # Load test data from views test directory

    doc_id = str(uuid.uuid4())
    ds.native_query(
        """
        INSERT INTO documents (id, document_name, document_layout, translated_content, data_model)
        VALUES (?, ?, ?, ?, ?)
        """,
        params=[
            doc_id,
            "test_file.pdf",
            "test_layout",
            json.dumps(sample_document),
            "orders_payments",
        ],
    )
    return doc_id


def test_view_generation_with_single_document(
    postgres_datasource: DataSource, mindsdb_db_name: str
):
    """Test that views can be generated and executed on a real database."""
    # Create the tables/udfs
    initialize_database("postgres", postgres_datasource)
    clear_tables(postgres_datasource)

    sample_document = load_document("orders_payments", "business_document.json")
    _ = setup_db_views(postgres_datasource, sample_document)

    postgres_datasource.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_ORDERS")
    postgres_datasource.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_PAYMENTS")

    # Generate the views
    generator = ViewGenerator(
        source_table_name="documents",
        document_column_name="translated_content",
        project_name="di_tests",
        datasource_name=mindsdb_db_name,
    )
    views = generator.generate_views(VIEWS_SAMPLE_SCHEMA, use_case_name="orders_payments")

    # Check that views were generated
    assert len(views) == 2
    assert next((v for v in views if v.name == "ORDERS_PAYMENTS_ORDERS"), None) is not None, (
        f"Did not find the ORDERS_PAYMENTS_ORDERS view: {views}"
    )
    assert next((v for v in views if v.name == "ORDERS_PAYMENTS_PAYMENTS"), None) is not None, (
        f"Did not find the ORDERS_PAYMENTS_PAYMENTS view: {views}"
    )

    # Create the views in the database
    for view in views:
        print(f"Creating view: {view.sql}")
        postgres_datasource.execute_sql(view.sql)

    # Test orders view
    # Query orders view
    results = postgres_datasource.execute_sql(
        "SELECT COUNT(1) as C FROM di_tests.ORDERS_PAYMENTS_ORDERS"
    )
    assert results is not None
    rows = [r for r in results.iter_as_tuples()]
    assert len(rows) == 1
    # Check that expected data is returned
    assert rows[0][0] == 3, "Expected 3 orders"

    # Query payments view
    results = postgres_datasource.execute_sql(
        "SELECT COUNT(1) as C FROM di_tests.ORDERS_PAYMENTS_PAYMENTS"
    )
    assert results is not None
    rows = [r for r in results.iter_as_tuples()]
    assert len(rows) == 1
    # Check that expected data is returned
    assert rows[0][0] == 2, "Expected 2 payments"

    # Test aggregate query on payments view
    results = postgres_datasource.execute_sql(
        "SELECT SUM(payment_amount) as TP FROM di_tests.ORDERS_PAYMENTS_PAYMENTS"
    )
    assert results is not None
    rows = [r for r in results.iter_as_tuples()]
    assert len(rows) == 1
    total_payment = rows[0][0]

    # Calculate expected total (69.97 + 47.97 = 117.94)
    expected_total = 69.97 + 47.97

    # Assert with a small tolerance for floating point precision
    assert float(total_payment) == expected_total

    # Test aggregate query with grouping
    results = postgres_datasource.execute_sql("""
        SELECT customer_id, SUM(payment_amount) AS total_payments
        FROM di_tests.ORDERS_PAYMENTS_PAYMENTS
        GROUP BY customer_id
    """)
    assert results is not None
    rows = [r for r in results.iter_as_tuples()]
    assert len(rows) == 1

    # Should have one customer (C123) with total payments of 117.94
    customer_total = rows[0][1]
    assert float(customer_total) == expected_total

    # Test that TEXT->NUMERIC conversion worked. We force the quantity attribute to be string.
    results = postgres_datasource.execute_sql(
        "SELECT SUM(item_quantity) as q FROM di_tests.ORDERS_PAYMENTS_ORDERS"
    )
    assert results is not None
    rows = results.to_dict_list()
    assert len(rows) == 1
    total_quantity = rows[0]["q"]
    assert total_quantity == 6

    # Price is already a number. Make sure TRY_TO_NUMBER still returns the number.
    results = postgres_datasource.execute_sql(
        "SELECT SUM(item_price) as p FROM di_tests.ORDERS_PAYMENTS_ORDERS"
    )
    assert results is not None
    rows = results.to_dict_list()
    assert len(rows) == 1
    total_price = rows[0]["p"]
    assert total_price == 65.97


def test_view_generation_with_multiple_documents(
    postgres_datasource: "DataSource",
    mindsdb_db_name: str,
):
    # Create the tables/udfs
    initialize_database("postgres", postgres_datasource)
    clear_tables(postgres_datasource)

    """Test view generation with multiple documents in the database."""
    postgres_datasource.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_ORDERS")
    postgres_datasource.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_PAYMENTS")

    """Test view generation with multiple documents in the database."""
    postgres_datasource.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_ORDERS")
    postgres_datasource.execute_sql("DROP VIEW IF EXISTS di_tests.ORDERS_PAYMENTS_PAYMENTS")

    sample_document = load_document("orders_payments", "business_document.json")
    first_doc_id = setup_db_views(postgres_datasource, sample_document)

    # Insert a second document
    second_document = {
        "customer": {"id": "C456", "name": "Jane Smith"},
        "orders": [
            {
                "id": "O123",
                "date": "2023-07-10",
                "items": [{"sku": "PROD-D", "name": "Product D", "qty": "5", "price": 9.99}],
            }
        ],
        "payments": [
            {
                "id": "P003",
                "order_id": "O123",
                "amount": 49.95,
                "method": "bank_transfer",
            }
        ],
    }

    second_doc_id = setup_db_views(postgres_datasource, second_document)

    # Generate and create views
    generator = ViewGenerator(
        source_table_name="documents",
        document_column_name="translated_content",
        project_name="di_tests",
        datasource_name=mindsdb_db_name,
    )
    views = generator.generate_views(VIEWS_SAMPLE_SCHEMA, use_case_name="orders_payments")

    # Create or replace the views
    for view in views:
        postgres_datasource.execute_sql(view.sql)

    # Test orders view with multiple documents
    results = postgres_datasource.execute_sql(
        "SELECT COUNT(1) as C FROM di_tests.ORDERS_PAYMENTS_ORDERS"
    )
    assert results is not None
    count = next(iter(results.iter_as_tuples()))[0]
    assert count == 4  # 3 from first document + 1 from second

    # Test that we can filter by document_id
    results = postgres_datasource.execute_sql(
        "SELECT DISTINCT document_id FROM di_tests.ORDERS_PAYMENTS_ORDERS"
    )
    assert results is not None
    rows = [r for r in results.iter_as_tuples()]
    document_ids = sorted([str(row[0]) for row in rows])
    assert len(document_ids) == 2
    assert str(first_doc_id) in document_ids
    assert str(second_doc_id) in document_ids

    # Test customer filter
    results = postgres_datasource.execute_sql(
        "SELECT COUNT(1) as C FROM di_tests.ORDERS_PAYMENTS_ORDERS WHERE customer_id = 'C456'"
    )
    assert results is not None
    count = next(iter(results.iter_as_tuples()))[0]
    assert count == 1

    # Test payments view with multiple documents
    results = postgres_datasource.execute_sql(
        "SELECT COUNT(1) as C FROM di_tests.ORDERS_PAYMENTS_PAYMENTS"
    )
    assert results is not None
    count = next(iter(results.iter_as_tuples()))[0]
    assert count == 3  # 2 from first document + 1 from second

    # Test aggregate query on payments view with multiple documents
    results = postgres_datasource.execute_sql(
        "SELECT SUM(payment_amount) as TP FROM di_tests.ORDERS_PAYMENTS_PAYMENTS"
    )
    assert results is not None
    total_payment = next(iter(results.iter_as_tuples()))[0]

    # Calculate expected total (69.97 + 47.97 + 49.95 = 167.89)
    expected_total = 69.97 + 47.97 + 49.95

    # Assert that the total payment is equal to the expected total
    assert float(total_payment) == expected_total

    # Test aggregate query with grouping by customer_id
    results = postgres_datasource.execute_sql("""
        SELECT customer_id, SUM(payment_amount) AS total_payments
        FROM di_tests.ORDERS_PAYMENTS_PAYMENTS
        GROUP BY customer_id
        ORDER BY customer_id
    """)
    assert results is not None
    rows = [r for r in results.iter_as_tuples()]

    # Should have two customers with their respective payment totals
    assert len(rows) == 2

    # First customer (C123) should have total payments of 117.94
    c1_total = rows[0][1]
    assert float(c1_total) == (69.97 + 47.97)
