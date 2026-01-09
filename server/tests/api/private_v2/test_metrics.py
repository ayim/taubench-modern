def test_metrics_response_serialization():
    """Test that model serialization (model_dump) uses camelCase aliases."""
    from agent_platform.server.api.private_v2.metrics import MetricsResponse

    # Create an instance with snake_case field names
    response = MetricsResponse(
        agent_count=10,
        thread_count=25,
        conversational_agent_count=8,
        worker_agent_count=2,
        message_count=150,
        generate_sql_count=5,
    )

    # Serialize using model_dump (this is what FastAPI uses for response serialization)
    serialized = response.model_dump(mode="json", by_alias=True)

    # Verify camelCase aliases are used in serialization
    assert "agentCount" in serialized
    assert "threadCount" in serialized
    assert "conversationalAgentCount" in serialized
    assert "workerAgentCount" in serialized
    assert "messageCount" in serialized
    assert "generateSqlCount" in serialized

    # Verify snake_case is NOT used
    assert "agent_count" not in serialized
    assert "thread_count" not in serialized
    assert "conversational_agent_count" not in serialized
    assert "worker_agent_count" not in serialized
    assert "message_count" not in serialized
    assert "generate_sql_count" not in serialized

    # Verify values are correct
    assert serialized["agentCount"] == 10
    assert serialized["threadCount"] == 25
    assert serialized["conversationalAgentCount"] == 8
    assert serialized["workerAgentCount"] == 2
    assert serialized["messageCount"] == 150
    assert serialized["generateSqlCount"] == 5
