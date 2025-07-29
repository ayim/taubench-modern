#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$CACHED_PROJECT_ID}"

# Get current user for resource scoping (use cached values from common.sh)
CURRENT_USER="$CACHED_USER"
CURRENT_USER_EMAIL="$CACHED_USER_EMAIL"

# User-scoped service names (matching deploy.sh pattern)
AGENT_SERVER_SERVICE="agent-server-${CURRENT_USER}"
WORKROOM_SERVICE="workroom-${CURRENT_USER}"

# Command line options
TEARDOWN_ALL=false
TEARDOWN_SERVICES=false
TEARDOWN_DATABASE=false
TEARDOWN_IMAGES=false
TEARDOWN_REVISIONS=false
TEARDOWN_SECRETS=false
FORCE=false
VERBOSE=false
USER_SCOPE_ONLY=false

# User role cache
USER_ROLE=""
HAS_ADMIN_ACCESS=false
HAS_OWNER_ACCESS=false

show_help() {
    cat << EOF
🗑️  Agent Platform GCP Teardown

USAGE:
    $0 [OPTIONS]

OPTIONS:
    --my-stuff          Remove only your personal resources (services + database + images + revisions)
    --all               Remove everything in project (services + database + images + secrets)
    --services          Remove only Cloud Run services
    --database          Remove Cloud SQL databases (developers: personal only, admins: all)
    --images            Remove only Artifact Registry images
    --revisions         Clean old Cloud Run revisions + their images (keeps latest 2)
    --secrets           Remove only secrets (requires admin access)
    --user-scope-only   Only operate on user-scoped resources (automatic for non-admins)
    --force             Skip confirmation prompts (DANGEROUS!)
    --verbose           Show detailed output
    -h, --help          Show this help

EXAMPLES:
    $0                          # Interactive menu with role-based options
    $0 --my-stuff              # Remove your personal resources (RECOMMENDED)
    $0 --services              # Remove only your Cloud Run services
    $0 --revisions             # Clean old revisions + images (keeps latest 2)
    $0 --database              # Remove databases (personal for developers, all for admins)
    $0 --all                   # Remove everything in project (admin only)
    $0 --all --force           # Remove everything without prompts (admin only)

PERMISSIONS:
    • Project Owner: Can tear down ALL resources including complete project reset
    • Admin (Editor): Can tear down any project resources except complete reset
    • Developers: Can tear down their own user-scoped resources + personal databases
    • Your services: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE

SAFETY:
    • By default, asks for confirmation before each destructive action
    • User role is checked and appropriate restrictions applied
    • All teardown operations are logged for audit purposes
    • Developers can delete personal databases, admins can delete shared databases
    • Use --force to skip confirmations (not recommended for production)

COST SAVINGS:
    • Cloud Run services: ~\$0.40/month (if idle)
    • Cloud SQL (db-f1-micro): ~\$7-15/month
    • Artifact Registry storage: ~\$0.10/GB/month
    • Old revisions + images: Variable (depends on # of deployments)
EOF
}

# Check user's role and permissions
check_user_role() {
    if [[ -z "$CURRENT_USER_EMAIL" ]]; then
        log_error "Unable to get authenticated user. Please run 'gcloud auth login' first."
        exit 1
    fi
    
    log_info "Checking user permissions for $CURRENT_USER_EMAIL..."
    
    # Check if user has owner access (most privileged)
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/owner" 2>/dev/null | grep -q "user:$CURRENT_USER_EMAIL"; then
        HAS_OWNER_ACCESS=true
        HAS_ADMIN_ACCESS=true
        USER_ROLE="owner"
        log_success "Project Owner access detected"
    # Check if user has admin access (editor)
    elif gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/editor" 2>/dev/null | grep -q "user:$CURRENT_USER_EMAIL"; then
        HAS_ADMIN_ACCESS=true
        USER_ROLE="admin"
        log_success "Admin access detected (Editor role)"
    else
        HAS_ADMIN_ACCESS=false
        USER_ROLE="developer"
        USER_SCOPE_ONLY=true
        log_info "Developer access detected - operations limited to user-scoped resources"
    fi
    
    if [[ "$VERBOSE" == "true" ]]; then
        echo "👤 User: $CURRENT_USER_EMAIL"
        echo "🔑 Role: $USER_ROLE"
        echo "🎯 Scope: $([ "$USER_SCOPE_ONLY" == "true" ] && echo "User resources only" || echo "All project resources")"
        echo ""
    fi
}

# Log teardown operation for audit purposes
log_teardown_operation() {
    local operation="$1"
    local resources="$2"
    local timestamp=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
    
    # Log to gcloud for audit trail
    if command -v gcloud >/dev/null 2>&1; then
        gcloud logging write agent-platform-teardown \
            "{\"operation\":\"$operation\",\"user\":\"$CURRENT_USER_EMAIL\",\"role\":\"$USER_ROLE\",\"resources\":\"$resources\",\"project\":\"$PROJECT_ID\",\"timestamp\":\"$timestamp\"}" \
            --severity=INFO 2>/dev/null || true
    fi
    
    # Also log locally for immediate reference
    echo "🔍 AUDIT: $timestamp - $CURRENT_USER_EMAIL ($USER_ROLE) - $operation: $resources" >&2
}

# Interactive teardown menu with role-based options
show_teardown_menu() {
    echo "🗑️  Agent Platform GCP Teardown"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo "👤 User: $CURRENT_USER_EMAIL ($USER_ROLE)"
    echo ""
    
    # Check current service status
    local agent_status="Not deployed"
    local workroom_status="Not deployed"
    local db_status="Not deployed"
    
    if [[ "$USER_SCOPE_ONLY" == "true" ]]; then
        # Check user-scoped services
        agent_status="$(get_service_status "$AGENT_SERVER_SERVICE" "$REGION" 2>/dev/null || echo "Not deployed")"
        workroom_status="$(get_service_status "$WORKROOM_SERVICE" "$REGION" 2>/dev/null || echo "Not deployed")"
        echo "📊 Your Resources:"
        printf "   Your Agent Server: %-15s" "$agent_status"
        echo ""
        printf "   Your Workroom:     %-15s" "$workroom_status"
        echo ""
    else
        # Check all services (admin view)
        agent_status="$(get_service_status "agent-server" "$REGION" 2>/dev/null || echo "Not deployed")"
        workroom_status="$(get_service_status "workroom" "$REGION" 2>/dev/null || echo "Not deployed")"
        local user_agent_status="$(get_service_status "$AGENT_SERVER_SERVICE" "$REGION" 2>/dev/null || echo "Not deployed")"
        local user_workroom_status="$(get_service_status "$WORKROOM_SERVICE" "$REGION" 2>/dev/null || echo "Not deployed")"
        
        if gcloud sql instances describe agent-postgres --quiet >/dev/null 2>&1; then
            db_status="Deployed"
        fi
        
        echo "📊 Project Resources:"
        printf "   Global Agent Server: %-15s" "$agent_status"
        echo ""
        printf "   Global Workroom:     %-15s" "$workroom_status"
        echo ""
        printf "   Your Agent Server:   %-15s" "$user_agent_status"
        echo ""
        printf "   Your Workroom:       %-15s" "$user_workroom_status"
        echo ""
        printf "   Database:            %-15s" "$db_status"
        echo ""
    fi
    echo ""
    
    echo "🗑️  What would you like to remove?"
    echo ""
    
    if [[ "$USER_SCOPE_ONLY" == "true" ]]; then
        # Developer menu - limited options
        echo " 1) 🌐 Your Cloud Run Services (${AGENT_SERVER_SERVICE}, ${WORKROOM_SERVICE})"
        echo " 2) 🗄️  Your Personal Database (agent-postgres-${CURRENT_USER})"
        echo " 3) 📦 Your Artifact Registry images"
        echo " 4) 🔄 Clean old revisions + their images (keeps latest 2)"
        echo " 5) 📊 Show current status"
        echo " 0) ❌ Cancel"
        echo ""
        echo "ℹ️  As a developer, you can manage your own user-scoped resources + personal database."
        echo "   Shared database and secrets require admin access."
        
        while true; do
            read -p "Select option (0-5): " choice
            
            case $choice in
                1)
                    echo "✅ Selected: Remove your Cloud Run services"
                    TEARDOWN_SERVICES=true
                    break
                    ;;
                2)
                    echo "✅ Selected: Remove your personal database"
                    TEARDOWN_DATABASE=true
                    break
                    ;;
                3)
                    echo "✅ Selected: Remove your Artifact Registry images"
                    TEARDOWN_IMAGES=true
                    break
                    ;;
                4)
                    echo "✅ Selected: Clean old revisions + their images"
                    TEARDOWN_REVISIONS=true
                    break
                    ;;
                5)
                    echo ""
                    show_user_resources_status
                    echo ""
                    echo "🗑️  What would you like to remove?"
                    echo ""
                    echo " 1) 🌐 Your Cloud Run Services (${AGENT_SERVER_SERVICE}, ${WORKROOM_SERVICE})"
                    echo " 2) 🗄️  Your Personal Database (agent-postgres-${CURRENT_USER})"
                    echo " 3) 📦 Your Artifact Registry images"
                    echo " 4) 🔄 Clean old revisions + their images (keeps latest 2)"
                    echo " 5) 📊 Show current status"
                    echo " 0) ❌ Cancel"
                    echo ""
                    ;;
                0)
                    echo "👋 Teardown cancelled"
                    exit 0
                    ;;
                *)
                    echo "❌ Invalid choice. Please enter 0-5"
                    ;;
            esac
        done
    else
        # Admin menu - simplified and clearer
        echo " 1) 👤 My stuff only (my services + my personal database)"
        
        # Only show nuclear option for project owners (not editors)
        local next_option=2
        if [[ "$HAS_OWNER_ACCESS" == "true" ]]; then
            echo " 2) 💥 ⚠️  RESET ENTIRE PROJECT ⚠️  (DELETES ALL USERS' DATA + EVERYTHING)"
            next_option=3
        fi
        
        echo " $next_option) 🌐 All Cloud Run services (all users)"
        echo " $((next_option + 1))) 🗄️  Databases with selection menu"
        echo " $((next_option + 2))) 📦 Images and cleanup (revisions + old images)"
        echo " $((next_option + 3))) 📊 Show current status"
        echo " 0) ❌ Cancel"
        echo ""
        
        if [[ "$HAS_OWNER_ACCESS" == "true" ]]; then
            echo "💡 Most common: Option 1 (clean up your own stuff)"
            echo "⚠️  DANGER: Option 2 will delete EVERYTHING for ALL USERS in this project!"
        else
            echo "💡 Recommended: Option 1 (clean up your own stuff)"
            if [[ "$HAS_ADMIN_ACCESS" == "true" ]]; then
                echo "ℹ️  Note: Project reset requires Owner role (you have Editor)"
            fi
        fi
        
        # Calculate max option for validation
        local max_option=$((next_option + 3))
        
        while true; do
            read -p "Select option (0-$max_option): " choice
            
            case $choice in
                1)
                    echo "✅ Selected: Clean up your personal resources only"
                    TEARDOWN_SERVICES=true
                    TEARDOWN_DATABASE=true
                    TEARDOWN_IMAGES=true
                    TEARDOWN_REVISIONS=true
                    USER_SCOPE_ONLY=true
                    break
                    ;;
                2)
                    if [[ "$HAS_OWNER_ACCESS" == "true" ]]; then
                        echo ""
                        echo "⚠️  ⚠️  ⚠️  FINAL WARNING ⚠️  ⚠️  ⚠️"
                        echo ""
                        echo "🚨 This will DELETE EVERYTHING in project: $PROJECT_ID"
                        echo "🚨 ALL USERS' DATA will be permanently lost:"
                        echo "   • All Cloud Run services (everyone's deployments)"
                        echo "   • All databases (shared + personal + ALL user data)"
                        echo "   • All Docker images (deployment history)"
                        echo "   • All secrets (npm tokens, etc.)"
                        echo ""
                        echo "💀 This action affects EVERY DEVELOPER in this project!"
                        echo "💀 Recovery is IMPOSSIBLE - all data will be gone forever!"
                        echo ""
                        if confirm_action "💥 RESET ENTIRE PROJECT 💥" "🚨 DESTROYS ALL USER DATA - CANNOT BE UNDONE 🚨"; then
                            echo "✅ Selected: Remove everything in project"
                            TEARDOWN_ALL=true
                            TEARDOWN_SERVICES=true
                            TEARDOWN_DATABASE=true
                            TEARDOWN_IMAGES=true
                            TEARDOWN_REVISIONS=true
                            TEARDOWN_SECRETS=true
                            break
                        fi
                    else
                        echo "❌ Invalid choice. Please enter 0-$max_option"
                    fi
                    ;;
                "$next_option")
                    echo "✅ Selected: Remove all Cloud Run services"
                    TEARDOWN_SERVICES=true
                    break
                    ;;
                "$((next_option + 1))")
                    echo "✅ Selected: Database selection menu"
                    TEARDOWN_DATABASE=true
                    break
                    ;;
                "$((next_option + 2))")
                    echo "✅ Selected: Clean images and revisions"
                    TEARDOWN_IMAGES=true
                    TEARDOWN_REVISIONS=true
                    break
                    ;;
                "$((next_option + 3))")
                    echo ""
                    make gcp status
                    echo ""
                    echo "🗑️  What would you like to remove?"
                    echo ""
                    echo " 1) 👤 My stuff only (my services + my personal database)"
                    
                    # Show nuclear option again if owner
                    if [[ "$HAS_OWNER_ACCESS" == "true" ]]; then
                        echo " 2) 💥 ⚠️  RESET ENTIRE PROJECT ⚠️  (DELETES ALL USERS' DATA + EVERYTHING)"
                    fi
                    
                    echo " $next_option) 🌐 All Cloud Run services (all users)"
                    echo " $((next_option + 1))) 🗄️  Databases with selection menu"
                    echo " $((next_option + 2))) 📦 Images and cleanup (revisions + old images)"
                    echo " $((next_option + 3))) 📊 Show current status"
                    echo " 0) ❌ Cancel"
                    echo ""
                    
                    if [[ "$HAS_OWNER_ACCESS" == "true" ]]; then
                        echo "💡 Most common: Option 1 (clean up your own stuff)"
                        echo "⚠️  DANGER: Option 2 will delete EVERYTHING for ALL USERS in this project!"
                    else
                        echo "💡 Recommended: Option 1 (clean up your own stuff)"
                        if [[ "$HAS_ADMIN_ACCESS" == "true" ]]; then
                            echo "ℹ️  Note: Project reset requires Owner role (you have Editor)"
                        fi
                    fi
                    ;;
                0)
                    echo "👋 Teardown cancelled"
                    exit 0
                    ;;
                *)
                    echo "❌ Invalid choice. Please enter 0-$max_option"
                    ;;
            esac
        done
    fi
    echo ""
}

# Show user's resources status
show_user_resources_status() {
    echo "📊 Your Resource Status:"
    echo "👤 User: $CURRENT_USER_EMAIL"
    echo ""
    
    # Check user services
    local user_agent_status="$(get_service_status "$AGENT_SERVER_SERVICE" "$REGION" 2>/dev/null || echo "Not deployed")"
    local user_workroom_status="$(get_service_status "$WORKROOM_SERVICE" "$REGION" 2>/dev/null || echo "Not deployed")"
    
    printf "   Agent Server: %-15s (%s)" "$user_agent_status" "$AGENT_SERVER_SERVICE"
    echo ""
    printf "   Workroom:     %-15s (%s)" "$user_workroom_status" "$WORKROOM_SERVICE"
    echo ""
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --my-stuff)
                TEARDOWN_SERVICES=true
                TEARDOWN_DATABASE=true
                TEARDOWN_IMAGES=true
                TEARDOWN_REVISIONS=true
                USER_SCOPE_ONLY=true
                shift
                ;;
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
            --revisions)
                TEARDOWN_REVISIONS=true
                shift
                ;;
            --secrets)
                TEARDOWN_SECRETS=true
                shift
                ;;
            --user-scope-only)
                USER_SCOPE_ONLY=true
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
    echo "User: $CURRENT_USER_EMAIL ($USER_ROLE)"
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

# Enhanced teardown_services with user scoping
teardown_services() {
    echo "🗑️  Removing Cloud Run services..."
    
    local services=()
    local removed_any=false
    local operation_desc=""
    
    if [[ "$USER_SCOPE_ONLY" == "true" ]]; then
        services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
        operation_desc="user-scoped services"
        echo "🎯 Targeting your user-scoped services only"
    else
        # Admin can remove all services or choose scope
        if [[ "$HAS_ADMIN_ACCESS" == "true" ]]; then
            echo "🔑 Admin access - checking all services in project..."
            
            # Get all Cloud Run services and filter for agent-platform related ones
            local all_services
            all_services=$(gcloud run services list --region="$REGION" --format="value(metadata.name)" --quiet 2>/dev/null || echo "")
            
            # Filter for agent-platform services (both global and user-scoped)
            while IFS= read -r service; do
                if [[ -n "$service" && ("$service" == "agent-server"* || "$service" == "workroom"*) ]]; then
                    services+=("$service")
                fi
            done <<< "$all_services"
            
            operation_desc="all agent-platform services"
        else
            # Fallback to user-scoped if somehow we get here without admin access
            services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
            operation_desc="user-scoped services"
        fi
    fi
    
    if [[ ${#services[@]} -eq 0 ]]; then
        echo "ℹ️  No agent-platform services found to remove"
        return 0
    fi
    
    echo "📋 Services to remove:"
    for service in "${services[@]}"; do
        if gcloud run services describe "$service" --region="$REGION" --quiet 2>/dev/null; then
            echo "   ✓ $service (deployed)"
        else
            echo "   ○ $service (not found)"
        fi
    done
    
    for service in "${services[@]}"; do
        if gcloud run services describe "$service" --region="$REGION" --quiet 2>/dev/null; then
            if confirm_action "Remove Cloud Run service: $service" "Service URL and all deployed code will be deleted"; then
                echo "🗑️  Deleting $service..."
                gcloud run services delete "$service" --region="$REGION" --quiet
                echo "✅ $service deleted"
                removed_any=true
                
                # Log this operation
                log_teardown_operation "delete_service" "$service"
            fi
        else
            echo "ℹ️  $service not found (already deleted or never deployed)"
        fi
    done
    
    if [[ "$removed_any" == "true" ]]; then
        echo "✅ Cloud Run services teardown complete"
        log_teardown_operation "teardown_services_complete" "$operation_desc"
    else
        echo "ℹ️  No Cloud Run services to remove"
    fi
}

# Teardown personal databases only (for developers)
teardown_personal_databases_only() {
    local personal_db="agent-postgres-${CURRENT_USER}"
    
    echo "👤 Personal Database Teardown (Developer Mode)"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo "👤 User: $CURRENT_USER_EMAIL ($USER_ROLE)"
    echo ""
    
    # Check if personal database exists
    if ! gcloud sql instances describe "$personal_db" --quiet >/dev/null 2>&1; then
        echo "ℹ️  No personal database found for your user: $personal_db"
        echo ""
        echo "💡 You can only delete your own personal databases"
        echo "🔑 For shared database deletion, contact an admin with Owner/Editor role"
        return 0
    fi
    
    # Get personal database info
    local personal_state=$(gcloud sql instances describe "$personal_db" --format="value(state)" --quiet 2>/dev/null)
    local personal_tier=$(gcloud sql instances describe "$personal_db" --format="value(settings.tier)" --quiet 2>/dev/null)
    local personal_created=$(gcloud sql instances describe "$personal_db" --format="value(createTime)" --quiet 2>/dev/null)
    
    echo "📊 Your personal database:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-30s %-15s %-12s %s\n" "DATABASE INSTANCE" "TIER" "STATE" "CREATED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local state_display=""
    case "$personal_state" in
        "RUNNABLE") state_display="✅ Running" ;;
        "STOPPED") state_display="⏹️  Stopped" ;;
        "PENDING_DELETE") state_display="🗑️  Deleting" ;;
        *) state_display="⚠️  $personal_state" ;;
    esac
    
    local formatted_created=""
    if [[ -n "$personal_created" ]]; then
        formatted_created=$(date -d "$personal_created" "+%Y-%m-%d" 2>/dev/null || echo "$personal_created")
    fi
    
    printf "%-30s %-15s %-12s %s\n" \
        "$(echo "$personal_db" | cut -c1-29)" \
        "$personal_tier" \
        "$state_display" \
        "$formatted_created"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Show cost savings
    case "$personal_tier" in
        "db-f1-micro") echo "💰 Cost savings: ~\$7-10/month" ;;
        "db-g1-small") echo "💰 Cost savings: ~\$25-35/month" ;;
        "db-custom-1-3840") echo "💰 Cost savings: ~\$50-70/month" ;;
        *) echo "💰 Cost savings: Variable (depends on tier)" ;;
    esac
    
    echo ""
    echo "⚠️  Impact of deletion:"
    echo "   • Your personal services (agent-server-${CURRENT_USER}, workroom-${CURRENT_USER}) will stop working"
    echo "   • All your personal agent data and conversations will be lost"
    echo "   • Shared databases and other users' data will NOT be affected"
    echo "   • You can recreate a new personal database anytime"
    echo ""
    
    # Confirmation for personal database deletion
    if [[ "$FORCE" != "true" ]]; then
        echo "🎯 Personal database deletion options:"
        echo " 1) 🗑️  Delete your personal database ($personal_db)"
        echo " 2) 📊 Check database status and abort"
        echo " 0) ❌ Cancel deletion"
        echo ""
        
        while true; do
            read -p "Select option (0-2): " choice
            case $choice in
                1)
                    if confirm_action "Delete your personal database" "Personal database '$personal_db' and ALL your data will be permanently deleted"; then
                        echo "🗑️  Deleting your personal database..."
                        setup_database_signal_handler
                        delete_single_database "$personal_db"
                        trap - INT TERM  # Reset signal handler
                        log_teardown_operation "delete_personal_database_developer" "$personal_db"
                        echo ""
                        echo "✅ Personal database deletion complete"
                        echo "💡 To recreate: scripts/gcp/deploy.sh --all --personal-isolated"
                    fi
                    break
                    ;;
                2)
                    echo ""
                    echo "📊 Personal database status: $state_display"
                    echo "🗑️  Personal database deletion cancelled for status check"
                    break
                    ;;
                0)
                    echo "❌ Personal database deletion cancelled"
                    break
                    ;;
                *)
                    echo "❌ Invalid choice. Please enter 0-2"
                    ;;
            esac
        done
    else
        # Force mode - delete personal database
        echo "🔥 FORCE mode: Deleting personal database"
        setup_database_signal_handler
        delete_single_database "$personal_db"
        trap - INT TERM  # Reset signal handler
        log_teardown_operation "delete_personal_database_developer_force" "$personal_db"
    fi
}

teardown_database() {
    echo "🗑️  Discovering Cloud SQL databases..."
    
    # For non-admin users, only allow personal database deletion
    if [[ "$HAS_ADMIN_ACCESS" != "true" ]]; then
        echo "👤 Developer access - can delete personal databases only"
        teardown_personal_databases_only
        return $?
    fi
    
    echo "🗑️  Discovering Cloud SQL databases..."
    
    # Discover all agent-related database instances
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"
    local available_databases=()
    local database_info=()
    
    # Check personal database
    if gcloud sql instances describe "$personal_db" --quiet >/dev/null 2>&1; then
        local personal_state=$(gcloud sql instances describe "$personal_db" --format="value(state)" --quiet 2>/dev/null)
        available_databases+=("$personal_db")
        database_info+=("$personal_db|personal|$personal_state|Affects only your services")
    fi
    
    # Check shared database
    if gcloud sql instances describe "$shared_db" --quiet >/dev/null 2>&1; then
        local shared_state=$(gcloud sql instances describe "$shared_db" --format="value(state)" --quiet 2>/dev/null)
        available_databases+=("$shared_db")
        database_info+=("$shared_db|shared|$shared_state|⚠️  Affects ALL users in project")
    fi
    
    # Check for template database (admin only)
    local template_db="agent-postgres-template"
    if gcloud sql instances describe "$template_db" --quiet >/dev/null 2>&1; then
        local template_state=$(gcloud sql instances describe "$template_db" --format="value(state)" --quiet 2>/dev/null)
        available_databases+=("$template_db")
        database_info+=("$template_db|template|$template_state|🏗️  Template database - saves team ~360s per personal DB creation")
    fi
    
    # Check for any other agent-related databases
    echo "🔍 Scanning for other agent-related databases..."
    local all_instances
    all_instances=$(gcloud sql instances list --format="value(name)" --quiet 2>/dev/null || echo "")
    
    while IFS= read -r instance; do
        if [[ -n "$instance" && "$instance" == *"agent"* && "$instance" != "$personal_db" && "$instance" != "$shared_db" && "$instance" != "$template_db" ]]; then
            local instance_state=$(gcloud sql instances describe "$instance" --format="value(state)" --quiet 2>/dev/null)
            available_databases+=("$instance")
            database_info+=("$instance|other|$instance_state|Unknown scope - check before deleting")
        fi
    done <<< "$all_instances"
    
    if [[ ${#available_databases[@]} -eq 0 ]]; then
        echo "ℹ️  No agent-related databases found to remove"
        return 0
    fi
    
    # Display available databases
    echo ""
    echo "📊 Available databases:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-3s %-30s %-10s %-12s %s\n" "#" "DATABASE INSTANCE" "TYPE" "STATE" "IMPACT"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local index=1
    for db_info in "${database_info[@]}"; do
        local db_name=$(echo "$db_info" | cut -d'|' -f1)
        local db_type=$(echo "$db_info" | cut -d'|' -f2)
        local db_state=$(echo "$db_info" | cut -d'|' -f3)
        local db_impact=$(echo "$db_info" | cut -d'|' -f4)
        
        local state_display=""
        case "$db_state" in
            "RUNNABLE") state_display="✅ Running" ;;
            "STOPPED") state_display="⏹️  Stopped" ;;
            "PENDING_DELETE") state_display="🗑️  Deleting" ;;
            *) state_display="⚠️  $db_state" ;;
        esac
        
        printf "%-3s %-30s %-10s %-12s %s\n" \
            "$index" \
            "$(echo "$db_name" | cut -c1-29)" \
            "$db_type" \
            "$state_display" \
            "$db_impact"
        ((index++))
    done
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Interactive database selection
    if [[ "$FORCE" != "true" ]]; then
        echo "🎯 Database deletion options:"
        echo " 1) 🗑️  Delete ALL databases listed above (DANGEROUS!)"
        echo " 2) 🎯 Select specific databases to delete"
        echo " 3) 👤 Delete only personal databases"
        echo " 4) 🌐 Delete only shared databases"
        echo " 5) 🏗️  Delete only template database (admin only)"
        echo " 6) 📊 Check database status and abort"
        echo " 0) ❌ Cancel database deletion"
        echo ""
        
        while true; do
            read -p "Select option (0-6): " choice
            case $choice in
                1)
                    delete_all_databases "${database_info[@]}"
                    break
                    ;;
                2)
                    delete_selective_databases "${database_info[@]}"
                    break
                    ;;
                3)
                    delete_personal_databases "${database_info[@]}"
                    break
                    ;;
                4)
                    delete_shared_databases "${database_info[@]}"
                    break
                    ;;
                5)
                    delete_template_databases "${database_info[@]}"
                    break
                    ;;
                6)
                    check_databases_status "${database_info[@]}"
                    echo ""
                    echo "🗑️  Database deletion cancelled for status check"
                    break
                    ;;
                0)
                    echo "❌ Database deletion cancelled"
                    break
                    ;;
                *)
                    echo "❌ Invalid choice. Please enter 0-6"
                    ;;
            esac
        done
    else
        # Force mode - be conservative and only delete personal databases
        echo "🔥 FORCE mode: Deleting personal databases only (safer default)"
        delete_personal_databases "${database_info[@]}"
    fi
}

# Database deletion helper functions with signal handling

# Setup signal handler for database operations
setup_database_signal_handler() {
    trap 'handle_database_interrupt' INT TERM
}

# Handle interrupt during database operations
handle_database_interrupt() {
    echo ""
    echo "⚠️  Database operation interrupted by user (ctrl-c)"
    echo ""
    echo "🔍 Checking current database states..."
    
    # Check what state databases are in
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"
    local databases_to_check=("$personal_db" "$shared_db")
    
    for db in "${databases_to_check[@]}"; do
        local db_state=$(gcloud sql instances describe "$db" --format="value(state)" --quiet 2>/dev/null || echo "NOT_FOUND")
        
        if [[ "$db_state" != "NOT_FOUND" ]]; then
            case "$db_state" in
                "PENDING_DELETE")
                    echo "🗑️  $db: Still deleting in background (check progress with: gcloud sql instances describe $db)"
                    ;;
                "RUNNABLE")
                    echo "✅ $db: Running (deletion was not started or was cancelled)"
                    ;;
                "STOPPED")
                    echo "⏹️  $db: Stopped (deletion was not started)"
                    ;;
                *)
                    echo "⚠️  $db: $db_state (unknown state - check manually)"
                    ;;
            esac
        fi
    done
    
    echo ""
    echo "💡 Recovery actions:"
    echo "   • Check operation status: gcloud sql operations list --filter='targetId:agent-postgres*'"
    echo "   • Resume teardown: ./scripts/gcp/teardown.sh --database"
    echo "   • Check costs: In-progress deletions may still incur charges until complete"
    echo ""
    
    log_teardown_operation "database_operation_interrupted" "user_abort"
    
    # Reset trap and exit gracefully
    trap - INT TERM
    exit 130  # Standard exit code for ctrl-c
}

# Delete all databases (dangerous)
delete_all_databases() {
    local database_info=("$@")
    
    echo ""
    echo "⚠️  DANGER: This will delete ALL agent-related databases!"
    echo "📊 Databases to delete: ${#database_info[@]}"
    
    local shared_count=0
    for db_info in "${database_info[@]}"; do
        local db_type=$(echo "$db_info" | cut -d'|' -f2)
        if [[ "$db_type" == "shared" ]]; then
            ((shared_count++))
        fi
    done
    
    if [[ $shared_count -gt 0 ]]; then
        echo "🚨 This includes $shared_count SHARED database(s) affecting ALL users!"
    fi
    
    if confirm_action "Delete ALL databases" "This will permanently delete ALL agent databases and data"; then
        setup_database_signal_handler
        
        for db_info in "${database_info[@]}"; do
            local db_name=$(echo "$db_info" | cut -d'|' -f1)
            delete_single_database "$db_name"
        done
        
        trap - INT TERM  # Reset signal handler
        log_teardown_operation "delete_all_databases" "$(echo "${database_info[@]}" | tr ' ' ',')"
    fi
}

# Delete specific selected databases
delete_selective_databases() {
    local database_info=("$@")
    
    echo ""
    echo "🎯 Select databases to delete (space-separated numbers, e.g., '1 3'):"
    echo "   Enter database numbers from the list above"
    echo "   ⚠️  Shared databases affect ALL users"
    echo ""
    
    while true; do
        read -p "Database numbers to delete (or 'cancel'): " selection
        
        if [[ "$selection" == "cancel" ]]; then
            echo "❌ Selective database deletion cancelled"
            return 0
        fi
        
        # Validate selection
        local valid=true
        local selected_databases=()
        
        for num in $selection; do
            if [[ "$num" =~ ^[0-9]+$ ]] && [[ "$num" -ge 1 ]] && [[ "$num" -le ${#database_info[@]} ]]; then
                local index=$((num - 1))
                selected_databases+=("${database_info[$index]}")
            else
                echo "❌ Invalid number: $num (must be 1-${#database_info[@]})"
                valid=false
                break
            fi
        done
        
        if [[ "$valid" == "true" && ${#selected_databases[@]} -gt 0 ]]; then
            echo ""
            echo "📋 Selected databases for deletion:"
            for db_info in "${selected_databases[@]}"; do
                local db_name=$(echo "$db_info" | cut -d'|' -f1)
                local db_type=$(echo "$db_info" | cut -d'|' -f2)
                local db_impact=$(echo "$db_info" | cut -d'|' -f4)
                echo "   🗑️  $db_name ($db_type) - $db_impact"
            done
            
            if confirm_action "Delete selected databases" "Selected databases will be permanently deleted"; then
                setup_database_signal_handler
                
                for db_info in "${selected_databases[@]}"; do
                    local db_name=$(echo "$db_info" | cut -d'|' -f1)
                    delete_single_database "$db_name"
                done
                
                trap - INT TERM  # Reset signal handler
                log_teardown_operation "delete_selective_databases" "$(echo "${selected_databases[@]}" | tr ' ' ',')"
            fi
            break
        elif [[ ${#selected_databases[@]} -eq 0 ]]; then
            echo "❌ No valid databases selected"
        fi
    done
}

# Delete only personal databases
delete_personal_databases() {
    local database_info=("$@")
    
    local personal_databases=()
    for db_info in "${database_info[@]}"; do
        local db_type=$(echo "$db_info" | cut -d'|' -f2)
        if [[ "$db_type" == "personal" ]]; then
            personal_databases+=("$db_info")
        fi
    done
    
    if [[ ${#personal_databases[@]} -eq 0 ]]; then
        echo "ℹ️  No personal databases found to delete"
        return 0
    fi
    
    echo ""
    echo "👤 Personal databases to delete:"
    for db_info in "${personal_databases[@]}"; do
        local db_name=$(echo "$db_info" | cut -d'|' -f1)
        echo "   🗑️  $db_name (affects only your services)"
    done
    
    if confirm_action "Delete personal databases" "Your personal databases will be deleted (shared databases preserved)"; then
        setup_database_signal_handler
        
        for db_info in "${personal_databases[@]}"; do
            local db_name=$(echo "$db_info" | cut -d'|' -f1)
            delete_single_database "$db_name"
        done
        
        trap - INT TERM  # Reset signal handler
        log_teardown_operation "delete_personal_databases" "$(echo "${personal_databases[@]}" | tr ' ' ',')"
    fi
}

# Delete only shared databases
delete_shared_databases() {
    local database_info=("$@")
    
    local shared_databases=()
    for db_info in "${database_info[@]}"; do
        local db_type=$(echo "$db_info" | cut -d'|' -f2)
        if [[ "$db_type" == "shared" ]]; then
            shared_databases+=("$db_info")
        fi
    done
    
    if [[ ${#shared_databases[@]} -eq 0 ]]; then
        echo "ℹ️  No shared databases found to delete"
        return 0
    fi
    
    echo ""
    echo "🌐 Shared databases to delete:"
    for db_info in "${shared_databases[@]}"; do
        local db_name=$(echo "$db_info" | cut -d'|' -f1)
        echo "   🗑️  $db_name (⚠️  affects ALL users in project)"
    done
    
    echo ""
    echo "🚨 WARNING: Shared databases affect ALL developers and users!"
    echo "   This will delete data for everyone in the project."
    
    if confirm_action "Delete shared databases" "⚠️  ALL USER DATA will be lost - affects entire project"; then
        setup_database_signal_handler
        
        for db_info in "${shared_databases[@]}"; do
            local db_name=$(echo "$db_info" | cut -d'|' -f1)
            delete_single_database "$db_name"
        done
        
        trap - INT TERM  # Reset signal handler
        log_teardown_operation "delete_shared_databases" "$(echo "${shared_databases[@]}" | tr ' ' ',')"
    fi
}

# Delete only template databases (admin only)
delete_template_databases() {
    local database_info=("$@")
    
    # Check admin permissions first
    if [[ "$HAS_ADMIN_ACCESS" != "true" ]]; then
        echo "❌ Template database deletion requires admin access (Owner/Editor role)"
        echo "💡 Only project admins can manage template databases"
        return 1
    fi
    
    local template_databases=()
    for db_info in "${database_info[@]}"; do
        local db_type=$(echo "$db_info" | cut -d'|' -f2)
        if [[ "$db_type" == "template" ]]; then
            template_databases+=("$db_info")
        fi
    done
    
    if [[ ${#template_databases[@]} -eq 0 ]]; then
        echo "ℹ️  No template databases found to delete"
        return 0
    fi
    
    echo ""
    echo "🏗️  Template databases to delete:"
    for db_info in "${template_databases[@]}"; do
        local db_name=$(echo "$db_info" | cut -d'|' -f1)
        echo "   🗑️  $db_name (saves team ~360s per personal DB creation)"
    done
    
    echo ""
    echo "⚠️  Impact of deleting template database:"
    echo "   • Personal database creation: Back to 450 seconds (vs 90-120 with template)"
    echo "   • Monthly cost savings: ~\$7-12"
    echo "   • Template can be recreated anytime: make gcp template-setup"
    echo "   • No impact on existing databases (they remain independent)"
    
    if confirm_action "Delete template database" "Template will be deleted but existing databases remain intact"; then
        setup_database_signal_handler
        
        for db_info in "${template_databases[@]}"; do
            local db_name=$(echo "$db_info" | cut -d'|' -f1)
            delete_single_database "$db_name"
        done
        
        trap - INT TERM  # Reset signal handler
        log_teardown_operation "delete_template_databases" "$(echo "${template_databases[@]}" | tr ' ' ',')"
        
        echo ""
        echo "✅ Template database deletion complete"
        echo "💡 To recreate template: ./scripts/gcp/setup-template.sh --create"
    fi
}

# Check current status of all databases
check_databases_status() {
    local database_info=("$@")
    
    echo ""
    echo "📊 Current database status:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    for db_info in "${database_info[@]}"; do
        local db_name=$(echo "$db_info" | cut -d'|' -f1)
        local db_type=$(echo "$db_info" | cut -d'|' -f2)
        
        echo ""
        echo "🗄️  Database: $db_name ($db_type)"
        
        # Get detailed status
        local db_state=$(gcloud sql instances describe "$db_name" --format="value(state)" --quiet 2>/dev/null || echo "NOT_FOUND")
        local db_tier=$(gcloud sql instances describe "$db_name" --format="value(settings.tier)" --quiet 2>/dev/null || echo "")
        local db_region=$(gcloud sql instances describe "$db_name" --format="value(region)" --quiet 2>/dev/null || echo "")
        local db_ip=$(gcloud sql instances describe "$db_name" --format="value(ipAddresses[0].ipAddress)" --quiet 2>/dev/null || echo "")
        
        echo "   📊 State:    $db_state"
        echo "   🏗️  Tier:     $db_tier"
        echo "   🌍 Region:   $db_region"
        echo "   🌐 IP:       $db_ip"
        
        # Check for ongoing operations
        local ongoing_ops=$(gcloud sql operations list --filter="targetId:$db_name AND status:RUNNING" --format="value(operationType)" --quiet 2>/dev/null || echo "")
        if [[ -n "$ongoing_ops" ]]; then
            echo "   ⚡ Active:   $ongoing_ops"
        fi
        
        # Estimate monthly cost
        case "$db_tier" in
            "db-f1-micro") echo "   💰 Cost:    ~\$7-10/month" ;;
            "db-g1-small") echo "   💰 Cost:    ~\$25-35/month" ;;
            "db-n1-standard-1") echo "   💰 Cost:    ~\$50-70/month" ;;
            *) echo "   💰 Cost:    Unknown tier" ;;
        esac
    done
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check for any pending operations across all instances
    echo ""
    echo "🔍 Checking for pending operations..."
    local all_ops=$(gcloud sql operations list --filter="status:RUNNING" --format="table(name,operationType,targetId,status,startTime)" --quiet 2>/dev/null || echo "")
    
    if [[ -n "$all_ops" && "$all_ops" != "NAME" ]]; then
        echo "⚡ Active operations found:"
        echo "$all_ops"
    else
        echo "✅ No active operations"
    fi
}

# Delete a single database instance with error handling
delete_single_database() {
    local db_name="$1"
    
    echo ""
    echo "🗑️  Deleting database: $db_name"
    
    # Check current state before deletion
    local current_state=$(gcloud sql instances describe "$db_name" --format="value(state)" --quiet 2>/dev/null || echo "NOT_FOUND")
    
    if [[ "$current_state" == "NOT_FOUND" ]]; then
        echo "ℹ️  $db_name not found (already deleted)"
        return 0
    fi
    
    if [[ "$current_state" == "PENDING_DELETE" ]]; then
        echo "⚠️  $db_name already being deleted (operation in progress)"
        return 0
    fi
    
    echo "📊 Current state: $current_state"
    echo "⏳ Starting deletion (this may take 2-5 minutes)..."
    
    # Start deletion with error handling
    local delete_result=0
    if ! gcloud sql instances delete "$db_name" --quiet 2>&1; then
        delete_result=$?
        echo ""
        echo "❌ Deletion command failed (exit code: $delete_result)"
        
        # Check what actually happened
        local new_state=$(gcloud sql instances describe "$db_name" --format="value(state)" --quiet 2>/dev/null || echo "NOT_FOUND")
        
        case "$new_state" in
            "NOT_FOUND")
                echo "✅ Database was actually deleted successfully"
                log_teardown_operation "delete_database" "$db_name"
                return 0
                ;;
            "PENDING_DELETE")
                echo "⚡ Deletion started but command was interrupted"
                echo "   💡 Monitor progress: gcloud sql instances describe $db_name"
                log_teardown_operation "delete_database_started" "$db_name"
                return 0
                ;;
            "$current_state")
                echo "❌ Deletion failed - database unchanged"
                log_teardown_operation "delete_database_failed" "$db_name"
                return 1
                ;;
            *)
                echo "⚠️  Unexpected state: $new_state"
                log_teardown_operation "delete_database_unknown_state" "$db_name:$new_state"
                return 1
                ;;
        esac
    else
        echo "✅ $db_name deletion completed successfully"
        log_teardown_operation "delete_database" "$db_name"
        return 0
    fi
}

# Enhanced teardown_images with selective deletion and deployment status
teardown_images() {
    echo "🗑️  Checking Artifact Registry images..."
    
    local repo="cloud-run-source-deploy"
    local removed_any=false
    
    if ! gcloud artifacts repositories describe "$repo" --location="$REGION" --quiet >/dev/null 2>&1; then
        echo "ℹ️  Artifact Registry repository not found"
        return 0
    fi
    
    # Get detailed image information
    local images_json
    images_json=$(gcloud artifacts docker images list "${REGION}-docker.pkg.dev/${PROJECT_ID}/${repo}" \
        --include-tags \
        --format="json" \
        --quiet 2>/dev/null || echo "[]")
    
    if [[ "$images_json" == "[]" || -z "$images_json" ]]; then
        echo "ℹ️  No images found in repository"
        return 0
    fi
    
    # Get currently deployed image references
    local deployed_images=()
    echo "🔍 Checking currently deployed images..."
    
    # Check all Cloud Run services for deployed images
    local all_services
    all_services=$(gcloud run services list --region="$REGION" --format="value(metadata.name)" --quiet 2>/dev/null || echo "")
    
    while IFS= read -r service; do
        if [[ -n "$service" && ("$service" == "agent-server"* || "$service" == "workroom"*) ]]; then
            local deployed_image
            deployed_image=$(gcloud run services describe "$service" --region="$REGION" \
                --format="value(spec.template.spec.template.spec.containers[0].image)" --quiet 2>/dev/null || echo "")
            if [[ -n "$deployed_image" ]]; then
                deployed_images+=("$deployed_image")
                echo "   📍 $service: $(basename "$deployed_image")"
            fi
        fi
    done <<< "$all_services"
    
    echo ""
    
    # Parse and display images with details
    local image_info=()
    local display_lines=()
    
    echo "📦 Available images in repository:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    printf "%-3s %-25s %-20s %-15s %-8s %s\n" "#" "SERVICE" "TAG" "CREATED" "SIZE" "STATUS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    local index=1
    
    # Use jq to extract all needed data at once (much more reliable than regex)
    local packages=($(echo "$images_json" | jq -r '.[].package // empty'))
    local create_times=($(echo "$images_json" | jq -r '.[].createTime // empty'))
    local all_tags=($(echo "$images_json" | jq -r '.[] | (.tags // []) | join(",")'))
    local sizes=($(echo "$images_json" | jq -r '.[] | .metadata.imageSizeBytes // .metadata.sizeBytes // empty'))
    
    # Process each image
    for i in "${!packages[@]}"; do
        local package="${packages[$i]}"
        local create_time="${create_times[$i]:-}"
        local tags="${all_tags[$i]:-}"
        local size_bytes="${sizes[$i]:-}"
        
        # Convert comma-separated tags to space-separated
        tags=$(echo "$tags" | tr ',' ' ')
        
        if [[ -n "$package" ]]; then
            
            # Parse service name from package
            local service_name=""
            if [[ "$package" == *"agent-server"* ]]; then
                service_name="agent-server"
                if [[ "$package" == *"agent-server-"* ]]; then
                    service_name=$(echo "$package" | grep -o 'agent-server-[^/]*' | head -1)
                fi
            elif [[ "$package" == *"workroom"* ]]; then
                service_name="workroom" 
                if [[ "$package" == *"workroom-"* ]]; then
                    service_name=$(echo "$package" | grep -o 'workroom-[^/]*' | head -1)
                fi
            else
                service_name=$(basename "$package")
            fi
            
            # Format creation time
            local formatted_time=""
            if [[ -n "$create_time" ]]; then
                formatted_time=$(date -d "$create_time" "+%m/%d %H:%M" 2>/dev/null || echo "$(echo $create_time | cut -c6-10)")
            fi
            
            # Format size
            local formatted_size=""
            if [[ -n "$size_bytes" && "$size_bytes" != "0" ]]; then
                if command -v numfmt >/dev/null 2>&1; then
                    formatted_size=$(numfmt --to=iec --suffix=B "$size_bytes" 2>/dev/null || echo "${size_bytes}B")
                else
                    # Simple MB calculation fallback
                    local mb=$((size_bytes / 1024 / 1024))
                    formatted_size="${mb}MB"
                fi
            else
                formatted_size="<1MB"
            fi
            
            # Check deployment status
            local status="Available"
            local full_image_ref="${REGION}-docker.pkg.dev/${PROJECT_ID}/${repo}/${package}"
            
            # Check if this image is currently deployed (avoid unbound variable error)
            if [[ ${#deployed_images[@]} -gt 0 ]]; then
                for deployed in "${deployed_images[@]}"; do
                    if [[ "$deployed" == *"$package"* ]]; then
                        status="🟢 DEPLOYED"
                        break
                    fi
                done
            fi
            
            # Apply user scoping filter
            local should_show=true
            if [[ "$USER_SCOPE_ONLY" == "true" ]]; then
                if [[ "$service_name" != "$AGENT_SERVER_SERVICE" && "$service_name" != "$WORKROOM_SERVICE" ]]; then
                    should_show=false
                fi
            fi
            
            if [[ "$should_show" == "true" ]]; then
                printf "%-3s %-25s %-20s %-15s %-8s %s\n" \
                    "$index" \
                    "$(echo "$service_name" | cut -c1-24)" \
                    "$(echo "$tags" | cut -c1-19)" \
                    "$formatted_time" \
                    "$formatted_size" \
                    "$status"
                
                image_info+=("$package|$tags|$status|$full_image_ref")
                ((index++))
            fi
        fi
    done
    
    if [[ ${#image_info[@]} -eq 0 ]]; then
        echo "ℹ️  No $([ "$USER_SCOPE_ONLY" == "true" ] && echo "user-scoped " || echo "")images found"
        return 0
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Interactive selection
    if [[ "$FORCE" != "true" ]]; then
        echo "🎯 Image deletion options:"
        echo " 1) 🧹 Delete ALL non-deployed images (safe cleanup) ⭐"
        echo " 2) 🎯 Select specific images to delete"
        echo " 3) 🗑️  Delete only old images (keep latest and deployed)"
        echo " 4) 💥 Delete ALL images (including deployed - DANGEROUS!)"
        echo " 5) 📦 Delete entire repository (admin only)"
        echo " 0) ❌ Cancel"
        echo ""
        
        while true; do
            read -p "Select option (0-5): " choice
            case $choice in
                1)
                    delete_all_non_deployed_images "$repo" "${image_info[@]}"
                    removed_any=true
                    break
                    ;;
                2)
                    delete_selective_images "$repo" "${image_info[@]}"
                    removed_any=true
                    break
                    ;;
                3)
                    delete_old_images "$repo" "${image_info[@]}"
                    removed_any=true
                    break
                    ;;
                4)
                    delete_all_images_including_deployed "$repo" "${image_info[@]}"
                    removed_any=true
                    break
                    ;;
                5)
                    if [[ "$HAS_ADMIN_ACCESS" == "true" && "$USER_SCOPE_ONLY" != "true" ]]; then
                        delete_repository "$repo"
                        removed_any=true
                    else
                        echo "❌ Repository deletion requires admin access"
                    fi
                    break
                    ;;
                0)
                    echo "❌ Image deletion cancelled"
                    break
                    ;;
                *)
                    echo "❌ Invalid choice. Please enter 0-5"
                    ;;
            esac
        done
    else
        # Force mode - use safer default (non-deployed only)
        delete_all_non_deployed_images "$repo" "${image_info[@]}"
        removed_any=true
    fi
    
    if [[ "$removed_any" == "true" ]]; then
        echo "✅ Artifact Registry teardown complete"
    else
        echo "ℹ️  No Artifact Registry resources removed"
    fi
}

# Delete all non-deployed images (safe default)
delete_all_non_deployed_images() {
    local repo="$1"
    shift
    local images=("$@")
    
    # Filter out deployed images
    local non_deployed_images=()
    local deployed_count=0
    
    for image_info in "${images[@]}"; do
        local status=$(echo "$image_info" | cut -d'|' -f3)
        if [[ "$status" == "🟢 DEPLOYED" ]]; then
            ((deployed_count++))
        else
            non_deployed_images+=("$image_info")
        fi
    done
    
    if [[ ${#non_deployed_images[@]} -eq 0 ]]; then
        echo "ℹ️  No non-deployed images to delete"
        if [[ $deployed_count -gt 0 ]]; then
            echo "   $deployed_count deployed images were preserved"
        fi
        return 0
    fi
    
    local action_desc="Delete ALL non-deployed $([ "$USER_SCOPE_ONLY" == "true" ] && echo "your " || echo "")images"
    local detail_desc="This will delete ${#non_deployed_images[@]} images but preserve $deployed_count deployed images"
    
    if confirm_action "$action_desc" "$detail_desc"; then
        echo "🗑️  Deleting non-deployed images (preserving $deployed_count deployed)..."
        for image_info in "${non_deployed_images[@]}"; do
            local package=$(echo "$image_info" | cut -d'|' -f1)
            local full_ref=$(echo "$image_info" | cut -d'|' -f4)
            
            echo "  🗑️  Deleting $package"
            gcloud artifacts docker images delete "$full_ref" --delete-tags --quiet 2>/dev/null || echo "    (already deleted)"
        done
        
        log_teardown_operation "delete_all_non_deployed_images" "$(echo "${non_deployed_images[@]}" | tr ' ' ',')"
        echo "✅ Non-deployed images deleted (deployed images preserved)"
    fi
}

# Delete ALL images including deployed ones (dangerous)
delete_all_images_including_deployed() {
    local repo="$1"
    shift
    local images=("$@")
    
    # Count deployed images for warning
    local deployed_count=0
    for image_info in "${images[@]}"; do
        local status=$(echo "$image_info" | cut -d'|' -f3)
        if [[ "$status" == "🟢 DEPLOYED" ]]; then
            ((deployed_count++))
        fi
    done
    
    local action_desc="Delete ALL $([ "$USER_SCOPE_ONLY" == "true" ] && echo "your " || echo "")images INCLUDING DEPLOYED"
    local detail_desc="⚠️  DANGER: This will delete ALL ${#images[@]} images including $deployed_count currently deployed images. Running services may break!"
    
    if confirm_action "$action_desc" "$detail_desc"; then
        echo "💥 Deleting ALL images including deployed ones..."
        for image_info in "${images[@]}"; do
            local package=$(echo "$image_info" | cut -d'|' -f1)
            local status=$(echo "$image_info" | cut -d'|' -f3)
            local full_ref=$(echo "$image_info" | cut -d'|' -f4)
            
            echo "  🗑️  Deleting $package $([ "$status" == "🟢 DEPLOYED" ] && echo "(⚠️  DEPLOYED)" || echo "")"
            gcloud artifacts docker images delete "$full_ref" --delete-tags --quiet 2>/dev/null || echo "    (already deleted)"
        done
        
        log_teardown_operation "delete_all_images_including_deployed" "$(echo "${images[@]}" | tr ' ' ',')"
        echo "💥 ALL images deleted (including deployed ones)"
    fi
}

# Delete specific selected images
delete_selective_images() {
    local repo="$1"
    shift
    local images=("$@")
    
    echo ""
    echo "🎯 Select images to delete (space-separated numbers, e.g., '1 3 5'):"
    echo "   Enter image numbers from the list above"
    echo "   ⚠️  Deployed images will be marked - deleting them may break running services"
    echo ""
    
    while true; do
        read -p "Image numbers to delete (or 'cancel'): " selection
        
        if [[ "$selection" == "cancel" ]]; then
            echo "❌ Selective deletion cancelled"
            return 0
        fi
        
        # Validate selection
        local valid=true
        local selected_images=()
        
        for num in $selection; do
            if [[ "$num" =~ ^[0-9]+$ ]] && [[ "$num" -ge 1 ]] && [[ "$num" -le ${#images[@]} ]]; then
                local index=$((num - 1))
                selected_images+=("${images[$index]}")
            else
                echo "❌ Invalid number: $num (must be 1-${#images[@]})"
                valid=false
                break
            fi
        done
        
        if [[ "$valid" == "true" && ${#selected_images[@]} -gt 0 ]]; then
            echo ""
            echo "📋 Selected images for deletion:"
            for image_info in "${selected_images[@]}"; do
                local package=$(echo "$image_info" | cut -d'|' -f1)
                local status=$(echo "$image_info" | cut -d'|' -f3)
                echo "   🗑️  $package $([ "$status" == "🟢 DEPLOYED" ] && echo "(⚠️  CURRENTLY DEPLOYED)" || echo "")"
            done
            
            if confirm_action "Delete selected images" "Selected images will be permanently deleted"; then
                echo "🗑️  Deleting selected images..."
                for image_info in "${selected_images[@]}"; do
                    local package=$(echo "$image_info" | cut -d'|' -f1)
                    local full_ref=$(echo "$image_info" | cut -d'|' -f4)
                    
                    echo "  🗑️  Deleting $package..."
                    gcloud artifacts docker images delete "$full_ref" --delete-tags --quiet 2>/dev/null || echo "    (already deleted)"
                done
                
                log_teardown_operation "delete_selective_images" "$(echo "${selected_images[@]}" | tr ' ' ',')"
                echo "✅ Selected images deleted"
            fi
            break
        elif [[ ${#selected_images[@]} -eq 0 ]]; then
            echo "❌ No valid images selected"
        fi
    done
}

# Delete old images (keep latest and deployed)
delete_old_images() {
    local repo="$1"
    shift
    local images=("$@")
    
    echo "🧹 Identifying old images (keeping latest and deployed)..."
    
    local images_to_delete=()
    local images_to_keep=()
    
    # Group images by service
    declare -A service_images
    for image_info in "${images[@]}"; do
        local package=$(echo "$image_info" | cut -d'|' -f1)
        local status=$(echo "$image_info" | cut -d'|' -f3)
        
        # Extract service name
        local service=""
        if [[ "$package" == *"agent-server"* ]]; then
            if [[ "$package" == *"agent-server-"* ]]; then
                service=$(echo "$package" | grep -o 'agent-server-[^/]*')
            else
                service="agent-server"
            fi
        elif [[ "$package" == *"workroom"* ]]; then
            if [[ "$package" == *"workroom-"* ]]; then
                service=$(echo "$package" | grep -o 'workroom-[^/]*')
            else
                service="workroom"
            fi
        fi
        
        if [[ -n "$service" ]]; then
            if [[ -z "${service_images[$service]}" ]]; then
                service_images[$service]="$image_info"
            else
                service_images[$service]="${service_images[$service]}|$image_info"
            fi
        fi
    done
    
    # For each service, keep the latest and deployed, mark others for deletion
    for service in "${!service_images[@]}"; do
        local service_image_list="${service_images[$service]}"
        local service_images_array
        IFS='|' read -ra service_images_array <<< "$service_image_list"
        
        # Keep deployed images and the most recent one
        local kept_count=0
        for image_info in "${service_images_array[@]}"; do
            local status=$(echo "$image_info" | cut -d'|' -f3)
            if [[ "$status" == "🟢 DEPLOYED" ]]; then
                images_to_keep+=("$image_info")
                ((kept_count++))
            fi
        done
        
        # Keep one additional (latest) if no deployed images
        if [[ $kept_count -eq 0 && ${#service_images_array[@]} -gt 0 ]]; then
            images_to_keep+=("${service_images_array[0]}")
            ((kept_count++))
        fi
        
        # Mark the rest for deletion
        local skipped=0
        for image_info in "${service_images_array[@]}"; do
            local status=$(echo "$image_info" | cut -d'|' -f3)
            if [[ "$status" != "🟢 DEPLOYED" ]]; then
                if [[ $skipped -lt 1 ]]; then
                    ((skipped++))  # Skip the first (latest) non-deployed
                else
                    images_to_delete+=("$image_info")
                fi
            fi
        done
    done
    
    if [[ ${#images_to_delete[@]} -eq 0 ]]; then
        echo "ℹ️  No old images found to delete (all images are either latest or deployed)"
        return 0
    fi
    
    echo ""
    echo "📋 Old images to delete:"
    for image_info in "${images_to_delete[@]}"; do
        local package=$(echo "$image_info" | cut -d'|' -f1)
        echo "   🗑️  $package"
    done
    
    echo ""
    echo "✅ Images to keep:"
    for image_info in "${images_to_keep[@]}"; do
        local package=$(echo "$image_info" | cut -d'|' -f1)
        local status=$(echo "$image_info" | cut -d'|' -f3)
        echo "   📦 $package $([ "$status" == "🟢 DEPLOYED" ] && echo "(deployed)" || echo "(latest)")"
    done
    
    if confirm_action "Delete old images" "Keep latest and deployed images, delete older ones"; then
        echo "🗑️  Deleting old images..."
        for image_info in "${images_to_delete[@]}"; do
            local package=$(echo "$image_info" | cut -d'|' -f1)
            local full_ref=$(echo "$image_info" | cut -d'|' -f4)
            
            echo "  🗑️  Deleting $package..."
            gcloud artifacts docker images delete "$full_ref" --delete-tags --quiet 2>/dev/null || echo "    (already deleted)"
        done
        
        log_teardown_operation "delete_old_images" "$(echo "${images_to_delete[@]}" | tr ' ' ',')"
        echo "✅ Old images deleted"
    fi
}

# Delete entire repository
delete_repository() {
    local repo="$1"
    
    if confirm_action "Remove Artifact Registry repository: $repo" "The entire Docker repository will be deleted - affects ALL users"; then
        echo "🗑️  Deleting repository..."
        gcloud artifacts repositories delete "$repo" --location="$REGION" --quiet
        echo "✅ Repository deleted"
        log_teardown_operation "delete_artifact_repository" "$repo"
    fi
}

# Clean old Cloud Run revisions and their corresponding Docker images
teardown_revisions() {
    echo "🔄 Cleaning old Cloud Run revisions and their images..."
    
    local services=()
    local removed_any=false
    
    if [[ "$USER_SCOPE_ONLY" == "true" ]]; then
        services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
        echo "🎯 Targeting your user-scoped services only"
    else
        # Get all agent-platform services
        local all_services
        all_services=$(gcloud run services list --region="$REGION" --format="value(metadata.name)" --quiet 2>/dev/null || echo "")
        
        while IFS= read -r service; do
            if [[ -n "$service" && ("$service" == "agent-server"* || "$service" == "workroom"*) ]]; then
                services+=("$service")
            fi
        done <<< "$all_services"
    fi
    
    if [[ ${#services[@]} -eq 0 ]]; then
        echo "ℹ️  No agent-platform services found"
        return 0
    fi
    
    local images_to_delete=()
    
    for service in "${services[@]}"; do
        if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
            echo "ℹ️  $service not found (not deployed)"
            continue
        fi
        
        echo ""
        echo "🔍 Checking revisions for $service..."
        
        # Get all revisions for this service, sorted by creation time (newest first)
        local revisions_json
        revisions_json=$(gcloud run revisions list --service="$service" --region="$REGION" \
            --format="json" --sort-by="~metadata.creationTimestamp" --quiet 2>/dev/null || echo "[]")
        
        if [[ "$revisions_json" == "[]" || -z "$revisions_json" ]]; then
            echo "   ℹ️  No revisions found for $service"
            continue
        fi
        
        # Parse revision data
        local revision_names=($(echo "$revisions_json" | jq -r '.[].metadata.name'))
        local revision_images=($(echo "$revisions_json" | jq -r '.[].spec.template.spec.template.spec.containers[0].image'))
        local revision_times=($(echo "$revisions_json" | jq -r '.[].metadata.creationTimestamp'))
        
        echo "   📋 Found ${#revision_names[@]} revisions for $service"
        
        if [[ ${#revision_names[@]} -le 2 ]]; then
            echo "   ✅ Only ${#revision_names[@]} revisions - keeping all (2 or fewer)"
            continue
        fi
        
        # Keep latest 2, delete the rest
        local revisions_to_delete=("${revision_names[@]:2}")  # Skip first 2 (latest)
        local images_to_delete_for_service=("${revision_images[@]:2}")  # Skip first 2 images
        
        echo "   🔄 Keeping latest 2 revisions, removing ${#revisions_to_delete[@]} old ones"
        echo "   ✅ Keeping: ${revision_names[0]}, ${revision_names[1]}"
        
        # Add images to deletion list
        for image in "${images_to_delete_for_service[@]}"; do
            # Extract just the image reference part after the last /
            local image_ref=$(basename "$image")
            if [[ -n "$image_ref" && "$image_ref" != "null" ]]; then
                images_to_delete+=("$image")
            fi
        done
        
        # Delete old revisions
        if [[ ${#revisions_to_delete[@]} -gt 0 ]]; then
            if confirm_action "Delete ${#revisions_to_delete[@]} old revisions for $service" "Keeps latest 2 revisions, removes older deployment history"; then
                echo "   🗑️  Deleting old revisions..."
                for revision in "${revisions_to_delete[@]}"; do
                    echo "     🗑️  Deleting revision: $revision"
                    gcloud run revisions delete "$revision" --region="$REGION" --quiet 2>/dev/null || echo "     (already deleted)"
                done
                removed_any=true
                log_teardown_operation "delete_revisions" "$service:${#revisions_to_delete[@]}"
            fi
        fi
    done
    
    # Now delete the corresponding Docker images
    if [[ ${#images_to_delete[@]} -gt 0 ]]; then
        echo ""
        echo "🗑️  Cleaning up ${#images_to_delete[@]} Docker images from deleted revisions..."
        
        # Remove duplicates
        local unique_images=($(printf "%s\n" "${images_to_delete[@]}" | sort -u))
        
        if confirm_action "Delete ${#unique_images[@]} Docker images from deleted revisions" "These images are no longer referenced by any revision"; then
            for image in "${unique_images[@]}"; do
                echo "   🗑️  Deleting image: $(basename "$image")"
                gcloud artifacts docker images delete "$image" --delete-tags --quiet 2>/dev/null || echo "     (already deleted or not found)"
            done
            removed_any=true
            log_teardown_operation "delete_revision_images" "$(echo "${unique_images[@]}" | tr ' ' ',')"
        fi
    fi
    
    if [[ "$removed_any" == "true" ]]; then
        echo ""
        echo "✅ Revision cleanup complete!"
        echo "💾 Kept latest 2 revisions per service"
        echo "🗑️  Removed old revisions and their unused images"
    else
        echo ""
        echo "ℹ️  No revisions or images to clean up"
    fi
}

teardown_secrets() {
    # Check admin permissions for secret operations
    if [[ "$HAS_ADMIN_ACCESS" != "true" ]]; then
        log_error "❌ Secrets teardown requires admin access (Owner/Editor role)"
        echo "   Your role: $USER_ROLE"
        echo "   Required roles: Owner or Editor"
        echo "   Reason: Secrets are shared across all users"
        return 1
    fi
    
    echo "🗑️  Checking secrets..."
    
    if gcloud secrets describe npmrc-secret --quiet >/dev/null 2>&1; then
        if confirm_action "Remove secret: npmrc-secret" "You'll need to recreate this for future deployments - affects ALL users"; then
            echo "🗑️  Deleting secret..."
            gcloud secrets delete npmrc-secret --quiet
            echo "✅ Secret deleted"
            log_teardown_operation "delete_secret" "npmrc-secret"
        fi
    else
        echo "ℹ️  npmrc-secret not found"
    fi
}

# Validate permissions before operations
validate_operation_permissions() {
    local errors=()
    
    # Database operations: developers can delete personal databases, admins can delete all
    # (No error for developers - they can delete personal databases)
    
    # Check secrets operations  
    if [[ "$TEARDOWN_SECRETS" == "true" && "$HAS_ADMIN_ACCESS" != "true" ]]; then
        errors+=("Secrets teardown requires admin access")
    fi
    
    # Force user scope for non-admins
    if [[ "$HAS_ADMIN_ACCESS" != "true" ]]; then
        USER_SCOPE_ONLY=true
    fi
    
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo ""
        log_error "❌ Permission validation failed:"
        for error in "${errors[@]}"; do
            echo "   • $error"
        done
        echo ""
        echo "💡 Available options for your role ($USER_ROLE):"
        echo "   • Remove your Cloud Run services: --services --user-scope-only"
        echo "   • Remove your personal database: --database"
        echo "   • Remove your Artifact Registry images: --images --user-scope-only"
        echo ""
        echo "🔑 For shared database/secrets operations, contact an admin with Owner/Editor role"
        exit 1
    fi
}

main() {
    parse_args "$@"
    
    # Check user role and permissions first
    check_user_role
    
    # If no teardown options specified, show interactive menu
    if [[ "$TEARDOWN_ALL" == "false" && "$TEARDOWN_SERVICES" == "false" && "$TEARDOWN_DATABASE" == "false" && "$TEARDOWN_IMAGES" == "false" && "$TEARDOWN_SECRETS" == "false" ]]; then
        show_teardown_menu
    else
        echo "🗑️  Agent Platform GCP Teardown"
        echo "📍 Project: $PROJECT_ID"
        echo "🌍 Region: $REGION"
        echo "👤 User: $CURRENT_USER_EMAIL ($USER_ROLE)"
        echo ""
    fi
    
    check_prerequisites_lite
    
    # Validate permissions for requested operations
    validate_operation_permissions
    
    # Show summary of what will be removed
    if [[ "$FORCE" == "false" ]]; then
        echo "📋 Teardown Summary:"
        echo "👤 User: $CURRENT_USER_EMAIL ($USER_ROLE)"
        echo "🎯 Scope: $([ "$USER_SCOPE_ONLY" == "true" ] && echo "User resources only" || echo "All project resources")"
        [[ "$TEARDOWN_SERVICES" == "true" ]] && echo "  • Cloud Run services $([ "$USER_SCOPE_ONLY" == "true" ] && echo "(your services only)" || echo "(all users)")"
        [[ "$TEARDOWN_DATABASE" == "true" ]] && echo "  • Cloud SQL database $([ "$HAS_ADMIN_ACCESS" == "true" ] && echo "(all databases - admin)" || echo "(personal database only - developer)")"
        [[ "$TEARDOWN_IMAGES" == "true" ]] && echo "  • Artifact Registry images $([ "$USER_SCOPE_ONLY" == "true" ] && echo "(your images only)" || echo "(all users)")"
        [[ "$TEARDOWN_REVISIONS" == "true" ]] && echo "  • Old Cloud Run revisions + their images (keeps latest 2)"
        [[ "$TEARDOWN_SECRETS" == "true" ]] && echo "  • Secrets (shared resource - admin only)"
        echo ""
    fi
    
    # Log the start of teardown operation
    local operations=()
    [[ "$TEARDOWN_SERVICES" == "true" ]] && operations+=("services")
    [[ "$TEARDOWN_DATABASE" == "true" ]] && operations+=("database")
    [[ "$TEARDOWN_IMAGES" == "true" ]] && operations+=("images")
    [[ "$TEARDOWN_REVISIONS" == "true" ]] && operations+=("revisions")
    [[ "$TEARDOWN_SECRETS" == "true" ]] && operations+=("secrets")
    
    log_teardown_operation "teardown_start" "$(IFS=','; echo "${operations[*]}")"
    
    # Execute teardown operations
    if [[ "$TEARDOWN_SERVICES" == "true" ]]; then
        teardown_services
        echo ""
    fi
    
    if [[ "$TEARDOWN_IMAGES" == "true" ]]; then
        teardown_images
        echo ""
    fi
    
    if [[ "$TEARDOWN_REVISIONS" == "true" ]]; then
        teardown_revisions
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
    
    # Final status and audit log
    echo "🎉 Teardown complete!"
    echo ""
    echo "💰 Cost Impact:"
    [[ "$TEARDOWN_SERVICES" == "true" ]] && echo "  • Cloud Run: ~\$0.40/month saved $([ "$USER_SCOPE_ONLY" == "true" ] && echo "(your services)" || echo "(all services)")"
    [[ "$TEARDOWN_DATABASE" == "true" ]] && echo "  • Cloud SQL: ~\$7-15/month saved"
    [[ "$TEARDOWN_IMAGES" == "true" ]] && echo "  • Storage: ~\$0.10/GB/month saved"
    [[ "$TEARDOWN_REVISIONS" == "true" ]] && echo "  • Old revisions/images: Variable savings (depends on cleanup volume)"
    echo ""
    echo "🔄 To redeploy: make gcp deploy"
    echo ""
    echo "📝 Audit: All operations logged to Cloud Logging (agent-platform-teardown)"
    
    # Final audit log
    log_teardown_operation "teardown_complete" "$(IFS=','; echo "${operations[*]}")"
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 