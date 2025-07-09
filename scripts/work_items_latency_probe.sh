#!/usr/bin/env bash
# Basic latency probe for agent-platform server
# Requires: curl, jq, bc

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

source "$DIR/../.env"

BASE_URL="${BASE_URL:-http://localhost:8000}"
AGENT_ID="${AGENT_ID:-demo-agent}"
NUM_ITEMS="${NUM_ITEMS:-10}"
POLL_INTERVAL="${POLL_INTERVAL:-1}"        # seconds between /health polls
THRESHOLD="${THRESHOLD:-1.0}"              # seconds considered "slow"

hdr_content='Content-Type: application/json'

# ────────────── Ensure test agent exists ──────────────
AGENT_NAME="latency-probe-agent-bedrock"

# URL-encode the name for the by-name lookup
NAME_ENC=$(python - <<'PY' "$AGENT_NAME"
import urllib.parse, sys; print(urllib.parse.quote(sys.argv[1]))
PY
)

# Try to fetch the agent by name
agent_resp=$(curl -s "${BASE_URL}/api/v2/agents/by-name?name=${NAME_ENC}")
agent_id=$(echo "$agent_resp" | jq -r .agent_id 2>/dev/null)

if [[ -z "$agent_id" || "$agent_id" == "null" ]]; then
  echo "Creating agent '$AGENT_NAME' ..."
  create_payload=$(jq -n \
    --arg name "$AGENT_NAME" \
    --arg aws_access_key_id "${AWS_ACCESS_KEY_ID:-dummy}" \
    --arg aws_secret_access_key "${AWS_SECRET_ACCESS_KEY:-dummy}" \
    --arg region_name "${AWS_DEFAULT_REGION:-dummy}" \
    '
    {
      mode: "conversational",
      name: $name,
      version: "1.0.0",
      description: "Latency-probe temporary agent.",
      runbook: "# Objective\nYou are a helpful assistant.",
      platform_configs: [
        {
          kind: "bedrock",
          aws_access_key_id: $aws_access_key_id,
          aws_secret_access_key: $aws_secret_access_key,
          region_name: $region_name
        }
      ],
      action_packages: [],
      mcp_servers: [],
      agent_architecture: {
        name: "agent_platform.architectures.default",
        version: "1.0.0"
      },
      observability_configs: [],
      question_groups: [],
      extra: {}
    }')

  agent_resp=$(curl -s -H "Content-Type: application/json" \
                     -d "$create_payload" \
                     "${BASE_URL}/api/v2/agents/")
  agent_id=$(echo "$agent_resp" | jq -r .agent_id)
fi

if [[ -z "$agent_id" || "$agent_id" == "null" ]]; then
  echo "ERROR: unable to obtain agent_id"; exit 1
fi
echo "→ Using agent_id=$agent_id"
echo
# ─────────────────────────────────────────────────────────────

json_template='{"agent_id":"%s","messages":[{"role":"user","content":[{"kind":"text","text":"What can you do?"}]}],"payload":{}}'

declare -a work_ids

echo "Submitting $NUM_ITEMS work-items..."
for ((i=1;i<=NUM_ITEMS;i++)); do
  resp=$(curl -s -H "$hdr_content" \
    -d "$(printf "$json_template" "$agent_id")" \
    "${BASE_URL}/api/v2/work-items/")
  wid=$(echo "$resp" | jq -r .work_item_id)
  echo "  → $wid"
  work_ids+=("$wid")
done

echo
echo "Polling /health every ${POLL_INTERVAL}s; flagging responses >${THRESHOLD}s"
echo "-----------------------------------------------------------------------"
slow_found=0
while : ; do
  ts_start=$(date +%s.%3N)
  code=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/v2/health")
  ts_end=$(date +%s.%3N)
  latency=$(echo "$ts_end - $ts_start" | bc)
  printf "health %s  %.3fs\n" "$code" "$latency"

  cmp=$(echo "$latency > $THRESHOLD" | bc)
  if [ "$cmp" -eq 1 ]; then
    echo "!!! Latency spike detected (>${THRESHOLD}s) !!!"
    slow_found=1
  fi

  # Are all work-items finished?
  all_done=1
  for wid in "${work_ids[@]}"; do
    status=$(curl -s "${BASE_URL}/api/v2/work-items/${wid}" | jq -r .status)
    if [[ "$status" != "completed" && "$status" != "error" && "$status" != "cancelled" ]]; then
      all_done=0
      break
    fi
  done

  [[ $all_done -eq 1 ]] && break
  sleep "$POLL_INTERVAL"
done

echo "-----------------------------------------------------------------------"
if [[ $slow_found -eq 1 ]]; then
  echo "At least one latency spike was observed while work-items were running."
else
  echo "No significant latency spikes observed."
fi
