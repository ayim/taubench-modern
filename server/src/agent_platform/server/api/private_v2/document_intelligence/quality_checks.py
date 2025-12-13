from fastapi import APIRouter
from sema4ai_docint import ValidationRule, ValidationSummary, validate_document_extraction
from sema4ai_docint.models.constants import PROJECT_NAME
from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.utils import normalize_name
from starlette.concurrency import run_in_threadpool
from structlog import get_logger

from agent_platform.core.document_intelligence.data_models import (
    ExecuteDataQualityChecksRequest,
    GenerateDataQualityChecksRequest,
    GenerateDataQualityChecksResponse,
)
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.server.api.dependencies import (
    AgentServerClientDependency,
    DocIntDatasourceDependency,
)

logger = get_logger(__name__)


router = APIRouter()


@router.post("/quality-checks/generate")
async def generate_quality_checks(
    payload: GenerateDataQualityChecksRequest,
    docint_ds: DocIntDatasourceDependency,
    agent_server_client: AgentServerClientDependency,
) -> GenerateDataQualityChecksResponse:
    try:
        if payload.description and payload.limit != 1:
            raise PlatformHTTPError(
                ErrorCode.BAD_REQUEST,
                "If a description is provided, limit count must be 1",
            )
        data_model_name = normalize_name(payload.data_model_name)
        data_model = DataModel.find_by_name(docint_ds, data_model_name)
        if not data_model:
            raise PlatformHTTPError(ErrorCode.NOT_FOUND, f"Data model not found: {data_model_name}")
        views = data_model.views
        if not views:
            raise PlatformHTTPError(
                ErrorCode.NOT_FOUND,
                f"No views have been defined for the data model: {payload.data_model_name}",
            )
        validation_rules = await run_in_threadpool(
            agent_server_client.generate_validation_rules,
            rules_description=payload.description,
            data_model=data_model,
            datasource=docint_ds,
            database_name=PROJECT_NAME,
            limit_count=payload.limit,
        )
        # we only return the first `limit` rules,
        # so we need to log a warning if we didn't generate enough
        if len(validation_rules) < payload.limit:
            logger.warning(f"Generated {len(validation_rules)} data quality checks, expected {payload.limit}")
        final_validation_rules = [ValidationRule.model_validate(rule) for rule in validation_rules]
        return GenerateDataQualityChecksResponse(quality_checks=final_validation_rules)
    except PlatformHTTPError:
        raise
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to generate data quality checks: {e!s}") from e


@router.post("/quality-checks/execute")
async def execute_quality_checks(
    payload: ExecuteDataQualityChecksRequest,
    docint_ds: DocIntDatasourceDependency,
) -> ValidationSummary:
    try:
        validation_summary = validate_document_extraction(payload.document_id, docint_ds, payload.quality_checks)
        return validation_summary
    except Exception as e:
        raise PlatformHTTPError(ErrorCode.UNEXPECTED, f"Failed to execute data quality checks: {e!s}") from e
