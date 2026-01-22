# SIMULATION
DEFAULT_MAX_STEPS = 200
DEFAULT_MAX_ERRORS = 10
DEFAULT_SEED = 300
DEFAULT_MAX_CONCURRENCY = 3
DEFAULT_NUM_TRIALS = 1
DEFAULT_SAVE_TO = None
DEFAULT_LOG_LEVEL = "ERROR"

# LLM
# Agent LLM: GPT-5.2 from OpenAI (direct) with low reasoning
#   - Requires OPENAI_API_KEY environment variable for direct OpenAI API calls
# User LLM: GPT-4.1 from Azure OpenAI
#   - Uses Azure OpenAI configuration below (AZURE_API_KEY, AZURE_API_BASE, etc.)
# Azure OpenAI model names use format: azure/<deployment-name>
DEFAULT_AGENT_IMPLEMENTATION = "llm_agent"
DEFAULT_USER_IMPLEMENTATION = "user_simulator"
DEFAULT_LLM_AGENT = "gpt-5.2"  # OpenAI GPT-5.2 (direct, not Azure) - requires OPENAI_API_KEY env var
DEFAULT_LLM_USER = "azure/gpt-4.1"  # Azure OpenAI GPT-4.1
DEFAULT_LLM_TEMPERATURE_AGENT = 0.0
DEFAULT_LLM_TEMPERATURE_USER = 0.0
DEFAULT_LLM_ARGS_AGENT = {
    "temperature": DEFAULT_LLM_TEMPERATURE_AGENT,
    "reasoning_effort": "low"  # GPT-5.2 reasoning level
}
DEFAULT_LLM_ARGS_USER = {"temperature": DEFAULT_LLM_TEMPERATURE_USER}

DEFAULT_LLM_NL_ASSERTIONS = "azure/gpt-4o-mini"  # Update deployment name to match your Azure OpenAI deployment
DEFAULT_LLM_NL_ASSERTIONS_TEMPERATURE = 0.0
DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"temperature": DEFAULT_LLM_NL_ASSERTIONS_TEMPERATURE}

DEFAULT_LLM_ENV_INTERFACE = "azure/gpt-4.1"  # Update deployment name to match your Azure OpenAI deployment
DEFAULT_LLM_ENV_INTERFACE_TEMPERATURE = 0.0
DEFAULT_LLM_ENV_INTERFACE_ARGS = {"temperature": DEFAULT_LLM_ENV_INTERFACE_TEMPERATURE}

# AZURE OPENAI
# Azure OpenAI configuration - can be overridden by environment variables
# Used for User LLM (GPT-4.1) and other Azure OpenAI models
AZURE_API_KEY = ""  # Set via AZURE_API_KEY environment variable
AZURE_API_BASE = "https://customer-shared.cognitiveservices.azure.com"
AZURE_API_VERSION = "2024-05-01-preview"
AZURE_REGION = "eastus2"

# LITELLM
DEFAULT_MAX_RETRIES = 3
LLM_CACHE_ENABLED = False
DEFAULT_LLM_CACHE_TYPE = "redis"

# API MODE
# Set to True to use OpenAI Responses API instead of Chat Completions
# Responses API is recommended for o1, o3 models and provides better reasoning support
DEFAULT_USE_RESPONSES_API = False

# REDIS CACHE
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = ""
REDIS_PREFIX = "tau2"
REDIS_CACHE_VERSION = "v1"
REDIS_CACHE_TTL = 60 * 60 * 24 * 30

# LANGFUSE
USE_LANGFUSE = False  # If True, make sure all the env variables are set for langfuse.

# API
API_PORT = 8000
