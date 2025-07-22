#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"
BUILD_ID="manual-$(date +%Y%m%d-%H%M%S)"

# Command line options
DEPLOY_ALL=false
DEPLOY_AGENT_SERVER=false
DEPLOY_WORKROOM=false
CONFIG_ONLY=false
FORCE_BUILD=false
SKIP_TESTS=false
VERBOSE=false

show_help() {
    cat << EOF
🚀 Agent Platform GCP Deployment

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --all                Deploy everything (agent-server + workroom)
    --agent-server       Deploy only agent-server
    --workroom          Deploy only workroom  
    --config-only       Update environment variables only (no build)
    --force-build       Force rebuild even if no changes detected
    --skip-tests        Skip health checks after deployment
    --verbose           Show detailed output
    -h, --help          Show this help

EXAMPLES:
    $0                          # Interactive menu (new!)
    $0 --all                    # Deploy both (skips builds if no changes)
    $0 --workroom              # Frontend only (skips if already deployed + no changes)
    $0 --agent-server          # Backend only (skips if already deployed + no changes)  
    $0 --agent-server --force-build  # Force backend rebuild
    $0 --config-only           # Just update env vars (super fast)

SMART DEPLOYMENT:
    • Automatically skips builds if service exists and no changes detected
    • Perfect for backend-only or frontend-only development
    • Use --force-build to override smart detection

CLOUD SQL:
    • Database automatically created during setup (./scripts/gcp/setup.sh)
    • Deploy script auto-detects and connects to existing Cloud SQL instance
    • No manual configuration needed!

CLEANUP:
    • Remove all resources: ./scripts/gcp/teardown.sh --all
    • Remove services only: ./scripts/gcp/teardown.sh --services
    • Interactive cleanup: ./scripts/gcp/teardown.sh

ENVIRONMENT:
    GCLOUD_PROJECT     Override project ID
    REGION             Override region (default: europe-west1)
EOF
}

# Interactive deployment menu
show_deployment_menu() {
    echo "🚀 Agent Platform GCP Deployment"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo ""
    
    # Check current service status
    local agent_status="$(get_service_status "agent-server" "$REGION" 2>/dev/null || echo "Not deployed")"
    local workroom_status="$(get_service_status "workroom" "$REGION" 2>/dev/null || echo "Not deployed")"
    
    echo "📊 Current Status:"
    printf "   Agent Server: %-15s" "$agent_status"
    if [[ "$agent_status" != "Not deployed" ]]; then
        local agent_age=$(get_last_deploy_time "agent-server" "$REGION" 2>/dev/null || echo "")
        if [[ -n "$agent_age" ]]; then
            echo " (deployed $agent_age)"
        else
            echo ""
        fi
    else
        echo ""
    fi
    
    printf "   Workroom:     %-15s" "$workroom_status"
    if [[ "$workroom_status" != "Not deployed" ]]; then
        local workroom_age=$(get_last_deploy_time "workroom" "$REGION" 2>/dev/null || echo "")
        if [[ -n "$workroom_age" ]]; then
            echo " (deployed $workroom_age)"
        else
            echo ""
        fi
    else
        echo ""
    fi
    echo ""
    
    echo "🎯 What would you like to deploy?"
    echo ""
    echo " 1) 🌐 Everything (agent-server + workroom)"
    echo " 2) 🖥️  Agent Server only (backend API)"
    echo " 3) 🎨 Workroom only (frontend UI)"
    echo " 4) ⚙️  Configuration only (env vars, no build)"
    echo " 5) 🔄 Force rebuild everything"
    echo " 6) 📊 Show current status"
    echo " 0) ❌ Exit"
    echo ""
    
    while true; do
        read -p "Select option (0-6): " choice
        
        case $choice in
            1)
                echo "✅ Selected: Deploy everything"
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                break
                ;;
            2)
                echo "✅ Selected: Deploy agent-server only"
                DEPLOY_AGENT_SERVER=true
                break
                ;;
            3)
                echo "✅ Selected: Deploy workroom only"
                DEPLOY_WORKROOM=true
                break
                ;;
            4)
                echo "✅ Selected: Configuration update only"
                CONFIG_ONLY=true
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                break
                ;;
            5)
                echo "✅ Selected: Force rebuild everything"
                FORCE_BUILD=true
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                break
                ;;
            6)
                echo ""
                "$SCRIPT_DIR/status.sh"
                echo ""
                echo "🎯 What would you like to deploy?"
                echo ""
                echo " 1) 🌐 Everything (agent-server + workroom)"
                echo " 2) 🖥️  Agent Server only (backend API)"
                echo " 3) 🎨 Workroom only (frontend UI)"
                echo " 4) ⚙️  Configuration only (env vars, no build)"
                echo " 5) 🔄 Force rebuild everything"
                echo " 6) 📊 Show current status"
                echo " 0) ❌ Exit"
                echo ""
                ;;
            0)
                echo "👋 Deployment cancelled"
                exit 0
                ;;
            *)
                echo "❌ Invalid choice. Please enter 0-6"
                ;;
        esac
    done
    echo ""
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all)
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                shift
                ;;
            --agent-server)
                DEPLOY_AGENT_SERVER=true
                shift
                ;;
            --workroom)
                DEPLOY_WORKROOM=true
                shift
                ;;
            --config-only)
                CONFIG_ONLY=true
                shift
                ;;
            --force-build)
                FORCE_BUILD=true
                shift
                ;;
            --skip-tests)
                SKIP_TESTS=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                echo "❌ Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

check_changes() {
    local service="$1"
    local watch_paths="$2"
    
    if [[ "$FORCE_BUILD" == "true" ]]; then
        echo "🔨 Force build requested for $service"
        return 0
    fi
    
    # Get last deployment time from Cloud Run labels
    local last_deploy=$(gcloud run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.labels.last-deploy)" \
        2>/dev/null || echo "")
    
    if [[ -z "$last_deploy" ]]; then
        echo "📦 $service not found or no deploy timestamp, building..."
        return 0
    fi
    
    # Check if any watched files changed since last deploy
    local changed_files=$(find $watch_paths -newer "$PROJECT_ROOT/.last-deploy-$service" 2>/dev/null | wc -l || echo "999")
    
    if [[ "$changed_files" -gt 0 ]]; then
        echo "📝 Changes detected in $service ($changed_files files), building..."
        return 0
    else
        echo "✅ No changes in $service since last deploy, skipping build"
        return 1
    fi
}

deploy_agent_server() {
    echo "🔧 Deploying agent-server..."
    
    local should_build=true
    
    # Check if agent-server is already deployed and working
    if [[ "$CONFIG_ONLY" == "false" && "$FORCE_BUILD" == "false" ]]; then
        local existing_url
        existing_url=$(get_service_url "agent-server" "$REGION")
        
        if [[ -n "$existing_url" ]]; then
            # Service exists, check if we have file changes
            if check_changes "agent-server" "$PROJECT_ROOT/server $PROJECT_ROOT/core $PROJECT_ROOT/Dockerfile"; then
                echo "📝 Agent-server changes detected, will rebuild..."
            else
                echo "✅ Agent-server already deployed with no changes, skipping build..."
                should_build=false
            fi
        else
            echo "📦 Agent-server not deployed yet, will build..."
        fi
    elif [[ "$CONFIG_ONLY" == "true" ]]; then
        should_build=false
    fi
    
    # Get database IP
    local sql_ip=$(gcloud sql instances describe agent-postgres \
        --format="value(ipAddresses[0].ipAddress)" \
        --quiet 2>/dev/null || echo "")
    
    if [[ -z "$sql_ip" ]]; then
        echo "⚠️  Database not found, running setup first..."
        "$SCRIPT_DIR/setup.sh" --database-only
        sql_ip=$(gcloud sql instances describe agent-postgres \
            --format="value(ipAddresses[0].ipAddress)" \
            --quiet)
    fi
    
    # Build if needed
    if [[ "$should_build" == "true" ]]; then
        echo "🔨 Building agent-server..."
        docker build \
            --platform linux/amd64 \
            --label "build-id=$BUILD_ID" \
            --label "last-deploy=$(date +%s)" \
            -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:$BUILD_ID" \
            -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest" \
            -f Dockerfile .
        
        echo "📤 Pushing agent-server..."
        docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:$BUILD_ID"
        docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest"
    fi
    
    # Deploy (always update env vars)
    echo "🚀 Deploying agent-server to Cloud Run..."
    gcloud run deploy agent-server \
        --image="$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest" \
        --platform=managed \
        --region="$REGION" \
        --allow-unauthenticated \
        --ingress=all \
        --port=8000 \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=0 \
        --max-instances=10 \
        --timeout=900 \
        --cpu-boost \
        --execution-environment=gen2 \
        --set-env-vars="SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true,SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true,SEMA4AI_OPTIMIZE_FOR_CONTAINER=1,SEMA4AI_AGENT_SERVER_DB_TYPE=postgres,POSTGRES_HOST=$sql_ip,POSTGRES_PORT=5432,POSTGRES_DB=agents,POSTGRES_USER=agents,POSTGRES_PASSWORD=agents,SEMA4AI_AGENT_SERVER_LOG_LEVEL=INFO,SEMA4AI_AGENT_SERVER_HOST=0.0.0.0,SEMA4AI_AGENT_SERVER_PORT=8000,LOG_LEVEL=INFO,FORWARDED_ALLOW_IPS=*,USE_FORWARDED_HOST=true,SECURE_SCHEME_HEADERS=X-Forwarded-Proto:https" \
        --add-cloudsql-instances="$PROJECT_ID:$REGION:agent-postgres" \
        --update-labels="last-deploy=$(date +%s)" \
        --quiet
}

deploy_workroom() {
    echo "🔧 Deploying workroom..."
    
    local should_build=true
    
    # Check if workroom is already deployed and working
    if [[ "$CONFIG_ONLY" == "false" && "$FORCE_BUILD" == "false" ]]; then
        local existing_url
        existing_url=$(get_service_url "workroom" "$REGION")
        
        if [[ -n "$existing_url" ]]; then
            # Service exists, check if we have file changes
            if check_changes "workroom" "$PROJECT_ROOT/workroom"; then
                echo "📝 Workroom changes detected, will rebuild..."
            else
                echo "✅ Workroom already deployed with no changes, skipping build..."
                should_build=false
            fi
        else
            echo "📦 Workroom not deployed yet, will build..."
        fi
    elif [[ "$CONFIG_ONLY" == "true" ]]; then
        should_build=false
    fi
    
    # Get agent server URL
    local agent_server_url=$(gcloud run services describe agent-server \
        --region="$REGION" \
        --format="value(status.url)" \
        --quiet 2>/dev/null || echo "")
    
    if [[ -z "$agent_server_url" ]]; then
        echo "❌ Agent server not found! Deploy agent-server first."
        exit 1
    fi
    
    local agent_server_host=$(echo "$agent_server_url" | sed 's|https://||')
    
    # Build if needed
    if [[ "$should_build" == "true" ]]; then
        echo "🔨 Building workroom..."
        
        # Get npmrc secret
        gcloud secrets versions access latest --secret=npmrc-secret > /tmp/.npmrc 2>/dev/null || {
            echo "❌ npmrc-secret not found. Create it first:"
            echo "gcloud secrets create npmrc-secret --data-file=~/.npmrc"
            exit 1
        }
        
        docker build \
            --platform linux/amd64 \
            --secret id=npmrc,src=/tmp/.npmrc \
            --build-arg VITE_INSTANCE_ID=dev \
            --build-arg VITE_DEPLOYMENT_TYPE=spar \
            --build-arg VITE_DEV_WORKROOM_TENANT_LIST_URL=/spar-tenants-list \
            --build-arg VITE_DEV_SERVER_PORT=8001 \
            --build-arg NODE_ENV=production \
            --label "build-id=$BUILD_ID" \
            --label "last-deploy=$(date +%s)" \
            -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:$BUILD_ID" \
            -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest" \
            -f workroom/Dockerfile ./workroom
        
        echo "📤 Pushing workroom..."
        docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:$BUILD_ID"
        docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest"
        touch "$PROJECT_ROOT/.last-deploy-workroom"
        rm -f /tmp/.npmrc
    fi
    
    # Deploy
    echo "🚀 Deploying workroom to Cloud Run..."
    gcloud run deploy workroom \
        --image="$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest" \
        --platform=managed \
        --region="$REGION" \
        --allow-unauthenticated \
        --port=3001 \
        --memory=1Gi \
        --cpu=1 \
        --timeout=300 \
        --update-labels="last-deploy=$(date +%s)" \
        --quiet
    
    # Get workroom URL and update meta URLs
    local workroom_url=$(gcloud run services describe workroom \
        --region="$REGION" \
        --format="value(status.url)" \
        --quiet)
    
    echo "🔄 Updating workroom meta URLs..."
    gcloud run services update workroom \
        --region="$REGION" \
        --update-env-vars="AGENT_SERVER_URL=$agent_server_url,AGENT_SERVER_HOST=$agent_server_host,DEPLOYMENT_TYPE=spar,META_URL=$workroom_url/meta,WORKROOM_URL=$workroom_url,NODE_ENV=production" \
        --quiet
}

main() {
    parse_args "$@"
    
    # If no deployment options specified, show interactive menu
    if [[ "$DEPLOY_ALL" == "false" && "$DEPLOY_AGENT_SERVER" == "false" && "$DEPLOY_WORKROOM" == "false" && "$CONFIG_ONLY" == "false" ]]; then
        show_deployment_menu
    else
        echo "🚀 Agent Platform GCP Deployment"
        echo "📍 Project: $PROJECT_ID"
        echo "🌍 Region: $REGION"
        echo ""
    fi
    
    check_prerequisites
    
    cd "$PROJECT_ROOT"
    
    # Deploy services (agent-server first, then workroom)
    if [[ "$DEPLOY_AGENT_SERVER" == "true" ]]; then
        deploy_agent_server
    fi
    
    if [[ "$DEPLOY_WORKROOM" == "true" ]]; then
        deploy_workroom
    fi
    
    # Show final status
    echo ""
    echo "🎉 Deployment complete!"
    "$SCRIPT_DIR/status.sh"
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 