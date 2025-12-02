#!/usr/bin/env python3
import asyncio
import os
from uuid import uuid4


async def main() -> None:
    # Lazy imports per repo style
    from agent_platform.core.integrations import Integration
    from agent_platform.core.integrations.settings.reducto import ReductoSettings
    from agent_platform.core.utils import SecretString
    from agent_platform.server.storage.errors import IntegrationNotFoundError
    from agent_platform.server.storage.option import StorageService

    endpoint = os.environ.get("REDUCTO_ENDPOINT")
    api_key = os.environ.get("REDUCTO_API_KEY")
    if not endpoint or not api_key:
        raise SystemExit("Set REDUCTO_ENDPOINT and REDUCTO_API_KEY")

    storage = StorageService.get_instance()
    await storage.setup()

    # Reuse existing ID if present; otherwise create one
    try:
        existing = await storage.get_integration_by_kind("reducto")
        integration_id = existing.id
        print(f"Updating existing reducto integration {integration_id}")
    except IntegrationNotFoundError:
        integration_id = str(uuid4())
        print(f"Creating reducto integration {integration_id}")

    # Store as plain string; storage layer encrypts config, so JSON encoding succeeds.
    integration = Integration(
        id=integration_id,
        kind="reducto",
        settings=ReductoSettings(endpoint=endpoint, api_key=api_key),
    )

    await storage.upsert_integration(integration)
    print("Reducto integration saved")


if __name__ == "__main__":
    asyncio.run(main())

# USAGE: REDUCTO_ENDPOINT=... REDUCTO_API_KEY=... \
# uv run --project agent_platform_server python scripts/seed_reducto_integration.py
