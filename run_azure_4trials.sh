#!/bin/bash

# GPT-5 Azure runs with 4 trials
echo "Running GPT-5 Azure (high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5 \
  --agent-llm-args '{"reasoning_effort": "high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt5_highazure

echo "Running GPT-5 Azure (low reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5 \
  --agent-llm-args '{"reasoning_effort": "low"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt5_lowazure

echo "Running GPT-5 Azure (minimal reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5 \
  --agent-llm-args '{"reasoning_effort": "minimal"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt5_minimalazure

# GPT-5.1 Azure runs with 4 trials
echo "Running GPT-5.1 Azure (high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1 \
  --agent-llm-args '{"reasoning_effort": "high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51_highazure

echo "Running GPT-5.1 Azure (low reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1 \
  --agent-llm-args '{"reasoning_effort": "low"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51_lowazure

echo "Running GPT-5.1 Azure (medium reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1 \
  --agent-llm-args '{"reasoning_effort": "medium"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51_mediumazure

echo "Running GPT-5.1 Azure (no reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1 \
  --agent-llm-args '{"reasoning_effort": "none"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51_noneazure

# GPT-5.1 Codex Max Azure runs with 4 trials
echo "Running GPT-5.1 Codex Max Azure (low reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1-codex-max \
  --agent-llm-args '{"reasoning_effort": "low"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51cm_azure_low

echo "Running GPT-5.1 Codex Max Azure (medium reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1-codex-max \
  --agent-llm-args '{"reasoning_effort": "medium"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51cm_azure_medium

echo "Running GPT-5.1 Codex Max Azure (high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1-codex-max \
  --agent-llm-args '{"reasoning_effort": "high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51cm_azure_high

echo "Running GPT-5.1 Codex Max Azure (x-high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.1-codex-max \
  --agent-llm-args '{"reasoning_effort": "x-high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt51cm_azure_xhigh

# GPT-5.2 Azure runs with 4 trials
echo "Running GPT-5.2 Azure (high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2 \
  --agent-llm-args '{"reasoning_effort": "high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52_highazure

echo "Running GPT-5.2 Azure (low reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2 \
  --agent-llm-args '{"reasoning_effort": "low"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52_lowazure

echo "Running GPT-5.2 Azure (medium reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2 \
  --agent-llm-args '{"reasoning_effort": "medium"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52_medazure

echo "Running GPT-5.2 Azure (no reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2 \
  --agent-llm-args '{"reasoning_effort": "none"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52_noneazure

echo "Running GPT-5.2 Azure (x-high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2 \
  --agent-llm-args '{"reasoning_effort": "x-high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52_xhighazure

# GPT-5.2 Codex Azure runs with 4 trials
echo "Running GPT-5.2 Codex Azure (high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2-codex \
  --agent-llm-args '{"reasoning_effort": "high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52c_azure_high

echo "Running GPT-5.2 Codex Azure (low reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2-codex \
  --agent-llm-args '{"reasoning_effort": "low"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52c_azure_low

echo "Running GPT-5.2 Codex Azure (medium reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2-codex \
  --agent-llm-args '{"reasoning_effort": "medium"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52c_azure_medium

echo "Running GPT-5.2 Codex Azure (x-high reasoning)..."
tau2 run --domain telecom \
  --agent-llm azure/gpt-5.2-codex \
  --agent-llm-args '{"reasoning_effort": "x-high"}' \
  --user-llm azure/gpt-4.1 \
  --num-trials 4 \
  --max-concurrency 3 \
  --save-to gpt52c_azure_xhigh

echo "All runs completed!"
