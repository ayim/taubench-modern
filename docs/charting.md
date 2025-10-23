# Charting Capabilities

This note traces how Vega/Vega-Lite charting is wired end-to-end across the agent platform: prompt scaffolds, runtime data structures, server/data-frame plumbing, and SPAR‑UI rendering.

## Agent Architecture Prompts

- **Default scaffold.** The default conversation prompt explicitly teaches chart output inside the `<response>` block by embedding a fenced `vega`/`vega-lite` code block with a v5 schema (`architectures/default/src/agent_platform/architectures/default/prompts/default/conversation-default.yml:94-121`). The same file later reminds the agent _not_ to demo charts unless the user asks (`…:148-151`).
- **Experimental scaffold.** The tool-loop prompt bans charts/buttons during tool-only turns and states they are only available after a terminal tool such as `ready_to_reply_to_user` (`architectures/experimental/src/agent_platform/architectures/experimental/prompts/tool-loop/conversation-default.yml:63-85`). The paired final-reply prompt reintroduces charts with the same fenced spec requirement and “use only if it improves comprehension” guidance (`…/final-reply/conversation-default.yml:70-88`).
- **Prompt enrichment.** Both prompts interpolate the data-frame summary blocks coming from `kernel.data_frames` so the agent sees hints like “use `data-frame://<name>` to feed vega-lite charts” (`server/src/agent_platform/server/kernel/data_frames.py:231-255`).

## Data-Frame Integration

- Enabling data frames (via `agent_settings.enable_data_frames` or the env flag) surfaces helper tools and instructs the agent that `data-frame://<name>` URLs can back chart specs (`server/src/agent_platform/server/kernel/data_frames.py:200-255`).
- When the agent emits a chart whose `data` section references that URL, SPAR-UI detects it and hydrates the spec with fresh row data by calling `/api/v2/threads/{tid}/data-frames/{data_frame_name}` through `useDataFrameQuery` (`workroom/spar-ui/src/queries/dataFrames.ts:111-146`).
- Server endpoints `GET /data-frames/{name}` and `POST /data-frames/slice` supply the JSON rows the UI injects when rendering Vega/Vega-Lite visualizations (`server/src/agent_platform/server/api/private_v2/threads_data_frames.py:904-952`).

## SPAR‑UI Rendering Pipeline

- **Markdown hook.** The chat markdown rules render fenced blocks tagged `vega` or `vega-lite` with the chart component instead of plain code (`workroom/spar-ui/src/components/Chat/components/markdown.tsx:9-19`).
- **Spec detection.** `isVegaChartBlock` handles streaming and complete-block heuristics, validating `$schema` values before opting into chart rendering (`…/chart/index.tsx:16-49`).
- **Theming & overrides.** Before embedding, `processChartSpecOverrides` normalizes sizing/autosize and applies the Sema4AI themes (`…/components/theming.ts:232-250`, `…:74-229`).
- **Data hydration.** If the spec’s `data` uses a `data-frame://` URL, the component fetches the rows and patches both the themed and raw spec (`…/chart/index.tsx:108-189`; helper regex in `components/utils.ts:1-12`).
- **Embed lifecycle.** Rendering flows through `ChartEmbed`, which mounts Vega using `vega-embed`, toggles between source view and canvas, and supports PNG/SVG export via the container menu (`…/components/Embed.tsx:1-58`, `…/components/Container.tsx:1-75`).
- **Loading states.** The UI shows `LoadingBox` spinners while specs stream or data loads (`…/components/Loading.tsx:1-34`, reused by both embed and data-frame variants).

## Quality Signals & Scenarios

- The QA scenario `003-charting-revenue-pie` exercises the full workflow: generate SQL, fetch data, and emit a vega-lite pie chart with embedded values (`quality/test-threads/002-snowflake-cortex-analyst/003-charting-revenue-pie.yml:1-56`).
- Unit coverage keeps the serialization contracts honest (see `ThreadVegaChartContent` tests above), ensuring regressions in schema validation are caught in CI.
