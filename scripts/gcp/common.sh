#!/bin/bash

# Common functions for GCP deployment scripts

# Default configuration
REGION="${REGION:-europe-west1}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_step() {
    echo -e "${PURPLE}🔧 $1${NC}"
}

# Check if Homebrew is installed and install if needed (macOS)
ensure_homebrew() {
    if command -v brew >/dev/null 2>&1; then
        log_success "Homebrew is installed"
        return 0
    fi
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        log_warning "Homebrew not found, installing..."
        log_step "Installing Homebrew (this may take a few minutes)..."
        
        # Install Homebrew
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        
        # Add to PATH for current session
        if [[ -f "/opt/homebrew/bin/brew" ]]; then
            export PATH="/opt/homebrew/bin:$PATH"
        elif [[ -f "/usr/local/bin/brew" ]]; then
            export PATH="/usr/local/bin:$PATH"
        fi
        
        if command -v brew >/dev/null 2>&1; then
            log_success "Homebrew installed successfully"
        else
            log_error "Homebrew installation failed. Please install manually:"
            echo "https://brew.sh"
            exit 1
        fi
    else
        log_error "Homebrew auto-installation only supported on macOS. Install manually:"
        echo "https://brew.sh"
        exit 1
    fi
}

# Check if gcloud is installed and install if needed (macOS)
ensure_gcloud() {
    if command -v gcloud >/dev/null 2>&1; then
        log_success "gcloud CLI is installed"
        return 0
    fi
    
    log_warning "gcloud CLI not found"
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # Ensure Homebrew is available first
        ensure_homebrew
        
        log_step "Installing gcloud via Homebrew..."
        brew install --cask google-cloud-sdk
        
        # Add to PATH for current session
        if [[ -d "/usr/local/Caskroom/google-cloud-sdk" ]]; then
            export PATH="/usr/local/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin:$PATH"
        elif [[ -d "/opt/homebrew/Caskroom/google-cloud-sdk" ]]; then
            export PATH="/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/bin:$PATH"
        fi
        
        if command -v gcloud >/dev/null 2>&1; then
            log_success "gcloud installed via Homebrew"
        else
            log_error "gcloud installation failed. Install manually:"
            echo "https://cloud.google.com/sdk/docs/install"
            exit 1
        fi
    else
        log_error "Auto-installation only supported on macOS. Install gcloud manually:"
        echo "https://cloud.google.com/sdk/docs/install"
        exit 1
    fi
}

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

# Enhanced project selection
select_project() {
    log_info "Setting up GCP project..."
    
    # Check if project is already set
    local current_project=$(gcloud config get-value project 2>/dev/null)
    if [[ -n "$current_project" && "$current_project" != "(unset)" ]]; then
        echo "Current project: $current_project"
        read -p "Use current project '$current_project'? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            export GCLOUD_PROJECT="$current_project"
            return 0
        fi
    fi
    
    # List available projects
    log_info "Fetching your GCP projects..."
    local projects=$(gcloud projects list --format="value(projectId,name)" --filter="lifecycleState:ACTIVE" 2>/dev/null)
    
    if [[ -z "$projects" ]]; then
        log_error "No accessible projects found. You may need to:"
        echo "  1. Create a new project: gcloud projects create PROJECT_ID"
        echo "  2. Get access to an existing project"
        echo "  3. Use a service account with project access"
        return 1
    fi
    
    echo
    log_info "Available projects:"
    echo
    
    local project_array=()
    local i=1
    while IFS=$'\t' read -r project_id project_name; do
        printf "%2d) %-30s %s\n" "$i" "$project_id" "$project_name"
        project_array+=("$project_id")
        ((i++))
    done <<< "$projects"
    
    echo
    echo " 0) Create new project"
    echo " q) Quit"
    echo
    
    while true; do
        read -p "Select project (number): " choice
        
        if [[ "$choice" == "q" ]]; then
            log_error "Setup cancelled"
            exit 1
        elif [[ "$choice" == "0" ]]; then
            create_new_project
            return $?
        elif [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -le ${#project_array[@]} ]]; then
            local selected_project="${project_array[$((choice-1))]}"
            gcloud config set project "$selected_project"
            export GCLOUD_PROJECT="$selected_project"
            log_success "Selected project: $selected_project"
            return 0
        else
            echo "Invalid choice. Please enter a number between 0-${#project_array[@]} or 'q'"
        fi
    done
}

# Create new project helper
create_new_project() {
    echo
    log_info "Creating new GCP project..."
    echo "Project ID requirements:"
    echo "  - 6-30 characters"
    echo "  - Lowercase letters, digits, hyphens only"
    echo "  - Must start with letter"
    echo "  - Must be globally unique"
    echo
    
    while true; do
        read -p "Enter new project ID: " new_project_id
        
        if [[ -z "$new_project_id" ]]; then
            echo "Project ID cannot be empty"
            continue
        fi
        
        if [[ ! "$new_project_id" =~ ^[a-z][a-z0-9-]{5,29}$ ]]; then
            echo "Invalid project ID format"
            continue
        fi
        
        log_info "Creating project '$new_project_id'..."
        if gcloud projects create "$new_project_id" 2>/dev/null; then
            gcloud config set project "$new_project_id"
            export GCLOUD_PROJECT="$new_project_id"
            log_success "Created and selected project: $new_project_id"
            
            # Link billing account if available
            link_billing_account "$new_project_id"
            return 0
        else
            log_error "Failed to create project (may already exist or you lack permissions)"
            echo "Try a different project ID or check your permissions"
        fi
    done
}

# Link billing account for new projects
link_billing_account() {
    local project_id="$1"
    
    log_info "Checking billing accounts..."
    local billing_accounts=$(gcloud billing accounts list --format="value(name,displayName)" --filter="open:true" 2>/dev/null)
    
    if [[ -z "$billing_accounts" ]]; then
        log_warning "No billing accounts found. You'll need to:"
        echo "  1. Set up billing at: https://console.cloud.google.com/billing"
        echo "  2. Link it to project '$project_id'"
        return 0
    fi
    
    echo
    log_info "Available billing accounts:"
    local billing_array=()
    local i=1
    while IFS=$'\t' read -r account_name display_name; do
        printf "%2d) %s\n" "$i" "$display_name"
        billing_array+=("$account_name")
        ((i++))
    done <<< "$billing_accounts"
    
    echo " 0) Skip billing setup"
    echo
    
    while true; do
        read -p "Select billing account (number): " choice
        
        if [[ "$choice" == "0" ]]; then
            log_warning "Skipping billing setup. APIs may not work without billing."
            return 0
        elif [[ "$choice" =~ ^[0-9]+$ ]] && [[ "$choice" -ge 1 ]] && [[ "$choice" -le ${#billing_array[@]} ]]; then
            local selected_billing="${billing_array[$((choice-1))]}"
            if gcloud billing projects link "$project_id" --billing-account="$selected_billing" 2>/dev/null; then
                log_success "Linked billing account to project"
            else
                log_warning "Failed to link billing account (may lack permissions)"
            fi
            return 0
        else
            echo "Invalid choice. Please enter a number between 0-${#billing_array[@]}"
        fi
    done
}

# Enhanced API enablement with zero-trust support
enable_apis() {
    log_info "Checking required APIs..."
    
    # Check current API status
    local disabled_apis=()
    for api in "${REQUIRED_APIS[@]}"; do
        if ! gcloud services list --enabled --filter="name:$api" --format="value(name)" | grep -q "$api"; then
            disabled_apis+=("$api")
        fi
    done
    
    if [[ ${#disabled_apis[@]} -eq 0 ]]; then
        log_success "All required APIs are already enabled"
        return 0
    fi
    
    echo
    log_info "The following APIs need to be enabled:"
    for api in "${disabled_apis[@]}"; do
        echo "  ✗ $api"
    done
    echo
    
    # Try to enable APIs
    log_info "Attempting to enable APIs..."
    local failed_apis=()
    
    for api in "${disabled_apis[@]}"; do
        if gcloud services enable "$api" 2>/dev/null; then
            log_success "Enabled $api"
        else
            failed_apis+=("$api")
            log_warning "Failed to enable $api (permission denied)"
        fi
    done
    
    # Handle failed APIs (zero-trust scenario)
    if [[ ${#failed_apis[@]} -gt 0 ]]; then
        echo
        log_error "⚠️  Zero-trust environment detected!"
        echo
        echo "🔒 Some APIs couldn't be enabled automatically. Request your GCP admin to enable:"
        echo
        for api in "${failed_apis[@]}"; do
            echo "  ❌ $api"
        done
        echo
        echo "📋 Copy this message for your admin:"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "GCP Admin: Please enable these APIs for project '$GCLOUD_PROJECT':"
        echo
        for api in "${failed_apis[@]}"; do
            echo "gcloud services enable $api --project=$GCLOUD_PROJECT"
        done
        echo
        echo "Or via Console: https://console.cloud.google.com/apis/library?project=$GCLOUD_PROJECT"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo
        
        read -p "Continue after admin enables APIs? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_error "Setup paused. Re-run script after APIs are enabled."
            exit 1
        fi
        
        # Re-check APIs
        enable_apis
        return $?
    fi
    
    log_success "All APIs enabled successfully"
}

# Service account authentication support
setup_service_account_auth() {
    log_info "Service Account Authentication Setup"
    echo
    echo "For enterprise/CI environments, you can use a service account key file:"
    echo "  1. Download service account key from GCP Console"
    echo "  2. Set GOOGLE_APPLICATION_CREDENTIALS environment variable"
    echo "  3. Re-run this script"
    echo
    
    read -p "Do you have a service account key file? (y/n): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        while true; do
            read -p "Enter path to service account key file: " key_file
            
            if [[ -f "$key_file" ]]; then
                export GOOGLE_APPLICATION_CREDENTIALS="$key_file"
                log_info "Activating service account..."
                
                if gcloud auth activate-service-account --key-file="$key_file" 2>/dev/null; then
                    log_success "Service account activated"
                    
                    # Get project from service account if not set
                    if [[ -z "$GCLOUD_PROJECT" ]]; then
                        local sa_project=$(python3 -c "
import json
with open('$key_file') as f:
    data = json.load(f)
    print(data.get('project_id', ''))
" 2>/dev/null)
                        
                        if [[ -n "$sa_project" ]]; then
                            gcloud config set project "$sa_project"
                            export GCLOUD_PROJECT="$sa_project"
                            log_success "Set project from service account: $sa_project"
                        fi
                    fi
                    return 0
                else
                    log_error "Failed to activate service account"
                fi
            else
                echo "File not found: $key_file"
            fi
        done
    fi
    
    return 1
}

# Enhanced authentication with multiple options
ensure_gcloud_auth() {
    log_info "Checking gcloud authentication..."
    
    # Check if already authenticated
    local current_account=$(gcloud config get-value account 2>/dev/null)
    if [[ -n "$current_account" && "$current_account" != "(unset)" ]]; then
        # Verify the auth actually works
        if gcloud auth list --filter="status:ACTIVE" --format="value(account)" | grep -q "$current_account"; then
            log_success "Authenticated as: $current_account"
            return 0
        fi
    fi
    
    log_warning "Not authenticated with gcloud"
    echo
    echo "Authentication options:"
    echo "  1) Personal account (gcloud auth login)"
    echo "  2) Service account key file"
    echo "  3) Exit and authenticate manually"
    echo
    
    while true; do
        read -p "Choose authentication method (1-3): " choice
        
        case $choice in
            1)
                log_info "Running gcloud auth login..."
                if gcloud auth login; then
                    log_success "Authentication successful"
                    return 0
                else
                    log_error "Authentication failed"
                fi
                ;;
            2)
                if setup_service_account_auth; then
                    return 0
                fi
                ;;
            3)
                log_error "Please authenticate manually:"
                echo "  Personal: gcloud auth login"
                echo "  Service Account: gcloud auth activate-service-account --key-file=KEY.json"
                exit 1
                ;;
            *)
                echo "Invalid choice. Please enter 1, 2, or 3"
                ;;
        esac
    done
}

# Check if Docker is installed and running
ensure_docker() {
    # First check if Docker command exists
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed."
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            log_info "To install Docker Desktop on macOS:"
            echo "1. Download from: https://www.docker.com/products/docker-desktop"
            echo "2. Or install via Homebrew:"
            echo "   brew install --cask docker"
            echo ""
            echo "Would you like to install Docker Desktop via Homebrew? (y/n)"
            read -r response
            if [[ "$response" =~ ^[Yy]$ ]]; then
                ensure_homebrew
                log_step "Installing Docker Desktop via Homebrew..."
                brew install --cask docker
                log_success "Docker Desktop installed. Please launch it from Applications."
                log_warning "After Docker Desktop starts, re-run this script."
                exit 0
            fi
        else
            log_info "Install Docker for your platform: https://docs.docker.com/get-docker/"
        fi
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is installed but not running."
        
        if [[ "$OSTYPE" == "darwin"* ]]; then
            log_info "Please start Docker Desktop:"
            echo "1. Open Applications folder"
            echo "2. Launch Docker Desktop"
            echo "3. Wait for Docker to start (whale icon in menu bar)"
            echo "4. Re-run this script"
        else
            log_info "Start Docker daemon:"
            echo "sudo systemctl start docker"
        fi
        exit 1
    fi
    
    log_success "Docker is installed and running"
}

# Configure Docker for Artifact Registry
configure_docker_auth() {
    local region="${1:-${REGION:-europe-west1}}"
    local project_id="${2:-${GCLOUD_PROJECT:-}}"
    
    if [[ -z "$project_id" ]]; then
        log_error "Project ID not set for Docker auth configuration"
        return 1
    fi
    
    log_step "Configuring Docker authentication for Artifact Registry..."
    
    # Configure Docker auth (this is safe even if API isn't ready)
    if gcloud auth configure-docker "$region-docker.pkg.dev" --quiet 2>/dev/null; then
        log_success "Docker authentication configured"
    else
        log_warning "Docker authentication configuration failed - will retry during deployment"
    fi
    
    # Create repository if it doesn't exist (with retry and graceful error handling)
    if ! gcloud artifacts repositories describe cloud-run-source-deploy \
         --location="$region" --quiet >/dev/null 2>&1; then
        log_step "Creating Artifact Registry repository..."
        
        local retry_count=0
        local max_retries=3
        local success=false
        
        while [[ $retry_count -lt $max_retries && $success == false ]]; do
            if gcloud artifacts repositories create cloud-run-source-deploy \
                --repository-format=docker \
                --location="$region" \
                --description="Docker repository for Cloud Run deployments" \
                --quiet 2>/dev/null; then
                log_success "Artifact Registry repository created"
                success=true
            else
                retry_count=$((retry_count + 1))
                if [[ $retry_count -lt $max_retries ]]; then
                    log_warning "Repository creation failed (attempt $retry_count/$max_retries), retrying in 10 seconds..."
                    sleep 10
                else
                    log_warning "Repository creation failed after $max_retries attempts"
                    echo ""
                    log_info "This might be due to:"
                    echo "  • Artifact Registry API still activating (wait a few minutes)"
                    echo "  • Missing permissions for artifact registry operations"
                    echo "  • Project quota or billing issues"
                    echo ""
                    log_info "The repository will be created automatically during deployment if needed."
                    echo "You can also create it manually:"
                    echo "  gcloud artifacts repositories create cloud-run-source-deploy \\"
                    echo "    --repository-format=docker \\"
                    echo "    --location=$region \\"
                    echo "    --project=$project_id"
                    echo ""
                fi
            fi
        done
    else
        log_success "Artifact Registry repository already exists"
    fi
}

# Check operating system and show platform-specific guidance
check_os_compatibility() {
    log_step "Checking operating system compatibility..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        log_success "macOS detected - full auto-installation support available"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        log_info "Linux detected - some manual installation may be required"
        log_warning "Auto-installation features work best on macOS"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        log_warning "Windows detected - limited auto-installation support"
        log_info "Consider using WSL2 for better compatibility"
        log_info "Manual installation guide: https://cloud.google.com/sdk/docs/install"
    else
        log_warning "Unknown OS detected: $OSTYPE"
        log_info "Manual installation may be required"
    fi
}

# Update the main check_prerequisites function
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # OS compatibility check
    log_info "Checking operating system compatibility..."
    local os_type=$(uname -s)
    local os_version=$(uname -r)
    
    case "$os_type" in
        "Darwin")
            log_success "macOS detected - full auto-installation support available"
            ;;
        "Linux")
            log_success "Linux detected - manual installation guidance available"
            ;;
        *)
            log_warning "Unsupported OS: $os_type - manual installation required"
            ;;
    esac
    
    # Install/check tools
    ensure_homebrew
    ensure_gcloud
    ensure_docker
    
    # Authentication
    ensure_gcloud_auth
    
    # Project selection
    select_project
    
    # Docker auth
    configure_docker_auth "$REGION" "$GCLOUD_PROJECT"
    
    # API enablement
    enable_apis
    
    log_success "Prerequisites check complete!"
    echo
    log_info "✅ Operating System: $os_type$os_version"
    if command -v brew >/dev/null 2>&1; then
        log_info "✅ Homebrew: Installed"
    fi
    local gcloud_version=$(gcloud version --format="value(Google Cloud SDK)" 2>/dev/null | head -n1)
    log_info "✅ gcloud CLI: $gcloud_version"
    local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ',')
    log_info "✅ Docker: $docker_version"
    local current_account=$(gcloud config get-value account 2>/dev/null)
    log_info "✅ Authentication: $current_account"
    log_info "✅ Project: $GCLOUD_PROJECT"
    echo
}

# Get service URL
get_service_url() {
    local service="$1"
    local region="$2"
    
    gcloud run services describe "$service" \
        --region="$region" \
        --format="value(status.url)" \
        --quiet 2>/dev/null || echo ""
}

# Get service status
get_service_status() {
    local service="$1"
    local region="$2"
    
    gcloud run services describe "$service" \
        --region="$region" \
        --format="value(status.conditions[0].status)" \
        --quiet 2>/dev/null || echo "Unknown"
}

# Check if service exists
service_exists() {
    local service="$1"
    local region="$2"
    
    gcloud run services describe "$service" \
        --region="$region" \
        --quiet >/dev/null 2>&1
}

# Format duration from seconds
format_duration() {
    local seconds="$1"
    local hours=$((seconds / 3600))
    local minutes=$(((seconds % 3600) / 60))
    local secs=$((seconds % 60))
    
    if [[ $hours -gt 0 ]]; then
        echo "${hours}h ${minutes}m ${secs}s"
    elif [[ $minutes -gt 0 ]]; then
        echo "${minutes}m ${secs}s"
    else
        echo "${secs}s"
    fi
}

# Get last deployment time
get_last_deploy_time() {
    local service="$1"
    local region="$2"
    
    local timestamp
    timestamp=$(gcloud run services describe "$service" \
        --region="$region" \
        --format="value(metadata.labels.last-deploy)" \
        --quiet 2>/dev/null || echo "")
    
    if [[ -n "$timestamp" ]]; then
        local current_time=$(date +%s)
        local duration=$((current_time - timestamp))
        format_duration "$duration"
    else
        echo "Unknown"
    fi
} 