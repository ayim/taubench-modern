# LangSmith Observability README

---

## Why look at LangSmith traces?

LangSmith turns the raw OTEL span stream that we already emit into an **interactive timeline** of every request:

- **Tree view** – collapsible hierarchy of chains → tools → LLM calls.
- **Inputs / Outputs pane** – shows the input request made by a user to the LLM, and what the response from the LLM was.
- **Token & cost stats** – automatically calculated for any span whose kind is `"llm"` and that uses the `gen_ai.*` keys.
- **Error bubbles** – any span that records an exception is flagged red with the error message inline.
- **Context search** – all other OTEL attributes (`user_id`, `agent_id`, latency, etc.) are indexed so you can filter traces later.

With the right attributes in place you can answer, at a glance:

| Question                                            | Where to look in the trace        |
| --------------------------------------------------- | --------------------------------- |
| “What prompt did I actually send to the model?”     | `openai_stream_response → Inputs` |
| “Which tools were called and what did they return?” | `tool_execution_* → Outputs`      |
| “Why did a run fail?”                               | Red-flagged span                  |
| “How long did the whole flow take?”                 | Root span duration bar            |

---

## Span cheat-sheet (what each one means & key attributes)

| Span name                    | Kind    | What it represents                    |
| ---------------------------- | ------- | ------------------------------------- |
| `stream_run` / `sync_run`    | `chain` | One end-to-end user request (root)    |
| `upsert_thread_and_messages` | `chain` | Saving new chat messages              |
| `fetch_agent`                | `chain` | DB lookup of the agent spec           |
| `create_run`                 | `chain` | Creation of an agent-arch run         |
| `get_agent_runner`           | `chain` | Instantiating the Python runner class |
| `start_runner`               | `chain` | Booting the runner process            |
| `openai_stream_response`     | `llm`   | Response from the LLM                 |
| `execute_pending_tool_calls` | `chain` | Coordinator that runs each tool call  |
| `tool_execution_*`           | `tool`  | A single tool invocation              |
| `initialize_kernel`          | `chain` | Starting the Python kernel            |

---

## Where the good stuff lives in the UI

| UI panel                       | Populated from                                                              | Typical span kinds     |
| ------------------------------ | --------------------------------------------------------------------------- | ---------------------- |
| **Inputs / Outputs**           | `input.value` / `output.value` or `gen_ai.prompt.*` / `gen_ai.completion.*` | `chain`, `tool`, `llm` |
| **Prompt / Completion viewer** | `gen_ai.*` attributes                                                       | `llm`                  |
| **Token & cost stats**         | Auto-derived when `gen_ai.*` present                                        | `llm`                  |
| **Error box**                  | `error.type`, `error.message`, `error.stack`                                | any                    |
| **Attributes sidebar**         | _all_ extra OTEL attributes that we include in spans                        | any                    |

---
