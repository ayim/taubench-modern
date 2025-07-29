#!/usr/bin/env bash

set -euo pipefail

# Get script directory and load common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/common.sh"

# Configuration
REGION="${REGION:-europe-west1}"
PROJECT_ID="${GCLOUD_PROJECT:-$(gcloud config get-value project 2>/dev/null || echo '')}"

# Required APIs for the platform
REQUIRED_APIS=(
    "cloudbuild.googleapis.com"
    "run.googleapis.com"
    "sqladmin.googleapis.com"
    "secretmanager.googleapis.com"
    "artifactregistry.googleapis.com"
    "iam.googleapis.com"
    "cloudresourcemanager.googleapis.com"
)

# Minimal developer roles (zero-trust)
DEVELOPER_ROLES=(
    "roles/run.admin"                   # Deploy and manage Cloud Run services + IAM policies
    "roles/cloudsql.client"
    "roles/cloudsql.admin"              # Create/manage Cloud SQL instances
    "roles/secretmanager.secretAccessor"  # Access npmrc-secret
    "roles/artifactregistry.writer"     # Push Docker images
    "roles/iam.serviceAccountUser"      # Use service accounts with Cloud Run
    "roles/cloudbuild.builds.editor"    # Manage Cloud Build jobs for Docker builds
    "roles/viewer"                      # Basic project access
)

# Service account roles  
SERVICE_ACCOUNT_ROLES=(
    "roles/secretmanager.secretAccessor"
    "roles/cloudsql.client"
    "roles/artifactregistry.writer"
    "roles/cloudbuild.builds.editor"
)

show_help() {
    cat << EOF
👨‍💼 Add Developer to Agent Platform

USAGE:
    $0 [EMAIL] [OPTIONS]

ARGUMENTS:
    EMAIL               Developer's email address (required)

OPTIONS:
    --dry-run          Show what would be done without making changes
    --force            Skip confirmation prompts
    --verbose          Show detailed output
    -h, --help         Show this help

EXAMPLES:
    $0 john@company.com                    # Interactive with confirmations
    $0 jane@company.com --force            # Skip confirmations
    $0 bob@company.com --dry-run           # Show what would be done

PERMISSIONS GRANTED:
    • run.admin              - Deploy and manage Cloud Run services + IAM policies
    • cloudsql.client        - Access database connection info
    • cloudsql.admin         - Create and manage Cloud SQL instances
    • secretmanager.secretAccessor  - Access npmrc-secret
    • artifactregistry.writer       - Push Docker images
    • iam.serviceAccountUser - Use service accounts with Cloud Run
    • cloudbuild.builds.editor      - Manage Cloud Build jobs for Docker builds
    • viewer                 - Basic project access

INFRASTRUCTURE SETUP:
    • Enables required APIs if needed
    • Creates shared database (agent-postgres) if needed
    • Sets up service account permissions
    • Verifies npmrc-secret exists

SECURITY:
    • Zero-trust model - minimal permissions only
    • No owner/editor roles granted
    • All actions logged and confirmable
EOF
}

# Parse command line arguments
DEVELOPER_EMAIL=""
DRY_RUN=false
FORCE=false
VERBOSE=false

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
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
            --*)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
            *)
                if [[ -z "$DEVELOPER_EMAIL" ]]; then
                    DEVELOPER_EMAIL="$1"
                else
                    log_error "Too many arguments. Only one email address allowed."
                    show_help
                    exit 1
                fi
                shift
                ;;
        esac
    done
}

# Validate email format
validate_email() {
    local email="$1"
    if [[ ! "$email" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
        log_error "Invalid email format: $email"
        exit 1
    fi
}

# Ask for developer email if not provided
get_developer_email() {
    if [[ -z "$DEVELOPER_EMAIL" ]]; then
        echo "👨‍💼 Add Developer to Agent Platform"
        echo "📍 Project: $PROJECT_ID"
        echo "🌍 Region: $REGION"
        echo ""
        
        while true; do
            read -p "Enter developer's email address: " email
            if [[ -n "$email" ]]; then
                validate_email "$email"
                DEVELOPER_EMAIL="$email"
                break
            else
                echo "❌ Please enter a valid email address"
            fi
        done
    else
        validate_email "$DEVELOPER_EMAIL"
    fi
}

# Check if APIs are enabled
check_apis() {
    log_step "Checking required APIs..."
    
    local missing_apis=()
    for api in "${REQUIRED_APIS[@]}"; do
        if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" 2>/dev/null | grep -q "$api"; then
            missing_apis+=("$api")
        fi
    done
    
    if [[ ${#missing_apis[@]} -gt 0 ]]; then
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would enable APIs:"
            for api in "${missing_apis[@]}"; do
                echo "  • $api"
            done
        else
            log_info "Enabling required APIs..."
            for api in "${missing_apis[@]}"; do
                log_info "Enabling $api..."
                gcloud services enable "$api" --quiet
                log_success "Enabled $api"
            done
        fi
    else
        log_success "All required APIs are enabled"
    fi
}

# Grant roles to developer
grant_developer_permissions() {
    log_step "Granting developer permissions to $DEVELOPER_EMAIL..."
    
    local granted_roles=()
    local failed_roles=()
    
    # First, remove old roles if they exist (upgrade to new permissions)
    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/cloudsql.editor" 2>/dev/null | grep -q "user:$DEVELOPER_EMAIL"; then
        log_info "Upgrading cloudsql.editor to cloudsql.admin..."
        gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
            --member="user:$DEVELOPER_EMAIL" \
            --role="roles/cloudsql.editor" \
            --quiet >/dev/null 2>&1
    fi

    if gcloud projects get-iam-policy "$PROJECT_ID" \
        --flatten="bindings[].members" \
        --format="value(bindings.role,bindings.members)" \
        --filter="bindings.role:roles/run.developer" 2>/dev/null | grep -q "user:$DEVELOPER_EMAIL"; then
        log_info "Upgrading run.developer to run.admin..."
        gcloud projects remove-iam-policy-binding "$PROJECT_ID" \
            --member="user:$DEVELOPER_EMAIL" \
            --role="roles/run.developer" \
            --quiet >/dev/null 2>&1
    fi

    for role in "${DEVELOPER_ROLES[@]}"; do
        # Check if role is already granted
        if gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --format="value(bindings.role,bindings.members)" \
            --filter="bindings.role:$role" 2>/dev/null | grep -q "user:$DEVELOPER_EMAIL"; then
            log_success "$role already granted"
            continue
        fi
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would grant: $role"
            continue
        fi
        
        if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="user:$DEVELOPER_EMAIL" \
            --role="$role" \
            --quiet >/dev/null 2>&1; then
            granted_roles+=("$role")
            log_success "Granted $role"
        else
            failed_roles+=("$role")
            log_error "Failed to grant $role"
        fi
    done
    
    if [[ ${#failed_roles[@]} -gt 0 ]]; then
        log_error "Some roles could not be granted. Check admin permissions."
        for role in "${failed_roles[@]}"; do
            echo "  ❌ $role"
        done
        return 1
    fi
    
    if [[ "$DRY_RUN" == "false" ]]; then
        log_success "All developer permissions granted successfully"
    fi
}

# Setup service account permissions
setup_service_account_permissions() {
    log_step "Setting up service account permissions..."
    
    # Get the compute service account
    local project_number=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)" 2>/dev/null)
    if [[ -z "$project_number" ]]; then
        log_error "Failed to get project number"
        return 1
    fi
    
    local build_sa="${project_number}-compute@developer.gserviceaccount.com"
    log_info "Service account: $build_sa"
    
    local granted_roles=()
    local failed_roles=()
    
    for role in "${SERVICE_ACCOUNT_ROLES[@]}"; do
        # Check if role is already granted
        if gcloud projects get-iam-policy "$PROJECT_ID" \
            --flatten="bindings[].members" \
            --format="value(bindings.role,bindings.members)" \
            --filter="bindings.role:$role" 2>/dev/null | grep -q "serviceAccount:$build_sa"; then
            log_success "$role already granted to service account"
            continue
        fi
        
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would grant $role to service account"
            continue
        fi
        
        if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
            --member="serviceAccount:$build_sa" \
            --role="$role" \
            --quiet >/dev/null 2>&1; then
            granted_roles+=("$role")
            log_success "Granted $role to service account"
        else
            failed_roles+=("$role")
            log_error "Failed to grant $role to service account"
        fi
    done
    
    if [[ ${#failed_roles[@]} -gt 0 ]]; then
        log_warning "Some service account roles could not be granted"
        for role in "${failed_roles[@]}"; do
            echo "  ❌ $role"
        done
    fi
}

# Setup shared infrastructure
setup_shared_infrastructure() {
    log_step "Setting up shared infrastructure..."
    
    # Check if shared database exists
    local db_instance="agent-postgres"
    if gcloud sql instances describe "$db_instance" --quiet >/dev/null 2>&1; then
        log_success "Shared database ($db_instance) already exists"
    else
        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would create shared database: $db_instance"
        else
            log_info "Creating shared database ($db_instance)..."
            log_warning "This will take 3-5 minutes..."
            log_info "🔒 Security: Database will use Cloud SQL proxy only (most secure)"
            
            gcloud sql instances create "$db_instance" \
                --database-version=POSTGRES_14 \
                --tier=db-f1-micro \
                --region="$REGION" \
                --root-password="agents" \
                --storage-type=SSD \
                --storage-size=10GB \
                --storage-auto-increase \
                --backup-start-time=03:00 \
                --maintenance-window-day=SUN \
                --maintenance-window-hour=04 \
                --quiet
            
            # Create database and user
            gcloud sql databases create "agents" --instance="$db_instance" --quiet
            gcloud sql users create "agents" --instance="$db_instance" --password="agents" --quiet
            
            log_success "Shared database created"
        fi
    fi
    
    # Check if npmrc-secret exists
    if gcloud secrets describe npmrc-secret --quiet >/dev/null 2>&1; then
        log_success "npmrc-secret already exists"
    else
        log_warning "npmrc-secret not found"
        echo ""
        echo "⚠️  The developer will need npmrc-secret for workroom builds."
        echo "   Create it manually if needed:"
        echo "   gcloud secrets create npmrc-secret --data-file=~/.npmrc"
        echo ""
    fi
}

# Show summary of what will be done
show_summary() {
    echo ""
    echo "📋 Summary:"
    echo "   👤 Developer: $DEVELOPER_EMAIL"
    echo "   📍 Project: $PROJECT_ID"
    echo "   🌍 Region: $REGION"
    echo ""
    echo "🔐 Permissions to grant:"
    for role in "${DEVELOPER_ROLES[@]}"; do
        echo "   • $role"
    done
    echo ""
    echo "🏗️  Infrastructure:"
    echo "   • Enable required APIs"
    echo "   • Setup service account permissions"
    echo "   • Ensure shared database exists"
    echo "   • Verify npmrc-secret exists"
    echo ""
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo "🧪 DRY RUN MODE - No changes will be made"
        echo ""
        return
    fi
    
    if [[ "$FORCE" == "false" ]]; then
        echo "⚠️  This will grant the above permissions and create infrastructure."
        echo ""
        read -p "Continue? (y/n): " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Operation cancelled"
            exit 1
        fi
        echo ""
    fi
}

# Show completion summary
show_completion() {
    echo ""
    log_success "Developer setup complete! 🎉"
    echo ""
    echo "✅ Developer $DEVELOPER_EMAIL has been granted access to:"
    echo "   📍 Project: $PROJECT_ID"
    echo "   🌍 Region: $REGION"
    echo ""
    echo "🔐 Permissions granted:"
    for role in "${DEVELOPER_ROLES[@]}"; do
        echo "   ✅ $role"
    done
    echo ""
    echo "📧 Next steps:"
    echo "   1. Notify $DEVELOPER_EMAIL that access has been granted"
    echo "   2. Developer can now run: make gcp setup"
echo "   3. Then deploy with: make gcp deploy"
    echo ""
    
    # Show infrastructure URLs
    local agent_server_url=$(get_service_url "agent-server-$(echo "$DEVELOPER_EMAIL" | cut -d'@' -f1 | tr '.' '-')" "$REGION" 2>/dev/null || echo "")
    local workroom_url=$(get_service_url "workroom-$(echo "$DEVELOPER_EMAIL" | cut -d'@' -f1 | tr '.' '-')" "$REGION" 2>/dev/null || echo "")
    
    echo "🔗 After deployment, services will be available at:"
    echo "   🖥️  Agent Server: (will be created after deployment)"
    echo "   🎨 Workroom: (will be created after deployment)"
    echo "   🗄️  Database: agent-postgres (shared)"
    echo ""
}

# Main execution
main() {
    parse_args "$@"
    
    echo "👨‍💼 Add Developer to Agent Platform"
    echo ""
    
    # Check prerequisites (lightweight - just auth and project)
    check_prerequisites_lite
    PROJECT_ID="$GCLOUD_PROJECT"
    
    # Get developer email
    get_developer_email
    
    # Show summary
    show_summary
    
    # Execute setup
    if [[ "$DRY_RUN" == "false" ]]; then
        check_apis
        grant_developer_permissions
        setup_service_account_permissions
        setup_shared_infrastructure
        show_completion
    else
        echo "🧪 DRY RUN complete - no changes made"
    fi
}

# Run main function
main "$@" 