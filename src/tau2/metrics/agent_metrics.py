import math
import re
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger
from pydantic import BaseModel

from tau2.data_model.simulation import Results


def is_successful(reward: float) -> bool:
    """
    Check if the reward is successful.
    """
    return (1 - 1e-6) <= reward <= (1 + 1e-6)


class TokenStats(BaseModel):
    """Token usage statistics."""
    total_input_tokens: int
    total_output_tokens: int
    total_turns: int
    num_simulations: int  # Number of runs/simulations
    num_test_cases: int  # Number of unique test cases (tasks)
    avg_input_per_test_case: float
    avg_output_per_test_case: float
    avg_turns_per_test_case: float
    input_p5: float
    input_p50: float
    input_p95: float
    output_p5: float
    output_p50: float
    output_p95: float
    turns_p5: float
    turns_p50: float
    turns_p95: float


class AgentMetrics(BaseModel):
    avg_reward: float
    pass_hat_ks: dict[int, float]
    avg_agent_cost: float
    token_stats: Optional[TokenStats] = None

    def as_dict(self) -> dict:
        data = {
            "avg_reward": self.avg_reward,
            "avg_agent_cost": self.avg_agent_cost,
        }
        for k, v in self.pass_hat_ks.items():
            data[f"pass_hat_{k}"] = v
        if self.token_stats:
            data.update({
                "total_input_tokens": self.token_stats.total_input_tokens,
                "total_output_tokens": self.token_stats.total_output_tokens,
                "total_turns": self.token_stats.total_turns,
            })
        return data


def pass_hat_k(num_trials: int, success_count: int, k: int) -> float:
    """
    Compute the pass^k metric for the given number of trials, success count, and k.
    from https://arxiv.org/pdf/2406.12045
    Args:
        num_trials: The number of trials.
        success_count: The number of successful trials.
        k: The number of trials to consider.
    Returns:
        The pass^k metric.
    """
    if num_trials < k:
        return 0.0  # Can't have k successes if we have fewer than k trials
    if success_count < k:
        return 0.0  # Can't choose k successes if we have fewer than k successes
    return math.comb(success_count, k) / math.comb(num_trials, k)


def get_metrics_df(results: Results) -> tuple[pd.DataFrame, int]:
    """
    Convert the results to a dataframe and add a column for success.
    Checks that all simulations have the same number of trials.
    Returns the maximum number of trials that can be used for pass^k metrics.
    """
    df = results.to_df()
    df["success"] = df.reward.apply(is_successful)
    if len(df.info_num_trials.unique()) > 1:
        logger.warning(
            f"All simulations must have the same number of trials. Found {df.info_num_trials.unique()}"
        )
    
    # Get the actual number of trials per task (may differ from expected if some failed)
    task_ids_counts = [(tid, count) for tid, count in df.task_id.value_counts().items()]
    if not task_ids_counts:
        logger.warning("No tasks found in results")
        return df, 0
    
    task_ids_counts.sort(key=lambda x: x[1])
    min_trials = task_ids_counts[0][1]
    max_trials = task_ids_counts[-1][1]
    
    # Use the maximum number of actual trials to calculate pass^k for all possible k values
    # Tasks with fewer trials will return 0.0 for k values they can't support
    max_k = max_trials
    
    if min_trials != max_trials:
        logger.info(
            f"Tasks have different numbers of trials (min: {min_trials}, max: {max_trials}). "
            f"Calculating pass^k for k=1 to {max_k}. Tasks with fewer than k trials will contribute 0.0."
        )
    else:
        logger.info(f"All tasks have {max_k} trials. Calculating pass^k for k=1 to {max_k}.")
    
    return df, max_k


def get_tasks_pass_hat_k(results: Results) -> pd.DataFrame:
    """
    Compute the pass^k for each k from 1 to the maximum number of trials.
    """
    df, max_k = get_metrics_df(results)
    dfs = []
    # Calculate pass^k for all k values from 1 to max_k
    for k in range(1, max_k + 1):
        res = df.groupby("task_id")["success"].apply(
            lambda task_successes: pass_hat_k(len(task_successes), task_successes.sum(), k)
        )
        res.name = f"pass^{k}"
        dfs.append(res)
    df_pass_hat_k = pd.concat(dfs, axis=1)
    task_columns = [
        "task_num_agent_actions",
        "task_num_user_actions",
        "task_num_actions",
    ]
    df_task_infos = df.groupby("task_id").first()[task_columns]
    df_pass_hat_k = df_task_infos.join(df_pass_hat_k)
    return df_pass_hat_k


def prepare_dfs(results: Results) -> tuple[pd.DataFrame, pd.DataFrame]:
    df, max_k = get_metrics_df(results)
    df_pass_hat_k = get_tasks_pass_hat_k(results)
    df_pass_hat_k["num_actions"] = df.groupby("task_id").first()["task_num_actions"]
    df_pass_hat_k = df_pass_hat_k.sort_values(by="num_actions")
    return df, df_pass_hat_k


def extract_token_stats(results: Results) -> Optional[TokenStats]:
    """
    Extract token usage statistics from simulation results.
    Calculates per-simulation token totals, then computes percentiles.
    Also calculates per-test-case (task) averages.
    Similar to extract_stats.py but works with Results objects.
    """
    all_input_tokens = []
    all_output_tokens = []
    all_turns = []
    
    # Group simulations by task_id to calculate per-test-case stats
    from collections import defaultdict
    task_tokens = defaultdict(lambda: {"input": 0, "output": 0, "turns": 0})
    
    # For each simulation, calculate total tokens
    for sim in results.simulations:
        messages = sim.messages
        
        # Count agent turns and tokens (only assistant messages)
        agent_turns = 0
        input_tokens = 0
        output_tokens = 0
        
        for msg in messages:
            # Only count assistant messages (agent responses)
            if msg.role == "assistant":
                usage = msg.usage
                if usage:
                    # Handle different usage formats - match extract_stats.py exactly
                    if isinstance(usage, dict):
                        # Use prompt_tokens/completion_tokens (OpenAI format)
                        # Fallback to input_tokens/output_tokens if needed
                        input_tokens += usage.get("prompt_tokens", usage.get("input_tokens", 0))
                        output_tokens += usage.get("completion_tokens", usage.get("output_tokens", 0))
                agent_turns += 1
        
        # Store per-simulation totals (for percentiles)
        if agent_turns > 0:
            all_input_tokens.append(input_tokens)
            all_output_tokens.append(output_tokens)
            all_turns.append(agent_turns)
            
            # Accumulate per task (test case)
            task_tokens[sim.task_id]["input"] += input_tokens
            task_tokens[sim.task_id]["output"] += output_tokens
            task_tokens[sim.task_id]["turns"] += agent_turns
    
    if not all_input_tokens:
        return None
    
    num_simulations = len(all_input_tokens)
    num_test_cases = len(task_tokens)
    
    # Calculate average per test case (across all trials for each task)
    if num_test_cases > 0:
        avg_input_per_test_case = sum(t["input"] for t in task_tokens.values()) / num_test_cases
        avg_output_per_test_case = sum(t["output"] for t in task_tokens.values()) / num_test_cases
        avg_turns_per_test_case = sum(t["turns"] for t in task_tokens.values()) / num_test_cases
    else:
        avg_input_per_test_case = 0
        avg_output_per_test_case = 0
        avg_turns_per_test_case = 0
    
    # Calculate percentiles across simulations (per test case stats)
    return TokenStats(
        total_input_tokens=sum(all_input_tokens),
        total_output_tokens=sum(all_output_tokens),
        total_turns=sum(all_turns),
        num_simulations=num_simulations,
        num_test_cases=num_test_cases,
        avg_input_per_test_case=avg_input_per_test_case,
        avg_output_per_test_case=avg_output_per_test_case,
        avg_turns_per_test_case=avg_turns_per_test_case,
        input_p5=float(np.percentile(all_input_tokens, 5)),
        input_p50=float(np.percentile(all_input_tokens, 50)),
        input_p95=float(np.percentile(all_input_tokens, 95)),
        output_p5=float(np.percentile(all_output_tokens, 5)),
        output_p50=float(np.percentile(all_output_tokens, 50)),
        output_p95=float(np.percentile(all_output_tokens, 95)),
        turns_p5=float(np.percentile(all_turns, 5)),
        turns_p50=float(np.percentile(all_turns, 50)),
        turns_p95=float(np.percentile(all_turns, 95)),
    )


def compute_metrics(results: Results) -> AgentMetrics:
    """
    Compute metrics for the agent.
    - average reward
    - pass^k
    - token statistics (input/output tokens)
    """
    df, df_pass_hat_k = prepare_dfs(results)
    avg_reward = df.reward.mean()
    pass_hat_ks = {}
    for column in df_pass_hat_k.columns:
        if match := re.match(r"pass\^(\d+)", column):
            k = int(match.group(1))
            pass_hat_ks[k] = df_pass_hat_k[column].mean()
    avg_agent_cost = df.agent_cost.mean()
    
    # Extract token statistics
    token_stats = extract_token_stats(results)
    
    return AgentMetrics(
        avg_reward=avg_reward,
        pass_hat_ks=pass_hat_ks,
        avg_agent_cost=avg_agent_cost,
        token_stats=token_stats,
    )


def display_metrics(metrics: AgentMetrics) -> None:
    print(f"🏆 Average reward: {metrics.avg_reward}")
    print("📈 Pass^k")
    for k, pass_hat_k in metrics.pass_hat_ks.items():
        print(f"  k={k}: {pass_hat_k}")
    print(f"💰 Average agent cost: {metrics.avg_agent_cost}")


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=str, required=True)
    args = parser.parse_args()
    results = Results.load(Path(args.results))
    metrics = compute_metrics(results)
    display_metrics(metrics)
