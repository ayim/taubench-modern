#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Get current user for namespacing
CURRENT_USER=$(gcloud config get-value account 2>/dev/null | cut -d'@' -f1 | tr '.' '-')
if [[ -z "$CURRENT_USER" ]]; then
    echo "❌ Unable to get authenticated user. Please run 'gcloud auth login' first."
    exit 1
fi

# User-namespaced service names
AGENT_SERVER_SERVICE="agent-server-${CURRENT_USER}"
WORKROOM_SERVICE="workroom-${CURRENT_USER}"

show_help() {
    cat << EOF
🔐 IAP Access Management for Agent Platform

USAGE:
    $0 [ACTION] [EMAIL|DOMAIN|GROUP] [OPTIONS]

ACTIONS:
    add     EMAIL|DOMAIN|GROUP  Grant IAP access to a user, domain, or group
    remove  EMAIL|DOMAIN|GROUP  Remove IAP access from a user, domain, or group
    list                        Show current IAP access policies
    status                      Check IAP status for services

INPUT FORMATS:
    user@company.com           Individual user access
    @company.com               All users from domain (domain-wide access)
    group@company.com          Google Group access (must be existing group)

OPTIONS:
    --service SERVICE          Specific service (agent-server|workroom)
    --type TYPE               Explicit member type (user|group|domain)
    --verbose                 Show detailed output
    -h, --help                Show this help

EXAMPLES:
    $0 add user@company.com                    # Add individual user
    $0 add @company.com                        # Add entire domain
    $0 add team@company.com --type group       # Explicitly add as group
    $0 add company.com --type domain           # Add domain (without @)
    $0 remove @company.com                     # Remove domain access
    $0 list                                    # Show who has access
    $0 status                                  # Check IAP status

REQUIREMENTS:
    • Services must be deployed with IAP enabled (--enable-iap flag)
    • Domain access requires Google Workspace organization
    • Group access requires existing Google Groups
    • Requires IAM permissions: roles/iap.admin or equivalent

NOTE:
    Your current services: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE
EOF
}

# Check if IAP is enabled for a service
check_iap_status() {
    local service="$1"
    
    if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
        echo "❌ Service $service not found"
        return 1
    fi
    
    # Check if service has IAP enabled (beta feature)
    local iap_status=$(gcloud beta run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
        --quiet 2>/dev/null || echo "")
    
    if [[ "$iap_status" == "true" ]]; then
        echo "✅ IAP enabled"
        return 0
    else
        echo "❌ IAP not enabled"
        return 1
    fi
}

# Detect input type and format IAM member
detect_member_type() {
    local input="$1"
    local explicit_type="${2:-}"
    
    if [[ -z "$input" ]]; then
        echo "❌ Email, domain, or group required"
        return 1
    fi
    
    # If explicit type is provided, use it
    if [[ -n "$explicit_type" ]]; then
        case "$explicit_type" in
            "user"|"u")
                if [[ "$input" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
                    echo "user:$input"
                    return 0
                else
                    echo "❌ Invalid email format for user: $input"
                    return 1
                fi
                ;;
            "group"|"g")
                if [[ "$input" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
                    echo "group:$input"
                    return 0
                else
                    echo "❌ Invalid email format for group: $input"
                    return 1
                fi
                ;;
            "domain"|"d")
                # Allow both @domain.com and domain.com formats
                if [[ "$input" =~ ^@?[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
                    local domain="${input#@}"
                    echo "domain:$domain"
                    return 0
                else
                    echo "❌ Invalid domain format: $input"
                    return 1
                fi
                ;;
            *)
                echo "❌ Invalid type: $explicit_type. Use: user, group, or domain"
                return 1
                ;;
        esac
    fi
    
    # Auto-detection logic
    # Domain format: @company.com
    if [[ "$input" =~ ^@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        local domain="${input#@}"
        echo "domain:$domain"
        return 0
    fi
    
    # Email format (could be user or group) 
    if [[ "$input" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        # Default to user (can be overridden with --type group)
        echo "user:$input"
        return 0
    fi
    
    echo "❌ Invalid format. Use: user@domain.com, @domain.com, or specify --type"
    return 1
}

# Get display name for member type
get_member_display_name() {
    local member="$1"
    
    if [[ "$member" =~ ^domain: ]]; then
        local domain="${member#domain:}"
        echo "🏢 Domain: @$domain"
    elif [[ "$member" =~ ^group: ]]; then
        local group="${member#group:}"
        echo "👥 Group: $group"
    elif [[ "$member" =~ ^user: ]]; then
        local user="${member#user:}"
        echo "👤 User: $user"
    else
        echo "❓ Unknown: $member"
    fi
}

# Add IAP access for a user, domain, or group
add_iap_access() {
    local input="$1"
    local specific_service="${2:-}"
    local member_type="$3"
    
    if [[ -z "$input" ]]; then
        echo "❌ Email, domain, or group required"
        show_help
        exit 1
    fi
    
    # Detect member type and get IAM format
    local member
    if ! member=$(detect_member_type "$input" "$member_type"); then
        echo "$member"  # Error message from detect_member_type
        exit 1
    fi
    
    local display_name=$(get_member_display_name "$member")
    echo "🔐 Adding IAP access for: $display_name"
    
    local services=()
    if [[ -n "$specific_service" ]]; then
        case "$specific_service" in
            "agent-server") services=("$AGENT_SERVER_SERVICE") ;;
            "workroom") services=("$WORKROOM_SERVICE") ;;
            *) echo "❌ Invalid service: $specific_service"; exit 1 ;;
        esac
    else
        services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
    fi
    
    for service in "${services[@]}"; do
        echo "🔒 Granting access to $service..."
        
        if ! check_iap_status "$service" >/dev/null; then
            echo "⚠️  Warning: $service does not have IAP enabled"
            echo "   Deploy with --enable-iap flag first"
            continue
        fi
        
        if gcloud beta iap web add-iam-policy-binding \
            --member="$member" \
            --role=roles/iap.httpsResourceAccessor \
            --region="$REGION" \
            --resource-type=cloud-run \
            --service="$service" \
            --quiet 2>/dev/null; then
            echo "✅ Access granted to $service"
            echo "⏱️  Note: Access changes may take 2-10 minutes to propagate"
        else
            echo "⚠️  Access may already exist for $service"
        fi
    done
    
    echo ""
    echo "✅ IAP access configuration complete for $display_name"
    echo ""
    echo "🔍 If you still get 'access denied' errors after 5 minutes:"
    echo "   • Try incognito/private browsing mode"
    echo "   • Clear browser cache for *.run.app domains" 
    echo "   • Verify you're signed into the correct Google account"
    echo "   • Wait up to 10 minutes for full propagation"
    
    # Additional guidance based on member type
    if [[ "$member" =~ ^domain: ]]; then
        echo "   • Domain access requires Google Workspace organization"
        echo "   • Users must sign in with their organizational account"
    elif [[ "$member" =~ ^group: ]]; then
        echo "   • Group members must be added to the Google Group first"
        echo "   • Group membership changes may take additional time to sync"
    fi
}

# Remove IAP access for a user, domain, or group
remove_iap_access() {
    local input="$1"
    local specific_service="${2:-}"
    local member_type="$3"
    
    if [[ -z "$input" ]]; then
        echo "❌ Email, domain, or group required"
        show_help
        exit 1
    fi
    
    # Detect member type and get IAM format
    local member
    if ! member=$(detect_member_type "$input" "$member_type"); then
        echo "$member"  # Error message from detect_member_type
        exit 1
    fi
    
    local display_name=$(get_member_display_name "$member")
    echo "🔐 Removing IAP access for: $display_name"
    
    local services=()
    if [[ -n "$specific_service" ]]; then
        case "$specific_service" in
            "agent-server") services=("$AGENT_SERVER_SERVICE") ;;
            "workroom") services=("$WORKROOM_SERVICE") ;;
            *) echo "❌ Invalid service: $specific_service"; exit 1 ;;
        esac
    else
        services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
    fi
    
    for service in "${services[@]}"; do
        echo "🔓 Removing access from $service..."
        
        if gcloud beta iap web remove-iam-policy-binding \
            --member="$member" \
            --role=roles/iap.httpsResourceAccessor \
            --region="$REGION" \
            --resource-type=cloud-run \
            --service="$service" \
            --quiet 2>/dev/null; then
            echo "✅ Access removed from $service"
        else
            echo "⚠️  Member may not have had access to $service"
        fi
    done
    
    echo ""
    echo "✅ IAP access removal complete for $display_name"
}

# List current IAP access
list_iap_access() {
    echo "🔐 Current IAP Access Policies"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo ""
    
    for service in "$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE"; do
        local display_name=$(echo "$service" | sed "s/-${CURRENT_USER}//")
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🔒 $display_name ($service)"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
            echo "❌ Service not deployed"
            echo ""
            continue
        fi
        
        local iap_status
        if check_iap_status "$service" >/dev/null; then
            iap_status="✅ Enabled"
        else
            iap_status="❌ Disabled"
        fi
        
        echo "📊 IAP Status: $iap_status"
        
        if [[ "$iap_status" == "✅ Enabled" ]]; then
            echo "👥 Authorized Users:"
            
            local policy=$(gcloud beta iap web get-iam-policy \
                --region="$REGION" \
                --resource-type=cloud-run \
                --service="$service" \
                --format="value(bindings[].members)" \
                --quiet 2>/dev/null || echo "")
            
            if [[ -n "$policy" ]]; then
                echo "$policy" | tr ',' '\n' | while read -r member; do
                    if [[ -n "$member" ]]; then
                        local display_name=$(get_member_display_name "$member")
                        echo "   $display_name"
                    fi
                done
            else
                echo "   (No users found)"
            fi
        else
            echo "⚠️  Deploy with --enable-iap to secure this service"
        fi
        
        echo ""
    done
}

# Show IAP status
show_iap_status() {
    echo "🔐 IAP Status Check"
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo ""
    
    for service in "$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE"; do
        local display_name=$(echo "$service" | sed "s/-${CURRENT_USER}//")
        printf "%-20s: " "$display_name"
        
        if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
            echo "❌ Not deployed"
            continue
        fi
        
        check_iap_status "$service"
    done
    
    echo ""
    echo "💡 To enable IAP: ./scripts/gcp/deploy.sh --all --enable-iap"
    echo "💡 To manage access: ./scripts/gcp/manage-iap-access.sh add user@company.com"
}

# Main function
main() {
    # Handle help flags as first argument
    if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
        show_help
        exit 0
    fi
    
    local action="${1:-}"
    local input="${2:-}"
    local specific_service=""
    local member_type=""
    local verbose=false
    
    # Skip the action and input arguments
    if [[ $# -ge 1 ]]; then
        shift  # Remove action
    fi
    if [[ $# -ge 1 && "$1" != --* ]]; then
        shift  # Remove input if it's not an option
    fi
    
    # Parse remaining arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --service)
                if [[ -z "${2:-}" ]]; then
                    echo "❌ --service requires a value"
                    show_help
                    exit 1
                fi
                specific_service="$2"
                shift 2
                ;;
            --type)
                if [[ -z "${2:-}" ]]; then
                    echo "❌ --type requires a value"
                    show_help
                    exit 1
                fi
                member_type="$2"
                shift 2
                ;;
            --verbose)
                verbose=true
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
    
    if [[ -z "$PROJECT_ID" ]]; then
        echo "❌ PROJECT_ID not set. Set GCLOUD_PROJECT environment variable or run:"
        echo "gcloud config set project YOUR_PROJECT_ID"
        exit 1
    fi
    
    case "$action" in
        add)
            add_iap_access "$input" "$specific_service" "$member_type"
            ;;
        remove)
            remove_iap_access "$input" "$specific_service" "$member_type"
            ;;
        list)
            list_iap_access
            ;;
        status)
            show_iap_status
            ;;
        "")
            echo "❌ Action required"
            show_help
            exit 1
            ;;
        *)
            echo "❌ Unknown action: $action"
            show_help
            exit 1
            ;;
    esac
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 