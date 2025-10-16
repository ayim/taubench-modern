#!/usr/bin/env python3
"""
Work Items Stress Test Script

This script creates an agent and submits configurable batches of work items at regular intervals,
then monitors their status and reports on any errors.

Usage:
    python work_items_stress_test.py --server-url http://localhost:8080 \\
        --num-items 50 --interval 900

Environment variables:
    AGENT_SERVER_URL: Base URL of the agent server
    OPENAI_API_KEY: OpenAI API key for the agent
    AWS_ACCESS_KEY_ID: AWS access key for Bedrock (alternative to OpenAI)
    AWS_SECRET_ACCESS_KEY: AWS secret key for Bedrock
    AWS_DEFAULT_REGION: AWS region for Bedrock (default: us-east-1)
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx


@dataclass
class WorkItemStats:
    """Statistics for work items."""

    total_created: int = 0
    completed: int = 0
    error: int = 0
    needs_review: int = 0
    indeterminate: int = 0
    cancelled: int = 0
    executing: int = 0
    pending: int = 0


class WorkItemStressTest:
    """Manages the work items stress test."""

    def __init__(  # noqa: PLR0913
        self,
        server_url: str,
        num_items: int = 50,
        interval_seconds: int = 900,
        max_parallel: int = 50,
        use_openai: bool = True,
        action_server_url: str | None = None,
        action_server_api_key: str | None = None,
    ):
        self.server_url = server_url.rstrip("/")
        self.num_items = num_items
        self.interval_seconds = interval_seconds
        self.max_parallel = max_parallel
        self.use_openai = use_openai
        self.action_server_url = action_server_url
        self.action_server_api_key = action_server_api_key
        self.agent_ids: list[str] = []  # Now multiple agents
        self.work_item_ids: list[str] = []
        self.stats = WorkItemStats()
        # Track which actions to use
        self.actions = ["sleep_for_duration", "generate_random_words"]

    async def set_max_parallel_work_items(self) -> None:
        """Set the max parallel work items configuration."""
        print(f"⚙️  Setting max parallel work items to {self.max_parallel}...")

        payload = {
            "config_type": "MAX_PARALLEL_WORK_ITEMS",
            "current_value": str(self.max_parallel),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.server_url}/api/v2/config",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                print(f"✓ Max parallel work items set to {self.max_parallel}")
            except httpx.HTTPError as e:
                print(f"⚠️  Warning: Could not set max parallel work items: {e}")
                print("   Continuing with default configuration...")

    async def create_agent(self, agent_number: int) -> str:
        """Create an agent for the stress test."""
        print(f"🤖 Creating agent #{agent_number}...")

        if self.use_openai:
            openai_api_key = os.getenv("OPENAI_API_KEY", "UNSET")
            if openai_api_key == "UNSET":
                print("⚠️  Warning: OPENAI_API_KEY not set. Using placeholder.")

            platform_configs = [
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                }
            ]
            provider_name = "OpenAI"
        else:
            aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "UNSET")
            aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "UNSET")
            region_name = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

            if aws_access_key_id == "UNSET" or aws_secret_access_key == "UNSET":
                print("⚠️  Warning: AWS credentials not set. Using placeholders.")

            platform_configs = [
                {
                    "kind": "bedrock",
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                    "region_name": region_name,
                }
            ]
            provider_name = "AWS Bedrock"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build action packages if action server is provided
        action_packages = []
        if self.action_server_url:
            action_packages.append(
                {
                    "name": "StressTestActions",
                    "organization": "TestOrg",
                    "version": "1.0.0",
                    "url": self.action_server_url,
                    "api_key": {
                        "value": self.action_server_api_key or "",
                    },
                    "allowed_actions": self.actions,
                }
            )

        agent_payload = {
            "mode": "conversational",
            "name": f"Stress Test Agent #{agent_number} - {timestamp}",
            "version": "1.0.0",
            "description": (
                f"Agent #{agent_number} for stress testing work items with {provider_name}"
            ),
            "runbook": """# Objective
You are a helpful assistant designed to test the work items system.

# Instructions
When asked to run an action, execute it with the specified parameters.
Always confirm that you've completed the task successfully.
For simple questions, provide concise answers.
""",
            "platform_configs": platform_configs,
            "action_packages": action_packages,
            "mcp_servers": [],
            "agent_architecture": {
                "name": "agent_platform.architectures.default",
                "version": "1.0.0",
            },
            "observability_configs": [],
            "question_groups": [],
            "extra": {},
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.server_url}/api/v2/agents/",
                    json=agent_payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                agent_id = data["agent_id"]
                print(f"✓ Agent #{agent_number} created with ID: {agent_id}")
                return agent_id
            except httpx.HTTPError as e:
                print(f"❌ Failed to create agent #{agent_number}: {e}")
                if isinstance(e, httpx.HTTPStatusError):
                    print(f"   Response: {e.response.text}")
                sys.exit(1)

    async def create_work_item(self, batch_num: int, item_num: int) -> str | None:
        """Create a single work item."""
        # Randomly select an agent
        agent_id = random.choice(self.agent_ids)

        # Create message based on whether we have actions
        if self.action_server_url:
            # Randomly choose an action
            action = random.choice(self.actions)
            if action == "sleep_for_duration":
                duration = random.randint(30, 60)  # 30-60 seconds
                message_text = (
                    f"Please run the action sleep_for_duration with "
                    f"duration_seconds={duration}. This is work item #{item_num} "
                    f"from batch #{batch_num}."
                )
            else:  # generate_random_words
                word_count = random.randint(500, 1000)  # 500-1000 words
                message_text = (
                    f"Please run the action generate_random_words with "
                    f"word_count={word_count}. This is work item #{item_num} "
                    f"from batch #{batch_num}."
                )
        else:
            message_text = (
                f"This is test work item #{item_num} from "
                f"batch #{batch_num}. Please acknowledge this test message. "
                f"Created at {datetime.now().isoformat()}"
            )

        work_item_payload = {
            "agent_id": agent_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "kind": "text",
                            "text": message_text,
                            "complete": True,
                        }
                    ],
                    "complete": True,
                    "commited": True,
                }
            ],
            "payload": {
                "batch": batch_num,
                "item": item_num,
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
            },
            "work_item_name": f"Test Batch {batch_num} - Item {item_num}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.server_url}/api/v2/work-items/",
                    json=work_item_payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()
                work_item_id = data["work_item_id"]
                return work_item_id
            except httpx.HTTPError as e:
                print(f"   ❌ Failed to create work item {item_num}: {e}")
                return None

    async def create_work_items_batch(self, batch_num: int) -> None:
        """Create a batch of work items."""
        print(f"\n📝 Creating batch #{batch_num} with {self.num_items} work items...")
        start_time = time.time()

        # Create work items concurrently
        tasks = [self.create_work_item(batch_num, i) for i in range(1, self.num_items + 1)]
        results = await asyncio.gather(*tasks)

        # Filter out None values (failed creations)
        new_work_item_ids = [wid for wid in results if wid is not None]
        self.work_item_ids.extend(new_work_item_ids)
        self.stats.total_created += len(new_work_item_ids)

        elapsed = time.time() - start_time
        success_rate = (len(new_work_item_ids) / self.num_items) * 100

        print(
            f"✓ Created {len(new_work_item_ids)}/{self.num_items} work items "
            f"in {elapsed:.2f}s ({success_rate:.1f}% success rate)"
        )

    async def get_work_item_status(self, work_item_id: str) -> dict[str, Any] | None:
        """Get the status of a work item."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.server_url}/api/v2/work-items/{work_item_id}",
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError:
                return None

    async def poll_work_items_status(self) -> None:
        """Poll all work items and update statistics."""
        print("\n🔍 Polling work item statuses...")

        tasks = [self.get_work_item_status(wid) for wid in self.work_item_ids]
        results = await asyncio.gather(*tasks)

        # Reset stats (except total_created)
        total_created = self.stats.total_created
        self.stats = WorkItemStats()
        self.stats.total_created = total_created

        for result in results:
            if result is None:
                continue

            status = result.get("status", "UNKNOWN")
            if status == "COMPLETED":
                self.stats.completed += 1
            elif status == "ERROR":
                self.stats.error += 1
            elif status == "NEEDS_REVIEW":
                self.stats.needs_review += 1
            elif status == "INDETERMINATE":
                self.stats.indeterminate += 1
            elif status == "CANCELLED":
                self.stats.cancelled += 1
            elif status == "EXECUTING":
                self.stats.executing += 1
            elif status == "PENDING":
                self.stats.pending += 1

    def print_status_report(self) -> None:
        """Print a status report."""
        print("\n" + "=" * 70)
        print("📊 WORK ITEMS STATUS REPORT")
        print("=" * 70)
        print(f"Total Created:    {self.stats.total_created}")
        print(f"Completed:        {self.stats.completed}")
        print(f"Executing:        {self.stats.executing}")
        print(f"Pending:          {self.stats.pending}")
        print(f"Needs Review:     {self.stats.needs_review}")
        print(f"Error:            {self.stats.error}")
        print(f"Indeterminate:    {self.stats.indeterminate}")
        print(f"Cancelled:        {self.stats.cancelled}")
        print("=" * 70)

        if self.stats.error > 0:
            print(f"⚠️  WARNING: {self.stats.error} work items ended in ERROR state!")

        if self.stats.indeterminate > 0:
            print(f"⚠️  WARNING: {self.stats.indeterminate} work items are INDETERMINATE!")

    async def get_error_work_items(self) -> list[dict[str, Any]]:
        """Get detailed information about work items in error state."""
        error_items = []

        for work_item_id in self.work_item_ids:
            result = await self.get_work_item_status(work_item_id)
            if result and result.get("status") == "ERROR":
                error_items.append(result)

        return error_items

    async def print_error_details(self) -> None:
        """Print detailed information about work items in error state."""
        if self.stats.error == 0:
            return

        print("\n" + "=" * 70)
        print("❌ ERROR WORK ITEMS DETAILS")
        print("=" * 70)

        error_items = await self.get_error_work_items()

        for item in error_items:
            print(f"\nWork Item ID: {item['work_item_id']}")
            print(f"Name:         {item.get('work_item_name', 'N/A')}")
            print(f"Created:      {item['created_at']}")
            print(f"Updated:      {item['updated_at']}")
            if item.get("payload"):
                print(f"Payload:      {json.dumps(item['payload'], indent=2)}")
            print("-" * 70)

    async def continuous_monitoring(self, poll_interval: int = 10) -> None:
        """Continuously monitor work items until all are complete or error."""
        print(f"\n⏱️  Monitoring work items (polling every {poll_interval}s)...")
        print("   Press Ctrl+C to stop monitoring\n")

        try:
            while True:
                await self.poll_work_items_status()

                # Print a one-line status update
                in_progress = self.stats.executing + self.stats.pending
                print(
                    f"[{datetime.now().strftime('%H:%M:%S')}] "
                    f"In Progress: {in_progress} | "
                    f"Completed: {self.stats.completed} | "
                    f"Error: {self.stats.error} | "
                    f"Needs Review: {self.stats.needs_review}",
                    end="\r",
                )

                # Check if all items are in final state
                if in_progress == 0:
                    print()  # New line after the status update
                    print("\n✓ All work items have reached a final state!")
                    break

                await asyncio.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\n\n⚠️  Monitoring interrupted by user")

    async def run(self, batch_count: int = 1, continuous_monitor: bool = True) -> None:
        """Run the stress test."""
        print("\n" + "=" * 70)
        print("🚀 WORK ITEMS STRESS TEST")
        print("=" * 70)
        print(f"Server URL:          {self.server_url}")
        print(f"Items per batch:     {self.num_items}")
        print(f"Batch interval:      {self.interval_seconds}s")
        print(f"Max parallel items:  {self.max_parallel}")
        print(f"Number of batches:   {batch_count}")
        print("Number of agents:    2")
        provider = "OpenAI" if self.use_openai else "AWS Bedrock"
        print(f"Provider:            {provider}")
        if self.action_server_url:
            print(f"Action Server:       {self.action_server_url}")
            print(f"Actions:             {', '.join(self.actions)}")
        print("=" * 70)

        # Set max parallel work items
        await self.set_max_parallel_work_items()

        # Create two agents
        for i in range(1, 3):
            agent_id = await self.create_agent(i)
            self.agent_ids.append(agent_id)

        # Create work items in batches
        for batch_num in range(1, batch_count + 1):
            await self.create_work_items_batch(batch_num)

            # Wait between batches (except after the last batch)
            if batch_num < batch_count:
                print(f"\n⏳ Waiting {self.interval_seconds}s before next batch...")
                await asyncio.sleep(self.interval_seconds)

        # Monitor work items
        if continuous_monitor:
            await self.continuous_monitoring()
        else:
            # Just poll once
            await self.poll_work_items_status()

        # Print final report
        self.print_status_report()
        await self.print_error_details()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Work Items Stress Test for Agent Platform")
    parser.add_argument(
        "--server-url",
        type=str,
        default=os.getenv("AGENT_SERVER_URL", "http://localhost:8080"),
        help="Base URL of the agent server (default: from AGENT_SERVER_URL env var or http://localhost:8080)",
    )
    parser.add_argument(
        "--num-items",
        type=int,
        default=50,
        help="Number of work items to create per batch (default: 50)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=900,
        help="Interval between batches in seconds (default: 900 = 15 minutes)",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=50,
        help="Maximum parallel work items (default: 50)",
    )
    parser.add_argument(
        "--batch-count",
        type=int,
        default=1,
        help="Number of batches to create (default: 1)",
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Don't continuously monitor work items, just create them and poll once",
    )
    parser.add_argument(
        "--use-bedrock",
        action="store_true",
        help="Use AWS Bedrock instead of OpenAI (requires AWS credentials in env vars)",
    )
    parser.add_argument(
        "--action-server-url",
        type=str,
        default=None,
        help="URL of the Action Server with test actions (optional)",
    )
    parser.add_argument(
        "--action-server-api-key",
        type=str,
        default="test-key",
        help="API key for the Action Server (default: test-key)",
    )

    args = parser.parse_args()

    stress_test = WorkItemStressTest(
        server_url=args.server_url,
        num_items=args.num_items,
        interval_seconds=args.interval,
        max_parallel=args.max_parallel,
        use_openai=not args.use_bedrock,
        action_server_url=args.action_server_url,
        action_server_api_key=args.action_server_api_key,
    )

    await stress_test.run(batch_count=args.batch_count, continuous_monitor=not args.no_monitor)


if __name__ == "__main__":
    asyncio.run(main())
