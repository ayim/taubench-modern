# Agent Platform Observability Stack

A comprehensive observability setup with Jaeger (traces) and Prometheus (metrics).

## Quick Start

Run:

```bash
python server/src/agent_platform/server/server.py --export-config > agent-server-config.yaml
```

This creates an `agent-server-config.yaml` file.

In the config file: search for agent_platform.server.otel.OTELConfig and set it to these values:

```yaml
agent_platform.server.otel.OTELConfig:
  collector_url: 'http://localhost:4318'
  # Whether to enable OpenTelemetry.
  # Environment variables: SEMA4AI_AGENT_SERVER_OTEL_ENABLED, OTEL_ENABLED
  is_enabled: true
```

Start the observability stack:

```bash
docker compose -f observability/docker-compose.observability.yml up -d
```

Stop the observability stack:

```bash
docker compose -f observability/docker-compose.observability.yml down
```

## Services

- **Jaeger UI**: <http://localhost:16686> - View distributed traces
- **Prometheus**: <http://localhost:9090> - Query and visualize metrics
- **OTEL Collector**: Receives telemetry on ports 4317 (gRPC) and 4318 (HTTP)

## Prometheus Queries

### Basic Token Metrics

**Compare models on same graph (cumulative totals):**

```promql
sum by (model) (sema4ai_agent_server_completion_tokens_total)
```

**Specific models only:**

```promql
sema4ai_agent_server_completion_tokens_total{model=~"gpt-4.1|gemini-2.5-flash-preview-04-17-high"}
```

**All prompt tokens:**

```promql
sum by (model) (sema4ai_agent_server_prompt_tokens_total)
```

### Filter by User, Agent, Thread

**Tokens for specific user:**

```promql
sema4ai_agent_server_completion_tokens_total{user_id="user123"}
```

**Tokens for specific agent:**

```promql
sema4ai_agent_server_completion_tokens_total{agent_id="agent456"}
```

**Tokens for specific thread:**

```promql
sema4ai_agent_server_completion_tokens_total{thread_id="thread789"}
```

**Combine filters (user + agent + model):**

```promql
sema4ai_agent_server_completion_tokens_total{user="user123", agent="agent456", thread="gpt-4.1"}
```

### Aggregations

**Total tokens per user (across all agents/models):**

```promql
sum by (user) (sema4ai_agent_server_completion_tokens_total)
```

**Total tokens per agent (across all users/models):**

```promql
sum by (agent) (sema4ai_agent_server_completion_tokens_total)
```

**Tokens per user-agent combination:**

```promql
sum by (user, agent) (sema4ai_agent_server_completion_tokens_total)
```

**Most active users (top 10):**

```promql
topk(10, sum by (user) (sema4ai_agent_server_completion_tokens_total))
```

**Most popular models:**

```promql
topk(5, sum by (model) (sema4ai_agent_server_completion_tokens_total))
```

### Rates and Activity

**Token consumption rate per user (tokens/second):**

```promql
rate(sema4ai_agent_server_completion_tokens_total[5m])
```

**Model usage rate comparison:**

```promql
sum by (model) (rate(sema4ai_agent_server_completion_tokens_total[5m]))
```

**Most active users by rate:**

```promql
topk(10, sum by (user) (rate(sema4ai_agent_server_completion_tokens_total[1h])))
```

**Token growth over last hour:**

```promql
increase(sema4ai_agent_server_completion_tokens_total[1h])
```

### Business Intelligence

**Total cost per user (example with GPT-4 pricing):**

```promql
sum by (user) (sema4ai_agent_server_completion_tokens_total{model="gpt-4.1"}) * 0.00003
```

**Agent utilization comparison:**

```promql
sum by (agent) (rate(sema4ai_agent_server_completion_tokens_total[1h]))
```

**Model preference by user:**

```promql
sum by (user, model) (sema4ai_agent_server_completion_tokens_total)
```

**Thread activity (most active conversations):**

```promql
topk(20, sum by (thread) (sema4ai_agent_server_completion_tokens_total))
```

### System Health

**Check which targets are up:**

```promql
up
```

**All available metrics:**

```promql
{__name__=~".+"}
```

**HTTP request metrics:**

```promql
sum by (user) (http_requests_total)
```

### Tips

- **Cumulative Totals**: Use metric names directly (e.g., `sema4ai_agent_server_completion_tokens_total`)
- **Rates**: Use `rate()` for per-second rates: `rate(metric[5m])`
- **Growth**: Use `increase()` for total growth over time: `increase(metric[1h])`
- **Multiple Lines**: Use `sum by (label)` to group and compare
- **Filtering**: Use `{label="value"}` or `{label=~"regex"}` to filter
- **Top N**: Use `topk(N, query)` to get top results

## Data Reset

To clear all data and start fresh:

```bash
docker compose -f observability/docker-compose.observability.yml down
docker volume rm agent-platform_prometheus_data
docker compose -f observability/docker-compose.observability.yml up -d
```
