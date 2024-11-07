import os

from agent_server_types import MODEL, AgentServerKernalBase, VectorStoreBase

from sema4ai_agent_server.storage.embed import get_chroma_vector, get_pg_vector


class AgentServerKernal(AgentServerKernalBase):
    def get_vector_store(self, model: MODEL | None = None) -> VectorStoreBase:
        db_type = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite")
        if db_type == "postgres":
            return get_pg_vector(model)
        elif db_type == "sqlite":
            return get_chroma_vector(model)
        raise ValueError("Invalid storage type")
