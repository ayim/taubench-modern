#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Command line options
TEARDOWN_ALL=false
TEARDOWN_SERVICES=false
TEARDOWN_DATABASE=false
TEARDOWN_IMAGES=false
TEARDOWN_SECRETS=false
FORCE=false
VERBOSE=false

show_help() {
    cat << EOF
🗑️  Agent Platform GCP Teardown

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --all               Remove everything (services + database + images)
    --services          Remove only Cloud Run services (agent-server + workroom)
    --database          Remove only Cloud SQL database
    --images            Remove only Artifact Registry images
    --secrets           Remove only secrets (npmrc-secret)
    --force             Skip confirmation prompts (DANGEROUS!)
    --verbose           Show detailed output
    -h, --help          Show this help

EXAMPLES:
    $0                          # Interactive menu
    $0 --services              # Remove only Cloud Run services
    $0 --database              # Remove only database (keeps services)
    $0 --all                   # Remove everything
    $0 --all --force           # Remove everything without prompts (DANGEROUS!)

SAFETY:
    • By default, asks for confirmation before each destructive action
    • Use --force to skip confirmations (not recommended for production)
    • Database deletion is irreversible - all data will be lost!

COST SAVINGS:
    • Cloud Run services: ~\$0.40/month (if idle)
    • Cloud SQL (db-f1-micro): ~\$7-15/month
    • Artifact Registry storage: ~\$0.10/GB/month
EOF
}

# Interactive teardown menu
show_teardown_menu() {
    echo "🗑️  Agent Platform GCP Teardown"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo ""
    
    # Check current service status
    local agent_status="$(get_service_status "agent-server" "$REGION" 2>/dev/null || echo "Not deployed")"
    local workroom_status="$(get_service_status "workroom" "$REGION" 2>/dev/null || echo "Not deployed")"
    local db_status
    if gcloud sql instances describe agent-postgres --quiet 2>/dev/null; then
        db_status="Deployed"
    else
        db_status="Not deployed"
    fi
    
    echo "📊 Current Resources:"
    printf "   Agent Server: %-15s" "$agent_status"
    if [[ "$agent_status" != "Not deployed" ]]; then
        echo ""
    else
        echo ""
    fi
    
    printf "   Workroom:     %-15s" "$workroom_status"
    if [[ "$workroom_status" != "Not deployed" ]]; then
        echo ""
    else
        echo ""
    fi
    
    printf "   Database:     %-15s" "$db_status"
    echo ""
    echo ""
    
    echo "🗑️  What would you like to remove?"
    echo ""
    echo " 1) 🌐 Cloud Run Services only (agent-server + workroom)"
    echo " 2) 🗄️  Database only (Cloud SQL + all data)"
    echo " 3) 📦 Artifact Registry images only"
    echo " 4) 🔐 Secrets only (npmrc-secret)"
    echo " 5) 💥 Everything (services + database + images + secrets)"
    echo " 6) 📊 Show current status"
    echo " 0) ❌ Cancel"
    echo ""
    
    while true; do
        read -p "Select option (0-6): " choice
        
        case $choice in
            1)
                echo "✅ Selected: Remove Cloud Run services"
                TEARDOWN_SERVICES=true
                break
                ;;
            2)
                echo "✅ Selected: Remove database"
                TEARDOWN_DATABASE=true
                break
                ;;
            3)
                echo "✅ Selected: Remove Artifact Registry images"
                TEARDOWN_IMAGES=true
                break
                ;;
            4)
                echo "✅ Selected: Remove secrets"
                TEARDOWN_SECRETS=true
                break
                ;;
            5)
                echo "✅ Selected: Remove everything"
                TEARDOWN_ALL=true
                TEARDOWN_SERVICES=true
                TEARDOWN_DATABASE=true
                TEARDOWN_IMAGES=true
                TEARDOWN_SECRETS=true
                break
                ;;
            6)
                echo ""
                "$SCRIPT_DIR/status.sh"
                echo ""
                echo "🗑️  What would you like to remove?"
                echo ""
                echo " 1) 🌐 Cloud Run Services only (agent-server + workroom)"
                echo " 2) 🗄️  Database only (Cloud SQL + all data)"
                echo " 3) 📦 Artifact Registry images only"
                echo " 4) 🔐 Secrets only (npmrc-secret)"
                echo " 5) 💥 Everything (services + database + images + secrets)"
                echo " 6) 📊 Show current status"
                echo " 0) ❌ Cancel"
                echo ""
                ;;
            0)
                echo "👋 Teardown cancelled"
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
                TEARDOWN_ALL=true
                TEARDOWN_SERVICES=true
                TEARDOWN_DATABASE=true
                TEARDOWN_IMAGES=true
                TEARDOWN_SECRETS=true
                shift
                ;;
            --services)
                TEARDOWN_SERVICES=true
                shift
                ;;
            --database)
                TEARDOWN_DATABASE=true
                shift
                ;;
            --images)
                TEARDOWN_IMAGES=true
                shift
                ;;
            --secrets)
                TEARDOWN_SECRETS=true
                shift
                ;;
            --force)
                FORCE=true
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

confirm_action() {
    local action="$1"
    local details="$2"
    
    if [[ "$FORCE" == "true" ]]; then
        echo "🔥 FORCE mode: $action"
        return 0
    fi
    
    echo ""
    echo "⚠️  CONFIRMATION REQUIRED"
    echo "Action: $action"
    echo "Details: $details"
    echo ""
    echo "This action cannot be undone!"
    echo ""
    
    while true; do
        read -p "Are you sure? Type 'yes' to confirm, 'no' to skip: " response
        case $response in
            yes)
                echo "✅ Confirmed"
                return 0
                ;;
            no)
                echo "❌ Skipped"
                return 1
                ;;
            *)
                echo "Please type 'yes' or 'no'"
                ;;
        esac
    done
}

teardown_services() {
    echo "🗑️  Removing Cloud Run services..."
    
    local services=("agent-server" "workroom")
    local removed_any=false
    
    for service in "${services[@]}"; do
        if gcloud run services describe "$service" --region="$REGION" --quiet 2>/dev/null; then
            if confirm_action "Remove Cloud Run service: $service" "Service URL and all deployed code will be deleted"; then
                echo "🗑️  Deleting $service..."
                gcloud run services delete "$service" --region="$REGION" --quiet
                echo "✅ $service deleted"
                removed_any=true
            fi
        else
            echo "ℹ️  $service not found (already deleted or never deployed)"
        fi
    done
    
    if [[ "$removed_any" == "true" ]]; then
        echo "✅ Cloud Run services teardown complete"
    else
        echo "ℹ️  No Cloud Run services to remove"
    fi
}

teardown_database() {
    echo "🗑️  Checking database..."
    
    if gcloud sql instances describe agent-postgres --quiet 2>/dev/null; then
        if confirm_action "Remove Cloud SQL database: agent-postgres" "ALL DATABASE DATA WILL BE PERMANENTLY LOST"; then
            echo "🗑️  Deleting Cloud SQL instance..."
            gcloud sql instances delete agent-postgres --quiet
            echo "✅ Database deleted"
        fi
    else
        echo "ℹ️  Database not found (already deleted or never created)"
    fi
}

teardown_images() {
    echo "🗑️  Checking Artifact Registry images..."
    
    local repo="cloud-run-source-deploy"
    local removed_any=false
    
    if gcloud artifacts repositories describe "$repo" --location="$REGION" --quiet 2>/dev/null; then
        # List images in the repository
        local images
        images=$(gcloud artifacts docker images list "${REGION}-docker.pkg.dev/${PROJECT_ID}/${repo}" --format="value(package)" --quiet 2>/dev/null || echo "")
        
        if [[ -n "$images" ]]; then
            if confirm_action "Remove all Artifact Registry images" "Images for agent-server and workroom will be deleted"; then
                echo "🗑️  Deleting images..."
                while IFS= read -r image; do
                    if [[ -n "$image" ]]; then
                        echo "  Deleting $image..."
                        gcloud artifacts docker images delete "$image" --delete-tags --quiet 2>/dev/null || echo "    (already deleted)"
                        removed_any=true
                    fi
                done <<< "$images"
                echo "✅ Images deleted"
            fi
        else
            echo "ℹ️  No images found in repository"
        fi
        
        # Optionally remove the repository itself
        if confirm_action "Remove Artifact Registry repository: $repo" "The entire Docker repository will be deleted"; then
            echo "🗑️  Deleting repository..."
            gcloud artifacts repositories delete "$repo" --location="$REGION" --quiet
            echo "✅ Repository deleted"
            removed_any=true
        fi
    else
        echo "ℹ️  Artifact Registry repository not found"
    fi
    
    if [[ "$removed_any" == "true" ]]; then
        echo "✅ Artifact Registry teardown complete"
    else
        echo "ℹ️  No Artifact Registry resources to remove"
    fi
}

teardown_secrets() {
    echo "🗑️  Checking secrets..."
    
    if gcloud secrets describe npmrc-secret --quiet 2>/dev/null; then
        if confirm_action "Remove secret: npmrc-secret" "You'll need to recreate this for future deployments"; then
            echo "🗑️  Deleting secret..."
            gcloud secrets delete npmrc-secret --quiet
            echo "✅ Secret deleted"
        fi
    else
        echo "ℹ️  npmrc-secret not found"
    fi
}

main() {
    parse_args "$@"
    
    # If no teardown options specified, show interactive menu
    if [[ "$TEARDOWN_ALL" == "false" && "$TEARDOWN_SERVICES" == "false" && "$TEARDOWN_DATABASE" == "false" && "$TEARDOWN_IMAGES" == "false" && "$TEARDOWN_SECRETS" == "false" ]]; then
        show_teardown_menu
    else
        echo "🗑️  Agent Platform GCP Teardown"
        echo "📍 Project: $PROJECT_ID"
        echo "🌍 Region: $REGION"
        echo ""
    fi
    
    check_prerequisites
    
    # Show summary of what will be removed
    if [[ "$FORCE" == "false" ]]; then
        echo "📋 Teardown Summary:"
        [[ "$TEARDOWN_SERVICES" == "true" ]] && echo "  • Cloud Run services (agent-server, workroom)"
        [[ "$TEARDOWN_DATABASE" == "true" ]] && echo "  • Cloud SQL database (agent-postgres)"
        [[ "$TEARDOWN_IMAGES" == "true" ]] && echo "  • Artifact Registry images"
        [[ "$TEARDOWN_SECRETS" == "true" ]] && echo "  • Secrets (npmrc-secret)"
        echo ""
    fi
    
    # Execute teardown operations
    if [[ "$TEARDOWN_SERVICES" == "true" ]]; then
        teardown_services
        echo ""
    fi
    
    if [[ "$TEARDOWN_IMAGES" == "true" ]]; then
        teardown_images
        echo ""
    fi
    
    if [[ "$TEARDOWN_SECRETS" == "true" ]]; then
        teardown_secrets
        echo ""
    fi
    
    # Database last (most destructive)
    if [[ "$TEARDOWN_DATABASE" == "true" ]]; then
        teardown_database
        echo ""
    fi
    
    # Final status
    echo "🎉 Teardown complete!"
    echo ""
    echo "💰 Cost Impact:"
    [[ "$TEARDOWN_SERVICES" == "true" ]] && echo "  • Cloud Run: ~\$0.40/month saved"
    [[ "$TEARDOWN_DATABASE" == "true" ]] && echo "  • Cloud SQL: ~\$7-15/month saved"
    [[ "$TEARDOWN_IMAGES" == "true" ]] && echo "  • Storage: ~\$0.10/GB/month saved"
    echo ""
    echo "🔄 To redeploy: ./scripts/gcp/deploy.sh --all"
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 