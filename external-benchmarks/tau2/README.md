# Tau2 Benchmark Helper

This directory contains a thin wrapper around the upstream
[`tau2-bench`](https://github.com/sierra-research/tau2-bench) repository so we
can pull it into the `agent-platform` workspace, keep it updated, and install
its editable Python package with a single command.

## Prerequisites

- `git`
- [`uv`](https://github.com/astral-sh/uv) (this repo manages all Python deps with `uv`)
- Python 3.10+ available on your path (tau2-bench's minimum)

## Setup

From the root of the `agent-platform` repo run:

```bash
make -C external-benchmarks/tau2 setup
```

The `setup` target does the following:

1. Clone `https://github.com/sierra-research/tau2-bench.git` into
   `external-benchmarks/tau2/tau2-bench.git` as a bare mirror (no nested `.git`
   inside the working copy so IDEs stay clean).
2. Fetch the requested ref (defaults to `main`) and fast-forward the local bare repo.
3. Export a fresh working tree into `external-benchmarks/tau2/tau2-bench` without
   any git metadata.
4. Run `uv pip install -e external-benchmarks/tau2/tau2-bench` from the repo
   root so the `tau2` CLI becomes available in the shared environment.

The install step reuses the workspace virtual environment at
`<repo>/.venv`. Ensure you have already run `make sync` (which creates and
hydrates that environment) before invoking the `setup` target. You can always
inspect the available helper targets via:

```bash
make -C external-benchmarks/tau2 help
```

You can override the repository URL, checkout ref, or target directory via
environment variables:

```bash
TAU2_BENCH_REF=v0.2.0 make -C external-benchmarks/tau2 setup
```

> **Heads up:** If you previously ran `setup` before this bare-clone workflow was
> added, delete `external-benchmarks/tau2/tau2-bench` (and its embedded `.git`)
> before re-running so the directory is exported without nested git metadata.

## Running τ²-bench

Once `tau2` is installed into the shared `.venv`, you can run benchmarks straight
from the monorepo root without touching the upstream repo manually. The helper
Makefile calls `run_tau2.py` via `<repo>/.venv/bin/python`, which stubs the optional
`gymnasium` dependency (so we stay compatible with upstream without installing RL
extras) and forwards every argument to `tau2.cli`.

### Quick starts

Run the airline domain against a custom model (with five smoke-test tasks):

```bash
make -C external-benchmarks/tau2 run-airline \
  TAU2_AGENT_LLM=gpt-4o-mini \
  TAU2_USER_LLM=gpt-4o-mini \
  TAU2_SAVE_TO=airline_smoke \
  TAU2_NUM_TASKS=5
```

If the target reports that `tau2` is missing from the workspace virtualenv, it will
automatically trigger `make -C external-benchmarks/tau2 install` before running.
When `gymnasium` is absent, the wrapper automatically injects a stub so non-RL
commands continue to work. Install the real dependency only if you need the gym
interfaces downstream.

Other convenience targets:

- `make -C external-benchmarks/tau2 run-retail`
- `make -C external-benchmarks/tau2 run-telecom`
- `make -C external-benchmarks/tau2 run-mock`

All of them accept the same variable overrides shown above. Use the generic
`run` target if you want to set `TAU2_DOMAIN` yourself.

## Using the Sema4AI agent shim

You can run tau2 against an agent hosted by the local agent server without
patching upstream by setting `TAU2_AGENT` to a value that starts with
`sema4ai`. The value format is `sema4ai/<platform>[:model][@architecture]`. For example:

```bash
make -C external-benchmarks/tau2 run-airline \
  TAU2_AGENT=sema4ai/openai:gpt-5-low \
  TAU2_AGENT_LLM_ARGS='{}'
```

When the wrapper sees the `sema4ai/*` prefix it will:

1. Ensure an agent server is available. If `SEMA4AI_BASE_URL` is not already
   set, `run_tau2.py` bootstraps a local instance under
   `external-benchmarks/tau2/.agent-server` (override with
   `TAU2_AGENTSERVER_HOME`). Set `TAU2_BOOTSTRAP_AGENT_SERVER=false` to skip
   auto-starting and manage the server yourself.
2. Register a shimmed tau2 agent named exactly after the value passed in
   `TAU2_AGENT`, so the standard CLI choices continue to work.

For remote servers set `SEMA4AI_BASE_URL` to the websocket root
(`ws://host:port`). The shim derives the HTTP base automatically.

### Architecture selection

Append `@default`, `@experimental_1`, `@experimental_2`, etc. to the agent spec
to select the architecture, or set `TAU2_AGENT_ARCHITECTURE=experimental_2`. The
shim maps those aliases to fully qualified architecture packages when
registering with tau2.

```bash
make -C external-benchmarks/tau2 run-telecom \
  TAU2_AGENT='sema4ai/openai:gpt-5-low@experimental_2' \
  TAU2_AGENT_LLM_ARGS='{}'
```

### Required credentials

Depending on the platform selected, set the following environment variables so
the shim can create the agent via the `/api/v2/agents` endpoint:

- OpenAI: `SEMA4AI_TAU2_OPENAI_API_KEY` (optional override `SEMA4AI_TAU2_MODEL`)
- Groq: `SEMA4AI_TAU2_GROQ_API_KEY`
- Bedrock: `SEMA4AI_TAU2_BEDROCK_ACCESS_KEY_ID`,
  `SEMA4AI_TAU2_BEDROCK_SECRET_ACCESS_KEY`, and optional
  `SEMA4AI_TAU2_BEDROCK_REGION_NAME`

Every entry also falls back to the common root `.env` names (`OPENAI_API_KEY`,
`GROQ_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, etc.) so existing
developer setups keep working without renaming variables.

The shim automatically creates or updates a persistent agent+thread per domain
before each tau2 turn and forwards tool calls over the websocket connection.

### Common knobs

Pass any of these variables on the `make` command line to control a run:

- `TAU2_AGENT` / `TAU2_USER` (default to `llm_agent` / `user_simulator`)
- `TAU2_AGENT_LLM` / `TAU2_USER_LLM` and their `_ARGS`
- `TAU2_NUM_TASKS`, `TAU2_TASK_IDS`, `TAU2_NUM_TRIALS`
- `TAU2_TASK_SPLIT` (defaults to `base` for leaderboard compatibility)
- `TAU2_SAVE_TO` to name the output JSON in `tau2-bench/data/simulations`
- `TAU2_DATA_DIR` if you keep the tau2 dataset elsewhere

Set `TAU2_ENFORCE_PROTOCOL=true` to forward the CLI flag of the same name or
use `TAU2_EXTRA_ARGS='--max-errors 5'` for uncommon switches. Combine the above
as needed to evaluate new models quickly.

> **Note**: When passing JSON blobs (e.g. `TAU2_AGENT_LLM_ARGS`), quote them at
> the shell level: `TAU2_AGENT_LLM_ARGS='{"temperature": 0.3}'`.

## After installation

Once installed, follow the upstream README (`tau2-bench/README.md`) for
additional data download instructions and available commands (e.g. `tau2 eval`,
`make env-cli`, etc.). If you use a non-editable install, remember to set
`TAU2_DATA_DIR` as described by tau2-bench.

The `tau2-bench/` directory is ignored via `.gitignore` so we never accidentally
commit the cloned repository.
