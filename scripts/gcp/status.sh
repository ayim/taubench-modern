#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

show_help() {
    cat << EOF
📊 Agent Platform Status

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --logs [service]    Show recent logs (agent-server|workroom)
    --health           Show health check details
    --urls             Show only URLs (useful for scripts)
    --json             Output in JSON format
    -h, --help         Show this help

EXAMPLES:
    $0                      # Show full status
    $0 --logs workroom      # Show workroom logs
    $0 --urls               # Just URLs for scripts
EOF
}

check_service_health() {
    local service="$1"
    local url="$2"
    
    if [[ -z "$url" ]]; then
        echo "❌ Not deployed"
        return 1
    fi
    
    local health_url="$url/healthz"
    if curl -s -m 10 "$health_url" >/dev/null 2>&1; then
        echo "✅ Healthy"
        return 0
    else
        echo "⚠️  Health check failed"
        return 1
    fi
}

show_service_status() {
    local service="$1"
    local display_name="$2"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "$display_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if service_exists "$service" "$REGION"; then
        local url status last_deploy
        url=$(get_service_url "$service" "$REGION")
        status=$(get_service_status "$service" "$REGION")
        last_deploy=$(get_last_deploy_time "$service" "$REGION")
        
        echo "🔗 URL:          $url"
        echo "📊 Status:       $(if [[ "$status" == "True" ]]; then echo "✅ Running"; else echo "❌ $status"; fi)"
        echo "⏰ Last Deploy:  $last_deploy ago"
        
        if [[ "$service" == "workroom" ]]; then
            echo "🌐 Health:       $(check_service_health "$service" "$url")"
        fi
        
        # Show recent revision info
        local revision
        revision=$(gcloud run services describe "$service" \
            --region="$REGION" \
            --format="value(status.latestReadyRevisionName)" \
            --quiet 2>/dev/null || echo "")
        
        if [[ -n "$revision" ]]; then
            echo "📦 Revision:     $revision"
        fi
        
    else
        log_error "Not deployed"
    fi
}

show_database_status() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Database (Cloud SQL)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local db_state db_ip
    db_state=$(gcloud sql instances describe agent-postgres \
        --format="value(state)" \
        --quiet 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$db_state" == "NOT_FOUND" ]]; then
        log_error "Database not found"
    else
        db_ip=$(gcloud sql instances describe agent-postgres \
            --format="value(ipAddresses[0].ipAddress)" \
            --quiet 2>/dev/null || echo "")
        
        echo "🗄️  Instance:     agent-postgres"
        echo "📊 State:        $(if [[ "$db_state" == "RUNNABLE" ]]; then echo "✅ $db_state"; else echo "⚠️  $db_state"; fi)"
        echo "🌐 IP Address:   $db_ip"
        echo "💾 Database:     agents"
        echo "👤 User:         agents"
    fi
}

show_quick_links() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Quick Links"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    echo "🔗 Cloud Console:"
    echo "   • Cloud Run:    https://console.cloud.google.com/run?project=$PROJECT_ID"
    echo "   • Cloud SQL:    https://console.cloud.google.com/sql/instances?project=$PROJECT_ID"
    echo "   • Logs:         https://console.cloud.google.com/logs/query?project=$PROJECT_ID"
    echo "   • Artifacts:    https://console.cloud.google.com/artifacts?project=$PROJECT_ID"
    
    echo ""
    echo "🛠 Common Commands:"
    echo "   • Deploy workroom only:    ./scripts/gcp/deploy.sh --workroom"
    echo "   • Deploy agent-server:     ./scripts/gcp/deploy.sh --agent-server"
    echo "   • Update config only:      ./scripts/gcp/deploy.sh --config-only"
    echo "   • Show logs:               ./scripts/gcp/status.sh --logs workroom"
    echo "   • Remove all resources:    ./scripts/gcp/teardown.sh --all"
}

show_logs() {
    local service="$1"
    local lines="${2:-50}"
    
    echo ""
    log_info "Recent logs for $service (last $lines lines)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    gcloud run services logs read "$service" \
        --region="$REGION" \
        --limit="$lines" \
        --format="table(timestamp,severity,textPayload)" | cat
}

show_urls_only() {
    local workroom_url agent_url
    workroom_url=$(get_service_url "workroom" "$REGION")
    agent_url=$(get_service_url "agent-server" "$REGION")
    
    echo "WORKROOM_URL=$workroom_url"
    echo "AGENT_SERVER_URL=$agent_url"
}

main() {
    local show_logs_service=""
    local show_health=false
    local urls_only=false
    local json_output=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --logs)
                show_logs_service="${2:-workroom}"
                shift 2
                ;;
            --health)
                show_health=true
                shift
                ;;
            --urls)
                urls_only=true
                shift
                ;;
            --json)
                json_output=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    if [[ -z "$PROJECT_ID" ]]; then
        log_error "PROJECT_ID not set. Set GCLOUD_PROJECT environment variable or run:"
        echo "gcloud config set project YOUR_PROJECT_ID"
        exit 1
    fi
    
    if [[ "$urls_only" == "true" ]]; then
        show_urls_only
        exit 0
    fi
    
    if [[ -n "$show_logs_service" ]]; then
        show_logs "$show_logs_service"
        exit 0
    fi
    
    # Show full status
    echo "📊 Agent Platform Status"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region:  $REGION"
    
    show_service_status "workroom" "Workroom (Frontend + Proxy)"
    show_service_status "agent-server" "Agent Server (Backend API)"
    show_database_status
    show_quick_links
    
    echo ""
    log_success "Status check complete"
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 