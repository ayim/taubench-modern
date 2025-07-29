#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Get current admin user
CURRENT_USER_EMAIL=$(gcloud config get-value account 2>/dev/null)

if [[ -z "$CURRENT_USER_EMAIL" ]]; then
    echo "❌ Unable to get authenticated user. Please run 'gcloud auth login' first."
    exit 1
fi

show_help() {
    cat << EOF
🔐 Admin IAP Control - Agent Platform

Control IAP across ALL instances in the project (admin-only).
This script allows project administrators to manage IAP settings
for all services: personal instances, shared instances, and demos.

USAGE:
    $0 [ACTION] [OPTIONS]

ACTIONS:
    list-all                      Show IAP status for all services
    list-users [SERVICE]          Show users with access to service(s)
    enable [SERVICE]              Enable IAP on service(s)
    disable [SERVICE]             Disable IAP on service(s)
    add-user EMAIL [SERVICE]      Add user to service(s)
    remove-user EMAIL [SERVICE]   Remove user from service(s)
    policy-reset [SERVICE]        Reset IAP policy (remove all users)
    bulk-enable                   Enable IAP on all services
    bulk-disable                  Disable IAP on all services

SERVICE OPTIONS:
    agent-server                  All agent-server instances
    workroom                      All workroom instances  
    shared                        Shared instances only (agent-server, workroom)
    personal                      All personal instances
    USER                          Specific user's instances (e.g., perry)
    SERVICE_NAME                  Specific service name

SECURITY OPTIONS:
    --force                       Skip confirmation prompts
    --dry-run                     Show what would be done without executing

EXAMPLES:
    # List all services and their IAP status
    $0 list-all
    
    # Show who has access to all workroom instances  
    $0 list-users workroom
    
    # Enable IAP on all shared services
    $0 enable shared
    
    # Add admin to a specific user's instances
    $0 add-user admin@company.com perry
    
    # Disable IAP on all personal workroom instances
    $0 disable workroom
    
    # Reset IAP policy for a specific service
    $0 policy-reset workroom-perry
    
    # Bulk operations (all services)
    $0 bulk-enable                # Enable IAP everywhere
    $0 bulk-disable --force       # Disable IAP everywhere (no prompts)

ADMIN PRIVILEGES:
    👤 Admin: $CURRENT_USER_EMAIL
    🔧 You can control ALL instances in project: $PROJECT_ID
    
    ⚠️  Use with caution: Changes affect all users' access
    
    Personal IAP management: scripts/gcp/manage-my-iap.sh (for users)
EOF
}

# Check admin permissions
check_admin_permissions() {
    local has_admin=false
    
    # Check if user has Owner or Editor role
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/owner OR bindings.role:roles/editor" 2>/dev/null | grep -q "user:$CURRENT_USER_EMAIL"; then
        has_admin=true
    fi
    
    if [[ "$has_admin" == "false" ]]; then
        echo "❌ Admin access required (Owner or Editor role)"
        echo "👤 Current user: $CURRENT_USER_EMAIL"
        echo "🔧 Contact project admin to grant access"
        exit 1
    fi
}

# Get all Cloud Run services in the project
get_all_services() {
    gcloud run services list \
        --region="$REGION" \
        --format="value(metadata.name)" \
        --quiet 2>/dev/null | grep -E "(agent-server|workroom)" || echo ""
}

# Filter services based on criteria
filter_services() {
    local filter="$1"
    local all_services
    all_services=$(get_all_services)
    
    case "$filter" in
        "agent-server")
            echo "$all_services" | grep "agent-server" || echo ""
            ;;
        "workroom")
            echo "$all_services" | grep "workroom" || echo ""
            ;;
        "shared")
            echo "$all_services" | grep -E "^(agent-server|workroom)$" || echo ""
            ;;
        "personal")
            echo "$all_services" | grep -E "(agent-server-.+|workroom-.+)" || echo ""
            ;;
        "all")
            echo "$all_services"
            ;;
        *)
            # Check if it's a specific user or service name
            if echo "$all_services" | grep -q "$filter"; then
                echo "$all_services" | grep "$filter"
            else
                # Check if it's a user prefix
                echo "$all_services" | grep -E "(agent-server-$filter|workroom-$filter)" || echo ""
            fi
            ;;
    esac
}

# Show IAP status for all services
list_all_services() {
    echo "🔐 IAP Status - All Services (Admin View)"
    echo "=========================================="
    echo "👤 Admin: $CURRENT_USER_EMAIL"
    echo "📍 Project: $PROJECT_ID"
    echo ""
    
    local all_services
    all_services=$(get_all_services)
    
    if [[ -z "$all_services" ]]; then
        echo "📭 No agent platform services found in project"
        echo "💡 Deploy some instances first: make gcp deploy"
        return 0
    fi
    
    # Group services by type
    local shared_services
    local personal_services
    shared_services=$(echo "$all_services" | grep -E "^(agent-server|workroom)$" || echo "")
    personal_services=$(echo "$all_services" | grep -E "(agent-server-.+|workroom-.+)" || echo "")
    
    if [[ -n "$shared_services" ]]; then
        echo "🌐 Shared/Demo Services:"
        echo "$shared_services" | while IFS= read -r service; do
            if [[ -n "$service" ]]; then
                show_service_status "$service" "    "
            fi
        done
        echo ""
    fi
    
    if [[ -n "$personal_services" ]]; then
        echo "👤 Personal Services:"
        echo "$personal_services" | while IFS= read -r service; do
            if [[ -n "$service" ]]; then
                show_service_status "$service" "    "
            fi
        done
    fi
    
    echo ""
    echo "💡 Manage specific services: $0 enable/disable [SERVICE]"
    echo "👥 Manage users: $0 add-user/remove-user EMAIL [SERVICE]"
}

# Show status for a single service
show_service_status() {
    local service="$1"
    local indent="${2:-}"
    
    # Get IAP status
    local iap_status
    iap_status=$(gcloud beta run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
        --quiet 2>/dev/null || echo "unknown")
    
    # Get ingress
    local ingress
    ingress=$(gcloud run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.annotations['run.googleapis.com/ingress'])" \
        --quiet 2>/dev/null || echo "unknown")
    
    # Show service info
    local iap_icon=""
    local ingress_icon=""
    
    case "$iap_status" in
        "true") iap_icon="🔐" ;;
        "false"|"") iap_icon="🔓" ;;
        *) iap_icon="⚠️" ;;
    esac
    
    case "$ingress" in
        "all") ingress_icon="🌐" ;;
        "internal") ingress_icon="🏠" ;;
        *) ingress_icon="❓" ;;
    esac
    
    echo "${indent}${iap_icon} ${ingress_icon} ${service}"
}

# List users with access to services
list_users() {
    local filter="${1:-all}"
    
    echo "👥 IAP Access - Users by Service"
    echo "================================="
    echo "👤 Admin: $CURRENT_USER_EMAIL"
    echo ""
    
    local services
    services=$(filter_services "$filter")
    
    if [[ -z "$services" ]]; then
        echo "📭 No services match filter: $filter"
        return 0
    fi
    
    echo "$services" | while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            echo "📋 $service:"
            
            # Get IAP access list
            local members_output
            members_output=$(gcloud beta iap web get-iam-policy \
                --region="$REGION" \
                --resource-type=cloud-run \
                --service="$service" \
                --format="value(bindings[].members[].flatten())" \
                --filter="bindings.role:roles/iap.httpsResourceAccessor" \
                --quiet 2>/dev/null || echo "")
            
            if [[ -z "$members_output" ]]; then
                echo "   📭 No users have access (IAP may be disabled)"
            else
                echo "$members_output" | while IFS= read -r member; do
                    if [[ -n "$member" ]]; then
                        case "$member" in
                            user:*) echo "   👤 $(echo "$member" | cut -d':' -f2)" ;;
                            group:*) echo "   👥 $(echo "$member" | cut -d':' -f2) (group)" ;;
                            domain:*) echo "   🏢 @$(echo "$member" | cut -d':' -f2) (domain)" ;;
                            *) echo "   ❓ $member" ;;
                        esac
                    fi
                done
            fi
            echo ""
        fi
    done
}

# Enable IAP on services
enable_iap() {
    local filter="${1:-all}"
    local force="${2:-false}"
    
    local services
    services=$(filter_services "$filter")
    
    if [[ -z "$services" ]]; then
        echo "❌ No services match filter: $filter"
        return 1
    fi
    
    local service_count
    service_count=$(echo "$services" | wc -l)
    
    echo "🔐 Enabling IAP on $service_count service(s)..."
    echo ""
    echo "Services:"
    echo "$services" | sed 's/^/  • /'
    echo ""
    
    if [[ "$force" != "true" ]]; then
        read -p "Continue? [y/N]: " confirm
        if [[ ! $confirm =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled"
            return 0
        fi
    fi
    
    # Enable IAP API first
    echo "🔧 Ensuring IAP API is enabled..."
    gcloud services enable iap.googleapis.com --quiet
    
    local success_count=0
    
    echo "$services" | while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            echo "🔧 Enabling IAP on $service..."
            
            if gcloud beta run services update "$service" \
                --region="$REGION" \
                --iap \
                --quiet 2>/dev/null; then
                echo "✅ IAP enabled on $service"
                ((success_count++))
                
                # Grant access to admin
                echo "👤 Granting admin access..."
                gcloud beta iap web add-iam-policy-binding \
                    --member="user:$CURRENT_USER_EMAIL" \
                    --role=roles/iap.httpsResourceAccessor \
                    --region="$REGION" \
                    --resource-type=cloud-run \
                    --service="$service" \
                    --quiet 2>/dev/null || true
            else
                echo "⚠️  Failed to enable IAP on $service"
            fi
        fi
    done
    
    echo ""
    echo "🎉 IAP enabled on services!"
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
    echo "👤 Admin access granted to: $CURRENT_USER_EMAIL"
}

# Disable IAP on services
disable_iap() {
    local filter="${1:-all}"
    local force="${2:-false}"
    
    local services
    services=$(filter_services "$filter")
    
    if [[ -z "$services" ]]; then
        echo "❌ No services match filter: $filter"
        return 1
    fi
    
    local service_count
    service_count=$(echo "$services" | wc -l)
    
    echo "⚠️  WARNING: Disabling IAP on $service_count service(s)!"
    echo "🌐 These services will become publicly accessible without authentication"
    echo ""
    echo "Services:"
    echo "$services" | sed 's/^/  • /'
    echo ""
    
    if [[ "$force" != "true" ]]; then
        read -p "Are you sure you want to continue? [y/N]: " confirm
        if [[ ! $confirm =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled"
            return 0
        fi
    fi
    
    local success_count=0
    
    echo "$services" | while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            echo "🔧 Disabling IAP on $service..."
            
            if gcloud beta run services update "$service" \
                --region="$REGION" \
                --no-iap \
                --allow-unauthenticated \
                --quiet 2>/dev/null; then
                echo "✅ IAP disabled on $service (now public)"
                ((success_count++))
            else
                echo "⚠️  Failed to disable IAP on $service"
            fi
        fi
    done
    
    echo ""
    echo "⚠️  IAP disabled - services are now publicly accessible"
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
}

# Add user to services
add_user() {
    local email="$1"
    local filter="${2:-all}"
    
    local services
    services=$(filter_services "$filter")
    
    if [[ -z "$services" ]]; then
        echo "❌ No services match filter: $filter"
        return 1
    fi
    
    echo "👤 Adding user '$email' to services..."
    echo ""
    echo "Services:"
    echo "$services" | sed 's/^/  • /'
    echo ""
    
    local success_count=0
    
    echo "$services" | while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            echo "🔧 Adding access to $service..."
            
            if gcloud beta iap web add-iam-policy-binding \
                --member="user:$email" \
                --role=roles/iap.httpsResourceAccessor \
                --region="$REGION" \
                --resource-type=cloud-run \
                --service="$service" \
                --quiet 2>/dev/null; then
                echo "✅ Access granted to $service"
                ((success_count++))
            else
                echo "⚠️  Failed to grant access to $service (may already exist)"
            fi
        fi
    done
    
    echo ""
    echo "🎉 User access granted!"
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
}

# Remove user from services
remove_user() {
    local email="$1"
    local filter="${2:-all}"
    
    # Prevent admin from removing themselves from shared services
    if [[ "$email" == "$CURRENT_USER_EMAIL" && ("$filter" == "shared" || "$filter" == "all") ]]; then
        echo "⚠️  WARNING: You are removing yourself from services!"
        echo "👤 This may prevent you from accessing shared services"
        read -p "Continue anyway? [y/N]: " confirm
        if [[ ! $confirm =~ ^[Yy]$ ]]; then
            echo "❌ Cancelled"
            return 0
        fi
    fi
    
    local services
    services=$(filter_services "$filter")
    
    if [[ -z "$services" ]]; then
        echo "❌ No services match filter: $filter"
        return 1
    fi
    
    echo "👤 Removing user '$email' from services..."
    echo ""
    echo "Services:"
    echo "$services" | sed 's/^/  • /'
    echo ""
    
    local success_count=0
    
    echo "$services" | while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            echo "🔧 Removing access from $service..."
            
            if gcloud beta iap web remove-iam-policy-binding \
                --member="user:$email" \
                --role=roles/iap.httpsResourceAccessor \
                --region="$REGION" \
                --resource-type=cloud-run \
                --service="$service" \
                --quiet 2>/dev/null; then
                echo "✅ Access removed from $service"
                ((success_count++))
            else
                echo "⚠️  Failed to remove access from $service (may not exist)"
            fi
        fi
    done
    
    echo ""
    echo "🎉 User access removed!"
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
}

# Reset IAP policy (remove all users)
policy_reset() {
    local filter="${1:-all}"
    
    local services
    services=$(filter_services "$filter")
    
    if [[ -z "$services" ]]; then
        echo "❌ No services match filter: $filter"
        return 1
    fi
    
    local service_count
    service_count=$(echo "$services" | wc -l)
    
    echo "⚠️  WARNING: Resetting IAP policy on $service_count service(s)!"
    echo "👥 This will remove ALL users from these services"
    echo "🔐 Services will have IAP enabled but no users with access"
    echo ""
    echo "Services:"
    echo "$services" | sed 's/^/  • /'
    echo ""
    
    read -p "Are you sure you want to continue? [y/N]: " confirm
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        return 0
    fi
    
    local success_count=0
    
    echo "$services" | while IFS= read -r service; do
        if [[ -n "$service" ]]; then
            echo "🔧 Resetting policy for $service..."
            
            # Get current policy and clear it
            if gcloud beta iap web set-iam-policy "$service" /dev/stdin \
                --region="$REGION" \
                --resource-type=cloud-run \
                --quiet 2>/dev/null << EOF
{
  "bindings": []
}
EOF
            then
                echo "✅ Policy reset for $service"
                ((success_count++))
                
                # Re-add admin access
                echo "👤 Re-adding admin access..."
                gcloud beta iap web add-iam-policy-binding \
                    --member="user:$CURRENT_USER_EMAIL" \
                    --role=roles/iap.httpsResourceAccessor \
                    --region="$REGION" \
                    --resource-type=cloud-run \
                    --service="$service" \
                    --quiet 2>/dev/null || true
            else
                echo "⚠️  Failed to reset policy for $service"
            fi
        fi
    done
    
    echo ""
    echo "🎉 IAP policies reset!"
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
    echo "👤 Admin access restored to: $CURRENT_USER_EMAIL"
}

# Parse command line arguments
main() {
    check_admin_permissions
    
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi
    
    local action="$1"
    shift
    
    # Parse options
    local force=false
    local dry_run=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                force=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                break
                ;;
        esac
    done
    
    case "$action" in
        "list-all")
            list_all_services
            ;;
        "list-users")
            list_users "${1:-all}"
            ;;
        "enable")
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would enable IAP on services matching: ${1:-all}"
                filter_services "${1:-all}" | sed 's/^/  • /'
            else
                enable_iap "${1:-all}" "$force"
            fi
            ;;
        "disable")
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would disable IAP on services matching: ${1:-all}"
                filter_services "${1:-all}" | sed 's/^/  • /'
            else
                disable_iap "${1:-all}" "$force"
            fi
            ;;
        "add-user")
            if [[ $# -eq 0 ]]; then
                echo "❌ Missing email. Usage: $0 add-user user@company.com [SERVICE]"
                exit 1
            fi
            local email="$1"
            shift
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would add user '$email' to services matching: ${1:-all}"
                filter_services "${1:-all}" | sed 's/^/  • /'
            else
                add_user "$email" "${1:-all}"
            fi
            ;;
        "remove-user")
            if [[ $# -eq 0 ]]; then
                echo "❌ Missing email. Usage: $0 remove-user user@company.com [SERVICE]"
                exit 1
            fi
            local email="$1"
            shift
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would remove user '$email' from services matching: ${1:-all}"
                filter_services "${1:-all}" | sed 's/^/  • /'
            else
                remove_user "$email" "${1:-all}"
            fi
            ;;
        "policy-reset")
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would reset IAP policy on services matching: ${1:-all}"
                filter_services "${1:-all}" | sed 's/^/  • /'
            else
                policy_reset "${1:-all}"
            fi
            ;;
        "bulk-enable")
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would enable IAP on ALL services"
                get_all_services | sed 's/^/  • /'
            else
                enable_iap "all" "$force"
            fi
            ;;
        "bulk-disable")
            if [[ "$dry_run" == "true" ]]; then
                echo "🔍 DRY RUN: Would disable IAP on ALL services"
                get_all_services | sed 's/^/  • /'
            else
                disable_iap "all" "$force"
            fi
            ;;
        "-h"|"--help"|"help")
            show_help
            ;;
        *)
            echo "❌ Unknown action: $action"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 