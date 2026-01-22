import json
import os
import re
from typing import Any, Optional

import litellm
from litellm import completion, completion_cost
from litellm.caching.caching import Cache
from litellm.main import ModelResponse, Usage
from loguru import logger

from tau2.config import (
    AZURE_API_BASE,
    AZURE_API_KEY,
    AZURE_API_VERSION,
    AZURE_REGION,
    DEFAULT_LLM_CACHE_TYPE,
    DEFAULT_MAX_RETRIES,
    LLM_CACHE_ENABLED,
    REDIS_CACHE_TTL,
    REDIS_CACHE_VERSION,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_PREFIX,
    USE_LANGFUSE,
)
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool

# litellm._turn_on_debug()

if USE_LANGFUSE:
    # set callbacks
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

# Configure Azure OpenAI
# LiteLLM will automatically use Azure OpenAI when:
# 1. Model name starts with "azure/" prefix
# 2. Environment variables or config values are set: AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION
# Example model name: "azure/gpt-4" or "azure/gpt-4o" (where "gpt-4" is your deployment name)

# Use environment variables if set, otherwise use config values
azure_api_key = os.getenv("AZURE_API_KEY", AZURE_API_KEY)
azure_api_base = os.getenv("AZURE_API_BASE", AZURE_API_BASE)
azure_api_version = os.getenv("AZURE_API_VERSION", AZURE_API_VERSION)

# Set Azure OpenAI environment variables for LiteLLM
os.environ["AZURE_API_KEY"] = azure_api_key
os.environ["AZURE_API_BASE"] = azure_api_base
os.environ["AZURE_API_VERSION"] = azure_api_version

logger.info("Azure OpenAI configuration set. Models with 'azure/' prefix will use Azure OpenAI.")
logger.info(f"Azure OpenAI endpoint: {azure_api_base}")
logger.info(f"Azure OpenAI API version: {azure_api_version}")
logger.info(f"Azure region: {AZURE_REGION}")

# Note: For direct OpenAI API calls (e.g., gpt-5.2), set OPENAI_API_KEY environment variable
# LiteLLM will automatically use OpenAI API when model name doesn't start with "azure/"
if os.getenv("OPENAI_API_KEY"):
    logger.info("OpenAI API key detected. Direct OpenAI models (e.g., gpt-5.2) will use OpenAI API.")
else:
    logger.warning("OPENAI_API_KEY not set. Direct OpenAI models (e.g., gpt-5.2) may fail without API key.")


if LLM_CACHE_ENABLED:
    if DEFAULT_LLM_CACHE_TYPE == "redis":
        logger.info(f"LiteLLM: Using Redis cache at {REDIS_HOST}:{REDIS_PORT}")
        litellm.cache = Cache(
            type=DEFAULT_LLM_CACHE_TYPE,
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            namespace=f"{REDIS_PREFIX}:{REDIS_CACHE_VERSION}:litellm",
            ttl=REDIS_CACHE_TTL,
        )
    elif DEFAULT_LLM_CACHE_TYPE == "local":
        logger.info("LiteLLM: Using local cache")
        litellm.cache = Cache(
            type="local",
            ttl=REDIS_CACHE_TTL,
        )
    else:
        raise ValueError(
            f"Invalid cache type: {DEFAULT_LLM_CACHE_TYPE}. Should be 'redis' or 'local'"
        )
    litellm.enable_cache()
else:
    logger.info("LiteLLM: Cache is disabled")
    litellm.disable_cache()


# =============================================================================
# Provider Detection Helpers
# =============================================================================

def is_anthropic_model(model: str) -> bool:
    """
    Detect Anthropic models for content block handling.
    
    Anthropic models return content as an array of blocks (thinking, text, tool_use, etc.)
    instead of a simple string, and require special handling for extended thinking.
    """
    model_lower = model.lower()
    return (
        model_lower.startswith("claude") or
        "anthropic" in model_lower or
        model_lower.startswith("bedrock/anthropic") or
        model_lower.startswith("vertex_ai/claude")
    )


def use_responses_api(model: str, config_flag: bool = False) -> bool:
    """
    Determine if OpenAI Responses API should be used instead of Chat Completions.
    
    Args:
        model: The model name
        config_flag: Explicit flag to enable Responses API
        
    Returns:
        True if Responses API should be used
    """
    # Could be model-based (e.g., o1, o3 reasoning models) or config-driven
    model_lower = model.lower()
    return config_flag or model_lower.startswith("o1") or model_lower.startswith("o3")


# =============================================================================
# Anthropic Extended Thinking - Parsing
# =============================================================================

def parse_anthropic_response(
    response_message: Any,
    cost: float,
    usage: Optional[dict],
    raw_response_dict: dict,
) -> AssistantMessage:
    """
    Parse an Anthropic response with content blocks into an AssistantMessage.
    
    Anthropic responses can contain multiple block types:
    - thinking: visible reasoning with cryptographic signature (MUST preserve verbatim)
    - redacted_thinking: hidden reasoning as base64 data (MUST preserve verbatim)
    - text: user-visible output (may be multiple, concatenate in order)
    - tool_use: function calls (may be multiple/parallel)
    - image: image content (preserve verbatim, don't derive)
    - document: document content (preserve verbatim, don't derive)
    
    We store the entire content array verbatim in raw_content_blocks and derive
    normalized fields (content, tool_calls) for evaluators.
    """
    # Get the content - could be string or list of blocks
    content_data = response_message.content
    
    # If content is a simple string (non-extended-thinking mode), handle normally
    if isinstance(content_data, str):
        tool_calls = None
        if hasattr(response_message, 'tool_calls') and response_message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                    arguments_raw=tc.function.arguments,
                )
                for tc in response_message.tool_calls
            ]
        return AssistantMessage(
            role="assistant",
            content=content_data,
            tool_calls=tool_calls or None,
            cost=cost,
            usage=usage,
            raw_data=raw_response_dict,
        )
    
    # Content is a list of blocks - extended thinking mode
    content_blocks = content_data if isinstance(content_data, list) else [content_data]
    
    # Convert to list of dicts for storage
    raw_content_blocks = []
    for block in content_blocks:
        if hasattr(block, 'model_dump'):
            raw_content_blocks.append(block.model_dump())
        elif hasattr(block, 'to_dict'):
            raw_content_blocks.append(block.to_dict())
        elif isinstance(block, dict):
            raw_content_blocks.append(block)
        else:
            # Try to convert to dict
            raw_content_blocks.append(dict(block) if hasattr(block, '__iter__') else {"type": "unknown", "data": str(block)})
    
    # Derive normalized fields from raw blocks
    text_parts = []
    tool_calls = []
    
    for block in raw_content_blocks:
        block_type = block.get("type", "")
        
        if block_type == "text":
            text_parts.append(block.get("text", ""))
        
        elif block_type == "tool_use":
            # Anthropic gives input as dict
            input_dict = block.get("input", {})
            tool_calls.append(ToolCall(
                id=block.get("id", ""),
                name=block.get("name", ""),
                arguments=input_dict,
                arguments_raw=json.dumps(input_dict, separators=(',', ':')),
            ))
        
        elif block_type in ("thinking", "redacted_thinking", "image", "document"):
            # These are stored in raw_content_blocks but not derived to normalized fields
            logger.debug(f"Preserving {block_type} block in raw_content_blocks")
        
        else:
            # Unknown block type - preserve but log warning
            logger.warning(f"Unknown Anthropic content block type: {block_type}")
    
    return AssistantMessage(
        role="assistant",
        content="\n".join(text_parts) if text_parts else None,
        tool_calls=tool_calls or None,
        cost=cost,
        usage=usage,
        raw_data=raw_response_dict,
        raw_content_blocks=raw_content_blocks,  # VERBATIM storage
    )


# =============================================================================
# Anthropic Extended Thinking - Serialization
# =============================================================================

def to_litellm_messages_anthropic(messages: list[Message]) -> list[dict]:
    """
    Convert Tau2 messages to LiteLLM messages for Anthropic.
    
    Critical: Replay raw_content_blocks exactly as received to preserve
    thinking/redacted_thinking blocks and their signatures.
    
    Tool Result Ordering Constraints:
    1. Tool results must immediately follow the assistant message containing tool_use
    2. In user message with tool_result, tool_result blocks come FIRST
    3. Multiple tool_use in one turn requires multiple tool_result in following user turn
    """
    result = []
    pending_tool_results = []  # Collect tool results to batch
    
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        
        elif isinstance(msg, AssistantMessage):
            # Flush any pending tool results first (shouldn't happen mid-conversation)
            if pending_tool_results:
                result.append(_make_anthropic_tool_result_message(pending_tool_results))
                pending_tool_results = []
            
            if msg.raw_content_blocks:
                # REPLAY VERBATIM - preserves thinking/redacted_thinking/signatures
                result.append({
                    "role": "assistant",
                    "content": msg.raw_content_blocks
                })
            else:
                # Fallback for legacy messages without raw blocks
                content = msg.content
                if msg.is_tool_call():
                    # Build tool_use blocks if we don't have raw_content_blocks
                    content_blocks = []
                    if msg.content:
                        content_blocks.append({"type": "text", "text": msg.content})
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.name,
                            "input": tc.arguments,
                        })
                    content = content_blocks if content_blocks else msg.content
                result.append({
                    "role": "assistant",
                    "content": content
                })
        
        elif isinstance(msg, ToolMessage):
            # Collect tool results - will batch into single user message
            pending_tool_results.append({
                "type": "tool_result",
                "tool_use_id": msg.id,
                "content": msg.content
            })
        
        elif isinstance(msg, UserMessage):
            # Flush pending tool results before user message
            if pending_tool_results:
                result.append(_make_anthropic_tool_result_message(pending_tool_results))
                pending_tool_results = []
            
            result.append({"role": "user", "content": msg.content})
    
    # Flush any remaining tool results
    if pending_tool_results:
        result.append(_make_anthropic_tool_result_message(pending_tool_results))
    
    return result


def _make_anthropic_tool_result_message(tool_results: list[dict]) -> dict:
    """
    Create an Anthropic user message containing tool results.
    
    Anthropic constraint: tool_result blocks must come FIRST in content array.
    If we need to add text, it goes AFTER tool_results.
    """
    return {
        "role": "user",
        "content": tool_results  # tool_result blocks first
    }


# =============================================================================
# OpenAI Responses API - Parsing
# =============================================================================

def parse_responses_api(response: Any, cost: float = 0.0) -> AssistantMessage:
    """
    Parse an OpenAI Responses API response into an AssistantMessage.
    
    Output item types to handle:
    - reasoning: model's internal reasoning (MUST preserve and replay for multi-turn correctness)
    - message: text output (may have multiple output_text content items - concatenate in order)
    - function_call: tool invocation (may be multiple for parallel calls; arguments is JSON STRING)
    - Other items (web_search_call, file_search_call, etc.) - preserve verbatim
    
    We store the entire output array verbatim in raw_output_items and derive
    normalized fields (content, tool_calls) for evaluators.
    """
    output_items = response.output if hasattr(response, 'output') else response.get('output', [])
    
    # Convert to list of dicts for storage
    raw_output_items = []
    for item in output_items:
        if hasattr(item, 'model_dump'):
            raw_output_items.append(item.model_dump())
        elif hasattr(item, 'to_dict'):
            raw_output_items.append(item.to_dict())
        elif isinstance(item, dict):
            raw_output_items.append(item)
        else:
            raw_output_items.append({"type": "unknown", "data": str(item)})
    
    # Derive normalized fields
    text_parts = []
    tool_calls = []
    
    for item in raw_output_items:
        item_type = item.get("type", "")
        
        if item_type == "message":
            # May have multiple output_text content items - concatenate all
            for content in item.get("content", []):
                content_type = content.get("type", "")
                if content_type == "output_text":
                    text_parts.append(content.get("text", ""))
        
        elif item_type == "function_call":
            # CRITICAL: arguments is a JSON STRING, not dict
            args_string = item.get("arguments", "{}")
            try:
                args_dict = json.loads(args_string)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"Failed to parse function_call arguments: {args_string}")
                args_dict = {}
            
            tool_calls.append(ToolCall(
                id=item.get("call_id", item.get("id", "")),  # Use call_id, fallback to id
                name=item.get("name", ""),
                arguments=args_dict,  # Parse for evaluators
                arguments_raw=args_string,  # Preserve original string exactly
            ))
        
        elif item_type == "reasoning":
            # Stored in raw_output_items, not derived to normalized fields
            logger.debug("Preserving reasoning item in raw_output_items")
        
        else:
            # Unknown item type - preserve but log
            logger.debug(f"Preserving unknown Responses API item type: {item_type}")
    
    # Get usage if available
    usage = None
    if hasattr(response, 'usage') and response.usage:
        usage_obj = response.usage
        if hasattr(usage_obj, 'model_dump'):
            usage = usage_obj.model_dump()
        elif isinstance(usage_obj, dict):
            usage = usage_obj
        else:
            usage = {
                "input_tokens": getattr(usage_obj, 'input_tokens', 0),
                "output_tokens": getattr(usage_obj, 'output_tokens', 0),
                "total_tokens": getattr(usage_obj, 'total_tokens', 0),
            }
    
    return AssistantMessage(
        role="assistant",
        content="".join(text_parts) if text_parts else None,  # No separator - preserve exact text
        tool_calls=tool_calls or None,
        cost=cost,
        usage=usage,
        raw_output_items=raw_output_items,  # VERBATIM storage
    )


# =============================================================================
# OpenAI Responses API - Serialization
# =============================================================================

def to_responses_api_input(messages: list[Message]) -> list[dict]:
    """
    Build input array for litellm.responses().
    
    Unlike Chat Completions, Responses API input is a flat array mixing:
    - User messages (role-based)
    - System messages (role-based)
    - Previous output items (replayed verbatim)
    - function_call_output items (tool results)
    
    Critical: Replay raw_output_items exactly to preserve reasoning items
    for multi-turn behavioral consistency.
    """
    result = []
    
    for msg in messages:
        if isinstance(msg, SystemMessage):
            result.append({"role": "system", "content": msg.content})
        
        elif isinstance(msg, UserMessage):
            result.append({"role": "user", "content": msg.content})
        
        elif isinstance(msg, AssistantMessage):
            if msg.raw_output_items:
                # REPLAY VERBATIM - preserves reasoning items for multi-turn correctness
                # This is critical: OpenAI docs say to include reasoning in subsequent turns
                result.extend(msg.raw_output_items)
            else:
                # Fallback for legacy messages
                result.append({"role": "assistant", "content": msg.content})
        
        elif isinstance(msg, ToolMessage):
            # Tool result format differs from Chat Completions
            result.append({
                "type": "function_call_output",
                "call_id": msg.id,  # Must match function_call.call_id exactly
                "output": msg.content
            })
    
    return result


# =============================================================================
# OpenAI Responses API - Generate
# =============================================================================

def generate_responses_api(
    model: str,
    messages: list[Message],
    tools: Optional[list[Tool]] = None,
    parallel_tool_calls: bool = False,
    **kwargs: Any,
) -> AssistantMessage:
    """
    Generate using OpenAI Responses API via LiteLLM.
    
    Args:
        model: The model to use
        messages: The messages to send
        tools: The tools available
        parallel_tool_calls: Whether to allow parallel tool calls (default False for simplicity)
        **kwargs: Additional arguments
        
    Returns:
        AssistantMessage with raw_output_items for verbatim replay
    """
    if kwargs.get("num_retries") is None:
        kwargs["num_retries"] = DEFAULT_MAX_RETRIES
    
    input_array = to_responses_api_input(messages)
    tool_schemas = [tool.openai_schema for tool in tools] if tools else None
    
    try:
        response = litellm.responses(
            model=model,
            input=input_array,
            tools=tool_schemas,
            parallel_tool_calls=parallel_tool_calls,
            stream=False,  # Get complete response like chat completions
            **kwargs
        )
    except Exception as e:
        logger.error(f"Responses API error: {e}")
        raise e
    
    # Try to get cost
    try:
        cost = completion_cost(completion_response=response)
    except Exception:
        cost = 0.0
    
    return parse_responses_api(response, cost=cost)


def _parse_ft_model_name(model: str) -> str:
    """
    Parse the ft model name from the litellm model name.
    e.g: "ft:gpt-4.1-mini-2025-04-14:sierra::BSQA2TFg" -> "gpt-4.1-mini-2025-04-14"
    """
    pattern = r"ft:(?P<model>[^:]+):(?P<provider>\w+)::(?P<id>\w+)"
    match = re.match(pattern, model)
    if match:
        return match.group("model")
    else:
        return model


def get_response_cost(response: ModelResponse) -> float:
    """
    Get the cost of the response from the litellm completion.
    """
    response.model = _parse_ft_model_name(
        response.model
    )  # FIXME: Check Litellm, passing the model to completion_cost doesn't work.
    try:
        cost = completion_cost(completion_response=response)
    except Exception as e:
        logger.error(e)
        return 0.0
    return cost


def get_response_usage(response: ModelResponse) -> Optional[dict]:
    usage: Optional[Usage] = response.get("usage")
    if usage is None:
        return None
    return {
        "completion_tokens": usage.completion_tokens,
        "prompt_tokens": usage.prompt_tokens,
    }


def to_tau2_messages(
    messages: list[dict], ignore_roles: set[str] = set()
) -> list[Message]:
    """
    Convert a list of messages from a dictionary to a list of Tau2 messages.
    """
    tau2_messages = []
    for message in messages:
        role = message["role"]
        if role in ignore_roles:
            continue
        if role == "user":
            tau2_messages.append(UserMessage(**message))
        elif role == "assistant":
            tau2_messages.append(AssistantMessage(**message))
        elif role == "tool":
            tau2_messages.append(ToolMessage(**message))
        elif role == "system":
            tau2_messages.append(SystemMessage(**message))
        else:
            raise ValueError(f"Unknown message type: {role}")
    return tau2_messages


def to_litellm_messages(messages: list[Message]) -> list[dict]:
    """
    Convert a list of Tau2 messages to a list of litellm messages.
    """
    litellm_messages = []
    for message in messages:
        if isinstance(message, UserMessage):
            litellm_messages.append({"role": "user", "content": message.content})
        elif isinstance(message, AssistantMessage):
            tool_calls = None
            if message.is_tool_call():
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),
                        },
                        "type": "function",
                    }
                    for tc in message.tool_calls
                ]
            litellm_messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": tool_calls,
                }
            )
        elif isinstance(message, ToolMessage):
            litellm_messages.append(
                {
                    "role": "tool",
                    "content": message.content,
                    "tool_call_id": message.id,
                }
            )
        elif isinstance(message, SystemMessage):
            litellm_messages.append({"role": "system", "content": message.content})
    return litellm_messages


def generate(
    model: str,
    messages: list[Message],
    tools: Optional[list[Tool]] = None,
    tool_choice: Optional[str] = None,
    use_responses_api_flag: bool = False,
    **kwargs: Any,
) -> UserMessage | AssistantMessage:
    """
    Generate a response from the model.

    Args:
        model: The model to use. For Azure OpenAI, use format "azure/<deployment-name>".
               Set environment variables: AZURE_API_KEY, AZURE_API_BASE, AZURE_API_VERSION (optional).
        messages: The messages to send to the model.
        tools: The tools to use.
        tool_choice: The tool choice to use.
        use_responses_api_flag: Whether to use OpenAI Responses API instead of Chat Completions.
        **kwargs: Additional arguments to pass to the model.

    Returns: An AssistantMessage (or UserMessage in some edge cases).
    """
    if kwargs.get("num_retries") is None:
        kwargs["num_retries"] = DEFAULT_MAX_RETRIES

    # Check if we should use Responses API
    if use_responses_api(model, use_responses_api_flag):
        logger.debug(f"Using Responses API for model: {model}")
        return generate_responses_api(
            model=model,
            messages=messages,
            tools=tools,
            parallel_tool_calls=kwargs.pop("parallel_tool_calls", False),
            **kwargs
        )

    # Check if this is an Anthropic model
    is_anthropic = is_anthropic_model(model)
    
    # For Anthropic models, only set thinking to disabled if user hasn't provided thinking config
    # User can enable thinking via: --agent-llm-args '{"thinking": {"type": "enabled", "budget_tokens": 10000}}'
    if is_anthropic and "thinking" not in kwargs:
        kwargs["thinking"] = {"type": "disabled"}
    
    # GPT-5 models only support temperature=1 (not temperature=0)
    # Check if model is gpt-5 (including gpt-5.1, gpt-5.2, gpt-5-codex, gpt-5.1-chat-latest, etc.)
    # Handle both "gpt-5" and "azure/gpt-5" prefixes, and "openai/gpt-5" patterns
    is_gpt5_model = (
        "gpt-5" in model.lower() or 
        model.startswith("azure/gpt-5") or
        model.startswith("openai/gpt-5")
    )
    if is_gpt5_model:
        if kwargs.get("temperature") != 1:
            if kwargs.get("temperature") is not None:
                logger.warning(
                    f"GPT-5 models only support temperature=1. "
                    f"Received temperature={kwargs.get('temperature')}, setting to 1."
                )
            kwargs["temperature"] = 1
    
    # Add allowed OpenAI params (reasoning, reasoning_effort for o-series models)
    kwargs["allowed_openai_params"] = ["tool_choice"]
    
    # Use appropriate message conversion based on provider
    if is_anthropic:
        litellm_messages = to_litellm_messages_anthropic(messages)
    else:
        litellm_messages = to_litellm_messages(messages)
    
    tool_schemas = [tool.openai_schema for tool in tools] if tools else None
    if tool_schemas and tool_choice is None:
        tool_choice = "auto"
    
    try:
        # Allow reasoning_effort param for Azure OpenAI (GPT-5 models support it)
        completion_kwargs = dict(kwargs)
        if model.startswith("azure/") and "reasoning_effort" in kwargs:
            completion_kwargs["allowed_openai_params"] = ["reasoning_effort"]
        
        response = completion(
            model=model,
            messages=litellm_messages,
            tools=tool_schemas,
            tool_choice=tool_choice,
            **completion_kwargs,
        )
    except Exception as e:
        logger.error(e)
        raise e
    
    cost = get_response_cost(response)
    usage = get_response_usage(response)
    full_response = response
    response = response.choices[0]
    
    try:
        finish_reason = response.finish_reason
        if finish_reason == "length":
            logger.warning("Output might be incomplete due to token limit!")
    except Exception as e:
        logger.error(e)
        raise e
    
    assert response.message.role == "assistant", (
        "The response should be an assistant message"
    )
    
    # For Anthropic models, use specialized parsing to handle content blocks
    if is_anthropic:
        return parse_anthropic_response(
            response_message=response.message,
            cost=cost,
            usage=usage,
            raw_response_dict=response.to_dict(),
        )
    
    # Standard Chat Completions parsing
    content = response.message.content
    
    # Handle reasoning models that might return empty content
    if not content and hasattr(response.message, 'reasoning_content'):
        content = response.message.reasoning_content
    elif not content:
        # If still no content, check raw data for reasoning
        logger.warning(f"Empty content received from model. Raw response: {response.to_dict()}")
        content = None
    
    raw_tool_calls = response.message.tool_calls or []
    tool_calls = [
        ToolCall(
            id=tool_call.id,
            name=tool_call.function.name,
            arguments=json.loads(tool_call.function.arguments),
            arguments_raw=tool_call.function.arguments,  # Preserve original string
        )
        for tool_call in raw_tool_calls
    ]
    tool_calls = tool_calls or None

    message = AssistantMessage(
        role="assistant",
        content=content,
        tool_calls=tool_calls,
        cost=cost,
        usage=usage,
        raw_data=response.to_dict(),
    )
    return message


def get_cost(messages: list[Message]) -> tuple[float, float] | None:
    """
    Get the cost of the interaction between the agent and the user.
    Returns None if any message has no cost.
    """
    agent_cost = 0
    user_cost = 0
    for message in messages:
        if isinstance(message, ToolMessage):
            continue
        if message.cost is not None:
            if isinstance(message, AssistantMessage):
                agent_cost += message.cost
            elif isinstance(message, UserMessage):
                user_cost += message.cost
        else:
            logger.warning(f"Message {message.role}: {message.content} has no cost")
            return None
    return agent_cost, user_cost


def get_token_usage(messages: list[Message]) -> dict:
    """
    Get the token usage of the interaction between the agent and the user.
    """
    usage = {"completion_tokens": 0, "prompt_tokens": 0}
    for message in messages:
        if isinstance(message, ToolMessage):
            continue
        if message.usage is None:
            logger.warning(f"Message {message.role}: {message.content} has no usage")
            continue
        usage["completion_tokens"] += message.usage["completion_tokens"]
        usage["prompt_tokens"] += message.usage["prompt_tokens"]
    return usage