import logging
import os
import threading
from collections.abc import Hashable

import requests
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from agent_platform.core.agent.observability_config import ObservabilityConfig

logger = logging.getLogger(__name__)


class ConditionalLangSmithProcessor(SpanProcessor):
    """
    Processor that routes spans to LangSmith based on agent_id,
    unless a global LangSmith config is set via env vars.
    If all three env vars (LANGCHAIN_API_KEY, LANGCHAIN_ENDPOINT, LANGCHAIN_PROJECT) are set,
    all spans are exported to a single global LangSmith processor,
    and per-agent configs are ignored.
    """

    _instance: "ConditionalLangSmithProcessor | None" = None
    _instance_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "ConditionalLangSmithProcessor":
        """Get the singleton instance of ConditionalLangSmithProcessor.

        Returns:
            The singleton instance
        """
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls()
                logger.debug("Created ConditionalLangSmithProcessor singleton instance")
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (primarily for testing).

        This will shutdown the existing instance if it exists.
        """
        with cls._instance_lock:
            if cls._instance is not None:
                try:
                    cls._instance.shutdown()
                except Exception as e:
                    logger.warning(f"Error shutting down processor during reset: {e}")
                cls._instance = None
                logger.debug("Reset ConditionalLangSmithProcessor singleton instance")

    def __init__(self):
        """Initialize the processor.

        Note: This should only be called by get_instance(). Do not call directly.
        """
        self._processors: dict[str, BatchSpanProcessor] = {}
        self._signatures: dict[str, Hashable] = {}
        self._lock = threading.Lock()
        self._global_processor: BatchSpanProcessor | None = None
        # Check for global LangSmith config via env vars
        cfg = self._env_cfg_from_vars()
        if cfg:
            self._global_processor = self._build_processor(cfg)
            logger.info(
                "Using Global LangSmith config from environment; per-agent configs will be ignored."
            )
        logger.debug("ConditionalLangSmithProcessor initialized")

    @staticmethod
    def _env_cfg_from_vars() -> "ObservabilityConfig | None":
        """
        Check for required LangSmith env vars and return an ObservabilityConfig if all are present.
        """
        api_key = os.getenv("LANGCHAIN_API_KEY")
        api_url = os.getenv("LANGCHAIN_ENDPOINT")
        project = os.getenv("LANGCHAIN_PROJECT")
        if all([api_key, api_url, project]):
            return ObservabilityConfig(
                type="langsmith",
                api_key=api_key,
                api_url=api_url,
                settings={"project_name": project},
            )
        return None

    @staticmethod
    def _signature(cfg: ObservabilityConfig) -> tuple[str, str, str]:
        """
        Create a hashable tuple that fully determines the exporter configuration.
        If the signature changes, we need to recreate the processor.
        """
        endpoint = (cfg.api_url or "https://api.smith.langchain.com").rstrip("/")
        api_key = (cfg.api_key or "").strip()
        project = cfg.settings.get("project_name", "").strip()
        return (endpoint, api_key, project)

    @staticmethod
    def _build_langsmith_session() -> requests.Session | None:
        """
        Build a requests.Session that:
        - trusts enterprise MITM certs via truststore
        - uses enterprise proxy settings
        using sema4ai-http-helper, but only for LangSmith OTLP exporter.
        """
        from requests.adapters import HTTPAdapter
        from sema4ai_http import get_network_profile

        net = get_network_profile()  # SSL context + proxy config (http, https, no_proxy)

        # Build an adapter that injects the SSL context into urllib3 pool managers.
        class _SSLContextAdapter(HTTPAdapter):
            def __init__(self, ssl_context, *args, **kwargs):
                self._ssl_context = ssl_context
                super().__init__(*args, **kwargs)

            def init_poolmanager(self, *args, **kwargs):
                # Force our ssl_context into the PoolManager constructor
                kwargs["ssl_context"] = self._ssl_context
                return super().init_poolmanager(*args, **kwargs)

            def proxy_manager_for(self, proxy, **kwargs):
                kwargs["ssl_context"] = self._ssl_context
                return super().proxy_manager_for(proxy, **kwargs)

        s = requests.Session()
        if net.ssl_context:
            adapter = _SSLContextAdapter(net.ssl_context)
            s.mount("https://", adapter)
            s.mount("http://", adapter)

        # Apply proxies if present in the profile (pick the first defined because
        # requests doesn't support providing multiple and chosing one).
        if net.proxy_config.http:
            prev = s.proxies.get("http")
            new = net.proxy_config.http[0]
            s.proxies["http"] = new
            logger.debug(f"Overriding LangSmith exporter http proxy from {prev} to {new}")

        if net.proxy_config.https:
            prev = s.proxies.get("https")
            new = net.proxy_config.https[0]
            s.proxies["https"] = new
            logger.debug(f"Overriding LangSmith exporter https proxy from {prev} to {new}")

        return s

    def _build_processor(self, cfg: ObservabilityConfig) -> BatchSpanProcessor:
        endpoint, api_key, project = self._signature(cfg)
        if not endpoint.endswith("/otel/v1/traces"):
            endpoint = endpoint + "/otel/v1/traces"

        logger.debug(f"Creating LangSmith exporter: endpoint={endpoint}, project={project}")

        session = ConditionalLangSmithProcessor._build_langsmith_session()

        exporter = OTLPSpanExporter(
            endpoint=endpoint,
            headers={
                "x-api-key": api_key,
                "Langsmith-Project": project,
            },
            session=session,
        )
        return BatchSpanProcessor(exporter)

    @staticmethod
    def _get_agent_id(span) -> str | None:
        """Extract agent_id from span attributes."""
        if not span.attributes:
            return None

        # Check for "agent_id" first (preferred)
        agent_id = span.attributes.get("agent_id")
        if agent_id:
            return str(agent_id)

        # Fallback to "agent.id" for backward compatibility
        agent_id = span.attributes.get("agent.id")
        if agent_id:
            return str(agent_id)

        return None

    def add_or_update_config(self, agent_id: str, cfg: ObservabilityConfig) -> bool:
        """
        Register or update LangSmith configuration for an agent.
        In global mode (env vars set), this is a no-op and returns False.
        """
        if self._global_processor:
            logger.info(
                f"Global LangSmith config is active; "
                f"ignoring per-agent config for agent {agent_id}."
            )
            return True
        if not agent_id or not cfg or not cfg.api_key:
            logger.debug(f"Skipping LangSmith config for agent {agent_id}: missing required fields")
            return False

        # Validate project name
        # TODO: We should use "default" for project name,
        # but we error out in a different place (agent_compat)
        # if project name is not set.
        # Hence, replicating the same behavior here.
        project = cfg.settings.get("project_name", "").strip()
        if not project:
            logger.error(f"Invalid LangSmith config for agent {agent_id}: missing project_name")
            return False

        new_sig = self._signature(cfg)

        with self._lock:
            # Check if configuration is already up-to-date
            old_sig = self._signatures.get(agent_id)
            if old_sig == new_sig:
                logger.debug(f"LangSmith config for agent {agent_id} is already up-to-date")
                return False

            # Shutdown old processor if it exists
            if agent_id in self._processors:
                try:
                    self._processors[agent_id].shutdown()
                    logger.debug(f"Shutdown old LangSmith processor for agent {agent_id}")
                except Exception as e:
                    logger.warning(f"Failed to shutdown old processor for agent {agent_id}: {e}")

            # Create and register new processor
            try:
                self._processors[agent_id] = self._build_processor(cfg)
                self._signatures[agent_id] = new_sig
                logger.info(
                    f"Registered/updated LangSmith config: agent {agent_id} → project {project}"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to create LangSmith processor for agent {agent_id}: {e}")
                return False

    def on_start(self, span, parent_context=None):
        """
        Route span start to appropriate LangSmith processor based on agent_id or global config.
        """
        if self._global_processor:
            try:
                self._global_processor.on_start(span, parent_context)
            except Exception as e:
                logger.error(f"Error in global LangSmith processor on_start: {e}")
            return
        agent_id = self._get_agent_id(span)
        if not agent_id:
            return

        with self._lock:
            processor = self._processors.get(agent_id)

        if processor:
            try:
                processor.on_start(span, parent_context)
            except Exception as e:
                logger.error(f"Error in LangSmith processor on_start for agent {agent_id}: {e}")

    def on_end(self, span):
        """Route span to appropriate LangSmith processor based on agent_id or global config."""
        if self._global_processor:
            try:
                self._global_processor.on_end(span)
                logger.debug(f"Exported span '{span.name}' to Global LangSmith processor.")
            except Exception as e:
                logger.error(f"Error in global LangSmith processor on_end: {e}")
            return
        agent_id = self._get_agent_id(span)
        if not agent_id:
            return

        with self._lock:
            processor = self._processors.get(agent_id)

        if processor:
            try:
                processor.on_end(span)
                logger.debug(f"Exported span '{span.name}' to LangSmith for agent {agent_id}")
            except Exception as e:
                logger.error(f"Error in LangSmith processor on_end for agent {agent_id}: {e}")

    def shutdown(self):
        """Shutdown all processors (global or per-agent)."""
        logger.debug("Shutting down ConditionalLangSmithProcessor")
        if self._global_processor:
            try:
                self._global_processor.shutdown()
                logger.debug("Shutdown global LangSmith processor")
            except Exception as e:
                logger.error(f"Error shutting down global LangSmith processor: {e}")
            return
        with self._lock:
            for agent_id, processor in self._processors.items():
                try:
                    processor.shutdown()
                    logger.debug(f"Shutdown LangSmith processor for agent {agent_id}")
                except Exception as e:
                    logger.error(f"Error shutting down processor for agent {agent_id}: {e}")

            self._processors.clear()
            self._signatures.clear()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush all processors (global or per-agent)."""
        logger.debug("Force flushing ConditionalLangSmithProcessor")
        if self._global_processor:
            try:
                result = self._global_processor.force_flush(timeout_millis)
                logger.debug(f"Force flush result for global LangSmith processor: {result}")
                return result
            except Exception as e:
                logger.error(f"Error force flushing global LangSmith processor: {e}")
                return False
        with self._lock:
            processors = list(self._processors.items())

        results = []
        # Note: This may take up to len(self.processors) * 30s to complete
        # (vs. the 30s in total) that is expected from OTEL's API.
        for agent_id, processor in processors:
            try:
                result = processor.force_flush(timeout_millis)
                results.append(result)
                logger.debug(f"Force flush result for agent {agent_id}: {result}")
            except Exception as e:
                logger.error(f"Error force flushing processor for agent {agent_id}: {e}")
                results.append(False)

        overall_result = all(results) if results else True
        logger.debug(f"ConditionalLangSmithProcessor force flush overall result: {overall_result}")
        return overall_result
