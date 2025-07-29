#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Get current user for namespacing
CURRENT_USER=$(gcloud config get-value account 2>/dev/null | cut -d'@' -f1 | tr '.' '-')
CURRENT_USER_EMAIL=$(gcloud config get-value account 2>/dev/null)

if [[ -z "$CURRENT_USER" ]]; then
    echo "❌ Unable to get authenticated user. Please run 'gcloud auth login' first."
    exit 1
fi

# Personal service names
AGENT_SERVER_SERVICE="agent-server-${CURRENT_USER}"
WORKROOM_SERVICE="workroom-${CURRENT_USER}"

show_help() {
    cat << EOF
🔐 Personal IAP Access Management

Manage access to YOUR personal agent platform instances only.
You have full control over who can access your instances.

USAGE:
    $0 [ACTION] [EMAIL|DOMAIN|GROUP] [OPTIONS]

ACTIONS:
    add     EMAIL|DOMAIN|GROUP  Grant access to your instances
    remove  EMAIL|DOMAIN|GROUP  Remove access from your instances  
    list                        Show who has access to your instances
    status                      Show IAP status for your instances
    enable                      Enable IAP on your instances
    disable                     Disable IAP on your instances

INPUT FORMATS:
    user@company.com           Individual user access
    @company.com               All users from domain (domain-wide access)
    group@company.com          Google Group access

OPTIONS:
    --service SERVICE          Specific service (agent-server|workroom|both)
    --type TYPE               Explicit member type (user|group|domain)
    --verbose                 Show detailed output
    -h, --help                Show this help

EXAMPLES:
    $0 list                                    # Show current access
    $0 status                                  # Check IAP status
    $0 add colleague@company.com               # Give colleague access
    $0 add @company.com                        # Give entire domain access
    $0 remove user@company.com                 # Remove user access
    $0 enable                                  # Enable IAP protection
    $0 disable                                 # Disable IAP (make public)

YOUR INSTANCES:
    🖥️  Agent Server: $AGENT_SERVER_SERVICE
    🎨 Workroom: $WORKROOM_SERVICE
    👤 Owner: $CURRENT_USER_EMAIL

SECURITY:
    • You can only manage YOUR instances (name-spaced to your account)
    • You are automatically the owner and cannot remove yourself
    • Changes take 2-10 minutes to propagate
    
    Admin access is controlled separately by: scripts/gcp/admin-iap.sh
EOF
}

# Check if user owns the services
check_service_ownership() {
    local service="$1"
    
    if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
        echo "❌ Service '$service' not found. Deploy your instances first:"
        echo "   make gcp deploy --all --personal-isolated"
        return 1
    fi
    
    # Check if service name contains current user (ownership check)
    if [[ "$service" != *"$CURRENT_USER"* ]]; then
        echo "❌ You can only manage your own instances. '$service' is not yours."
        echo "💡 Your instances should be named: agent-server-$CURRENT_USER, workroom-$CURRENT_USER"
        return 1
    fi
    
    return 0
}

# List current IAP access for personal services
list_access() {
    echo "🔐 IAP Access for Your Personal Instances"
    echo "=========================================="
    echo "👤 Owner: $CURRENT_USER_EMAIL"
    echo ""
    
    for service in "$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE"; do
        local display_name=""
        case "$service" in
            *"agent-server"*) display_name="🖥️  Agent Server" ;;
            *"workroom"*) display_name="🎨 Workroom" ;;
        esac
        
        echo "$display_name ($service):"
        
        if ! check_service_ownership "$service"; then
            continue
        fi
        
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
    done
}

# Show IAP status for personal services  
show_status() {
    echo "🔐 IAP Status for Your Personal Instances"
    echo "========================================="
    echo "👤 Owner: $CURRENT_USER_EMAIL"
    echo ""
    
    for service in "$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE"; do
        local display_name=""
        case "$service" in
            *"agent-server"*) display_name="🖥️  Agent Server" ;;
            *"workroom"*) display_name="🎨 Workroom" ;;
        esac
        
        echo "$display_name ($service):"
        
        if ! check_service_ownership "$service"; then
            continue
        fi
        
        # Check IAP status
        local iap_status
        iap_status=$(gcloud beta run services describe "$service" \
            --region="$REGION" \
            --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
            --quiet 2>/dev/null || echo "unknown")
        
        # Check ingress
        local ingress
        ingress=$(gcloud run services describe "$service" \
            --region="$REGION" \
            --format="value(spec.traffic[0].revisionName.split('-')[0:-1].join('-'),status.traffic[0].percent,metadata.annotations['run.googleapis.com/ingress'])" \
            --quiet 2>/dev/null | cut -d',' -f3 || echo "unknown")
        
        case "$iap_status" in
            "true") echo "   🔐 IAP: ✅ Enabled (protected)" ;;
            "false"|"") echo "   🔐 IAP: ❌ Disabled (public access)" ;;
            *) echo "   🔐 IAP: ⚠️ Unknown ($iap_status)" ;;
        esac
        
        case "$ingress" in
            "all") echo "   🌐 Ingress: Public (accessible from internet)" ;;
            "internal") echo "   🏠 Ingress: Internal (GCP project only)" ;;
            *) echo "   🌐 Ingress: Unknown ($ingress)" ;;
        esac
        
        # Show URL
        local url
        url=$(gcloud run services describe "$service" \
            --region="$REGION" \
            --format="value(status.url)" \
            --quiet 2>/dev/null || echo "")
        
        if [[ -n "$url" ]]; then
            echo "   🔗 URL: $url"
        fi
        
        echo ""
    done
    
    echo "💡 To change access: $0 add/remove user@company.com"
    echo "🔧 To enable/disable IAP: $0 enable/disable"
}

# Add access to personal services
add_access() {
    local input="$1"
    local member_type="${2:-auto}"
    local target_service="${3:-both}"
    
    echo "🔐 Adding access to your personal instances..."
    
    # Parse input and determine member type
    local member=""
    if [[ "$member_type" == "auto" ]]; then
        if [[ "$input" == @* ]]; then
            member="domain:${input#@}"
            member_type="domain"
        elif [[ "$input" == *@*.* ]]; then
            # Could be user or group - default to user
            member="user:$input"
            member_type="user"
        else
            echo "❌ Invalid email/domain format: $input"
            return 1
        fi
    else
        case "$member_type" in
            user) member="user:$input" ;;
            group) member="group:$input" ;;
            domain) member="domain:$input" ;;
            *) echo "❌ Invalid member type: $member_type"; return 1 ;;
        esac
    fi
    
    echo "👤 Adding: $member"
    echo ""
    
    # Determine target services
    local services=()
    case "$target_service" in
        "agent-server") services=("$AGENT_SERVER_SERVICE") ;;
        "workroom") services=("$WORKROOM_SERVICE") ;;
        "both") services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE") ;;
        *) echo "❌ Invalid service: $target_service"; return 1 ;;
    esac
    
    local success_count=0
    local total_count=${#services[@]}
    
    for service in "${services[@]}"; do
        local display_name=""
        case "$service" in
            *"agent-server"*) display_name="Agent Server" ;;
            *"workroom"*) display_name="Workroom" ;;
        esac
        
        echo "🔧 Adding access to $display_name..."
        
        if ! check_service_ownership "$service"; then
            continue
        fi
        
        # Add IAP access
        if gcloud beta iap web add-iam-policy-binding \
            --member="$member" \
            --role=roles/iap.httpsResourceAccessor \
            --region="$REGION" \
            --resource-type=cloud-run \
            --service="$service" \
            --quiet 2>/dev/null; then
            echo "✅ Access granted to $display_name"
            ((success_count++))
        else
            echo "⚠️  Failed to grant access to $display_name (may already exist)"
        fi
    done
    
    echo ""
    if [[ $success_count -eq $total_count ]]; then
        echo "🎉 Access granted successfully!"
    else
        echo "⚠️  Completed with some warnings (this is often normal)"
    fi
    
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
    echo "💡 Test access: $0 list"
}

# Remove access from personal services
remove_access() {
    local input="$1"
    local member_type="${2:-auto}"
    local target_service="${3:-both}"
    
    # Prevent user from removing themselves
    if [[ "$input" == "$CURRENT_USER_EMAIL" ]]; then
        echo "❌ You cannot remove yourself as the owner of your instances"
        echo "💡 You always have access to your own instances"
        return 1
    fi
    
    echo "🔐 Removing access from your personal instances..."
    
    # Parse input and determine member type
    local member=""
    if [[ "$member_type" == "auto" ]]; then
        if [[ "$input" == @* ]]; then
            member="domain:${input#@}"
            member_type="domain"
        elif [[ "$input" == *@*.* ]]; then
            member="user:$input"
            member_type="user"
        else
            echo "❌ Invalid email/domain format: $input"
            return 1
        fi
    else
        case "$member_type" in
            user) member="user:$input" ;;
            group) member="group:$input" ;;
            domain) member="domain:$input" ;;
            *) echo "❌ Invalid member type: $member_type"; return 1 ;;
        esac
    fi
    
    echo "👤 Removing: $member"
    echo ""
    
    # Determine target services
    local services=()
    case "$target_service" in
        "agent-server") services=("$AGENT_SERVER_SERVICE") ;;
        "workroom") services=("$WORKROOM_SERVICE") ;;
        "both") services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE") ;;
        *) echo "❌ Invalid service: $target_service"; return 1 ;;
    esac
    
    local success_count=0
    local total_count=${#services[@]}
    
    for service in "${services[@]}"; do
        local display_name=""
        case "$service" in
            *"agent-server"*) display_name="Agent Server" ;;
            *"workroom"*) display_name="Workroom" ;;
        esac
        
        echo "🔧 Removing access from $display_name..."
        
        if ! check_service_ownership "$service"; then
            continue
        fi
        
        # Remove IAP access
        if gcloud beta iap web remove-iam-policy-binding \
            --member="$member" \
            --role=roles/iap.httpsResourceAccessor \
            --region="$REGION" \
            --resource-type=cloud-run \
            --service="$service" \
            --quiet 2>/dev/null; then
            echo "✅ Access removed from $display_name"
            ((success_count++))
        else
            echo "⚠️  Failed to remove access from $display_name (may not exist)"
        fi
    done
    
    echo ""
    if [[ $success_count -eq $total_count ]]; then
        echo "🎉 Access removed successfully!"
    else
        echo "⚠️  Completed with some warnings"
    fi
    
    echo ""
    echo "⏱️  Changes may take 2-10 minutes to propagate"
    echo "💡 Check access: $0 list"
}

# Enable IAP on personal services
enable_iap() {
    echo "🔐 Enabling IAP on your personal instances..."
    echo ""
    
    # Enable IAP API first
    echo "🔧 Ensuring IAP API is enabled..."
    gcloud services enable iap.googleapis.com --quiet
    
    local services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
    local success_count=0
    
    for service in "${services[@]}"; do
        local display_name=""
        case "$service" in
            *"agent-server"*) display_name="Agent Server" ;;
            *"workroom"*) display_name="Workroom" ;;
        esac
        
        echo "🔧 Enabling IAP on $display_name..."
        
        if ! check_service_ownership "$service"; then
            continue
        fi
        
        # Enable IAP
        if gcloud beta run services update "$service" \
            --region="$REGION" \
            --iap \
            --quiet 2>/dev/null; then
            echo "✅ IAP enabled on $display_name"
            
            # Grant access to owner
            echo "👤 Granting access to owner ($CURRENT_USER_EMAIL)..."
            gcloud beta iap web add-iam-policy-binding \
                --member="user:$CURRENT_USER_EMAIL" \
                --role=roles/iap.httpsResourceAccessor \
                --region="$REGION" \
                --resource-type=cloud-run \
                --service="$service" \
                --quiet 2>/dev/null || true
            
            ((success_count++))
        else
            echo "⚠️  Failed to enable IAP on $display_name"
        fi
    done
    
    echo ""
    if [[ $success_count -gt 0 ]]; then
        echo "🎉 IAP enabled on your instances!"
        echo ""
        echo "⏱️  Changes may take 2-10 minutes to propagate"
        echo "👤 You have been granted access as the owner"
        echo "💡 Add others: $0 add colleague@company.com"
    else
        echo "❌ Failed to enable IAP on any service"
    fi
}

# Disable IAP on personal services  
disable_iap() {
    echo "⚠️  WARNING: Disabling IAP will make your instances publicly accessible!"
    echo "🌐 Anyone on the internet will be able to access them without authentication"
    echo ""
    read -p "Are you sure you want to continue? [y/N]: " confirm
    
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        return 0
    fi
    
    echo "🔓 Disabling IAP on your personal instances..."
    echo ""
    
    local services=("$AGENT_SERVER_SERVICE" "$WORKROOM_SERVICE")
    local success_count=0
    
    for service in "${services[@]}"; do
        local display_name=""
        case "$service" in
            *"agent-server"*) display_name="Agent Server" ;;
            *"workroom"*) display_name="Workroom" ;;
        esac
        
        echo "🔧 Disabling IAP on $display_name..."
        
        if ! check_service_ownership "$service"; then
            continue
        fi
        
        # Disable IAP
        if gcloud beta run services update "$service" \
            --region="$REGION" \
            --no-iap \
            --allow-unauthenticated \
            --quiet 2>/dev/null; then
            echo "✅ IAP disabled on $display_name (now public)"
            ((success_count++))
        else
            echo "⚠️  Failed to disable IAP on $display_name"
        fi
    done
    
    echo ""
    if [[ $success_count -gt 0 ]]; then
        echo "⚠️  IAP disabled - your instances are now publicly accessible"
        echo ""
        echo "⏱️  Changes may take 2-10 minutes to propagate"
        echo "🔐 Re-enable: $0 enable"
    else
        echo "❌ Failed to disable IAP on any service"
    fi
}

# Parse command line arguments
main() {
    if [[ $# -eq 0 ]]; then
        show_help
        exit 0
    fi
    
    local action="$1"
    shift
    
    case "$action" in
        "add")
            if [[ $# -eq 0 ]]; then
                echo "❌ Missing email/domain. Usage: $0 add user@company.com"
                exit 1
            fi
            add_access "$1" "${2:-auto}" "${3:-both}"
            ;;
        "remove")
            if [[ $# -eq 0 ]]; then
                echo "❌ Missing email/domain. Usage: $0 remove user@company.com"
                exit 1
            fi
            remove_access "$1" "${2:-auto}" "${3:-both}"
            ;;
        "list")
            list_access
            ;;
        "status")
            show_status
            ;;
        "enable")
            enable_iap
            ;;
        "disable")
            disable_iap
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