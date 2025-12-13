from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString


@dataclass(frozen=True, kw_only=True)
class LiteLLMPlatformParameters(PlatformParameters):
    """Parameters for configuring the LiteLLM platform client."""

    kind: Literal["litellm"] = field(
        default="litellm",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )

    litellm_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": ("The LiteLLM API key. If not provided, it is loaded from LITELLM_API_KEY."),
        },
    )
    litellm_base_url: str | None = field(
        default=None,
        metadata={
            "description": "Optional override for the LiteLLM base URL (defaults to https://llm.backend.sema4.ai).",
        },
    )

    def __post_init__(self) -> None:
        from os import getenv

        super().__post_init__()

        if self.litellm_api_key and not isinstance(self.litellm_api_key, SecretString):
            object.__setattr__(
                self,
                "litellm_api_key",
                SecretString.from_value(self.litellm_api_key),
            )
        elif not self.litellm_api_key:
            api_key = getenv("LITELLM_API_KEY")
            if api_key:
                object.__setattr__(self, "litellm_api_key", SecretString(api_key))
            else:
                raise ValueError("LITELLM_API_KEY environment variable is required")

        if not self.litellm_base_url:
            base_url = getenv("LITELLM_BASE_URL", "https://llm.backend.sema4.ai")
            object.__setattr__(self, "litellm_base_url", base_url)

    def model_dump(self, *, exclude_none: bool = True) -> dict:
        extra = {
            "litellm_api_key": (
                self.litellm_api_key.get_secret_value() if isinstance(self.litellm_api_key, SecretString) else None
            ),
            "litellm_base_url": self.litellm_base_url,
        }
        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "LiteLLMPlatformParameters":
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}
        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return LiteLLMPlatformParameters(**current_params)

        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return LiteLLMPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "LiteLLMPlatformParameters":
        obj = dict(obj)
        cls._convert_datetime_fields(obj)
        return cls(**obj)


PlatformParameters.register_platform_parameters("litellm", LiteLLMPlatformParameters)
