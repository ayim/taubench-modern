import json
import os
import re
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError
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


# =============================================================================
# Lazy configuration — runs once on first generate() call, not at import time
# =============================================================================

_configured = False


def _ensure_configured():
    """Configure litellm, Azure, caching, and Langfuse on first use."""
    global _configured
    if _configured:
        return
    _configured = True

    if USE_LANGFUSE:
        litellm.success_callback = ["langfuse"]
        litellm.failure_callback = ["langfuse"]

    # Azure OpenAI: use env vars if set, otherwise fall back to config values
    azure_api_key = os.getenv("AZURE_API_KEY", AZURE_API_KEY)
    azure_api_base = os.getenv("AZURE_API_BASE", AZURE_API_BASE)
    azure_api_version = os.getenv("AZURE_API_VERSION", AZURE_API_VERSION)

    os.environ["AZURE_API_KEY"] = azure_api_key
    os.environ["AZURE_API_BASE"] = azure_api_base
    os.environ["AZURE_API_VERSION"] = azure_api_version

    logger.info("Azure OpenAI configuration set. Models with 'azure/' prefix will use Azure OpenAI.")
    logger.info(f"Azure OpenAI endpoint: {azure_api_base}")
    logger.info(f"Azure OpenAI API version: {azure_api_version}")
    logger.info(f"Azure region: {AZURE_REGION}")

    if os.getenv("OPENAI_API_KEY"):
        logger.info("OpenAI API key detected. Direct OpenAI models (e.g., gpt-5.2) will use OpenAI API.")
    else:
        logger.warning("OPENAI_API_KEY not set. Direct OpenAI models (e.g., gpt-5.2) may fail without API key.")

    # Cache
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
    # Could be model-based (e.g., o1, o3 reasoning models, codex models) or config-driven
    model_lower = model.lower()
    
    # Remove azure/ prefix for matching
    if model_lower.startswith("azure/"):
        model_lower = model_lower[6:]
    
    # Check for reasoning/codex models that should use Responses API
    return (
        config_flag or 
        model_lower.startswith("o1") or 
        model_lower.startswith("o3") or
        "codex" in model_lower  # gpt-5.1-codex-max, gpt-5.2-codex, etc.
    )


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
    
    NOTE: litellm normalizes responses, storing thinking blocks separately in
    response_message.thinking_blocks. We reconstruct the Anthropic content array
    format with thinking blocks FIRST (required for multi-turn with thinking enabled).
    """
    # Get the content - could be string or list of blocks
    content_data = response_message.content
    
    # Check for litellm's separate thinking_blocks field (used by Bedrock and other providers)
    thinking_blocks = getattr(response_message, 'thinking_blocks', None) or []
    
    # Check for litellm's separate tool_calls field (OpenAI format)
    litellm_tool_calls = getattr(response_message, 'tool_calls', None) or []
    
    # Debug: Log what litellm actually returned
    logger.debug(f"parse_anthropic_response: content_data type={type(content_data)}, "
                 f"thinking_blocks={len(thinking_blocks) if thinking_blocks else 0}, "
                 f"tool_calls={len(litellm_tool_calls) if litellm_tool_calls else 0}")
    if thinking_blocks:
        logger.debug(f"Thinking blocks: {[tb.get('type') if isinstance(tb, dict) else getattr(tb, 'type', 'unknown') for tb in thinking_blocks]}")
    
    # If we have thinking_blocks from litellm, we need to reconstruct Anthropic format
    # Thinking blocks MUST come first, then text, then tool_use
    if thinking_blocks:
        logger.debug(f"Found {len(thinking_blocks)} thinking blocks from litellm")
        raw_content_blocks = []
        
        # 1. Add thinking blocks first (REQUIRED - must precede tool_use)
        for tb in thinking_blocks:
            if hasattr(tb, 'model_dump'):
                raw_content_blocks.append(tb.model_dump())
            elif hasattr(tb, 'to_dict'):
                raw_content_blocks.append(tb.to_dict())
            elif isinstance(tb, dict):
                raw_content_blocks.append(tb)
            else:
                # Convert to dict format
                block_dict = {"type": getattr(tb, 'type', 'thinking')}
                if hasattr(tb, 'thinking'):
                    block_dict["thinking"] = tb.thinking
                if hasattr(tb, 'signature'):
                    block_dict["signature"] = tb.signature
                if hasattr(tb, 'data'):
                    block_dict["data"] = tb.data
                raw_content_blocks.append(block_dict)
        
        # 2. Add text content if present
        if content_data and isinstance(content_data, str):
            raw_content_blocks.append({"type": "text", "text": content_data})
        
        # 3. Add tool_use blocks from litellm's tool_calls
        for tc in litellm_tool_calls:
            raw_content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.function.name,
                "input": json.loads(tc.function.arguments),
            })
        
        # 4. Ensure thinking is not the final block (Bedrock requirement)
        # If we only have thinking blocks, add an empty text block
        if raw_content_blocks and raw_content_blocks[-1].get("type") in ("thinking", "redacted_thinking"):
            # Check if there's any non-thinking content
            has_non_thinking = any(
                b.get("type") not in ("thinking", "redacted_thinking") 
                for b in raw_content_blocks
            )
            if not has_non_thinking:
                # Add empty text block - required by Bedrock
                raw_content_blocks.append({"type": "text", "text": ""})
                logger.debug("Added empty text block after thinking (Bedrock requirement)")
        
        # Derive normalized fields
        text_parts = [content_data] if content_data and isinstance(content_data, str) else []
        tool_calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments),
                arguments_raw=tc.function.arguments,
            )
            for tc in litellm_tool_calls
        ]
        
        logger.debug(f"Creating AssistantMessage with raw_content_blocks types: {[b.get('type') for b in raw_content_blocks]}")
        return AssistantMessage(
            role="assistant",
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls or None,
            cost=cost,
            usage=usage,
            raw_data=raw_response_dict,
            raw_content_blocks=raw_content_blocks,  # VERBATIM storage with thinking first
        )
    
    # If content is a simple string (non-extended-thinking mode), handle normally
    if isinstance(content_data, str):
        tool_calls = None
        if litellm_tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                    arguments_raw=tc.function.arguments,
                )
                for tc in litellm_tool_calls
            ]
        return AssistantMessage(
            role="assistant",
            content=content_data,
            tool_calls=tool_calls or None,
            cost=cost,
            usage=usage,
            raw_data=raw_response_dict,
        )
    
    # Content is a list of blocks - extended thinking mode (direct Anthropic API)
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
                # REPLAY raw_content_blocks - preserves thinking/redacted_thinking/signatures
                # This is used for direct Anthropic API (non-Bedrock), which properly handles thinking
                content_blocks = list(msg.raw_content_blocks)  # Make a copy
                
                logger.debug(f"Serializing assistant message with content types: {[b.get('type') for b in content_blocks]}")
                result.append({
                    "role": "assistant",
                    "content": content_blocks
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
# AWS Bedrock Direct API (boto3) - Bypasses litellm for proper thinking support
# =============================================================================

# Cache for Bedrock clients by region
_bedrock_clients: dict[str, Any] = {}


def _get_bedrock_client(region: str = None):
    """Get or create a cached Bedrock Runtime client."""
    region = region or os.environ.get("AWS_REGION_NAME", "us-east-1")
    if region not in _bedrock_clients:
        _bedrock_clients[region] = boto3.client("bedrock-runtime", region_name=region)
    return _bedrock_clients[region]


def _is_bedrock_retryable_error(exception: Exception) -> bool:
    """
    Check if a Bedrock error is retryable.
    
    Matches litellm's approach: retry on rate limits, service errors, timeouts.
    Non-retryable: ValidationException, AccessDeniedException, etc.
    """
    if isinstance(exception, ClientError):
        error_code = exception.response.get("Error", {}).get("Code", "")
        # Retryable errors (transient)
        retryable = error_code in (
            "ThrottlingException",
            "ServiceUnavailableException",
            "ModelStreamErrorException",
            "InternalServerException",
            "ModelTimeoutException",
        )
        # Non-retryable errors (client errors, validation, auth)
        non_retryable = error_code in (
            "ValidationException",
            "AccessDeniedException",
            "ResourceNotFoundException",
            "ModelNotReadyException",
        )
        return retryable and not non_retryable
    # Retry on connection/timeout errors
    return isinstance(exception, (ConnectionError, TimeoutError))


def _convert_messages_for_bedrock(messages: list[Message]) -> tuple[list[dict], str | None]:
    """
    Convert Tau2 messages to Bedrock Converse API format.
    
    Returns:
        Tuple of (messages, system_prompt)
    """
    bedrock_messages = []
    system_prompt = None
    pending_tool_results = []
    
    for msg in messages:
        if isinstance(msg, SystemMessage):
            system_prompt = msg.content
        
        elif isinstance(msg, AssistantMessage):
            # Flush pending tool results first
            if pending_tool_results:
                bedrock_messages.append({
                    "role": "user",
                    "content": pending_tool_results
                })
                pending_tool_results = []
            
            content = []
            
            # If we have raw_content_blocks, replay them (preserves thinking)
            if msg.raw_content_blocks:
                for block in msg.raw_content_blocks:
                    block_type = block.get("type")
                    if block_type == "thinking":
                        content.append({
                            "reasoningContent": {
                                "reasoningText": {
                                    "text": block.get("thinking", ""),
                                    "signature": block.get("signature", "")
                                }
                            }
                        })
                    elif block_type == "redacted_thinking":
                        content.append({
                            "reasoningContent": {
                                "redactedContent": block.get("data", "")
                            }
                        })
                    elif block_type == "text":
                        if block.get("text"):
                            content.append({"text": block.get("text", "")})
                    elif block_type == "tool_use":
                        tool_name = block.get("name", "")
                        # Validate tool name matches Bedrock regex: [a-zA-Z0-9_-]+
                        if not tool_name or not re.match(r'^[a-zA-Z0-9_-]+$', tool_name):
                            logger.warning(f"Invalid tool name '{tool_name}', using 'unknown_tool'")
                            tool_name = "unknown_tool"
                        content.append({
                            "toolUse": {
                                "toolUseId": block.get("id", "") or f"tool_{len(content)}",
                                "name": tool_name,
                                "input": block.get("input", {})
                            }
                        })
            else:
                # Fallback for messages without raw_content_blocks
                if msg.content:
                    content.append({"text": msg.content})
                if msg.tool_calls:
                    for idx, tc in enumerate(msg.tool_calls):
                        tool_name = tc.name or "unknown_tool"
                        # Validate tool name matches Bedrock regex: [a-zA-Z0-9_-]+
                        if not re.match(r'^[a-zA-Z0-9_-]+$', tool_name):
                            logger.warning(f"Invalid tool name '{tool_name}', using 'unknown_tool'")
                            tool_name = "unknown_tool"
                        content.append({
                            "toolUse": {
                                "toolUseId": tc.id or f"tool_{idx}",
                                "name": tool_name,
                                "input": tc.arguments
                            }
                        })
            
            if content:
                bedrock_messages.append({"role": "assistant", "content": content})
        
        elif isinstance(msg, ToolMessage):
            pending_tool_results.append({
                "toolResult": {
                    "toolUseId": msg.id,
                    "content": [{"text": msg.content or ""}],
                    "status": "error" if msg.error else "success"
                }
            })
        
        elif isinstance(msg, UserMessage):
            # Flush pending tool results first
            if pending_tool_results:
                bedrock_messages.append({
                    "role": "user",
                    "content": pending_tool_results
                })
                pending_tool_results = []
            
            bedrock_messages.append({
                "role": "user",
                "content": [{"text": msg.content or ""}]
            })
    
    # Flush remaining tool results
    if pending_tool_results:
        bedrock_messages.append({
            "role": "user",
            "content": pending_tool_results
        })
    
    return bedrock_messages, system_prompt


def _convert_tools_for_bedrock(tools: list[Tool]) -> dict:
    """Convert tools to Bedrock toolConfig format."""
    if not tools:
        return {}
    
    tool_specs = []
    for tool in tools:
        schema = tool.openai_schema
        tool_name = schema["function"]["name"]
        # Validate tool name matches Bedrock regex: [a-zA-Z0-9_-]+
        if not re.match(r'^[a-zA-Z0-9_-]+$', tool_name):
            # Sanitize: replace invalid chars with underscore
            original_name = tool_name
            tool_name = re.sub(r'[^a-zA-Z0-9_-]', '_', tool_name)
            logger.warning(f"Sanitized tool name '{original_name}' -> '{tool_name}'")
        tool_specs.append({
            "toolSpec": {
                "name": tool_name,
                "description": schema["function"].get("description", ""),
                "inputSchema": {
                    "json": schema["function"].get("parameters", {"type": "object", "properties": {}})
                }
            }
        })
    
    return {
        "toolConfig": {
            "tools": tool_specs,
            "toolChoice": {"auto": {}}
        }
    }


def _parse_bedrock_response(response: dict, model: str) -> AssistantMessage:
    """Parse Bedrock Converse API response into AssistantMessage."""
    output = response.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])
    
    # Build raw_content_blocks in Anthropic format for storage
    raw_content_blocks = []
    text_parts = []
    tool_calls = []
    
    for block in content_blocks:
        if "reasoningContent" in block:
            reasoning = block["reasoningContent"]
            if "reasoningText" in reasoning:
                raw_content_blocks.append({
                    "type": "thinking",
                    "thinking": reasoning["reasoningText"].get("text", ""),
                    "signature": reasoning["reasoningText"].get("signature", "")
                })
            elif "redactedContent" in reasoning:
                raw_content_blocks.append({
                    "type": "redacted_thinking",
                    "data": reasoning["redactedContent"]
                })
        
        elif "text" in block:
            text_parts.append(block["text"])
            raw_content_blocks.append({
                "type": "text",
                "text": block["text"]
            })
        
        elif "toolUse" in block:
            tool_use = block["toolUse"]
            tool_name = tool_use.get("name", "")
            tool_id = tool_use.get("toolUseId", "") or f"tool_{len(tool_calls)}"
            # Validate tool name
            if not tool_name:
                logger.warning(f"Empty tool name in Bedrock response, block: {block}")
                tool_name = "unknown_tool"
            tool_calls.append(ToolCall(
                id=tool_id,
                name=tool_name,
                arguments=tool_use.get("input", {}),
                arguments_raw=json.dumps(tool_use.get("input", {}), separators=(',', ':'))
            ))
            raw_content_blocks.append({
                "type": "tool_use",
                "id": tool_id,
                "name": tool_name,
                "input": tool_use.get("input", {})
            })
    
    # Calculate usage
    usage_data = response.get("usage", {})
    usage = {
        "prompt_tokens": usage_data.get("inputTokens", 0),
        "completion_tokens": usage_data.get("outputTokens", 0),
        "total_tokens": usage_data.get("inputTokens", 0) + usage_data.get("outputTokens", 0)
    }
    
    # Calculate cost using litellm's cost function
    try:
        # litellm needs the model name without bedrock/ prefix for cost lookup
        # and uses anthropic. prefix for Claude models
        litellm_model = model.replace("bedrock/", "").replace("us.", "")
        cost = litellm.cost_calculator.completion_cost(
            model=litellm_model,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"]
        )
    except Exception as e:
        logger.debug(f"Could not calculate cost via litellm: {e}, falling back to model_cost lookup")
        # Fallback: look up per-token costs from litellm's model_cost registry
        cost = 0.0
        cost_entry = litellm.model_cost.get(litellm_model, {})
        input_cost_per_token = cost_entry.get("input_cost_per_token", 0)
        output_cost_per_token = cost_entry.get("output_cost_per_token", 0)
        if input_cost_per_token or output_cost_per_token:
            cost = (usage["prompt_tokens"] * input_cost_per_token) + (usage["completion_tokens"] * output_cost_per_token)
        else:
            logger.warning(f"No cost data found for model '{litellm_model}' in litellm.model_cost; cost will be 0")
    
    return AssistantMessage(
        role="assistant",
        content=" ".join(text_parts) if text_parts else None,
        tool_calls=tool_calls if tool_calls else None,
        cost=cost,
        usage=usage,
        raw_data=response,
        raw_content_blocks=raw_content_blocks if raw_content_blocks else None
    )


def _bedrock_converse_with_retry(client, request: dict, num_retries: int = DEFAULT_MAX_RETRIES) -> dict:
    """
    Make Bedrock converse call with retry logic matching litellm's approach.
    
    Uses exponential backoff (like litellm's exponential_backoff_retry strategy)
    with retries only on transient errors.
    """
    import tenacity
    
    retryer = tenacity.Retrying(
        wait=tenacity.wait_exponential(multiplier=1, max=10),  # Match litellm: max=10
        stop=tenacity.stop_after_attempt(num_retries),
        retry=tenacity.retry_if_exception(_is_bedrock_retryable_error),
        reraise=True,
    )
    return retryer(client.converse, **request)


def generate_bedrock_converse(
    model: str,
    messages: list[Message],
    tools: Optional[list[Tool]] = None,
    thinking_budget: Optional[int] = None,
    temperature: float = 1.0,
    max_tokens: int = 8192,
    num_retries: int = DEFAULT_MAX_RETRIES,
    **kwargs
) -> AssistantMessage:
    """
    Generate a response using AWS Bedrock Converse API directly via boto3.
    
    This bypasses litellm to properly support extended thinking for Claude models.
    
    Args:
        model: The model ID (e.g., "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0")
        messages: The conversation messages
        tools: Optional tools/functions
        thinking_budget: If set, enables extended thinking with this token budget
        temperature: Sampling temperature (default 1.0 for thinking models)
        max_tokens: Maximum output tokens
        num_retries: Number of retries for transient errors (default: DEFAULT_MAX_RETRIES)
    """
    # Extract model ID from bedrock/ prefix
    model_id = model.replace("bedrock/", "")
    
    # Convert messages
    bedrock_messages, system_prompt = _convert_messages_for_bedrock(messages)
    
    # Build request
    request = {
        "modelId": model_id,
        "messages": bedrock_messages,
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
        }
    }
    
    # Add system prompt if present
    if system_prompt:
        request["system"] = [{"text": system_prompt}]
    
    # Add tools if present
    if tools:
        tool_config = _convert_tools_for_bedrock(tools)
        request.update(tool_config)
    
    # Add thinking/reasoning config
    if thinking_budget and thinking_budget > 0:
        # max_tokens must be > budget_tokens, so ensure we have room for actual output
        # Set max_tokens to budget + 16k for response, capped at 64k
        min_max_tokens = thinking_budget + 16384
        if request["inferenceConfig"]["maxTokens"] < min_max_tokens:
            request["inferenceConfig"]["maxTokens"] = min(min_max_tokens, 65536)
            logger.debug(f"Adjusted maxTokens to {request['inferenceConfig']['maxTokens']} for thinking budget {thinking_budget}")
        
        request["additionalModelRequestFields"] = {
            "thinking": {
                "type": "enabled",
                "budget_tokens": thinking_budget
            }
        }
        # Thinking requires temperature=1
        request["inferenceConfig"]["temperature"] = 1.0
        logger.debug(f"Bedrock extended thinking enabled with budget: {thinking_budget}")
    
    # Make the API call with retry
    client = _get_bedrock_client()
    
    try:
        logger.debug(f"Bedrock converse request: model={model_id}, messages={len(bedrock_messages)}")
        response = _bedrock_converse_with_retry(client, request, num_retries=num_retries)
        logger.debug(f"Bedrock converse response: stop_reason={response.get('stopReason')}")
        
        return _parse_bedrock_response(response, model)
        
    except Exception as e:
        logger.error(f"Bedrock converse error: {e}")
        raise


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
    
    # Convert tool schemas to Responses API format
    # Chat Completions: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
    # Responses API:    {"type": "function", "name": ..., "description": ..., "parameters": ...}
    tool_schemas = None
    if tools:
        tool_schemas = []
        for tool in tools:
            chat_schema = tool.openai_schema
            # Flatten the function object to top level
            if "function" in chat_schema:
                func = chat_schema["function"]
                tool_schemas.append({
                    "type": "function",
                    "name": func.get("name"),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
            else:
                # Already in flat format
                tool_schemas.append(chat_schema)
    
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
    _ensure_configured()

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

    # Check if this is an Anthropic model or Bedrock
    is_anthropic = is_anthropic_model(model)
    is_bedrock = model.startswith("bedrock/")
    
    # For Bedrock, use our direct boto3 implementation (bypasses litellm bugs with thinking)
    if is_bedrock:
        # Extract thinking config
        thinking_config = kwargs.pop("thinking", {})
        thinking_budget = None
        if thinking_config.get("type") == "enabled":
            thinking_budget = thinking_config.get("budget_tokens", 10000)
        
        # Extract supported kwargs before removing unsupported ones
        num_retries = kwargs.pop("num_retries", DEFAULT_MAX_RETRIES)
        temperature = kwargs.pop("temperature", 1.0)
        max_tokens = kwargs.pop("max_tokens", 8192)
        
        # Remove unsupported kwargs for our direct implementation
        kwargs.pop("seed", None)
        kwargs.pop("allowed_openai_params", None)
        
        logger.debug(f"Using direct boto3 for Bedrock: {model}, thinking_budget={thinking_budget}")
        return generate_bedrock_converse(
            model=model,
            messages=messages,
            tools=tools,
            thinking_budget=thinking_budget,
            temperature=temperature,
            max_tokens=max_tokens,
            num_retries=num_retries,
            **kwargs
        )
    
    # For direct Anthropic models, set thinking to disabled if user hasn't provided thinking config
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
    
    # Use standard OpenAI-format messages for all litellm calls.
    # litellm handles OpenAI-to-Anthropic translation internally (anthropic_messages_pt).
    # Note: extended thinking multi-turn replay requires the Bedrock boto3 path above,
    # which uses its own message converter (_convert_messages_for_bedrock).
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