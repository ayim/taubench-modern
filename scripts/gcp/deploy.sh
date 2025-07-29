#!/bin/bash

set -euo pipefail

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source common functions and configuration
source "$SCRIPT_DIR/common.sh"

# Import modular function libraries
source "$SCRIPT_DIR/functions/iap-functions.sh"
source "$SCRIPT_DIR/functions/database-functions.sh"
source "$SCRIPT_DIR/functions/build-functions.sh"
source "$SCRIPT_DIR/functions/menu-functions.sh"

# Default configuration
REGION="europe-west1"
PROJECT_ID="${GCLOUD_PROJECT:-$CACHED_PROJECT_ID}"

# Get current user for namespacing (use cached value from common.sh)
CURRENT_USER="$CACHED_USER"
if [[ -z "$CURRENT_USER" ]]; then
    echo "❌ Unable to get authenticated user. Please run 'gcloud auth login' first."
    exit 1
fi

BUILD_ID="manual-${CURRENT_USER}-$(date +%Y%m%d-%H%M%S)"

# Deployment target options
DEPLOYMENT_TARGET="personal"  # Default to personal deployment
AGENT_SERVER_SERVICE=""
WORKROOM_SERVICE=""

# Set service names based on deployment target
set_service_names() {
    if [[ "$DEPLOYMENT_TARGET" == "shared" ]]; then
        AGENT_SERVER_SERVICE="agent-server"
        WORKROOM_SERVICE="workroom"
    else
        # Personal deployment (default)
        AGENT_SERVER_SERVICE="agent-server-${CURRENT_USER}"
        WORKROOM_SERVICE="workroom-${CURRENT_USER}"
    fi
}

# Deployment profiles configuration
set_deployment_profile() {
    local profile="$1"
    
    case "$profile" in
        "personal-isolated")
            DEPLOYMENT_TARGET="personal"
            DATABASE_CHOICE="personal"
            ;;
        "personal-shared")
            DEPLOYMENT_TARGET="personal"
            DATABASE_CHOICE="shared"
            ;;
        "team-production")
            DEPLOYMENT_TARGET="shared"
            DATABASE_CHOICE="shared"
            ;;
        *)
            echo "❌ Invalid deployment profile: $profile"
            exit 1
            ;;
    esac
    
    set_service_names
}

# Streamlined deployment profile selection
select_deployment_profile() {
    echo "🚀 Deploy to $PROJECT_ID"
    echo ""
    
    # Check admin permissions
    local has_admin=false
    if check_shared_deployment_permissions; then
        has_admin=true
    fi
    
    echo "Choose deployment profile:"
    echo ""
    echo " 1) 🌟 Isolated (My instance + My database) [RECOMMENDED]"
    echo " 2) My Instance + Shared Database (team data access)"
    if [[ "$has_admin" == "true" ]]; then
        echo " 3) Demo (Shared Instance + Shared Database) - great for demos!"
    else
        echo " 3) Demo (requires admin access)"
    fi
    echo ""
    
    while true; do
        read -p "Select [1-3]: " choice
        case $choice in
            1)
                set_deployment_profile "personal-isolated"
                ENABLE_IAP=true  # Auto-enable IAP for personal instances
                echo "✅ Isolated mode selected - complete isolation for safe development"
                echo "🔐 IAP security will be enabled automatically"
                break
                ;;
            2)
                set_deployment_profile "personal-shared"
                ENABLE_IAP=true  # Auto-enable IAP for personal instances
                echo "✅ My Instance + Shared Database selected - access team data with your own endpoints"
                echo "🔐 IAP security will be enabled automatically"
                break
                ;;
            3)
                if [[ "$has_admin" == "true" ]]; then
                    set_deployment_profile "team-production"
                    ENABLE_IAP=true  # Auto-enable IAP for all GCP deployments
                    echo "⚠️  Demo mode - affects shared team services"
                    read -p "Continue? [y/N]: " -n 1 -r
                    echo
                    if [[ $REPLY =~ ^[Yy]$ ]]; then
                        echo "✅ Demo mode confirmed"
                        echo "🔐 IAP security will be enabled automatically"
                        break
                    fi
                else
                    echo "❌ Admin access required for demo deployment"
                fi
                ;;
            *)
                echo "Please enter 1, 2, or 3"
                ;;
        esac
    done
    echo ""
}

# Explain deployment profiles to users
explain_deployment_profiles() {
    echo "�� Deployment Profile Options:"
    echo ""
    echo "   1️⃣  Isolated (My instance + My database) - 🌟 RECOMMENDED"
    echo "      • Your services: agent-server-${CURRENT_USER}, workroom-${CURRENT_USER}"  
    echo "      • Your database: agent-postgres-${CURRENT_USER}"
    echo "      • Complete isolation - safe for development and testing"
    echo "      • 🔐 IAP security enabled automatically"
    echo ""
    echo "   2️⃣  My Instance + Shared Database"
    echo "      • Your services: agent-server-${CURRENT_USER}, workroom-${CURRENT_USER}"
    echo "      • Shared database: agent-postgres (team data)"
    echo "      • Access team data while keeping your own service endpoints"
    echo "      • 🔐 IAP security enabled automatically"
    echo ""
    echo "   3️⃣  Demo (Shared Instance + Shared Database)"
    echo "      • Shared services: agent-server, workroom"
    echo "      • Shared database: agent-postgres"  
    echo "      • Great for demos and team production (requires admin permissions)"
    echo "      • 🔐 IAP security optional (admin controlled)"
    echo ""
}

# Command line options
DEPLOY_ALL=false
DEPLOY_AGENT_SERVER=false
DEPLOY_WORKROOM=false
CONFIG_ONLY=false
FORCE_BUILD=false
SKIP_TESTS=false
VERBOSE=false
ENABLE_IAP=false
DATABASE_CHOICE=""

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
    --enable-iap        Enable Identity-Aware Proxy for security
    --personal-isolated Deploy isolated setup (my instance + my database) [RECOMMENDED]
    --personal-shared   Deploy my instance + shared database (team data access)
    --team-production   Deploy demo setup (shared instance + shared database, requires admin)
    --shared            Deploy to shared services (legacy - use --team-production)
    --personal          Deploy to personal services (legacy - use --personal-shared)
    --verbose           Show detailed output
    -h, --help          Show this help

DEPLOYMENT PROFILES:
    1️⃣  Isolated (--personal-isolated) [RECOMMENDED]:
       • My services: agent-server-${CURRENT_USER}, workroom-${CURRENT_USER}
       • My database: agent-postgres-${CURRENT_USER}
       • Complete isolation - safe for development and testing
       • 🔐 IAP security enabled automatically (you control access)
    
    2️⃣  My Instance + Shared Database (--personal-shared):  
       • My services: agent-server-${CURRENT_USER}, workroom-${CURRENT_USER}
       • Shared database: agent-postgres (team data)
       • Access team data while keeping your own service endpoints
       • 🔐 IAP security enabled automatically (you control access)
    
    3️⃣  Demo (--team-production):
       • Shared services: agent-server, workroom (requires admin)
       • Shared database: agent-postgres
       • Great for demos and team production
       • 🔐 IAP security enabled automatically (admin controlled)

EXAMPLES:
    $0                              # Interactive menu with profile selection
    $0 --all --personal-isolated    # Isolated setup (RECOMMENDED for new users)
    $0 --all --personal-shared      # My instance + shared database (team data access)
    $0 --all --team-production      # Demo setup (shared services, admin required)
    $0 --agent-server --personal-isolated # Deploy only agent-server in isolated mode

PERMISSIONS:
    • Personal deployments: Available to all developers
    • Shared deployments: Require admin access (Owner/Editor role)
    • IAP can be enabled on both personal and shared services

PROFILE BENEFITS:
    1️⃣  Isolated [RECOMMENDED]:
      • Complete data isolation (your own database)
      • Safe for breaking changes and experiments  
      • No impact on team's data or services
      • Perfect for feature development and onboarding
      • 🔐 Automatic IAP security (you control who accesses)
    
    2️⃣  My Instance + Shared Database:
      • Access to team's shared data and agents
      • Service isolation (your own endpoints)
      • Great for development with team context
      • Common choice for experienced developers
      • 🔐 Automatic IAP security (you control who accesses)
    
    3️⃣  Demo:
      • Production-ready shared services
      • Consistent URLs for the entire team
      • Perfect for demos and presentations
      • Requires admin permissions
      • 🔐 Optional IAP security (admin can set domain-wide access)
EOF
}



# Check if profile change requires updating both services
check_profile_dependencies() {
    local workroom_profile=$(gcloud run services describe "$WORKROOM_SERVICE" \
        --region="$REGION" \
        --format="value(metadata.labels.deployment-profile)" \
        --quiet 2>/dev/null || echo "")
    
    local agent_profile=$(gcloud run services describe "$AGENT_SERVER_SERVICE" \
        --region="$REGION" \
        --format="value(metadata.labels.deployment-profile)" \
        --quiet 2>/dev/null || echo "")
    
    local desired_profile=""
    case "$DEPLOYMENT_TARGET-$DATABASE_CHOICE" in
        "personal-personal") desired_profile="personal-isolated" ;;
        "personal-shared") desired_profile="personal-shared" ;;
        "shared-shared") desired_profile="team-production" ;;
    esac
    
    # Function to explain profile in user-friendly terms
    explain_profile() {
        case "$1" in
            "personal-isolated") echo "Isolated (My instance + My database)" ;;
            "personal-shared") echo "My Instance + Shared Database" ;;
            "team-production") echo "Demo (Shared Instance + Shared Database)" ;;
            "") echo "No deployment profile set" ;;
            *) echo "Unknown profile: $1" ;;
        esac
    }
    
    # Smart profile inheritance: if one service has the desired profile and the other doesn't,
    # inherit the profile instead of asking the user
    local needs_consistency_check=false
    
    if [[ -n "$agent_profile" && -z "$workroom_profile" && "$agent_profile" == "$desired_profile" ]]; then
        # Agent-server has correct profile, workroom has none - inherit silently
        echo "📋 Inheriting deployment profile from agent-server: $(explain_profile "$desired_profile")"
        return 0
    elif [[ -n "$workroom_profile" && -z "$agent_profile" && "$workroom_profile" == "$desired_profile" ]]; then
        # Workroom has correct profile, agent-server has none - inherit silently  
        echo "📋 Inheriting deployment profile from workroom: $(explain_profile "$desired_profile")"
        return 0
    elif [[ "$workroom_profile" != "$desired_profile" || "$agent_profile" != "$desired_profile" ]]; then
        needs_consistency_check=true
    fi
    
    # Check if either service needs profile update
    if [[ "$needs_consistency_check" == "true" ]]; then
        echo "🔄 Deployment profile update needed:"
        echo ""
        echo "   📊 Current deployment profiles:"
        echo "      • Workroom: $(explain_profile "$workroom_profile")"
        echo "      • Agent-server: $(explain_profile "$agent_profile")"
        echo ""
        echo "   🎯 Target deployment profile:"
        echo "      • $(explain_profile "$desired_profile")"
        echo ""
        echo "   💡 Why both services need the same profile:"
        echo "      The agent-server and workroom must use the same database"
        echo "      configuration for proper data consistency and functionality."
        echo ""
        
        # If user only selected one service, ask if they want to update both
        if [[ "$DEPLOY_AGENT_SERVER" == "true" && "$DEPLOY_WORKROOM" == "false" ]]; then
            echo "👉 You selected agent-server only, but workroom also needs updating"
            echo "   This ensures both services use the same deployment profile."
            read -p "Update both services? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                DEPLOY_WORKROOM=true
                echo "✅ Will update both agent-server and workroom"
            else
                echo "⚠️  Warning: Services may have different deployment profiles"
                echo "   This could cause database connectivity issues"
            fi
        elif [[ "$DEPLOY_WORKROOM" == "true" && "$DEPLOY_AGENT_SERVER" == "false" ]]; then
            echo "👉 You selected workroom only, but agent-server also needs updating"
            echo "   This ensures both services use the same deployment profile."
            read -p "Update both services? (y/n): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                DEPLOY_AGENT_SERVER=true
                echo "✅ Will update both agent-server and workroom"
            else
                echo "⚠️  Warning: Services may have different deployment profiles"
                echo "   This could cause database connectivity issues"
            fi
        fi
        echo ""
    fi
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
            --enable-iap)
                ENABLE_IAP=true
                shift
                ;;
            --personal-isolated)
                set_deployment_profile "personal-isolated"
                ENABLE_IAP=true  # Auto-enable IAP for personal instances
                shift
                ;;
            --personal-shared)
                set_deployment_profile "personal-shared"
                ENABLE_IAP=true  # Auto-enable IAP for personal instances
                shift
                ;;
            --team-production)
                set_deployment_profile "team-production"
                ENABLE_IAP=true  # Auto-enable IAP for all GCP deployments
                shift
                ;;
            --shared)
                # Legacy support
                set_deployment_profile "team-production"
                ENABLE_IAP=true  # Auto-enable IAP for all GCP deployments
                shift
                ;;
            --personal)
                # Legacy support
                set_deployment_profile "personal-shared"
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
    
    # Set service names after parsing arguments
    set_service_names
    
    # If deployment target was set but no database choice, set default profile
    if [[ -n "$DEPLOYMENT_TARGET" && -z "$DATABASE_CHOICE" ]]; then
        if [[ "$DEPLOYMENT_TARGET" == "shared" ]]; then
            DATABASE_CHOICE="shared"
        else
            DATABASE_CHOICE="shared"  # Default to shared database for personal services
        fi
    fi
}

main() {
    parse_args "$@"
    
    # Validate shared deployment permissions if specified via command line
    if [[ "$DEPLOYMENT_TARGET" == "shared" && ! check_shared_deployment_permissions ]]; then
        echo "❌ Shared deployment requires admin access (Owner/Editor role)"
        echo "   Your current permissions only allow personal deployments"
        echo "   Use --personal flag or contact an admin for shared service access"
        echo ""
        echo "💡 Available options:"
        echo "   $0 --all --personal         # Deploy to your personal services"
        echo "   $0 --agent-server --personal # Deploy only agent-server to personal service"
        exit 1
    fi
    
    # If no deployment options specified, show interactive menu
    if [[ "$DEPLOY_ALL" == "false" && "$DEPLOY_AGENT_SERVER" == "false" && "$DEPLOY_WORKROOM" == "false" && "$CONFIG_ONLY" == "false" ]]; then
        select_deployment_profile
        show_deployment_actions
    else
        if [[ "$VERBOSE" == "true" ]]; then
            echo "🚀 Agent Platform GCP Deployment"
            echo "📍 Project: $PROJECT_ID"
            echo "🌍 Region: $REGION"
            echo "👤 User: $CURRENT_USER"
            echo "🎯 Profile: $([ "$DEPLOYMENT_TARGET" == "shared" ] && echo "Demo (Shared Services)" || echo "My Instance")"
            echo "🏷️  Services: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE"
            echo ""
        else
            echo "🚀 Deploying $([ "$DEPLOYMENT_TARGET" == "shared" ] && echo "demo setup" || echo "my instance") to $PROJECT_ID..."
        fi
    fi
    
    check_prerequisites_lite
    check_docker_lite
    
    cd "$PROJECT_ROOT"
    
    # Check if profile changes require updating both services
    check_profile_dependencies
    
    # Deploy services (sequential when both are selected due to dependency)
    if [[ "$DEPLOY_AGENT_SERVER" == "true" && "$DEPLOY_WORKROOM" == "true" ]]; then
        echo ""
        log_info "Deploying both services sequentially (workroom depends on agent server)"
        echo ""
        
        # Deploy agent server first (workroom needs its URL)
        echo "1️⃣  Deploying agent server first..."
        deploy_agent_server
        local agent_status=$?
        
        if [[ $agent_status -eq 0 ]]; then
            echo ""
            echo "2️⃣  Deploying workroom (now that agent server is ready)..."
            deploy_workroom
            local workroom_status=$?
            
            # Check final result
            if [[ $workroom_status -eq 0 ]]; then
                log_success "Sequential deployment completed successfully"
            else
                log_error "Workroom deployment failed"
                exit 1
            fi
        else
            log_error "Agent-server deployment failed - skipping workroom deployment"
            exit 1
        fi
    else
        # Deploy individually (single service deployments)
        if [[ "$DEPLOY_AGENT_SERVER" == "true" ]]; then
            deploy_agent_server
        fi
        
        if [[ "$DEPLOY_WORKROOM" == "true" ]]; then
            deploy_workroom
        fi
    fi
    
    # Setup IAP permissions if enabled
    if [[ "$ENABLE_IAP" == "true" ]]; then
        setup_iap_permissions
    fi
    
    # Show authentication configuration summary
    show_authentication_summary
    
    # Show final status (streamlined)
    echo ""
    if [[ "$DEPLOYMENT_TARGET" == "shared" ]]; then
        echo "🎉 Demo deployment complete"
        echo "🌐 Shared services: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE"
    else
        echo "🎉 My instance deployment complete"  
        echo "👤 Your services: $AGENT_SERVER_SERVICE, $WORKROOM_SERVICE"
    fi
    
    echo ""
    echo "📊 Status: make gcp status  |  🗑️  Teardown: make gcp teardown"
}



# Make script executable from anywhere
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi 