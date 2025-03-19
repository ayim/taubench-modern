# Exclude the integration_tests directory from the pytest collection
collect_ignore = ["tests/integration_tests"]

pytest_plugins = [
    "tests.unit_tests.unittest_fixtures",
    "tests.integration_tests.integration_fixtures",
    "agent_server_orchestrator.pytest_fixtures",
]
