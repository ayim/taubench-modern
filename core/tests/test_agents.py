import pytest
from pydantic import SecretStr, ValidationError

from agent_server_types.agents import (
    ActionPackage,
    AgentAdvancedConfig,
    AgentMetadata,
    AgentMode,
    AgentPayload,
    AgentReasoning,
    SerializableSecretStr,
    WorkerConfig,
    WorkerType,
)
from agent_server_types.constants import NOT_CONFIGURED
from agent_server_types.models import dummy_model


def test_action_package_configuration_status():
    action_package = ActionPackage(
        name="UnconfiguredPackage",
        organization="TestOrg",
        version="1.0.0",
        url=NOT_CONFIGURED,
        api_key=SecretStr(NOT_CONFIGURED),
    )
    is_configured, _ = action_package.is_configured()
    assert not is_configured


def test_agent_advanced_config_recursion_limit():
    # Test default recursion_limit
    config = AgentAdvancedConfig(
        architecture="some_architecture", reasoning=AgentReasoning.ENABLED
    )
    assert config.recursion_limit == 100

    # Test valid recursion_limit
    config = AgentAdvancedConfig(
        architecture="some_architecture",
        reasoning=AgentReasoning.ENABLED,
        recursion_limit=50,
    )
    assert config.recursion_limit == 50

    # Test invalid recursion_limit (negative value)
    with pytest.raises(ValueError):
        AgentAdvancedConfig(
            architecture="some_architecture",
            reasoning=AgentReasoning.ENABLED,
            recursion_limit=-10,
        )


def test_agent_metadata_worker_config():
    # Test mode WORKER with worker_config provided
    worker_config = WorkerConfig(
        type=WorkerType.DOCUMENT_INTELLIGENCE, document_type="invoice"
    )
    metadata = AgentMetadata(mode=AgentMode.WORKER, worker_config=worker_config)
    assert metadata.worker_config == worker_config

    # Test mode WORKER without worker_config
    with pytest.raises(ValueError):
        AgentMetadata(mode=AgentMode.WORKER, worker_config=None)

    # Test mode CONVERSATIONAL with worker_config provided
    with pytest.raises(ValueError):
        AgentMetadata(mode=AgentMode.CONVERSATIONAL, worker_config=worker_config)

    # Test mode CONVERSATIONAL without worker_config
    metadata = AgentMetadata(mode=AgentMode.CONVERSATIONAL, worker_config=None)
    assert metadata.worker_config is None


def test_agent_payload_model_validator():
    # Test with model as a valid JSON string
    model_json = '{"provider": "OpenAI", "config": {"openai_api_key": "dummy"}}'
    payload = AgentPayload(
        public=False,
        name="Test Agent",
        description="Test Description",
        runbook=SerializableSecretStr("Test Runbook"),
        version="1.0",
        model=model_json,
        advanced_config=AgentAdvancedConfig(
            architecture="some_architecture", reasoning=AgentReasoning.ENABLED
        ),
        action_packages=[],
        metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
    )
    assert payload.model.provider == "OpenAI"
    assert payload.model.config.openai_api_key.get_secret_value() == "dummy"

    # Test with invalid model JSON string
    invalid_model_json = '{"name": "test_model", "vendor": "test_vendor"'
    with pytest.raises(ValidationError):
        AgentPayload(
            public=False,
            name="Test Agent",
            description="Test Description",
            runbook=SerializableSecretStr("Test Runbook"),
            version="1.0",
            model=invalid_model_json,
            advanced_config=AgentAdvancedConfig(
                architecture="some_architecture", reasoning=AgentReasoning.ENABLED
            ),
            action_packages=[],
            metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
        )

    # Test with 'null' as model
    invalid_model_json = "null"
    with pytest.raises(ValueError):
        AgentPayload(
            public=False,
            name="Test Agent",
            description="Test Description",
            runbook=SerializableSecretStr("Test Runbook"),
            version="1.0",
            model=invalid_model_json,
            advanced_config=AgentAdvancedConfig(
                architecture="some_architecture", reasoning=AgentReasoning.ENABLED
            ),
            action_packages=[],
            metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
        )


def test_agent_payload_action_packages_validator():
    # Test with action_packages as a valid JSON string
    action_packages_json = '[{"name": "package1", "organization": "org", "version": "1.0", "url": "http://example.com", "api_key": "secret", "whitelist": ""}]'
    payload = AgentPayload(
        public=False,
        name="Test Agent",
        description="Test Description",
        runbook=SerializableSecretStr("Test Runbook"),
        version="1.0",
        model=dummy_model,
        advanced_config=AgentAdvancedConfig(
            architecture="some_architecture", reasoning=AgentReasoning.ENABLED
        ),
        action_packages=action_packages_json,
        metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
    )
    assert len(payload.action_packages) == 1
    assert payload.action_packages[0].name == "package1"

    # Test with invalid action_packages JSON string
    invalid_action_packages_json = (
        '[{"name": "package1", "organization": "org", "version": "1.0"'
    )
    with pytest.raises(ValidationError):
        AgentPayload(
            public=False,
            name="Test Agent",
            description="Test Description",
            runbook=SerializableSecretStr("Test Runbook"),
            version="1.0",
            model=dummy_model,
            advanced_config=AgentAdvancedConfig(
                architecture="some_architecture", reasoning=AgentReasoning.ENABLED
            ),
            action_packages=invalid_action_packages_json,
            metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
        )


def test_agent_payload_metadata_validator():
    # Test with metadata as a valid JSON string
    metadata_json = '{"mode": "conversational", "question_groups": []}'
    payload = AgentPayload(
        public=False,
        name="Test Agent",
        description="Test Description",
        runbook=SerializableSecretStr("Test Runbook"),
        version="1.0",
        model=dummy_model,
        advanced_config=AgentAdvancedConfig(
            architecture="some_architecture", reasoning=AgentReasoning.ENABLED
        ),
        action_packages=[],
        metadata=metadata_json,
    )
    assert payload.metadata.mode == AgentMode.CONVERSATIONAL

    # Test with invalid metadata JSON string
    invalid_metadata_json = '{"mode": "conversational", "question_groups": '
    with pytest.raises(ValidationError):
        AgentPayload(
            public=False,
            name="Test Agent",
            description="Test Description",
            runbook=SerializableSecretStr("Test Runbook"),
            version="1.0",
            model=dummy_model,
            advanced_config=AgentAdvancedConfig(
                architecture="some_architecture", reasoning=AgentReasoning.ENABLED
            ),
            action_packages=[],
            metadata=invalid_metadata_json,
        )


def test_agent_payload_advanced_config_validator():
    # Test with advanced_config as a valid JSON string
    advanced_config_json = (
        '{"architecture": "some_architecture", "reasoning": "enabled"}'
    )
    payload = AgentPayload(
        public=False,
        name="Test Agent",
        description="Test Description",
        runbook=SerializableSecretStr("Test Runbook"),
        version="1.0",
        model=dummy_model,
        advanced_config=advanced_config_json,
        action_packages=[],
        metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
    )
    assert payload.advanced_config.architecture == "some_architecture"
    assert payload.advanced_config.reasoning == AgentReasoning.ENABLED

    # Test with invalid advanced_config JSON string
    invalid_advanced_config_json = (
        '{"architecture": "some_architecture", "reasoning": "enabled"'
    )
    with pytest.raises(ValidationError):
        AgentPayload(
            public=False,
            name="Test Agent",
            description="Test Description",
            runbook=SerializableSecretStr("Test Runbook"),
            version="1.0",
            model=dummy_model,
            advanced_config=invalid_advanced_config_json,
            action_packages=[],
            metadata=AgentMetadata(mode=AgentMode.CONVERSATIONAL),
        )
