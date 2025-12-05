from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from .data_server_cli_wrapper import DataServerCliWrapper


def wait_for_non_error_condition(generate_error_or_none, timeout=10, sleep=1 / 20.0):
    import time

    curtime = time.time()

    while True:
        try:
            error_msg = generate_error_or_none()
        except Exception as e:
            error_msg = str(e)
            print("Saw error waiting for condition:", error_msg)

        if error_msg is None:
            break

        if timeout is not None and (time.time() - curtime > timeout):
            raise TimeoutError(f"Condition not reached in {timeout} seconds\n{error_msg}")
        time.sleep(sleep)


@contextmanager
def _bootstrap_test_datasources(
    data_server_cli: "DataServerCliWrapper", pg_params: dict, mindsdb_db_name: str
):
    """
    Note: many tests may use the same db name, so we need to ensure that the db is
    created with the expected data (even when running in parallel with pytest-xdist).
    """
    import time

    http_port, _ = data_server_cli.get_http_and_mysql_ports()

    http_connection = None

    print("testing connection to mindsdb")

    def make_connection():
        from sema4ai.data._data_server_connection import _HttpConnectionHelper

        nonlocal http_connection
        curtime = time.time()
        http_connection = _HttpConnectionHelper(
            http_url=f"http://localhost:{http_port}",
            http_user=data_server_cli.get_username(),
            http_password=data_server_cli.get_password(),
        )
        http_connection.login()
        print(f"Took {time.time() - curtime:.2f} seconds to connect/login")

    # We wait for the data server to be ready when launching it, so, this should not take long.
    wait_for_non_error_condition(make_connection, timeout=60, sleep=2)

    assert http_connection is not None, "HTTP connection should be established"

    # Convert dbname to database for MindsDB compatibility
    mindsdb_params = pg_params.copy()
    if "dbname" in mindsdb_params:
        mindsdb_params["database"] = mindsdb_params.pop("dbname")

    http_connection.run_sql(f"DROP DATABASE IF EXISTS `{mindsdb_db_name}`")

    print(f"Creating database {mindsdb_db_name} with params {mindsdb_params}")
    http_connection.run_sql(
        f"CREATE DATABASE `{mindsdb_db_name}` ENGINE = 'postgres' , PARAMETERS = {mindsdb_params}",
    )

    # Also create DocumentIntelligence integration for production code compatibility
    http_connection.run_sql("DROP DATABASE IF EXISTS `documentintelligence`")
    http_connection.run_sql(
        f"CREATE DATABASE IF NOT EXISTS `documentintelligence` ENGINE = 'postgres' , "
        f"PARAMETERS = {mindsdb_params}",
    )

    yield http_connection

    http_connection.run_sql(f"DROP DATABASE IF EXISTS `{mindsdb_db_name}`")
    http_connection.run_sql("DROP DATABASE IF EXISTS DocumentIntelligence")


@pytest.fixture(scope="session")
def data_server_cli(
    request, tmpdir_factory, postgres, mindsdb_db_name
) -> Iterator["DataServerCliWrapper"]:
    from .data_server_cli_wrapper import DataServerCliWrapper

    wrapper = DataServerCliWrapper(Path(str(tmpdir_factory.mktemp("data-server-cli"))))
    # This can be pretty slow (and may be common with pytest-xdist).
    wrapper.download_data_server_cli()
    wrapper.start()

    def teardown():
        if request.session.testsfailed:
            wrapper.print_log()

    _, params = postgres

    try:
        with _bootstrap_test_datasources(wrapper, params, mindsdb_db_name) as http_connection:
            wrapper.http_connection = http_connection
            yield wrapper
    finally:
        teardown()


@pytest.fixture(scope="session")
def mindsdb_ports(data_server_cli: "DataServerCliWrapper") -> tuple[int, int]:
    return data_server_cli.get_http_and_mysql_ports()
