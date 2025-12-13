from fastapi.testclient import TestClient


def _normalize_value(value):
    if isinstance(value, int | float):
        try:
            return int(value)
        except Exception:
            return value
    return value


def _assert_config_contains(actual: dict, expected: dict):
    assert isinstance(actual, dict)
    for key, exp_val in expected.items():
        assert key in actual
        act_val = actual[key]
        if isinstance(exp_val, dict):
            assert isinstance(act_val, dict)
            _assert_config_contains(act_val, exp_val)
        elif isinstance(exp_val, list):
            assert isinstance(act_val, list)
            assert act_val == exp_val
        else:
            assert _normalize_value(act_val) == _normalize_value(exp_val)


def test_create_all_types_and_fetch(client: TestClient):
    payloads = [
        {
            "name": "PostgreSQL Production DB",
            "description": "Main production PostgreSQL database",
            "engine": "postgres",
            "configuration": {
                "host": "localhost",
                "port": 5432,
                "database": "mydb",
                "user": "myuser",
                "password": "mypassword",
                "schema": "public",
                "sslmode": "require",
            },
        },
        {
            "name": "Redshift Analytics DB",
            "description": "Amazon Redshift data warehouse",
            "engine": "redshift",
            "configuration": {
                "host": "mycluster.abc123.us-east-1.redshift.amazonaws.com",
                "port": 5439,
                "database": "analytics",
                "user": "analytics_user",
                "password": "analytics_password",
                "schema": "public",
                "sslmode": "require",
            },
        },
        {
            "name": "Snowflake Linked Connection",
            "description": "Snowflake with linked credentials",
            "engine": "snowflake",
            "configuration": {
                "warehouse": "COMPUTE_WH",
                "database": "SNOWFLAKE_SAMPLE_DATA",
                "schema": "TPCH_SF1",
                "credential_type": "linked",
            },
        },
        {
            "name": "Snowflake Key Pair Connection",
            "description": "Snowflake with custom key pair authentication",
            "engine": "snowflake",
            "configuration": {
                "account": "myaccount.snowflakecomputing.com",
                "user": "myuser",
                "private_key_path": "/path/to/private_key.pem",
                "warehouse": "COMPUTE_WH",
                "database": "MY_DATABASE",
                "schema": "MY_SCHEMA",
                "credential_type": "custom-key-pair",
                "role": "MY_ROLE",
                "private_key_passphrase": "optional_passphrase",
            },
        },
        {
            "name": "Snowflake Standard Connection",
            "description": "Snowflake with username/password authentication",
            "engine": "snowflake",
            "configuration": {
                "credential_type": "username_password",
                "account": "myaccount.snowflakecomputing.com",
                "user": "myuser",
                "password": "mypassword",
                "warehouse": "COMPUTE_WH",
                "database": "MY_DATABASE",
                "schema": "MY_SCHEMA",
                "role": "MY_ROLE",
            },
        },
        {
            "name": "Confluence Wiki",
            "description": "Company Confluence instance",
            "engine": "confluence",
            "configuration": {
                "api_base": "https://mycompany.atlassian.net/wiki",
                "username": "myuser@company.com",
                "password": "my_api_token",
            },
        },
        {
            "name": "MySQL Application DB",
            "description": "Main application MySQL database",
            "engine": "mysql",
            "configuration": {
                "host": "localhost",
                "port": 3306,
                "database": "myapp",
                "user": "myuser",
                "password": "mypassword",
                "ssl": True,
                "ssl_ca": "/path/to/ca-cert.pem",
                "ssl_cert": "/path/to/client-cert.pem",
                "ssl_key": "/path/to/client-key.pem",
            },
        },
        {
            "name": "MSSQL Enterprise DB",
            "description": "Microsoft SQL Server database",
            "engine": "mssql",
            "configuration": {
                "host": "localhost",
                "database": "master",
                "user": "sa",
                "password": "mypassword",
                "port": 1433,
                "server": "localhost\\SQLEXPRESS",
            },
        },
        {
            "name": "Oracle Enterprise DB",
            "description": "Oracle database connection",
            "engine": "oracle",
            "configuration": {
                "host": "localhost",
                "user": "system",
                "password": "mypassword",
                "service_name": "ORCL",
                "port": 1521,
                "dsn": "localhost:1521/ORCL",
                "sid": "ORCL",
                "disable_oob": False,
                "auth_mode": "normal",
            },
        },
        {
            "name": "Slack Workspace",
            "description": "Company Slack workspace",
            "engine": "slack",
            "configuration": {
                "token": "xoxb-your-bot-token",
                "app_token": "xapp-your-app-token",
            },
        },
        {
            "name": "Salesforce CRM",
            "description": "Salesforce CRM instance",
            "engine": "salesforce",
            "configuration": {
                "username": "user@company.com",
                "password": "mypassword",
                "client_id": "your_connected_app_client_id",
                "client_secret": "your_connected_app_client_secret",
            },
        },
        {
            "name": "TimescaleDB Time Series",
            "description": "TimescaleDB for time series data",
            "engine": "timescaledb",
            "configuration": {
                "host": "localhost",
                "port": 5432,
                "database": "timeseries",
                "user": "timescale_user",
                "password": "timescale_password",
            },
        },
        {
            "name": "PgVector Embeddings",
            "description": "PostgreSQL with pgvector extension for embeddings",
            "engine": "pgvector",
            "configuration": {
                "host": "localhost",
                "port": 5432,
                "database": "embeddings",
                "user": "vector_user",
                "password": "vector_password",
                "schema": "public",
                "sslmode": "require",
            },
        },
        {
            "name": "BigQuery Analytics",
            "description": "Google BigQuery data warehouse",
            "engine": "bigquery",
            "configuration": {
                "project_id": "my-gcp-project",
                "dataset": "analytics_dataset",
                "service_account_keys": "path/to/service-account-key.json",
                "service_account_json": ('{"type": "service_account", "project_id": "my-gcp-project"}'),
            },
        },
        {
            "name": "Sema4 Knowledge Base",
            "description": "Sema4 knowledge base with OpenAI embeddings",
            "engine": "sema4_knowledge_base",
            "configuration": {
                "embedding_model": {
                    "model_name": "text-embedding-3-small",
                    "api_key": "sk-your-openai-api-key",
                    "provider": "openai",
                },
                "storage": "local",
                "reranking_model": {
                    "model_name": "text-search-babbage-query-001",
                    "api_key": "sk-your-openai-api-key",
                    "provider": "openai",
                },
                "metadata_columns": ["title", "category", "tags"],
                "content_columns": ["content", "summary"],
                "id_column": "document_id",
            },
        },
        {
            "name": "Sema4 Knowledge Base Azure",
            "description": "Sema4 knowledge base with Azure OpenAI embeddings",
            "engine": "sema4_knowledge_base",
            "configuration": {
                "embedding_model": {
                    "model_name": "text-embedding-3-small",
                    "api_key": "your-azure-openai-api-key",
                    "base_url": "https://your-resource.openai.azure.com/",
                    "api_version": "2024-02-15-preview",
                    "provider": "azure_openai",
                },
                "storage": "local",
                "reranking_model": {
                    "model_name": "text-search-babbage-query-001",
                    "api_key": "your-azure-openai-api-key",
                    "base_url": "https://your-resource.openai.azure.com/",
                    "api_version": "2024-02-15-preview",
                    "provider": "azure_openai",
                },
                "metadata_columns": ["title", "category"],
                "content_columns": ["content"],
                "id_column": "id",
            },
        },
    ]

    created = []
    for payload in payloads:
        r = client.post("/api/v2/private/data-connections/", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == payload["name"]
        assert body["description"] == payload["description"]
        assert body["engine"] == payload["engine"]
        _assert_config_contains(body["configuration"], payload["configuration"])
        assert body.get("id")
        created.append(body)

    skip_get_by_engine = {"mysql", "timescaledb"}
    for c in created:
        if c["engine"] in skip_get_by_engine:
            continue
        gr = client.get(f"/api/v2/private/data-connections/{c['id']}")
        assert gr.status_code == 200
        gd = gr.json()
        assert gd["name"] == c["name"]
        assert gd["engine"] == c["engine"]
        _assert_config_contains(
            gd["configuration"],
            payloads[[p["name"] for p in payloads].index(c["name"])]["configuration"],
        )


def test_update_data_connection_endpoint(client: TestClient):
    create_payload = {
        "name": "Postgres Original",
        "description": "Original Postgres connection",
        "engine": "postgres",
        "configuration": {
            "host": "localhost",
            "port": 5432,
            "database": "myapp",
            "user": "myuser",
            "password": "mypassword",
            "schema": "public",
            "sslmode": "require",
        },
    }
    r = client.post("/api/v2/private/data-connections/", json=create_payload)
    assert r.status_code == 200
    connection_id = r.json()["id"]

    updated_payload = {
        "name": "Postgres Updated",
        "description": "Updated Postgres connection",
        "engine": "postgres",
        "configuration": {
            "host": "db.example.com",
            "port": 5432,
            "database": "prod",
            "user": "prod_user",
            "password": "prod_password",
            "schema": "analytics",
            "sslmode": "require",
        },
    }

    r2 = client.put(f"/api/v2/private/data-connections/{connection_id}", json=updated_payload)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["name"] == updated_payload["name"]
    assert body2["description"] == updated_payload["description"]
    _assert_config_contains(body2["configuration"], updated_payload["configuration"])

    r3 = client.get(f"/api/v2/private/data-connections/{connection_id}")
    assert r3.status_code == 200
    got = r3.json()
    assert {k: got[k] for k in ("name", "description", "engine")} == {
        k: updated_payload[k] for k in ("name", "description", "engine")
    }
    _assert_config_contains(got["configuration"], updated_payload["configuration"])
