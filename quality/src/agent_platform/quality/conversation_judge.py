import json
import os
from dataclasses import dataclass
from typing import Any

import httpx

from agent_platform.quality.models import Message


@dataclass
class EvaluationResult:
    passed: bool
    value: Any
    error: str | None = None


class ConversationJudge:
    def __init__(self, agent_server_url):
        self.agent_server_url = agent_server_url

    async def evaluate(self, benchmark: list[Message], target: list[Message]):
        target_conversation = "\n\n".join([f"Message {i + 1}: {msg.content}" for i, msg in enumerate(target)])

        benchmark_conversation = "\n\n".join([f"Message {i + 1}: {msg.content}" for i, msg in enumerate(benchmark)])

        evaluation_prompt = (
            f"Please evaluate if the following conversation is CONSISTENT with the "
            f"benchmark according to the given criteria."
            f"Note that our agents have thoughts (visible to the user, but hidden by default; these"
            f"can be more verbose in nature) and tool calls (to carry out tasks). In a given agent"
            f"message the <text>...</text> is the agent's primary response."
            f"\n\n"
            f"CRITERIA:\n"
            f"- Allow natural variation in wording, but not in intent or outcomes."
            f"\n\n"
            f"TARGET CONVERSATION\n\n"
            f"{target_conversation}"
            f"\n\n"
            f"BENCHMARK CONVERSATION\n\n"
            f"{benchmark_conversation}"
            f"\n\n"
            f"Please respond with a JSON object containing (in this order):\n"
            f'- "explanation": a brief explanation of your thoughts/evaluation\n'
            f'- "score": a number from 0-10 indicating quality (10 = perfect match)\n'
            f'- "passed": true/false indicating if the response meets the criteria (score >= 6)\n'
            f"\n\n"
            f"Only respond with the JSON object, no other text."
        )

        prompt_data = {
            "system_instruction": (
                "You are an impartial evaluator of conversation quality and consistency. "
                "Provide accurate, objective evaluations."
            ),
            "messages": [{"role": "user", "content": [{"kind": "text", "text": evaluation_prompt}]}],
            "temperature": 0.1,
            "max_output_tokens": 500,
        }

        platform_config = {
            "kind": "openai",
            "openai_api_key": os.environ["OPENAI_API_KEY"],
        }

        async with httpx.AsyncClient(timeout=60.0 * 5) as client:
            response = await client.post(
                f"{self.agent_server_url}/api/v2/prompts/generate",
                json={
                    "prompt": prompt_data,
                    "platform_config_raw": platform_config,
                    "model": "gpt-5-low",
                },
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            llm_response = response.json()

            content_text = ""
            for content in llm_response.get("content", []):
                if content.get("kind") == "text":
                    content_text += content.get("text", "")

            try:
                eval_result = json.loads(content_text.strip())
                passed = eval_result.get("passed", False)
                explanation = eval_result.get("explanation", "No explanation provided")
                score = eval_result.get("score", 0)

                return EvaluationResult(
                    passed=passed,
                    value={
                        "passed": passed,
                        "explanation": explanation,
                        "score": score,
                        "llm_response": content_text,
                    },
                )
            except json.JSONDecodeError:
                content_lower = content_text.lower()
                passed = "true" in content_lower and "false" not in content_lower

                return EvaluationResult(
                    passed=passed,
                    value={
                        "passed": passed,
                        "explanation": "Parsed from text response",
                        "llm_response": content_text,
                    },
                )
