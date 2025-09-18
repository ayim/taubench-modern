from agent_platform.core.payloads.document_intelligence import ExtractDocumentPayload


def test_extract_document_payload_generate_citations_defaults_to_true():
    """Test that generate_citations defaults to True when not provided in JSON payload."""
    # Create a minimal valid payload without generate_citations field
    json_payload = {
        "thread_id": "test-thread-123",
        "file_name": "test-document.pdf",
        "layout_name": "test-layout",
        "data_model_name": "test-model",
    }

    # Validate the payload using model_validate
    payload = ExtractDocumentPayload.model_validate(json_payload)

    # Assert that generate_citations defaults to True
    assert payload.generate_citations is True


def test_extract_document_payload_generate_citations_respects_explicit_false():
    """Test that generate_citations respects explicit False value."""
    # Create a payload with generate_citations explicitly set to False
    json_payload = {
        "thread_id": "test-thread-123",
        "file_name": "test-document.pdf",
        "layout_name": "test-layout",
        "data_model_name": "test-model",
        "generate_citations": False,
    }

    # Validate the payload using model_validate
    payload = ExtractDocumentPayload.model_validate(json_payload)

    # Assert that generate_citations is False as explicitly set
    assert payload.generate_citations is False


def test_extract_document_payload_generate_citations_respects_explicit_true():
    """Test that generate_citations respects explicit True value."""
    # Create a payload with generate_citations explicitly set to True
    json_payload = {
        "thread_id": "test-thread-123",
        "file_name": "test-document.pdf",
        "layout_name": "test-layout",
        "data_model_name": "test-model",
        "generate_citations": True,
    }

    # Validate the payload using model_validate
    payload = ExtractDocumentPayload.model_validate(json_payload)

    # Assert that generate_citations is True as explicitly set
    assert payload.generate_citations is True
