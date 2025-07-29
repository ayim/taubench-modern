#!/usr/bin/env bash

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load common functions
source "$SCRIPT_DIR/common.sh"

# Configuration
REGION="${REGION:-europe-west1}"

# Usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "🛠️  Agent Platform GCP Setup & Deploy"
    echo "   Streamlined setup for personal account deployment"
    echo
    echo "Options:"
    echo "  --check             Check current setup status"
    echo "  --missing-only      Setup missing components + deploy (recommended)"
    echo "  --database-only     Setup database only"
    echo "  --secrets-only      Setup secrets only"
    echo "  --permissions       Setup permissions only"
    echo "  --all              Complete setup + deploy"
    echo "  --help             Show this help"
    echo
    echo "Examples:"
    echo "  $0                          # Interactive menu (recommended)"
    echo "  $0 --check                  # Check what's setup and missing"
    echo "  $0 --missing-only           # Setup missing components → deploy"
    echo "  $0 --database-only          # Just create database"
    echo
    echo "🚀 After setup, automatically runs:"
    echo "   make gcp deploy --all --personal-isolated"
    echo
    echo "Environment Variables:"
    echo "  REGION                      # GCP region (default: europe-west1)"
    echo "  GCLOUD_PROJECT             # GCP project ID (will prompt if not set)"
    echo
}

# Parse command line arguments
CHECK_ONLY=false
DATABASE_ONLY=false
SECRETS_ONLY=false
PERMISSIONS_ONLY=false
MISSING_ONLY=false
SETUP_ALL=false
SHOW_MENU=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --check)
            CHECK_ONLY=true
            SHOW_MENU=false
            shift
            ;;
        --database-only)
            DATABASE_ONLY=true
            SHOW_MENU=false
            shift
            ;;
        --secrets-only)
            SECRETS_ONLY=true
            SHOW_MENU=false
            shift
            ;;
        --permissions)
            PERMISSIONS_ONLY=true
            SHOW_MENU=false
            shift
            ;;
        --missing-only)
            MISSING_ONLY=true
            SHOW_MENU=false
            shift
            ;;
        --all)
            SETUP_ALL=true
            SHOW_MENU=false
            shift
            ;;
        --help)
            usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Health check functions
check_prerequisites_status() {
    local missing=()
    local warnings=()
    
    # Check if gcloud is installed and authenticated
    if ! command -v gcloud &> /dev/null; then
        missing+=("gcloud CLI not installed")
    elif ! gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q .; then
        missing+=("gcloud authentication required")
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        missing+=("Docker not running")
    fi
    
    # Check project selection (use cached value)
    if [[ -z "${GCLOUD_PROJECT:-}" ]] && [[ -z "$CACHED_PROJECT_ID" ]]; then
        missing+=("GCP project not selected")
    fi
    
    # Handle empty arrays safely
    local missing_str=""
    local warnings_str=""
    if [[ ${#missing[@]} -gt 0 ]]; then
        missing_str="$(IFS=',' ; echo "${missing[*]}")"
    fi
    if [[ ${#warnings[@]} -gt 0 ]]; then
        warnings_str="$(IFS=',' ; echo "${warnings[*]}")"
    fi
    
    printf "%s|%s" "$missing_str" "$warnings_str"
}

check_apis_status() {
    local missing=()
    local required_apis=(
        "cloudbuild.googleapis.com"
        "run.googleapis.com"
        "sqladmin.googleapis.com"
        "secretmanager.googleapis.com"
        "artifactregistry.googleapis.com"
        "iam.googleapis.com"
        "cloudresourcemanager.googleapis.com"
    )
    
    for api in "${required_apis[@]}"; do
        if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
            missing+=("$api")
        fi
    done
    
    # Handle empty array safely
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "$(IFS=',' ; echo "${missing[*]}")"
    else
        echo ""
    fi
}

check_permissions_status() {
    local missing=()
    local current_user="$CACHED_USER_EMAIL"
    
    # Check if user has admin access (Owner/Editor) first
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/owner OR bindings.role:roles/editor" 2>/dev/null | grep -q "user:$current_user"; then
        # User has admin access - no need to check individual roles
        echo ""
        return 0
    fi
    
    # Check individual roles for non-admin users
    local developer_roles=(
        "roles/run.admin"
        "roles/cloudsql.client"
        "roles/cloudsql.admin"
        "roles/secretmanager.secretAccessor"
        "roles/artifactregistry.writer"
        "roles/iam.serviceAccountUser"
        "roles/cloudbuild.builds.editor"
        "roles/viewer"
    )
    
    # Check required permissions for personal deployment
    for role in "${developer_roles[@]}"; do
        if ! gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --format="value(bindings.role,bindings.members)" \
            --filter="bindings.role:$role" 2>/dev/null | grep -q "user:$current_user"; then
            missing+=("$role")
        fi
    done
    
    # Handle empty array safely
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "$(IFS=',' ; echo "${missing[*]}")"
    else
        echo ""
    fi
}

# Generate Slack message for access request
generate_slack_message() {
    local developer_email="$1"
    local missing_apis="$2"
    local missing_permissions="$3"
    
    echo ""
    echo "🚫 Permission denied. Request access via #access-request:"
    echo ""
    echo "**Access Request for Agent Platform**"
    echo "Developer: $developer_email"
    echo "Project: $PROJECT_ID"
    if [[ -n "$missing_apis" ]]; then
        echo "APIs needed: $missing_apis"
    fi
    if [[ -n "$missing_permissions" ]]; then
        echo "Permissions needed: $missing_permissions"
    fi
    echo "Admin command: \`./scripts/gcp/add-developer.sh $developer_email\`"
    echo "@Simen please grant access 🙏"
    echo ""
    echo "After access is granted, re-run: make gcp setup"
    echo ""
}

check_database_status() {
    local instance_name="agent-postgres"
    local db_name="agents"
    local db_user="agents"
    local missing=()
    
    # Check instance
    if ! gcloud sql instances describe "$instance_name" --quiet >/dev/null 2>&1; then
        missing+=("instance")
    else
        # Check database
        if ! gcloud sql databases describe "$db_name" --instance="$instance_name" --quiet >/dev/null 2>&1; then
            missing+=("database")
        fi
        
        # Check user
        if ! gcloud sql users describe "$db_user" --instance="$instance_name" --quiet >/dev/null 2>&1; then
            missing+=("user")
        fi
    fi
    
    # Handle empty array safely
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "$(IFS=',' ; echo "${missing[*]}")"
    else
        echo ""
    fi
}

check_secrets_status() {
    local missing=()
    
    if ! gcloud secrets describe npmrc-secret --quiet >/dev/null 2>&1; then
        missing+=("npmrc-secret")
    fi
    
    # Handle empty array safely
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "$(IFS=',' ; echo "${missing[*]}")"
    else
        echo ""
    fi
}

check_iap_status() {
    local missing=()
    
    # Check if IAP API is enabled
    if ! gcloud services list --enabled --filter="name:iap.googleapis.com" --format="value(name)" 2>/dev/null | grep -q "iap.googleapis.com"; then
        missing+=("iap-api")
    fi
    
    # Handle empty array safely
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "$(IFS=',' ; echo "${missing[*]}")"
    else
        echo ""
    fi
}

show_setup_status() {
    echo "🔍 Agent Platform Setup Status"
    echo "📍 Project: ${PROJECT_ID:-"Not selected"}"
    echo "🌍 Region:  $REGION"
    echo ""
    
    # Check prerequisites
    local prereq_result=$(check_prerequisites_status)
    local prereq_missing=$(echo "$prereq_result" | cut -d'|' -f1)
    local prereq_warnings=$(echo "$prereq_result" | cut -d'|' -f2)
    
    printf "🛠️  Prerequisites:     "
    if [[ -z "$prereq_missing" ]]; then
        echo "✅ All good"
    else
        echo "❌ Missing: $prereq_missing"
    fi
    
    # Check APIs (only if prerequisites are met)
    if [[ -z "$prereq_missing" ]]; then
        local apis_missing=$(check_apis_status)
        printf "🔌 APIs:               "
        if [[ -z "$apis_missing" ]]; then
            echo "✅ All enabled"
        else
            echo "❌ Missing: $apis_missing"
        fi
        
        # Check permissions
        local perms_missing=$(check_permissions_status)
        printf "🔑 Permissions:        "
        if [[ -z "$perms_missing" ]]; then
            # Check if admin access or individual roles
            local current_user="$CACHED_USER_EMAIL"
            if gcloud projects get-iam-policy "$PROJECT_ID" \
                --flatten="bindings[].members" \
                --format="value(bindings.role,bindings.members)" \
                --filter="bindings.role:roles/owner OR bindings.role:roles/editor" 2>/dev/null | grep -q "user:$current_user"; then
                echo "✅ Admin access (Owner/Editor)"
            else
                echo "✅ All granted"
            fi
        else
            echo "❌ Missing: $perms_missing"
        fi
        
        # Check database
        local db_missing=$(check_database_status)
        printf "🗄️  Database:           "
        if [[ -z "$db_missing" ]]; then
            echo "✅ Ready"
        else
            echo "❌ Missing: $db_missing"
        fi
        
        # Check secrets
        local secrets_missing=$(check_secrets_status)
        printf "🔐 Secrets:            "
        if [[ -z "$secrets_missing" ]]; then
            echo "✅ Ready"
        else
            echo "❌ Missing: $secrets_missing"
        fi
        
        # Check IAP
        local iap_missing=$(check_iap_status)
        printf "🛡️  IAP (Security):     "
        if [[ -z "$iap_missing" ]]; then
            echo "✅ Ready"
        else
            echo "❌ Missing: $iap_missing"
        fi
    else
        printf "🔌 APIs:               ⏸️  Skipped (fix prerequisites first)\n"
        printf "🔑 Permissions:        ⏸️  Skipped (fix prerequisites first)\n" 
        printf "🗄️  Database:           ⏸️  Skipped (fix prerequisites first)\n"
        printf "🔐 Secrets:            ⏸️  Skipped (fix prerequisites first)\n"
    fi
    
    echo ""
}

show_setup_menu() {
    show_setup_status
    
    echo "🎯 Ready to setup and deploy?"
    echo ""
    echo " 1) 🚀 Quick Setup → Deploy (recommended)"
    echo "    Sets up missing components then automatically deploys"
    echo ""
    echo " 2) 🔧 Setup missing components only"
    echo " 3) 🔌 Setup APIs and permissions only"
    echo " 4) 🗄️  Setup database only"
    echo " 5) 🔐 Setup secrets only"
    echo " 6) 🛡️  Setup IAP (security) only"
    echo " 7) 🔍 Refresh status check"
    echo " 0) ❌ Exit"
    echo ""
    
    while true; do
        read -p "Select option (0-7): " choice
        
        case $choice in
            1)
                echo "✅ Selected: Quick setup → deploy"
                MISSING_ONLY=true
                break
                ;;
            2)
                echo "✅ Selected: Setup missing components only"
                MISSING_ONLY=true
                break
                ;;
            3)
                echo "✅ Selected: Setup APIs and permissions"
                PERMISSIONS_ONLY=true
                break
                ;;
            4)
                echo "✅ Selected: Setup database only"
                DATABASE_ONLY=true
                break
                ;;
            5)
                echo "✅ Selected: Setup secrets only"
                SECRETS_ONLY=true
                break
                ;;
            6)
                echo "✅ Selected: Setup IAP (security) only"
                setup_personal_iap
                break
                ;;
            7)
                echo ""
                show_setup_status
                echo "🎯 Ready to setup and deploy?"
                echo ""
                echo " 1) 🚀 Quick Setup → Deploy (recommended)"
                echo "    Sets up missing components then automatically deploys"
                echo ""
                echo " 2) 🔧 Setup missing components only"
                echo " 3) 🔌 Setup APIs and permissions only"
                echo " 4) 🗄️  Setup database only"
                echo " 5) 🔐 Setup secrets only"
                echo " 6) 🛡️  Setup IAP (security) only"
                echo " 7) 🔍 Refresh status check"
                echo " 0) ❌ Exit"
                echo ""
                ;;
            0)
                echo "👋 Setup cancelled"
                exit 0
                ;;
            *)
                echo "❌ Invalid choice. Please enter 0-7"
                ;;
        esac
    done
    echo ""
}

# Setup functions

setup_permissions() {
    log_step "Checking permissions and access..."
    
    # Get current user
    local current_user=$(gcloud config get-value account 2>/dev/null)
    log_info "Current user: $current_user"
    
    # Check APIs first
    local missing_apis=$(check_apis_status)
    local missing_permissions=$(check_permissions_status)
    
    # If user has admin access, try to setup everything
    local has_admin_access=false
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/owner OR bindings.role:roles/editor" 2>/dev/null | grep -q "user:$current_user"; then
        has_admin_access=true
        log_info "Admin access detected - will enable APIs and check permissions"
    fi
    
    # If missing permissions and not admin, generate Slack message
    if [[ (-n "$missing_apis" || -n "$missing_permissions") && "$has_admin_access" == "false" ]]; then
        echo ""
        log_error "🚫 Insufficient permissions for setup"
        echo ""
        echo "You're missing required permissions to set up the Agent Platform."
        echo "This is normal in zero-trust environments."
        echo ""
        
        generate_slack_message "$current_user" "$missing_apis" "$missing_permissions"
        
        echo "ℹ️  What happens next:"
        echo "  1. Copy the message above to #access-request in Slack"
        echo "  2. Wait for admin to grant access"
        echo "  3. Re-run this script: make gcp setup"
        echo ""
        
        exit 0
    fi
    
    # Admin path - enable APIs if needed (simplified for personal accounts)
    if [[ "$has_admin_access" == "true" && -n "$missing_apis" ]]; then
        log_info "Enabling required APIs..."
        local required_apis=(
            "cloudbuild.googleapis.com"
            "run.googleapis.com"
            "sqladmin.googleapis.com"
            "secretmanager.googleapis.com"
            "artifactregistry.googleapis.com"
            "iam.googleapis.com"
            "cloudresourcemanager.googleapis.com"
        )
        
        for api in "${required_apis[@]}"; do
            if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
                log_info "Enabling $api..."
                if gcloud services enable "$api" --quiet 2>/dev/null; then
                    log_success "Enabled $api"
                else
                    log_warning "Failed to enable $api"
                fi
            fi
        done
        
        # Wait for APIs to propagate
        log_info "Waiting 10 seconds for APIs to fully activate..."
        sleep 10
    fi
    
    log_success "Permissions and APIs ready for personal account deployment"
}

setup_database() {
    log_step "Setting up Cloud SQL database..."
    
    local instance_name="agent-postgres"
    local db_name="agents"
    local db_user="agents"
    local db_password="agents"
    
    # Check if instance exists
    if gcloud sql instances describe "$instance_name" --quiet >/dev/null 2>&1; then
        log_success "Database instance '$instance_name' already exists"
    else
        log_info "Creating PostgreSQL instance '$instance_name'..."
        log_warning "This will take 3-5 minutes..."
        
        if gcloud sql instances create "$instance_name" \
            --database-version=POSTGRES_14 \
            --tier=db-f1-micro \
            --region="$REGION" \
            --root-password="$db_password" \
            --storage-type=SSD \
            --storage-size=10GB \
            --storage-auto-increase \
            --backup-start-time=03:00 \
            --maintenance-window-day=SUN \
            --maintenance-window-hour=04 \
            --quiet; then
            log_success "Database instance created"
        else
            log_error "Failed to create database instance"
            return 1
        fi
    fi
    
    # Check if database exists
    if gcloud sql databases describe "$db_name" --instance="$instance_name" --quiet >/dev/null 2>&1; then
        log_success "Database '$db_name' already exists"
    else
        log_info "Creating database '$db_name'..."
        gcloud sql databases create "$db_name" --instance="$instance_name" --quiet
        log_success "Database created"
    fi
    
    # Check if user exists, update password regardless
    if gcloud sql users describe "$db_user" --instance="$instance_name" --quiet >/dev/null 2>&1; then
        log_info "Updating password for user '$db_user'..."
        gcloud sql users set-password "$db_user" --instance="$instance_name" --password="$db_password" --quiet
    else
        log_info "Creating user '$db_user'..."
        gcloud sql users create "$db_user" --instance="$instance_name" --password="$db_password" --quiet
    fi
    
    log_success "Database setup complete"
    
    # Get instance IP
    local instance_ip=$(gcloud sql instances describe "$instance_name" --format="value(ipAddresses[0].ipAddress)" --quiet 2>/dev/null)
    
    echo
    log_info "Database Connection Info:"
    echo "🗄️  Instance: $instance_name"
    echo "🌐 IP:       $instance_ip"
    echo "💾 Database: $db_name"
    echo "👤 User:     $db_user"
    echo "🔑 Password: $db_password"
    echo
}

setup_secrets() {
    log_step "Setting up secrets..."
    
    # Check if npmrc-secret exists
    if gcloud secrets describe npmrc-secret --quiet >/dev/null 2>&1; then
        log_success "npmrc-secret already exists"
    else
        # Check if ~/.npmrc exists
        if [[ ! -f ~/.npmrc ]]; then
            log_error "~/.npmrc not found. Create it first with your npm authentication token:"
            echo
            echo "echo '//npm.pkg.github.com/:_authToken=YOUR_TOKEN' > ~/.npmrc"
            echo
            echo "Then run: gcloud secrets create npmrc-secret --data-file=~/.npmrc"
            echo
            read -p "Continue after creating ~/.npmrc and secret? (y/n): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log_error "Setup paused. Create ~/.npmrc and npmrc-secret first."
                exit 1
            fi
            
            # Check again
            if gcloud secrets describe npmrc-secret --quiet >/dev/null 2>&1; then
                log_success "npmrc-secret found"
            else
                log_error "npmrc-secret still not found. Please create it manually."
                exit 1
            fi
        else
            log_info "Creating npmrc-secret from ~/.npmrc..."
            gcloud secrets create npmrc-secret --data-file=~/.npmrc --quiet
            log_success "npmrc-secret created"
        fi
    fi
    
    log_success "Secrets setup complete"
}

setup_personal_iap() {
    log_step "Setting up personal IAP configuration..."
    
    local current_user_email=$(gcloud config get-value account 2>/dev/null)
    if [[ -z "$current_user_email" ]]; then
        log_error "Unable to get current user email"
        return 1
    fi
    
    log_info "Configuring IAP for your personal instances..."
    log_info "Your email: $current_user_email"
    
    # Enable IAP API
    log_info "Enabling IAP API..."
    if gcloud services enable iap.googleapis.com --quiet; then
        log_success "IAP API enabled"
    else
        log_warning "IAP API may already be enabled"
    fi
    
    # Wait for API to propagate
    log_info "Waiting for IAP API to fully activate..."
    sleep 5
    
    log_success "Personal IAP configuration ready"
    
    echo ""
    log_info "IAP Setup Complete:"
    echo "🔐 When you deploy your personal instances, IAP will be enabled automatically"
    echo "👤 You will be the owner and can manage access to your instances"
    echo "🛡️  Your instances: agent-server-$(echo "$current_user_email" | cut -d'@' -f1 | tr '.' '-'), workroom-$(echo "$current_user_email" | cut -d'@' -f1 | tr '.' '-')"
    echo ""
    echo "📋 Manage your IAP access later:"
    echo "   ./scripts/gcp/manage-my-iap.sh add colleague@company.com"
    echo "   ./scripts/gcp/manage-my-iap.sh list"
    echo ""
}

setup_missing_components() {
    log_step "Setting up missing components only..."
    
    # Check what's missing and setup accordingly
    local prereq_result=$(check_prerequisites_status)
    local prereq_missing=$(echo "$prereq_result" | cut -d'|' -f1)
    
    if [[ -n "$prereq_missing" ]]; then
        log_error "Prerequisites missing: $prereq_missing"
        echo "Please fix prerequisites first, then re-run setup."
        exit 1
    fi
    
    local apis_missing=$(check_apis_status)
    local perms_missing=$(check_permissions_status)
    local db_missing=$(check_database_status)
    local secrets_missing=$(check_secrets_status)
    local iap_missing=$(check_iap_status)
    
    if [[ -n "$apis_missing" || -n "$perms_missing" ]]; then
        setup_permissions
    fi
    
    if [[ -n "$db_missing" ]]; then
        setup_database
    fi
    
    if [[ -n "$secrets_missing" ]]; then
        setup_secrets
    fi
    
    if [[ -n "$iap_missing" ]]; then
        setup_personal_iap
    fi
    
    if [[ -z "$apis_missing" && -z "$perms_missing" && -z "$db_missing" && -z "$secrets_missing" && -z "$iap_missing" ]]; then
        log_success "All components already setup! ✨"
    fi
}

# Main execution
main() {
    # Handle check-only mode
    if [[ "$CHECK_ONLY" == "true" ]]; then
        # Run minimal prerequisites check for project selection
        check_prerequisites
        PROJECT_ID="$GCLOUD_PROJECT"
        show_setup_status
        exit 0
    fi
    
    # Show interactive menu if no specific options provided
    if [[ "$SHOW_MENU" == "true" ]]; then
        echo "🛠️  Agent Platform GCP Setup & Deploy"
        echo "   Streamlined setup for personal account deployment"
        echo ""
        
        # Run prerequisites check (includes project selection)
        check_prerequisites
        PROJECT_ID="$GCLOUD_PROJECT"
        
        # Check if user has admin access for auto-setup
        local current_user=$(gcloud config get-value account 2>/dev/null)
        if gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --format="value(bindings.role,bindings.members)" \
            --filter="bindings.role:roles/owner OR bindings.role:roles/editor" 2>/dev/null | grep -q "user:$current_user"; then
            
            echo "🔑 Admin access detected ($current_user)"
            echo "🚀 Auto-proceeding with setup → deploy..."
            echo ""
            MISSING_ONLY=true
        else
            show_setup_menu
        fi
    else
        echo "🛠️  Agent Platform GCP Setup & Deploy"
        echo "📍 Project: ${GCLOUD_PROJECT:-"(will be selected)"}"
        echo "🌍 Region:  $REGION"
        echo ""
        
        # Run prerequisites check (includes project selection)
        check_prerequisites
        PROJECT_ID="$GCLOUD_PROJECT"
    fi
    
    # Execute based on options
    if [[ "$SETUP_ALL" == "true" ]]; then
        setup_permissions
        setup_database
        setup_secrets
    elif [[ "$MISSING_ONLY" == "true" ]]; then
        setup_missing_components
    else
        if [[ "$PERMISSIONS_ONLY" == "true" ]]; then
            setup_permissions
        fi
        
        if [[ "$DATABASE_ONLY" == "true" ]]; then
            setup_database
        fi
        
        if [[ "$SECRETS_ONLY" == "true" ]]; then
            setup_secrets
        fi
    fi
    
    # Only show completion and deploy if we actually ran setup
    if [[ "$SETUP_ALL" == "true" || "$MISSING_ONLY" == "true" || "$PERMISSIONS_ONLY" == "true" || "$DATABASE_ONLY" == "true" || "$SECRETS_ONLY" == "true" ]]; then
        echo
        log_success "✅ Setup complete! Starting deployment..."
        echo
        echo "🚀 Proceeding to deployment menu..."
        echo ""
        
        # Run deployment through make (no flags needed)
        echo "▶️  Executing: make gcp deploy"
        echo ""
        exec make gcp deploy
    fi
}

# Run main function
main "$@" 