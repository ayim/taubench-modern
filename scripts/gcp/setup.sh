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
    echo "GCP setup script for Agent Platform"
    echo
    echo "Options:"
    echo "  --check             Check current setup status"
    echo "  --database-only     Setup database only"
    echo "  --secrets-only      Setup secrets only"
    echo "  --permissions       Setup permissions only"
    echo "  --missing-only      Setup only missing components"
    echo "  --all              Complete setup"
    echo "  --help             Show this help"
    echo
    echo "Examples:"
    echo "  $0                          # Interactive menu (default)"
    echo "  $0 --check                  # Check what's setup and missing"
    echo "  $0 --all                    # Complete setup"
    echo "  $0 --missing-only           # Setup only what's missing"
    echo "  $0 --database-only          # Just create database"
    echo "  $0 --permissions            # Just setup permissions"
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
    
    # Check project selection
    if [[ -z "${GCLOUD_PROJECT:-}" ]] && [[ -z "$(gcloud config get-value project 2>/dev/null)" ]]; then
        missing+=("GCP project not selected")
    fi
    
    printf "%s|%s" "$(IFS=',' ; echo "${missing[*]}")" "$(IFS=',' ; echo "${warnings[*]}")"
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
    
    echo "$(IFS=',' ; echo "${missing[*]}")"
}

check_permissions_status() {
    local missing=()
    local current_user=$(gcloud config get-value account 2>/dev/null)
    local build_sa="${PROJECT_ID}-compute@developer.gserviceaccount.com"
    
    # Try to get the actual compute service account
    local actual_build_sa=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null)
    if [[ -n "$actual_build_sa" ]]; then
        build_sa="${actual_build_sa}-compute@developer.gserviceaccount.com"
    fi
    
    local roles=(
        "roles/secretmanager.secretAccessor"
        "roles/cloudsql.client"
        "roles/artifactregistry.writer"
    )
    
    for role in "${roles[@]}"; do
        if ! gcloud projects get-iam-policy "$PROJECT_ID" --flatten="bindings[].members" --format="table(bindings.role)" --filter="bindings.role:$role AND bindings.members:serviceAccount:$build_sa" 2>/dev/null | grep -q "$role"; then
            missing+=("$role")
        fi
    done
    
    echo "$(IFS=',' ; echo "${missing[*]}")"
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
    
    echo "$(IFS=',' ; echo "${missing[*]}")"
}

check_secrets_status() {
    local missing=()
    
    if ! gcloud secrets describe npmrc-secret --quiet >/dev/null 2>&1; then
        missing+=("npmrc-secret")
    fi
    
    echo "$(IFS=',' ; echo "${missing[*]}")"
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
            echo "✅ All granted"
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
    
    echo "🎯 What would you like to do?"
    echo ""
    echo " 1) 🚀 Complete setup (everything)"
    echo " 2) 🔧 Setup only missing components ⭐ (recommended)"
    echo " 3) 🔌 Setup APIs and permissions only"
    echo " 4) 🗄️  Setup database only"
    echo " 5) 🔐 Setup secrets only"
    echo " 6) 🔍 Refresh status check"
    echo " 0) ❌ Exit"
    echo ""
    
    while true; do
        read -p "Select option (0-6): " choice
        
        case $choice in
            1)
                echo "✅ Selected: Complete setup"
                SETUP_ALL=true
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
                echo ""
                show_setup_status
                echo "🎯 What would you like to do?"
                echo ""
                echo " 1) 🚀 Complete setup (everything)"
                echo " 2) 🔧 Setup only missing components"
                echo " 3) 🔌 Setup APIs and permissions only"
                echo " 4) 🗄️  Setup database only"
                echo " 5) 🔐 Setup secrets only"
                echo " 6) 🔍 Refresh status check"
                echo " 0) ❌ Exit"
                echo ""
                ;;
            0)
                echo "👋 Setup cancelled"
                exit 0
                ;;
            *)
                echo "❌ Invalid choice. Please enter 0-6"
                ;;
        esac
    done
    echo ""
}

# Setup functions

setup_permissions() {
    log_step "Setting up APIs and permissions..."
    
    # First, ensure APIs are enabled (critical for all subsequent operations)
    log_info "Ensuring required APIs are enabled..."
    local required_apis=(
        "cloudbuild.googleapis.com"
        "run.googleapis.com"
        "sqladmin.googleapis.com"
        "secretmanager.googleapis.com"
        "artifactregistry.googleapis.com"
        "iam.googleapis.com"
        "cloudresourcemanager.googleapis.com"
    )
    
    local failed_apis=()
    for api in "${required_apis[@]}"; do
        if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
            log_info "Enabling $api..."
            if gcloud services enable "$api" --quiet 2>/dev/null; then
                log_success "Enabled $api"
            else
                failed_apis+=("$api")
                log_warning "Failed to enable $api (permission denied)"
            fi
        else
            log_success "$api already enabled"
        fi
    done
    
    # Handle failed APIs
    if [[ ${#failed_apis[@]} -gt 0 ]]; then
        echo
        log_error "⚠️  Some APIs couldn't be enabled automatically."
        echo
        echo "🔒 Request your GCP admin to enable these APIs:"
        for api in "${failed_apis[@]}"; do
            echo "  ❌ $api"
        done
        echo
        echo "📋 Copy this for your admin:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        for api in "${failed_apis[@]}"; do
            echo "gcloud services enable $api --project=$PROJECT_ID"
        done
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo
        
        read -p "Continue after admin enables APIs? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Setup paused. Re-run script after APIs are enabled."
            exit 1
        fi
    fi
    
    # Wait a moment for APIs to propagate
    if [[ ${#failed_apis[@]} -eq 0 ]]; then
        log_info "Waiting 10 seconds for APIs to fully activate..."
        sleep 10
    fi
    
    # Now set up service account permissions
    local current_user=$(gcloud config get-value account 2>/dev/null)
    local build_sa="${PROJECT_ID}-compute@developer.gserviceaccount.com"
    
    # Try to get the actual compute service account
    local actual_build_sa=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null)
    if [[ -n "$actual_build_sa" ]]; then
        build_sa="${actual_build_sa}-compute@developer.gserviceaccount.com"
    fi
    
    log_info "Current user: $current_user"
    log_info "Build service account: $build_sa"
    
    # Required roles for the build service account
    local roles=(
        "roles/secretmanager.secretAccessor"
        "roles/cloudsql.client"
        "roles/artifactregistry.writer"
    )
    
    log_info "Granting required roles to build service account..."
    
    local failed_roles=()
    for role in "${roles[@]}"; do
        if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$build_sa" \
            --role="$role" \
            --quiet >/dev/null 2>&1; then
            log_success "Granted $role to build service account"
        else
            failed_roles+=("$role")
            log_warning "Failed to grant $role (permission denied)"
        fi
    done
    
    if [[ ${#failed_roles[@]} -gt 0 ]]; then
        echo
        log_error "⚠️  Some permissions couldn't be granted automatically."
        echo
        echo "🔒 Request your GCP admin to grant these roles to service account:"
        echo "   $build_sa"
        echo
        for role in "${failed_roles[@]}"; do
            echo "  ❌ $role"
        done
        echo
        echo "📋 Copy this for your admin:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        for role in "${failed_roles[@]}"; do
            echo "gcloud projects add-iam-policy-binding $PROJECT_ID \\"
            echo "  --member='serviceAccount:$build_sa' \\"
            echo "  --role='$role'"
            echo
        done
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        read -p "Continue after admin grants permissions? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Setup paused. Re-run script after permissions are granted."
            exit 1
        fi
    fi
    
    log_success "APIs and permissions setup complete"
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
    
    if [[ -n "$apis_missing" || -n "$perms_missing" ]]; then
        setup_permissions
    fi
    
    if [[ -n "$db_missing" ]]; then
        setup_database
    fi
    
    if [[ -n "$secrets_missing" ]]; then
        setup_secrets
    fi
    
    if [[ -z "$apis_missing" && -z "$perms_missing" && -z "$db_missing" && -z "$secrets_missing" ]]; then
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
        echo "🛠 Agent Platform GCP Setup"
        echo ""
        
        # Run prerequisites check (includes project selection)
        check_prerequisites
        PROJECT_ID="$GCLOUD_PROJECT"
        
        show_setup_menu
    else
        echo "🛠 Agent Platform GCP Setup"
        echo "📍 Project: ${GCLOUD_PROJECT:-"(will be selected)"}"
        echo "🌍 Region:  $REGION"
        echo
        
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
    
    # Only show completion message if we actually ran setup
    if [[ "$SETUP_ALL" == "true" || "$MISSING_ONLY" == "true" || "$PERMISSIONS_ONLY" == "true" || "$DATABASE_ONLY" == "true" || "$SECRETS_ONLY" == "true" ]]; then
        echo
        log_success "Setup complete! You can now run:"
        echo "  ./scripts/gcp/deploy.sh"
        echo
    fi
}

# Run main function
main "$@" 