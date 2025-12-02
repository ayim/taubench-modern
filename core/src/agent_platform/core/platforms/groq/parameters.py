from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString

BASE_GROQ_RESPONSES_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True, kw_only=True)
class GroqPlatformParameters(PlatformParameters):
    """Parameters for the Groq platform."""

    kind: Literal["groq"] = field(
        default="groq",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )

    groq_api_key: SecretString | None = field(
        default=None,
        metadata={
            "description": "The Groq API key. If not provided, it will be "
            "attempted to be inferred from the environment.",
        },
    )
    groq_base_url: str | None = field(
        default=None,
        metadata={
            "description": (
                "Optional override for the Groq base URL "
                "(defaults to https://api.groq.com/openai/v1)."
            ),
        },
    )

    def __post_init__(self):
        from os import getenv

        super().__post_init__()

        if self.groq_api_key and not isinstance(self.groq_api_key, SecretString):
            object.__setattr__(self, "groq_api_key", SecretString.from_value(self.groq_api_key))
        elif not self.groq_api_key:
            key_from_env = getenv("GROQ_API_KEY")
            if key_from_env:
                object.__setattr__(self, "groq_api_key", SecretString(key_from_env))
            else:
                raise ValueError("GROQ_API_KEY environment variable is required")

        if not self.groq_base_url:
            base_url = getenv("GROQ_BASE_URL", BASE_GROQ_RESPONSES_URL)
            object.__setattr__(self, "groq_base_url", base_url)

    def api_key(self) -> str | None:
        if self.groq_api_key:
            if isinstance(self.groq_api_key, SecretString):
                return self.groq_api_key.get_secret_value()
            return str(self.groq_api_key)
        return None

    @property
    def base_url(self) -> str:
        return self.groq_base_url or BASE_GROQ_RESPONSES_URL

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
    ) -> dict:
        extra = {
            "groq_api_key": self.api_key(),
            "groq_base_url": self.base_url,
        }
        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "GroqPlatformParameters":
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return GroqPlatformParameters(**current_params)

        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return GroqPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "GroqPlatformParameters":
        obj = dict(obj)
        cls._convert_datetime_fields(obj)
        return cls(**obj)


PlatformParameters.register_platform_parameters("groq", GroqPlatformParameters)
