#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Get current user
CURRENT_USER_EMAIL=$(gcloud config get-value account 2>/dev/null)
CURRENT_USER=$(echo "$CURRENT_USER_EMAIL" | cut -d'@' -f1 | tr '.' '-')

if [[ -z "$CURRENT_USER_EMAIL" ]]; then
    echo "❌ Unable to get authenticated user. Please run 'gcloud auth login' first."
    exit 1
fi

# Personal service names
AGENT_SERVER_SERVICE="agent-server-${CURRENT_USER}"
WORKROOM_SERVICE="workroom-${CURRENT_USER}"

# Check if user has admin permissions
check_admin_permissions() {
    local has_admin=false
    
    # Check if user has Owner or Editor role
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/owner OR bindings.role:roles/editor" 2>/dev/null | grep -q "user:$CURRENT_USER_EMAIL"; then
        has_admin=true
    fi
    
    echo "$has_admin"
}

# Get and display users with access to a service
show_service_users() {
    local service="$1"
    local indent="$2"
    
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
        echo "${indent}     📭 No users configured"
    else
        local user_count=0
        local domain_count=0
        local group_count=0
        
        while IFS= read -r member; do
            if [[ -n "$member" ]]; then
                case "$member" in
                    user:*) 
                        if [[ $user_count -eq 0 ]]; then
                            echo "${indent}     👤 $(echo "$member" | cut -d':' -f2)"
                        fi
                        ((user_count++))
                        ;;
                    group:*) 
                        echo "${indent}     👥 $(echo "$member" | cut -d':' -f2) (group)"
                        ((group_count++))
                        ;;
                    domain:*) 
                        echo "${indent}     🏢 @$(echo "$member" | cut -d':' -f2) (domain-wide)"
                        ((domain_count++))
                        ;;
                esac
            fi
        done <<< "$members_output"
        
        # Show summary if there are multiple users
        if [[ $user_count -gt 1 ]]; then
            echo "${indent}     👥 ... and $((user_count - 1)) more user(s)"
        fi
    fi
}

# Show current IAP status summary with users
show_iap_status_summary() {
    echo "🔐 IAP Status & Access Summary"
    echo "============================="
    echo "👤 User: $CURRENT_USER_EMAIL"
    echo "📍 Project: $PROJECT_ID"
    echo ""
    
    # Check personal services
    local personal_services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
    local personal_found=false
    
    for service in "${personal_services[@]}"; do
        if gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
            if [[ "$personal_found" == "false" ]]; then
                echo "👤 Your Personal Instances:"
                personal_found=true
            fi
            
            local iap_status
            iap_status=$(gcloud beta run services describe "$service" \
                --region="$REGION" \
                --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
                --quiet 2>/dev/null || echo "unknown")
            
            local icon="❓"
            local status_text="Unknown"
            case "$iap_status" in
                "true") 
                    icon="🔐"
                    status_text="Protected"
                    echo "   $icon $service: $status_text"
                    show_service_users "$service" "   "
                    ;;
                "false"|"") 
                    icon="🌐"
                    status_text="Public (no auth required)"
                    echo "   $icon $service: $status_text"
                    ;;
            esac
            echo ""
        fi
    done
    
    if [[ "$personal_found" == "false" ]]; then
        echo "👤 Your Personal Instances: Not deployed"
        echo "   💡 Deploy first: make gcp deploy --personal-isolated"
        echo ""
    fi
    
    # Check shared services (if admin)
    local has_admin=$(check_admin_permissions)
    if [[ "$has_admin" == "true" ]]; then
        local shared_services=("agent-server" "workroom")
        local shared_found=false
        
        for service in "${shared_services[@]}"; do
            if gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
                if [[ "$shared_found" == "false" ]]; then
                    echo "🌐 Shared/Demo Instances:"
                    shared_found=true
                fi
                
                local iap_status
                iap_status=$(gcloud beta run services describe "$service" \
                    --region="$REGION" \
                    --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
                    --quiet 2>/dev/null || echo "unknown")
                
                local icon="❓"
                local status_text="Unknown"
                case "$iap_status" in
                    "true") 
                        icon="🔐"
                        status_text="Protected"
                        echo "   $icon $service: $status_text"
                        show_service_users "$service" "   "
                        ;;
                    "false"|"") 
                        icon="🌐"
                        status_text="Public (no auth required)"
                        echo "   $icon $service: $status_text"
                        ;;
                esac
                echo ""
            fi
        done
        
        if [[ "$shared_found" == "false" ]]; then
            echo "🌐 Shared/Demo Instances: Not deployed"
            echo "   💡 Deploy first: make gcp deploy --team-production"
            echo ""
        fi
    fi
    
    # Summary of access patterns
    echo "🔍 Access Summary:"
    local has_domain_access=false
    local has_individual_access=false
    local total_protected_services=0
    
    # Check all services for access patterns
    local all_services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
    local has_admin=$(check_admin_permissions)
    if [[ "$has_admin" == "true" ]]; then
        all_services+=("agent-server" "workroom")
    fi
    
    for service in "${all_services[@]}"; do
        if gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
            local iap_status
            iap_status=$(gcloud beta run services describe "$service" \
                --region="$REGION" \
                --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
                --quiet 2>/dev/null || echo "unknown")
            
            if [[ "$iap_status" == "true" ]]; then
                ((total_protected_services++))
                
                # Check for domain vs individual access
                local members_output
                members_output=$(gcloud beta iap web get-iam-policy \
                    --region="$REGION" \
                    --resource-type=cloud-run \
                    --service="$service" \
                    --format="value(bindings[].members[].flatten())" \
                    --filter="bindings.role:roles/iap.httpsResourceAccessor" \
                    --quiet 2>/dev/null || echo "")
                
                if echo "$members_output" | grep -q "domain:"; then
                    has_domain_access=true
                fi
                if echo "$members_output" | grep -q "user:\|group:"; then
                    has_individual_access=true
                fi
            fi
        fi
    done
    
    if [[ $total_protected_services -gt 0 ]]; then
        echo "   🔐 $total_protected_services service(s) protected by IAP"
        if [[ "$has_domain_access" == "true" ]]; then
            echo "   🏢 Domain-wide access configured (org users can access)"
        fi
        if [[ "$has_individual_access" == "true" ]]; then
            echo "   👤 Individual user access configured"
        fi
    else
        echo "   🌐 All services are public (no IAP protection)"
    fi
    echo ""
}

# Show main IAP menu
show_iap_menu() {
    clear
    echo "🔐 Agent Platform - IAP Management"
    echo "=================================="
    echo ""
    
    show_iap_status_summary
    
    # Quick tips for common actions
    local any_services_found=false
    if gcloud run services describe "$AGENT_SERVER_SERVICE" --region="$REGION" --quiet >/dev/null 2>&1 || \
       gcloud run services describe "$WORKROOM_SERVICE" --region="$REGION" --quiet >/dev/null 2>&1; then
        any_services_found=true
    fi
    
    if [[ "$any_services_found" == "true" ]]; then
        echo "💡 Quick Actions (no menu needed):"
        echo "   • Add user:    ./scripts/gcp/manage-my-iap.sh add user@company.com"
        echo "   • Remove user: ./scripts/gcp/manage-my-iap.sh remove user@company.com"
        echo "   • View details: ./scripts/gcp/manage-my-iap.sh list"
        echo ""
    fi
    
    echo "🎯 What would you like to do?"
    echo ""
    
    # Personal management options (always available)
    echo "👤 Personal Instance Management:"
    echo " 1) 📋 Show detailed access list"
    echo " 2) 👥 Add user to my instances"
    echo " 3) ❌ Remove user from my instances"
    echo " 4) 🔐 Enable IAP on my instances"
    echo " 5) 🔓 Disable IAP on my instances"
    echo ""
    
    # Admin options (if user has admin access)
    local has_admin=$(check_admin_permissions)
    if [[ "$has_admin" == "true" ]]; then
        echo "🔧 Admin Management (All Instances):"
        echo " 6) 📊 Show all services IAP status"
        echo " 7) 👥 Show users with access (all services)"
        echo " 8) 🔐 Enable IAP on specific services"
        echo " 9) 🔓 Disable IAP on specific services"
        echo "10) 👤 Add user to specific services"
        echo "11) ❌ Remove user from specific services"
        echo "12) 🔄 Reset IAP policy (remove all users)"
        echo "13) 🚀 Bulk enable IAP (all services)"
        echo "14) 🚫 Bulk disable IAP (all services)"
        echo ""
    else
        echo "🔧 Admin Management: Requires Owner/Editor role"
        echo ""
    fi
    
    echo " 0) ❌ Exit"
    echo ""
}

# Handle personal IAP actions
handle_personal_action() {
    local action="$1"
    
    case "$action" in
        1)
            echo "📋 Showing your IAP access list..."
            echo ""
            "$SCRIPT_DIR/manage-my-iap.sh" list
            ;;
        2)
            echo "👥 Add user to your instances"
            echo ""
            read -p "Enter email address: " email
            if [[ -n "$email" ]]; then
                "$SCRIPT_DIR/manage-my-iap.sh" add "$email"
            else
                echo "❌ No email provided"
            fi
            ;;
        3)
            echo "❌ Remove user from your instances"
            echo ""
            read -p "Enter email address: " email
            if [[ -n "$email" ]]; then
                "$SCRIPT_DIR/manage-my-iap.sh" remove "$email"
            else
                echo "❌ No email provided"
            fi
            ;;
        4)
            echo "🔐 Enabling IAP on your instances..."
            echo ""
            "$SCRIPT_DIR/manage-my-iap.sh" enable
            ;;
        5)
            echo "🔓 Disabling IAP on your instances..."
            echo ""
            "$SCRIPT_DIR/manage-my-iap.sh" disable
            ;;
        *)
            echo "❌ Invalid action: $action"
            return 1
            ;;
    esac
}

# Handle admin IAP actions
handle_admin_action() {
    local action="$1"
    
    case "$action" in
        6)
            echo "📊 Showing all services IAP status..."
            echo ""
            "$SCRIPT_DIR/admin-iap.sh" list-all
            ;;
        7)
            echo "👥 Show users with access to services"
            echo ""
            echo "Filter options: all, agent-server, workroom, shared, personal, or specific service name"
            read -p "Enter filter (or Enter for all): " filter
            "$SCRIPT_DIR/admin-iap.sh" list-users "${filter:-all}"
            ;;
        8)
            echo "🔐 Enable IAP on specific services"
            echo ""
            echo "Service options: all, agent-server, workroom, shared, personal, or specific service name"
            read -p "Enter service filter: " filter
            if [[ -n "$filter" ]]; then
                "$SCRIPT_DIR/admin-iap.sh" enable "$filter"
            else
                echo "❌ No filter provided"
            fi
            ;;
        9)
            echo "🔓 Disable IAP on specific services"
            echo ""
            echo "Service options: all, agent-server, workroom, shared, personal, or specific service name"
            read -p "Enter service filter: " filter
            if [[ -n "$filter" ]]; then
                "$SCRIPT_DIR/admin-iap.sh" disable "$filter"
            else
                echo "❌ No filter provided"
            fi
            ;;
        10)
            echo "👤 Add user to specific services"
            echo ""
            read -p "Enter email address: " email
            read -p "Enter service filter (or Enter for all): " filter
            if [[ -n "$email" ]]; then
                "$SCRIPT_DIR/admin-iap.sh" add-user "$email" "${filter:-all}"
            else
                echo "❌ No email provided"
            fi
            ;;
        11)
            echo "❌ Remove user from specific services"
            echo ""
            read -p "Enter email address: " email
            read -p "Enter service filter (or Enter for all): " filter
            if [[ -n "$email" ]]; then
                "$SCRIPT_DIR/admin-iap.sh" remove-user "$email" "${filter:-all}"
            else
                echo "❌ No email provided"
            fi
            ;;
        12)
            echo "🔄 Reset IAP policy (remove all users)"
            echo ""
            echo "Service options: all, agent-server, workroom, shared, personal, or specific service name"
            read -p "Enter service filter: " filter
            if [[ -n "$filter" ]]; then
                "$SCRIPT_DIR/admin-iap.sh" policy-reset "$filter"
            else
                echo "❌ No filter provided"
            fi
            ;;
        13)
            echo "🚀 Bulk enable IAP (all services)..."
            echo ""
            "$SCRIPT_DIR/admin-iap.sh" bulk-enable
            ;;
        14)
            echo "🚫 Bulk disable IAP (all services)..."
            echo ""
            "$SCRIPT_DIR/admin-iap.sh" bulk-disable
            ;;
        *)
            echo "❌ Invalid action: $action"
            return 1
            ;;
    esac
}

# Main menu loop
main() {
    local has_admin=$(check_admin_permissions)
    
    while true; do
        show_iap_menu
        
        if [[ "$has_admin" == "true" ]]; then
            read -p "Select option (0-14): " choice
        else
            read -p "Select option (0-5): " choice
        fi
        
        echo ""
        
        case "$choice" in
            0)
                echo "👋 Goodbye!"
                exit 0
                ;;
            1|2|3|4|5)
                handle_personal_action "$choice"
                ;;
            6|7|8|9|10|11|12|13|14)
                if [[ "$has_admin" == "true" ]]; then
                    handle_admin_action "$choice"
                else
                    echo "❌ Admin access required for this option"
                fi
                ;;
            *)
                echo "❌ Invalid choice. Please try again."
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

# Show help if requested
if [[ $# -gt 0 && ("$1" == "-h" || "$1" == "--help" || "$1" == "help") ]]; then
    cat << EOF
🔐 Agent Platform - IAP Management

QUICK COMMANDS (no menu needed):
    ./scripts/gcp/manage-my-iap.sh add user@company.com     # Add user to your instances
    ./scripts/gcp/manage-my-iap.sh remove user@company.com  # Remove user from your instances
    ./scripts/gcp/manage-my-iap.sh list                     # Show who has access
    ./scripts/gcp/manage-my-iap.sh enable                   # Enable IAP protection
    ./scripts/gcp/manage-my-iap.sh disable                  # Disable IAP (public access)

INTERACTIVE MENU:
    $0                      # Show status and interactive menu
    make gcp iap           # Same as above

WHAT YOU'LL SEE:
    • IAP status for each service (Protected 🔐 or Public 🌐)
    • Who has access (users, groups, domains)
    • Access type summary (domain-wide vs individual users)
    • Quick action commands for common tasks

FEATURES:
    👤 Personal Management:
       • Control access to YOUR instances only ($AGENT_SERVER_SERVICE, $WORKROOM_SERVICE)
       • Add/remove specific users
       • Enable/disable IAP protection
    
    🔧 Admin Management (requires Owner/Editor role):
       • Control IAP across ALL instances in project
       • Bulk operations and domain-wide access
       • Service filtering and advanced management

PROJECT INFO:
    📍 Project: $PROJECT_ID
    👤 User: $CURRENT_USER_EMAIL
    🎯 Your instances: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE
EOF
    exit 0
fi

# Run main menu
main 