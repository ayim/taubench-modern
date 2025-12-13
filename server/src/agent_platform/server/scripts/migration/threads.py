import json
import uuid

import structlog

logger = structlog.get_logger(__name__)


def convert_thread_to_v2_format(v1_thread: dict) -> dict:
    def require(key: str) -> str:
        val = v1_thread.get(key)
        if not val:
            raise Exception(f"Skipping thread because it has no {key}")
        return val

    thread_id = require("thread_id")
    agent_id = require("agent_id")
    user_id = require("user_id")
    name = require("name")
    created_at = require("created_at")
    updated_at = require("updated_at")

    # Ensure metadata is never None/null - always provide a valid dict
    metadata = v1_thread.get("metadata")
    if metadata is None:
        metadata = {}

    return {
        "thread_id": thread_id,
        "agent_id": agent_id,
        "user_id": user_id,
        "name": name,
        "created_at": created_at,
        "updated_at": updated_at,
        "metadata": json.dumps(metadata),
    }


async def migrate_threads(storage):
    """
    Migrate threads using the provided storage connection
    Args:
        storage: Connected storage interface
    """
    try:
        threads = await storage.get_all_threads()
        all_messages_to_insert = []  # Collect all messages here

        for v1_thread in threads:
            try:
                thread_dict = convert_thread_to_v2_format(v1_thread)
            except Exception as e:
                logger.error(f"Skipping thread: {v1_thread.get('name', 'unknown')} - error converting format: {e}")
                continue

            try:
                await storage.insert_thread(thread_dict)
                logger.info(f"Successfully migrated thread: {v1_thread['name']}")
                latest_checkpoint_record = await storage.get_latest_checkpoint(v1_thread["thread_id"])
                latest_checkpoint = latest_checkpoint_record["checkpoint"].decode("utf-8")

                latest_checkpoint = json.loads(latest_checkpoint)
                checkpoint_messages = latest_checkpoint["channel_values"]["messages"]
                ts = latest_checkpoint["ts"]
                sequence_id = 0
                for message in checkpoint_messages:
                    # Original message id is not a valid uuid, so we generate a new one
                    message_id = str(uuid.uuid4())
                    message_type = message["kwargs"]["type"]
                    message_content = message["kwargs"]["content"]
                    current_message_sequence_id = sequence_id
                    current_thread_id = v1_thread["thread_id"]
                    parent_run_id = None
                    role = "agent" if message_type == "ai" else "user" if message_type == "human" else "tool"
                    agent_metadata = {}
                    server_metadata = {}

                    v2_thread_message_content = []

                    # Handle non-tool messages: create standard text content
                    if role != "tool" and message_content:
                        v2_thread_message_content = [
                            {
                                "content_id": message_id,
                                "kind": "text",
                                "complete": True,
                                "text": message_content,
                                "citations": [],
                            }
                        ]

                    # Handle tool messages: attach tool results to the previous agent message
                    # In the v1 format, tool results come as separate messages after the agent's
                    # tool calls. In v2 format, tool results should be embedded within the agent
                    # message's tool_call content. So we find the last inserted message
                    # (which should be the agent message with tool calls),
                    # and attach this tool result to the appropriate tool call within that message.
                    if role == "tool":
                        if all_messages_to_insert:
                            last_inserted_message = all_messages_to_insert.pop()
                            last_inserted_content = json.loads(last_inserted_message["content"])
                            if last_inserted_content:
                                # Add the tool result to the last tool call in the previous message
                                last_inserted_content[-1]["result"] = message["kwargs"]["content"]
                                last_inserted_message["content"] = json.dumps(last_inserted_content)
                            all_messages_to_insert.append(last_inserted_message)
                            continue

                    if role == "agent":
                        if (
                            "kwargs" in message
                            and "additional_kwargs" in message["kwargs"]
                            and "tool_calls" in message["kwargs"]["additional_kwargs"]
                            and len(message["kwargs"]["additional_kwargs"]["tool_calls"]) > 0
                        ):
                            for each_tool_call in message["kwargs"]["additional_kwargs"]["tool_calls"]:
                                v2_thread_message_content.append(
                                    {
                                        "content_id": str(uuid.uuid4()),
                                        "kind": "tool_call",
                                        "complete": True,
                                        "name": each_tool_call["function"]["name"],
                                        "tool_call_id": each_tool_call["id"],
                                        "arguments_raw": each_tool_call["function"]["arguments"],
                                        "status": "finished",
                                    }
                                )
                        elif (
                            "kwargs" in message
                            and "tool_calls" in message["kwargs"]
                            and len(message["kwargs"]["tool_calls"]) > 0
                        ):
                            for each_tool_call in message["kwargs"]["tool_calls"]:
                                v2_thread_message_content.append(
                                    {
                                        "content_id": str(uuid.uuid4()),
                                        "kind": "tool_call",
                                        "complete": True,
                                        "name": each_tool_call["name"],
                                        "tool_call_id": each_tool_call["id"],
                                        "arguments_raw": json.dumps(each_tool_call["args"]),
                                        "status": "finished",
                                    }
                                )

                    v2_thread_message_data = {
                        "message_id": message_id,
                        "sequence_number": current_message_sequence_id,
                        "thread_id": current_thread_id,
                        "parent_run_id": parent_run_id,
                        "created_at": ts,
                        "updated_at": ts,
                        "role": role,
                        "content": json.dumps(v2_thread_message_content),
                        "agent_metadata": json.dumps(agent_metadata),
                        "server_metadata": json.dumps(server_metadata),
                    }

                    # Add message to collection instead of inserting immediately
                    all_messages_to_insert.append(v2_thread_message_data)
                    sequence_id += 1

            except Exception as e:
                logger.error(f"Error migrating thread {v1_thread['name']}: {e}")

        # Insert all messages at the end
        logger.info(f"Starting batch insertion of {len(all_messages_to_insert)} messages...")
        for message_data in all_messages_to_insert:
            try:
                await storage.insert_v2_thread_message(message_data)
                logger.info(f"Successfully migrated message: {message_data['message_id']}")
            except Exception as e:
                logger.error(f"Error migrating message {message_data['message_id']}: {e}")

        logger.info(f"Completed batch insertion of {len(all_messages_to_insert)} messages")

    except Exception as e:
        logger.error(f"Error during threads migration: {e}")
        raise

    logger.info("Threads migration completed!")
