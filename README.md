# Monorepo Work In Progress

Initial setup with uv;

1. You need `uv` installed
2. `uv venv` to create a venv in the root directory
3. `source .venv/bin/activate` to activate the venv
4. `uv sync --all-extras --all-groups --all-packages` to install the whole monorepo
5. `PYTHONPATH=core/src:architectures/default/src:server/src uv run -m agent_platform.server` to run the server
6. `uv run pytest core/ server/` to run tests
7. `uv run ruff check` to lint everything

Blissfully simple.

(To run notebook, you need a terminal in `./server/examples/debug_widget` and to have `pnpm` installed; then `pnpm i` and `pnpm run dev` in that terminal to build the widget UX.)

Note: we have some dep that doesn't like python > 3.12 (at least on OSX). I had to run:

```shell
uv venv --python=python3.12
```

To make a venv pinned to 3.12 on my mac. Still easy peasy.
