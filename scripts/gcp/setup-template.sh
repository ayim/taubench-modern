#!/bin/bash

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common functions and configuration
source "$SCRIPT_DIR/common.sh"
source "$SCRIPT_DIR/functions/database-functions.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$CACHED_PROJECT_ID}"
CURRENT_USER="$CACHED_USER"

# Command line options
FORCE=false
VERBOSE=false
CHECK_ONLY=false
DELETE_TEMPLATE=false

show_help() {
    cat << EOF
🏗️  Agent Platform Database Template Manager

USAGE:
    $0 [OPTIONS]

DESCRIPTION:
    Manages the optimized database template for fast personal database cloning.
    Template enables 90-120 second database creation vs 450 seconds from scratch.

OPTIONS:
    --create            Create the database template (default action)
    --check             Check if template exists and show status
    --delete            Delete the template database (admin only)
    --force             Skip confirmation prompts
    --verbose           Show detailed output
    -h, --help          Show this help

EXAMPLES:
    $0                  # Create template (interactive)
    $0 --create         # Create template
    $0 --check          # Check template status
    $0 --force          # Create template without prompts
    $0 --delete --force # Delete template (admin use)

COST ANALYSIS:
    • Template database: ~\$7-12/month (one-time cost for entire team)
    • Benefit: 90-120 second personal database creation vs 450 seconds
    • ROI: Pays for itself if 2+ developers create personal databases monthly
    • Alternative: \$0/month but 450 second blocking waits for every developer

REQUIREMENTS:
    • Admin permissions (Cloud SQL Admin role)
    • Project quota for additional Cloud SQL instance
    • ~10GB storage allocation

TEMPLATE BENEFITS:
    • Personal isolated databases: 90-120 second cloning
    • Shared database fallback: Available if primary shared DB missing
    • Consistent database structure across all environments
    • Pre-configured with agents database and user
EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --create)
                # Default action, no flag needed
                shift
                ;;
            --check)
                CHECK_ONLY=true
                shift
                ;;
            --delete)
                DELETE_TEMPLATE=true
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

# Check template status
check_template_status() {
    local template_name="agent-postgres-template"
    
    echo "🔍 Checking template database status..."
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo ""
    
    if gcloud sql instances describe "$template_name" --format="value(state)" --quiet >/dev/null 2>&1; then
        local template_state=$(gcloud sql instances describe "$template_name" --format="value(state)" --quiet 2>/dev/null)
        local template_tier=$(gcloud sql instances describe "$template_name" --format="value(settings.tier)" --quiet 2>/dev/null)
        local template_region=$(gcloud sql instances describe "$template_name" --format="value(region)" --quiet 2>/dev/null)
        local template_ip=$(gcloud sql instances describe "$template_name" --format="value(ipAddresses[0].ipAddress)" --quiet 2>/dev/null)
        local template_created=$(gcloud sql instances describe "$template_name" --format="value(createTime)" --quiet 2>/dev/null)
        
        echo "✅ Template database exists:"
        echo "   🗄️  Instance: $template_name"
        echo "   📊 State: $template_state"
        echo "   🏗️  Tier: $template_tier"
        echo "   🌍 Region: $template_region"
        echo "   🌐 IP: $template_ip"
        echo "   📅 Created: $(date -d "$template_created" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "$template_created")"
        
        # Check for ongoing operations
        local ongoing_ops=$(gcloud sql operations list --filter="targetId:$template_name AND status:RUNNING" --format="value(operationType)" --quiet 2>/dev/null || echo "")
        if [[ -n "$ongoing_ops" ]]; then
            echo "   ⚡ Active operations: $ongoing_ops"
        fi
        
        # Estimate cost
        case "$template_tier" in
            "db-f1-micro") echo "   💰 Monthly cost: ~\$7-10" ;;
            "db-g1-small") echo "   💰 Monthly cost: ~\$25-35" ;;
            *) echo "   💰 Monthly cost: Unknown tier" ;;
        esac
        
        echo ""
        echo "🚀 Template ready for cloning!"
        echo "   • Personal database creation: 90-120 seconds"
        echo "   • Usage: scripts/gcp/deploy.sh --all --personal-isolated"
        
        return 0
    else
        echo "❌ Template database not found"
        echo ""
        echo "💡 Create template:"
        echo "   $0 --create"
        echo ""
        echo "📊 Without template:"
        echo "   • Personal database creation: 450 seconds (blocking)"
        echo "   • Cost: \$0/month but slower developer experience"
        
        return 1
    fi
}

# Delete template database
delete_template() {
    local template_name="agent-postgres-template"
    
    echo "🗑️  Deleting template database..."
    echo ""
    
    # Check if template exists
    if ! gcloud sql instances describe "$template_name" --format="value(state)" --quiet >/dev/null 2>&1; then
        echo "ℹ️  Template database not found (already deleted)"
        return 0
    fi
    
    # Show what will be deleted
    echo "📋 Template to delete:"
    echo "   🗄️  Instance: $template_name"
    
    local template_tier=$(gcloud sql instances describe "$template_name" --format="value(settings.tier)" --quiet 2>/dev/null)
    case "$template_tier" in
        "db-f1-micro") echo "   💰 Savings: ~\$7-10/month" ;;
        "db-g1-small") echo "   💰 Savings: ~\$25-35/month" ;;
        *) echo "   💰 Savings: Unknown" ;;
    esac
    
    echo ""
    echo "⚠️  Impact after deletion:"
    echo "   • Personal database creation: 450 seconds (vs 90-120 with template)"
    echo "   • Shared database fallback: Not available"
    echo "   • Template can be recreated anytime"
    
    if [[ "$FORCE" != "true" ]]; then
        echo ""
        read -p "Delete template database? Type 'delete' to confirm: " confirmation
        if [[ "$confirmation" != "delete" ]]; then
            echo "❌ Template deletion cancelled"
            return 0
        fi
    fi
    
    echo ""
    echo "🗑️  Deleting template database (this may take 2-3 minutes)..."
    
    if gcloud sql instances delete "$template_name" --quiet; then
        echo "✅ Template database deleted successfully"
        echo ""
        echo "📊 Result:"
        echo "   • Monthly cost savings: ~\$7-10"
        echo "   • Personal database creation: Back to 450 seconds"
        echo "   • Template can be recreated: $0 --create"
    else
        echo "❌ Failed to delete template database"
        echo "💡 Check manually: gcloud sql instances describe $template_name"
        return 1
    fi
}

# Create template database
create_template() {
    echo "🏗️  Creating database template system..."
    echo "📍 Project: $PROJECT_ID"
    echo "🌍 Region: $REGION"
    echo ""
    
    # Check if template already exists
    if check_template_database; then
        echo "✅ Template database already exists!"
        echo ""
        check_template_status
        return 0
    fi
    
    # Cost analysis
    echo "💰 Template Cost Analysis:"
    echo "   • One-time setup: ~\$7-12/month for template database"
    echo "   • Benefit: 90-120 second database cloning vs 450 seconds from scratch"
    echo "   • ROI: Pays for itself if 2+ developers use personal databases monthly"
    echo "   • Serves entire team: One template, multiple fast clones"
    echo ""
    
    if [[ "$FORCE" != "true" ]]; then
        read -p "Create database template? (y/n): " choice
        if [[ "$choice" != "y" && "$choice" != "Y" ]]; then
            echo "❌ Template setup cancelled"
            return 0
        fi
    fi
    
    echo ""
    echo "🚀 Creating template database..."
    echo "⏳ This will take 3-5 minutes (one-time setup for entire team)"
    echo ""
    
    # Create the template
    if create_template_database; then
        echo ""
        echo "🎉 Template setup complete!"
        echo ""
        
        # Show final status
        check_template_status
        
        echo ""
        echo "💡 Next steps for developers:"
        echo "   • Fast personal DB: scripts/gcp/deploy.sh --all --personal-isolated"
        echo "   • Check template: $0 --check"
        echo ""
    else
        echo "❌ Template creation failed"
        echo "💡 Check permissions and try again"
        return 1
    fi
}

main() {
    parse_args "$@"
    
    echo "🏗️  Database Template Manager"
    echo "📍 Project: $PROJECT_ID"
    echo "👤 User: $CURRENT_USER"
    echo ""
    
    # Check prerequisites
    check_prerequisites_lite
    
    # Check admin permissions for template operations
    if [[ "$CHECK_ONLY" != "true" ]]; then
        if ! check_shared_deployment_permissions; then
            echo "❌ Template management requires admin permissions (Owner/Editor role)"
            echo "💡 Contact your project admin to manage templates"
            echo ""
            echo "🔍 You can still check template status:"
            echo "   $0 --check"
            exit 1
        fi
    fi
    
    # Execute requested action
    if [[ "$CHECK_ONLY" == "true" ]]; then
        check_template_status
    elif [[ "$DELETE_TEMPLATE" == "true" ]]; then
        delete_template
    else
        # Default action: create template
        create_template
    fi
}

# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 