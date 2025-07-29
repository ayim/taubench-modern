#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
source "$SCRIPT_DIR/functions/database-functions.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$CACHED_PROJECT_ID}"

# Get current user for namespacing (use cached value from common.sh)
CURRENT_USER="$CACHED_USER"
if [[ -z "$CURRENT_USER" ]]; then
    echo "❌ Unable to get authenticated user. Please run 'gcloud auth login' first."
    exit 1
fi

# User-namespaced service names (same as deploy.sh)
AGENT_SERVER_SERVICE="agent-server-${CURRENT_USER}"
WORKROOM_SERVICE="workroom-${CURRENT_USER}"

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

MULTI-DEVELOPER SUPPORT:
    🏷️  Services are automatically namespaced by your authenticated user
    👤 Your services: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE
    🗄️  Database: Checks personal database first, falls back to shared

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

# Gather service data in parallel (optimized for speed)
gather_service_data() {
    local service="$1"
    local temp_file="$2"
    
    if service_exists "$service" "$REGION"; then
        local url status last_deploy revision
        
        # Run all gcloud calls in parallel for this service
        {
            url=$(get_service_url "$service" "$REGION")
            status=$(get_service_status "$service" "$REGION")
            last_deploy=$(get_last_deploy_time "$service" "$REGION")
            revision=$(gcloud run services describe "$service" \
                --region="$REGION" \
                --format="value(status.latestReadyRevisionName)" \
                --quiet 2>/dev/null || echo "")
            
            # Save results to temp file (properly quoted)
            echo "url='$url'" > "$temp_file"
            echo "status='$status'" >> "$temp_file"
            echo "last_deploy='$last_deploy'" >> "$temp_file"
            echo "revision='$revision'" >> "$temp_file"
            echo "exists=true" >> "$temp_file"
        }
    else
        echo "exists=false" > "$temp_file"
    fi
}

# Display service status from gathered data
show_service_status() {
    local service="$1"
    local display_name="$2"
    local data_file="$3"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "$display_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [[ -f "$data_file" ]]; then
        source "$data_file"
        
        if [[ "$exists" == "true" ]]; then
            echo "🔗 URL:          $url"
            echo "📊 Status:       $(if [[ "$status" == "Running" ]]; then echo "✅ $status"; else echo "❌ $status"; fi)"
            echo "⏰ Last Deploy:  $last_deploy"
            
            if [[ "$service" == *"workroom"* ]]; then
                echo "🌐 Health:       $(check_service_health "$service" "$url")"
            fi
            
            if [[ -n "$revision" ]]; then
                echo "📦 Revision:     $revision"
            fi
        else
            log_error "Not deployed"
        fi
    else
        log_error "Status data not available"
    fi
}

# Gather database data in parallel
gather_database_data() {
    local temp_file="$1"
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"
    
    # Check both databases in parallel
    {
        personal_state=$(gcloud sql instances describe "$personal_db" \
            --format="value(state)" \
            --quiet 2>/dev/null || echo "NOT_FOUND")
        shared_state=$(gcloud sql instances describe "$shared_db" \
            --format="value(state)" \
            --quiet 2>/dev/null || echo "NOT_FOUND")
        
        local db_instance="" db_state="" db_type=""
        
        if [[ "$personal_state" != "NOT_FOUND" ]]; then
            db_instance="$personal_db"
            db_state="$personal_state"
            db_type="personal"
        elif [[ "$shared_state" != "NOT_FOUND" ]]; then
            db_instance="$shared_db"
            db_state="$shared_state"
            db_type="shared"
        fi
        
        if [[ -n "$db_instance" ]]; then
            db_ip=$(gcloud sql instances describe "$db_instance" \
                --format="value(ipAddresses[0].ipAddress)" \
                --quiet 2>/dev/null || echo "")
        fi
        
        # Save results (properly quoted)
        echo "db_instance='$db_instance'" > "$temp_file"
        echo "db_state='$db_state'" >> "$temp_file"
        echo "db_type='$db_type'" >> "$temp_file"
        echo "db_ip='$db_ip'" >> "$temp_file"
        echo "personal_db='$personal_db'" >> "$temp_file"
        echo "shared_db='$shared_db'" >> "$temp_file"
    }
}

show_database_status() {
    local data_file="$1"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Database (Cloud SQL)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [[ -f "$data_file" ]]; then
        source "$data_file"
        
        if [[ -n "$db_instance" ]]; then
            echo "🗄️  Instance:     $db_instance ($db_type)"
            echo "📊 State:        $(if [[ "$db_state" == "RUNNABLE" ]]; then echo "✅ $db_state"; else echo "⚠️  $db_state"; fi)"
            echo "🌐 IP Address:   $db_ip"
            echo "💾 Database:     agents"
            echo "👤 User:         agents"
            
            # Show connection information if database is running
            if [[ "$db_state" == "RUNNABLE" ]]; then
                show_database_connection_info "$db_instance" "agents" "agents" "agents"
            fi
        else
            log_error "No database found (checked: $personal_db, $shared_db)"
        fi
    else
        log_error "Database status data not available"
    fi
}

show_quick_links() {
    echo ""
    echo "💡 Quick actions: make gcp deploy (deploy) | ./scripts/gcp/status.sh --logs workroom (logs)"
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
    # Parallel URL gathering for faster response
    local temp_dir=$(mktemp -d)
    
    # Get URLs in parallel
    get_service_url "$WORKROOM_SERVICE" "$REGION" > "$temp_dir/workroom_url" &
    local workroom_pid=$!
    get_service_url "$AGENT_SERVER_SERVICE" "$REGION" > "$temp_dir/agent_url" &  
    local agent_pid=$!
    
    # Wait for both to complete
    wait $workroom_pid
    wait $agent_pid
    
    # Read results
    local workroom_url=$(cat "$temp_dir/workroom_url" 2>/dev/null || echo "")
    local agent_url=$(cat "$temp_dir/agent_url" 2>/dev/null || echo "")
    
    echo "WORKROOM_URL=$workroom_url"
    echo "AGENT_SERVER_URL=$agent_url"
    
    # Cleanup
    rm -rf "$temp_dir"
}

main() {
    local show_logs_service=""
    local show_health=false
    local urls_only=false
    local json_output=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --logs)
                local raw_service="${2:-workroom}"
                # Map short names to namespaced service names
                case "$raw_service" in
                    "workroom") show_logs_service="$WORKROOM_SERVICE" ;;
                    "agent-server") show_logs_service="$AGENT_SERVER_SERVICE" ;;
                    *) show_logs_service="$raw_service" ;;  # Allow full service names
                esac
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
    
    # Show full status with parallel data gathering
    echo "📊 Agent Platform Status"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region:  $REGION"
    echo "👤 User: $CURRENT_USER"
    
    # Create temp directory for parallel data gathering
    local temp_dir=$(mktemp -d)
    local workroom_data="$temp_dir/workroom.data"
    local agent_data="$temp_dir/agent.data"
    local database_data="$temp_dir/database.data"
    
    # Start parallel data gathering (this is the speed optimization!)
    show_progress "Gathering service and database status"
    gather_service_data "$WORKROOM_SERVICE" "$workroom_data" &
    local workroom_pid=$!
    gather_service_data "$AGENT_SERVER_SERVICE" "$agent_data" &
    local agent_pid=$!
    gather_database_data "$database_data" &
    local database_pid=$!
    
    # Wait for all parallel operations to complete
    wait $workroom_pid
    wait $agent_pid
    wait $database_pid
    
    # Display results using gathered data
    show_service_status "$WORKROOM_SERVICE" "Workroom (Frontend + Proxy)" "$workroom_data"
    show_service_status "$AGENT_SERVER_SERVICE" "Agent Server (Backend API)" "$agent_data"
    show_database_status "$database_data"
    show_quick_links
    
    # Cleanup temp files
    rm -rf "$temp_dir"
    
    echo ""
    log_success "Status check complete"
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 