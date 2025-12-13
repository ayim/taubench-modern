from typing import Any

import structlog
from fastapi import HTTPException, status
from ruamel.yaml import YAML

from agent_platform.core.agent.question_group import QuestionGroup
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler

_yaml = YAML(typ="safe")

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def read_question_groups(handler: AgentPackageHandler) -> list[QuestionGroup]:
    conversation_guide_raw = await handler.read_conversation_guide_raw()

    if not conversation_guide_raw:
        return []

    try:
        guide_yaml = _yaml.load(conversation_guide_raw.decode())
        qg_list = guide_yaml.get("question-groups", []) if isinstance(guide_yaml, dict) else []

        question_groups = [QuestionGroup.model_validate(qg) for qg in qg_list if isinstance(qg, dict)]

        return question_groups
    except Exception as e:
        logger.error(
            "Failed to parse or validate conversation guide",
            exc_info=True,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to parse or validate conversation guide",
        ) from e


async def read_semantic_data_models(
    handler: AgentPackageHandler,
) -> dict[str, dict[str, Any]] | None:
    """
    Extract semantic data models from the semantic-data-models/ folder.

    Returns:
        Dictionary mapping filename to SDM content (parsed YAML), or None if no SDMs
    """
    logger.info("[_extract_semantic_data_models] Starting SDM extraction")
    spec_agent = await handler.get_spec_agent()
    sdm_refs = spec_agent.semantic_data_models or []

    logger.info(f"[_extract_semantic_data_models] Found {len(sdm_refs)} SDM references in spec: {sdm_refs}")

    if not sdm_refs:
        logger.info("[_extract_semantic_data_models] No SDM references found, returning None")
        return None

    sdms: dict[str, dict[str, Any]] = {}

    for sdm_ref in sdm_refs:
        sdm_filename = sdm_ref.name
        if not sdm_filename:
            logger.warning("SDM reference missing 'name' field, skipping")
            continue

        try:
            sdm_bytes = await handler.read_semantic_data_model_raw(sdm_filename)
            # Parse YAML (Snowflake Cortex Analyst semantic model format)
            sdm_content = _yaml.load(sdm_bytes.decode("utf-8"))

            if not isinstance(sdm_content, dict):
                logger.warning(
                    "SDM file '%s' does not contain valid YAML dict, skipping",
                    sdm_filename,
                )
                continue

            sdms[sdm_filename] = sdm_content
            logger.info(f"[_extract_semantic_data_models] Successfully extracted SDM: {sdm_filename}")

        except KeyError:
            logger.warning(f"[_extract_semantic_data_models] SDM file not found in package: {sdm_filename}")
        except Exception as e:
            logger.error(
                f"[_extract_semantic_data_models] Failed to parse SDM file {sdm_filename}: {e}",
                exc_info=True,
                error=str(e),
            )
            # Continue with other SDMs even if one fails
            continue

    result = sdms if sdms else None
    sdm_count = len(sdms) if sdms else 0
    sdm_keys = list(sdms.keys()) if sdms else []
    logger.info(f"[_extract_semantic_data_models] Extraction complete. Returning {sdm_count} SDMs: {sdm_keys}")
    return result
