#!/usr/bin/env python3

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
AGENT_NAME = "agent"
PDF_FILE_PATH = Path(__file__).parent / "sample1.pdf"


async def verify_server_alive() -> bool:
    """Verify that the agent server is alive and responding."""
    print("🔍 Checking if agent server is alive...")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{BASE_URL}/api/v2/ok")
            response.raise_for_status()

            data = response.json()
            if data.get("ok") is True:
                print("✅ Agent server is alive and responding")
                return True
            else:
                print(f"❌ Agent server responded but with unexpected data: {data}")
                return False

    except httpx.RequestError as e:
        print(f"❌ Failed to connect to agent server: {e}")
        return False
    except httpx.HTTPStatusError as e:
        print(f"❌ Agent server returned error status {e.response.status_code}: {e.response.text}")
        return False


async def list_available_agents() -> list[dict[str, Any]]:
    """List all available agents for the current user."""
    print("🔍 Listing available agents...")

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            response = await client.get(f"{BASE_URL}/api/v2/agents")
            response.raise_for_status()

            agents = response.json()

            print(f"✅ Found {len(agents)} available agents:")
            for agent in agents:
                print(f"   - {agent.get('name', 'Unknown')} (ID: {agent.get('id', 'Unknown')})")

            return agents

    except httpx.HTTPStatusError as e:
        print(f"❌ Error listing agents: {e.response.status_code} - {e.response.text}")
        return []
    except httpx.RequestError as e:
        print(f"❌ Failed to connect to agent server: {e}")
        return []


async def lookup_agent_id(agent_name: str) -> str | None:
    """Look up the agent_id for an agent by name."""
    print(f"🔍 Looking up agent_id for agent named '{agent_name}'...")

    # First, list all available agents to see what's available
    agents = await list_available_agents()

    # Look for the agent by name
    for agent in agents:
        if agent.get("name", "").lower() == agent_name.lower():
            agent_id = agent.get("id")
            print(f"✅ Found agent '{agent_name}' with ID: {agent_id}")
            return agent_id

    print(f"Agent named '{agent_name}' not found among available agents")
    return None


async def _to_document_content(uploaded_file: Path) -> dict:
    import base64

    with open(uploaded_file, "rb") as f:
        value = f.read()

    return {
        "kind": "document",
        "name": uploaded_file.name,
        "mime_type": "application/pdf",
        "value": base64.b64encode(value).decode("utf-8"),
        "sub_type": "base64",
    }


async def call_prompts_generate(
    agent_id: str,
    uploaded_file: Path,
) -> dict[str, Any] | None:
    """Call the prompts/generate endpoint with a simple hello world message."""
    print("🚀 Calling prompts/generate endpoint...")

    # Create the request payload with just the prompt
    request_payload = {
        "prompt": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"kind": "text", "text": "Please summarize this document."},
                        await _to_document_content(uploaded_file),
                    ],
                },
            ]
        }
    }

    print(f"📝 Request payload: {json.dumps(request_payload, indent=2)}")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{BASE_URL}/api/v2/prompts/generate",
                json=request_payload,
                params={"agent_id": agent_id},
            )
            response.raise_for_status()

            result = response.json()
            print("✅ Successfully called prompts/generate endpoint!")
            print(f"📝 Response: {json.dumps(result, indent=2)}")
            return result

    except httpx.HTTPStatusError as e:
        print(f"❌ Error calling prompts/generate: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"❌ Failed to connect to agent server: {e}")
        return None


async def main():
    """Main function that orchestrates the entire flow."""
    print("🤖 Agent Platform Prompts/Generate Test Script")
    print("=" * 50)

    # Step 1: Verify server is alive
    if not await verify_server_alive():
        print("\n❌ Cannot proceed - agent server is not responding")
        sys.exit(1)

    print()

    # Step 2: Look up agent ID
    agent_id = await lookup_agent_id(AGENT_NAME)
    if not agent_id:
        print(f"\n❌ Cannot proceed - agent '{AGENT_NAME}' not found")
        sys.exit(1)

    print()

    # Step 4: Call prompts/generate
    result = await call_prompts_generate(agent_id, PDF_FILE_PATH)
    if not result:
        print("\n❌ Failed to call prompts/generate endpoint")
        sys.exit(1)

    print("\n🎉 All steps completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
