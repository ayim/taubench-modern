from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel


# storage.get_agent_semantic_data_models returns SDMs in a form { sdm_id: sdm }, and for Agent Package
# use cases, we only need the actual SDM data.
def unwrap_semantic_data_model_dicts(semantic_data_model_dicts: list[dict]) -> list[SemanticDataModel]:
    semantic_data_models: list[SemanticDataModel] = []

    for sdm_dict in semantic_data_model_dicts:
        values = sdm_dict.values()

        if len(values) != 1:
            raise ValueError("Expected exactly one semantic data model per dict")

        semantic_data_models.append(next(iter(values)))

    return semantic_data_models
