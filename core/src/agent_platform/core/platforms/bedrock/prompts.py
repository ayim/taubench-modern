from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agent_platform.core.platforms.base import PlatformPrompt

if TYPE_CHECKING:
    from types_boto3_bedrock_runtime.type_defs import (
        ConverseRequestTypeDef,
        ConverseStreamRequestTypeDef,
        GuardrailStreamConfigurationTypeDef,
        InferenceConfigurationTypeDef,
        MessageTypeDef,
        PerformanceConfigurationTypeDef,
        PromptVariableValuesTypeDef,
        SystemContentBlockTypeDef,
        ToolConfigurationTypeDef,
    )


@dataclass(frozen=True)
class BedrockPrompt(PlatformPrompt):
    """A prompt for the Bedrock platform.

    This class stores the prompt in the format expected by the Bedrock API
    and its fields match the `ConverseRequestTypeDef` and `ConverseStreamRequestTypeDef`
    type but in snake_case (except for `model_id`).
    """

    # TODO: We need to consider if embedding the inference config and other configs
    # into the prompt is intuitive or if we should keep them separate. Bedrock keeps
    # them together so this mirrors that, but we may want to decide that they should
    # generally be separate.

    messages: "list[MessageTypeDef] | None" = None
    system: "list[SystemContentBlockTypeDef] | None" = None
    inference_config: "InferenceConfigurationTypeDef | None" = None
    tool_config: "ToolConfigurationTypeDef | None" = None
    guardrail_config: "GuardrailStreamConfigurationTypeDef | None" = None
    additional_model_request_fields: dict[str, Any] | None = None
    prompt_variables: "dict[str, PromptVariableValuesTypeDef] | None" = None
    additional_model_response_field_paths: list[str] | None = None
    request_metadata: dict[str, str] | None = None
    performance_config: "PerformanceConfigurationTypeDef | None" = None

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ) -> "ConverseRequestTypeDef | ConverseStreamRequestTypeDef":
        """Convert the prompt to a Bedrock request.

        Args:
            model: The Bedrock model ID to use to generate the request.
            stream: Whether to return a stream request.

        Returns:
            A Bedrock request.
        """
        from types_boto3_bedrock_runtime.type_defs import (
            ConverseRequestTypeDef,
            ConverseStreamRequestTypeDef,
        )

        request_dict = {
            "modelId": model,
            "messages": self.messages,
            "system": self.system,
            "inferenceConfig": self.inference_config,
            "toolConfig": self.tool_config,
            "guardrailConfig": self.guardrail_config,
            "additionalModelRequestFields": self.additional_model_request_fields,
            "promptVariables": self.prompt_variables,
            "additionalModelResponseFieldPaths": self.additional_model_response_field_paths,  # noqa: E501
            "requestMetadata": self.request_metadata,
            "performanceConfig": self.performance_config,
        }

        # Remove None values
        request_dict = {k: v for k, v in request_dict.items() if v is not None}

        if stream:
            return ConverseStreamRequestTypeDef(**request_dict)
        else:
            return ConverseRequestTypeDef(**request_dict)
