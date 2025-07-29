#!/bin/bash

# Database Functions Module
# Handles PostgreSQL database setup and management

# Get current machine's public IP address for secure database access
get_current_machine_ip() {
    local current_ip=""
    
    # Try multiple IP detection services for reliability (silent)
    for service in "ifconfig.me" "ipecho.net/plain" "icanhazip.com" "ident.me"; do
        current_ip=$(curl -s --connect-timeout 5 --max-time 10 "https://$service" 2>/dev/null | grep -E '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$' | head -1)
        if [[ -n "$current_ip" ]]; then
            echo "$current_ip"
            return 0
        fi
    done
    
    return 1
}

# Get current machine's public IP address with verbose output for user information
get_current_machine_ip_verbose() {
    local current_ip=""
    
    echo "🔍 Detecting current machine's public IP address..."
    
    # Try multiple IP detection services for reliability
    for service in "ifconfig.me" "ipecho.net/plain" "icanhazip.com" "ident.me"; do
        current_ip=$(curl -s --connect-timeout 5 --max-time 10 "https://$service" 2>/dev/null | grep -E '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$' | head -1)
        if [[ -n "$current_ip" ]]; then
            echo "📍 Current machine IP: $current_ip (via $service)"
            echo "$current_ip"
            return 0
        fi
    done
    
    echo "⚠️  Could not detect current machine's IP address"
    echo "   Using Cloud SQL proxy for agent-server (secure)"
    echo "   Database will only be accessible via Cloud SQL proxy"
    echo ""
    return 1
}

# Get authorized networks for secure database access (silent)
get_authorized_networks() {
    local current_ip=""
    current_ip=$(get_current_machine_ip)
    
    if [[ -n "$current_ip" ]]; then
        # Allow current machine IP for development access
        echo "$current_ip/32"
    else
        # No direct IP access - rely only on Cloud SQL proxy
        echo ""
    fi
}

# Get authorized networks with verbose user feedback for database creation
get_authorized_networks_verbose() {
    echo "🔍 Detecting current machine's public IP address..." >&2
    local current_ip=""
    current_ip=$(get_current_machine_ip)
    
    if [[ -n "$current_ip" ]]; then
        echo "📍 Current machine IP: $current_ip" >&2
        echo "🔒 Will allow database access from: $current_ip/32" >&2
        echo "$current_ip/32"  # Only the clean CIDR to stdout
    else
        echo "⚠️  Could not detect current machine's IP address" >&2
        echo "🔒 Database will use Cloud SQL proxy only (most secure)" >&2
        echo ""  # Empty string for no authorized networks
    fi
}

# Generate database connection information for local development
show_database_connection_info() {
    local db_instance="$1"
    local db_name="${2:-agents}"
    local db_user="${3:-agents}"
    local db_password="${4:-agents}"
    
    echo ""
    echo "🔗 Database Connection Information"
    echo "=================================="
    
    echo "📋 Instance: $db_instance"
    echo "💾 Database: $db_name"
    echo "👤 User:     $db_user"
    echo "🔑 Password: $db_password"
    echo "🔒 Access:   Cloud SQL Proxy only (no public IP)"
    echo ""
    
    # Show Cloud SQL proxy connection method (only way to connect)
    echo "🛡️  Cloud SQL Proxy Connection:"
    echo "   # Quick connect:"
    echo "   gcloud sql connect $db_instance --user=$db_user --database=$db_name"
    echo ""
    echo "   # Manual proxy setup:"
    echo "   cloud-sql-proxy --port 5432 $PROJECT_ID:$REGION:$db_instance"
    echo "   # Then connect:"
    echo "   postgresql://$db_user:$db_password@localhost:5432/$db_name"
    echo ""
    echo "💡 Agent-server connects via Cloud SQL proxy automatically (fast & secure)"
    echo ""
}

# Wait for database instance to be ready for use and test connectivity
wait_for_database_ready() {
    local db_instance="$1"
    local max_wait_time=600  # 10 minutes max wait
    local check_interval=15  # Check every 15 seconds
    local elapsed_time=0
    
    show_progress "Waiting for database to be ready"
    
    while [[ $elapsed_time -lt $max_wait_time ]]; do
        local db_state=$(gcloud sql instances describe "$db_instance" \
            --format="value(state)" \
            --quiet 2>/dev/null || echo "NOT_FOUND")
        
        case "$db_state" in
            "RUNNABLE")
                echo "🔄 Database state is RUNNABLE, testing connectivity..."
                
                # Test actual database connectivity
                if test_database_connectivity "$db_instance"; then
                    echo "✅ Database is ready and accepting connections!"
                    return 0
                else
                    echo "⚠️  Database is RUNNABLE but not accepting connections yet (${elapsed_time}s elapsed)"
                fi
                ;;
            "PENDING_CREATE")
                echo "🔄 Database is being created... (${elapsed_time}s elapsed)"
                ;;
            "PENDING_UPDATE")
                echo "🔄 Database is being updated... (${elapsed_time}s elapsed)"
                ;;
            "STOPPED")
                echo "⚠️  Database is stopped, attempting to start..."
                gcloud sql instances patch "$db_instance" --activation-policy=ALWAYS --quiet
                ;;
            "NOT_FOUND")
                echo "❌ Database instance not found!"
                return 1
                ;;
            *)
                echo "⚠️  Database state: $db_state (${elapsed_time}s elapsed)"
                ;;
        esac
        
        sleep $check_interval
        elapsed_time=$((elapsed_time + check_interval))
    done
    
    echo "❌ Timeout waiting for database to be ready after ${max_wait_time}s"
    echo "💡 Check database status manually: gcloud sql instances describe $db_instance"
    return 1
}

# Test database connectivity
test_database_connectivity() {
    local db_instance="$1"
    
    # Get database IP to verify it's available
    local db_ip=$(gcloud sql instances describe "$db_instance" \
        --format="value(ipAddresses[0].ipAddress)" \
        --quiet 2>/dev/null || echo "")
    
    if [[ -z "$db_ip" ]]; then
        echo "⚠️  Could not get database IP"
        return 1
    fi
    
    # Check for ongoing operations
    echo "🔌 Testing readiness of $db_instance ($db_ip)..."
    
    local operations=$(gcloud sql operations list \
        --filter="targetId:$db_instance AND status:RUNNING" \
        --format="value(operationType)" \
        --quiet 2>/dev/null || echo "")
    
    if [[ -n "$operations" ]]; then
        echo "⚠️  Database has ongoing operations: $operations"
        return 1
    fi
    
    # Additional wait time after operations complete
    echo "⏳ Allowing extra time for database initialization..."
    sleep 30
    
    echo "✅ Database appears ready for connections"
    return 0
}

# Setup database (shared or personal) with permission error handling
setup_database() {
    local db_instance="$1"
    local db_name="agents"
    local db_user="agents"
    local db_password="agents"
    
    echo "🗄️  Setting up database: $db_instance"
    
    # Check if instance exists
    if gcloud sql instances describe "$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "✅ Database instance '$db_instance' already exists"
        
        # Make sure existing database is ready
        wait_for_database_ready "$db_instance"
    else
        echo "📦 Creating PostgreSQL instance '$db_instance'..."
        echo "⏳ This will take 3-5 minutes (you'll see progress below)..."
        echo ""
        
        # Build the create command optimized for speed (no IP allocation, better tier, 10GB minimum)
        echo "🔒 Using Cloud SQL proxy only (no public IP) - fastest and most secure setup"
        local create_cmd="gcloud sql instances create \"$db_instance\" \
            --database-version=POSTGRES_14 \
            --tier=db-custom-1-3840 \
            --region=\"$REGION\" \
            --root-password=\"$db_password\" \
            --storage-type=SSD \
            --storage-size=10GB \
            --storage-auto-increase \
            --backup-start-time=03:00 \
            --maintenance-window-day=SUN \
            --maintenance-window-hour=04 \
            --no-assign-ip"
        
        echo "🛡️  Security: Agent-server will connect via Cloud SQL proxy (secure)"
        echo ""
        
        # Create the database instance with secure network access
        if ! eval "$create_cmd"; then
            
            echo ""
            echo "❌ Failed to create database instance '$db_instance'"
            echo ""
            echo "💡 Common causes:"
            echo "   • Permission denied (need Cloud SQL Admin role)"
            echo "   • Cloud SQL quota limits (max 2-3 instances per project)"
            echo "   • Region capacity issues" 
            echo "   • Instance name conflicts"
            echo ""
            echo "🔧 Possible solutions:"
            echo "   • Request Cloud SQL permissions: ./scripts/gcp/add-developer.sh $(gcloud config get-value account 2>/dev/null)"
            echo "   • Use existing database if available"
            echo "   • Try different region: export REGION=us-central1"
            echo ""
            echo "🚫 Deployment stopped - please resolve the issue above and try again"
            return 1
        fi
        
        echo "✅ Database instance created"
        
        # Wait for database to be ready
        wait_for_database_ready "$db_instance"
    fi
    
    # ALWAYS check and ensure database exists (even if instance existed)
    # This fixes the race condition issue where instance exists but database doesn't
    echo "🔍 Verifying database '$db_name' exists..."
    if gcloud sql databases describe "$db_name" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "✅ Database '$db_name' already exists"
    else
        echo "📦 Creating database '$db_name'..."
        if gcloud sql databases create "$db_name" --instance="$db_instance"; then
            echo "✅ Database '$db_name' created successfully"
        else
            echo "❌ Failed to create database '$db_name'"
            return 1
        fi
    fi
    
    # ALWAYS check and ensure user exists (even if instance existed)
    # This fixes the race condition issue where instance exists but user doesn't
    echo "🔍 Verifying user '$db_user' exists..."
    if gcloud sql users describe "$db_user" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "🔄 Updating password for existing user '$db_user'..."
        if gcloud sql users set-password "$db_user" --instance="$db_instance" --password="$db_password"; then
            echo "✅ Password updated for user '$db_user'"
        else
            echo "⚠️  Warning: Failed to update password for user '$db_user'"
        fi
    else
        echo "📦 Creating user '$db_user'..."
        if gcloud sql users create "$db_user" --instance="$db_instance" --password="$db_password"; then
            echo "✅ User '$db_user' created successfully"
        else
            echo "❌ Failed to create user '$db_user'"
            return 1
        fi
    fi
    
    echo "✅ Database setup complete"
    
    # Show connection information for local development
    show_database_connection_info "$db_instance" "$db_name" "$db_user" "$db_password"
    
    return 0  # Explicitly return success
}

# Fast database setup optimized for development environments
setup_database_fast() {
    local db_instance="$1"
    local environment="${2:-development}"
    local db_name="agents"
    local db_user="agents" 
    local db_password="agents"
    
    echo "🚀 Setting up database (fast mode): $db_instance"
    echo "🔧 Environment: $environment"
    
    # Check if instance exists
    if gcloud sql instances describe "$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "✅ Database instance '$db_instance' already exists"
        wait_for_database_ready "$db_instance"
    else
        echo "📦 Creating PostgreSQL instance '$db_instance' (optimized for speed)..."
        echo "⏳ This should take 2-4 minutes with optimized settings..."
        echo ""
        
        # Choose configuration based on environment (optimized for speed, 10GB minimum)
        echo "🔒 Using Cloud SQL proxy only (no public IP) - fastest and most secure setup"
        local create_cmd="gcloud sql instances create \"$db_instance\" \
            --database-version=POSTGRES_14 \
            --region=\"$REGION\" \
            --storage-type=SSD \
            --storage-size=10GB \
            --root-password=\"$db_password\" \
            --no-assign-ip"
        
        echo "🛡️  Security: Agent-server will connect via Cloud SQL proxy (secure)"
            
        case "$environment" in
            "development"|"dev")
                # Optimized configuration for fastest creation
                create_cmd="$create_cmd \
                    --tier=db-custom-1-3840 \
                    --no-backup \
                    --maintenance-release-channel=production"
                echo "🔧 Using optimized dev configuration (1 vCPU, no backups, fast provisioning)"
                ;;
            "testing"|"test")
                # Slightly more robust for testing
                create_cmd="$create_cmd \
                    --tier=db-custom-1-3840 \
                    --backup-start-time=03:00 \
                    --maintenance-window-day=SUN \
                    --maintenance-window-hour=04"
                echo "🔧 Using testing configuration (1 vCPU, backups enabled)"
                ;;
            "production"|"prod")
                # Full production configuration (will be slower)
                create_cmd="$create_cmd \
                    --tier=db-custom-2-7680 \
                    --availability-type=REGIONAL \
                    --backup-start-time=03:00 \
                    --maintenance-window-day=SUN \
                    --maintenance-window-hour=04 \
                    --storage-auto-increase"
                echo "🔧 Using production configuration (2 vCPU, HA, full backups)"
                ;;
            *)
                # Default to optimized development settings
                create_cmd="$create_cmd \
                    --tier=db-custom-1-3840 \
                    --no-backup"
                echo "🔧 Using default optimized configuration (1 vCPU, no backups)"
                ;;
        esac
        
        if ! eval $create_cmd; then
            echo ""
            echo "❌ Failed to create database instance '$db_instance'"
            echo ""
            echo "💡 Common causes and solutions:"
            echo "   • Permission issues: Check Cloud SQL Admin role"
            echo "   • Resource limits: Try different region or smaller tier"
            echo "   • Name conflicts: Instance name already exists"
            echo ""
            return 1
        fi
        
        echo "✅ Database instance created"
        
        # For development environment, enable backups after creation to speed up initial setup
        if [[ "$environment" == "development" || "$environment" == "dev" ]]; then
            echo "🔄 Enabling backups post-creation for development instance..."
            gcloud sql instances patch "$db_instance" \
                --backup-start-time=03:00 \
                --backup-location="$REGION" \
                --quiet >/dev/null 2>&1 || echo "⚠️  Note: Backup setup can be done later if needed"
        fi
        
        wait_for_database_ready "$db_instance"
    fi
    
    # Rest of database setup (database and user creation)
    # ALWAYS check and ensure database exists (even if instance existed)
    # This fixes the race condition issue where instance exists but database doesn't
    echo "🔍 Verifying database '$db_name' exists..."
    if gcloud sql databases describe "$db_name" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "✅ Database '$db_name' already exists"
    else
        echo "📦 Creating database '$db_name'..."
        if gcloud sql databases create "$db_name" --instance="$db_instance"; then
            echo "✅ Database '$db_name' created successfully"
        else
            echo "❌ Failed to create database '$db_name'"
            return 1
        fi
    fi
    
    # ALWAYS check and ensure user exists (even if instance existed)
    # This fixes the race condition issue where instance exists but user doesn't
    echo "🔍 Verifying user '$db_user' exists..."
    if gcloud sql users describe "$db_user" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "🔄 Updating password for existing user '$db_user'..."
        if gcloud sql users set-password "$db_user" --instance="$db_instance" --password="$db_password"; then
            echo "✅ Password updated for user '$db_user'"
        else
            echo "⚠️  Warning: Failed to update password for user '$db_user'"
        fi
    else
        echo "📦 Creating user '$db_user'..."
        if gcloud sql users create "$db_user" --instance="$db_instance" --password="$db_password"; then
            echo "✅ User '$db_user' created successfully"
        else
            echo "❌ Failed to create user '$db_user'"
            return 1
        fi
    fi
    
    echo "✅ Fast database setup complete"
    
    # Show connection information for local development
    show_database_connection_info "$db_instance" "$db_name" "$db_user" "$db_password"
    
    return 0
}

# Benchmark database creation times with different configurations
benchmark_database_creation() {
    local base_name="$1"
    local region="${2:-$REGION}"
    
    echo "🕒 Benchmarking database creation times..."
    echo "📍 Region: $region"
    echo ""
    
    local configs=(
        "minimal:db-f1-micro:10:--no-backup"
        "standard:db-f1-micro:10:--backup-start-time=03:00"
        "performance:db-custom-1-3840:20:--backup-start-time=03:00"
    )
    
    for config in "${configs[@]}"; do
        IFS=':' read -r name tier storage extra_flags <<< "$config"
        local instance_name="${base_name}-${name}-$(date +%s)"
        
        echo "⏱️  Testing configuration: $name"
        echo "   Tier: $tier, Storage: ${storage}GB"
        echo "   Extra flags: $extra_flags"
        
        local start_time=$(date +%s)
        
        if eval "gcloud sql instances create \"$instance_name\" \
            --database-version=POSTGRES_14 \
            --tier=\"$tier\" \
            --region=\"$region\" \
            --storage-size=\"${storage}GB\" \
            --storage-type=SSD \
            --quiet $extra_flags"; then
            
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            
            echo "   ✅ Created in ${duration} seconds ($(($duration / 60))m $(($duration % 60))s)"
            
            # Clean up test instance
            echo "   🗑️  Cleaning up test instance..."
            gcloud sql instances delete "$instance_name" --quiet
        else
            echo "   ❌ Failed to create $instance_name"
        fi
        
        echo ""
    done
}

# Get current database instance from deployed service
get_current_database() {
    local service="$1"
    local region="$2"
    
    # Check if service exists
    if ! gcloud run services describe "$service" --region="$region" --quiet >/dev/null 2>&1; then
        echo ""  # Service doesn't exist
        return 1
    fi
    
    # Get the CloudSQL instance annotation
    local cloudsql_instances=$(gcloud run services describe "$service" \
        --region="$region" \
        --format="value(spec.template.metadata.annotations['run.googleapis.com/cloudsql-instances'])" \
        --quiet 2>/dev/null || echo "")
    
    # Extract database instance names (format: project:region:instance)
    if [[ -n "$cloudsql_instances" ]]; then
        # Handle multiple instances, return the primary one (first in list)
        echo "$cloudsql_instances" | cut -d',' -f1 | sed 's/.*://'
    else
        echo ""  # No database configured
    fi
}

# Check if database switch is needed
check_database_switch() {
    local service="$1"
    local region="$2"
    local new_db_instance="$3"
    
    local current_db=$(get_current_database "$service" "$region")
    
    if [[ -z "$current_db" ]]; then
        echo "NEW"  # No current database, this is a new deployment
    elif [[ "$current_db" == "$new_db_instance" ]]; then
        echo "SAME"  # Same database
    else
        echo "SWITCH"  # Different database - need to switch
    fi
}

# Interactive database selection
choose_database() {
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"
    
    echo "" >&2
    echo "🗄️  Database Selection" >&2
    echo "    Services: $([ "$DEPLOYMENT_TARGET" == "shared" ] && echo "Shared (agent-server, workroom)" || echo "Personal (agent-server-${CURRENT_USER}, workroom-${CURRENT_USER})")" >&2
    echo "" >&2
    
    # Check what databases exist (in any state)
    local shared_exists personal_exists shared_state personal_state
    
    if shared_state=$(gcloud sql instances describe "$shared_db" --format="value(state)" --quiet 2>/dev/null); then
        shared_exists="true"
    else
        shared_exists="false"
        shared_state="NOT_FOUND"
    fi
    
    if personal_state=$(gcloud sql instances describe "$personal_db" --format="value(state)" --quiet 2>/dev/null); then
        personal_exists="true"
    else
        personal_exists="false"
        personal_state="NOT_FOUND"
    fi
    
    echo "📊 Which database should your services use?" >&2
    echo "" >&2
    local option_num=1
    local options=()
    
    if [[ "$shared_exists" == "true" ]]; then
        if [[ "$shared_state" == "RUNNABLE" ]]; then
            echo " $option_num) 🌐 Shared Database (agent-postgres) - ready" >&2
        else
            echo " $option_num) 🌐 Shared Database (agent-postgres) - $shared_state" >&2
        fi
        echo "    • Collaborate with other developers" >&2
        echo "    • Shared data and agents" >&2
        echo "    • Production/team environment" >&2
        options[$option_num]="shared_existing"
        ((option_num++))
    else
        echo " $option_num) 🌐 Shared Database (agent-postgres) - will create" >&2
        echo "    • Collaborate with other developers" >&2
        echo "    • Shared data and agents" >&2
        echo "    • Production/team environment" >&2
        options[$option_num]="shared_new"
        ((option_num++))
    fi
    
    echo "" >&2
    
    if [[ "$personal_exists" == "true" ]]; then
        if [[ "$personal_state" == "RUNNABLE" ]]; then
            echo " $option_num) 👤 Personal Database ($personal_db) - ready" >&2
        else
            echo " $option_num) 👤 Personal Database ($personal_db) - $personal_state" >&2
        fi
        echo "    • Independent development data" >&2
        echo "    • Your own agents and conversations" >&2
        echo "    • Safe testing environment" >&2
        options[$option_num]="personal_existing"
        ((option_num++))
    else
        echo " $option_num) 👤 Personal Database ($personal_db) - will create" >&2
        echo "    • Independent development data" >&2
        echo "    • Your own agents and conversations" >&2
        echo "    • Safe testing environment" >&2
        options[$option_num]="personal_new"
        ((option_num++))
    fi
    
    echo "" >&2
    echo " 0) ❌ Cancel deployment" >&2
    echo "" >&2
    
    # Show recommendation based on service choice
    if [[ "$DEPLOYMENT_TARGET" == "personal" ]]; then
        echo "💡 Recommendation for personal services:" >&2
        echo "   • Shared database: Great for testing with team data" >&2
        echo "   • Personal database: Full isolation for development" >&2
    else
        echo "💡 Recommendation for shared services:" >&2
        echo "   • Shared database: Standard for production/team use" >&2
        echo "   • Personal database: Uncommon but valid for testing" >&2
    fi
    echo "" >&2
    
    while true; do
        read -p "Select database (0-$((option_num-1))): " choice >&2
        
        if [[ "$choice" == "0" ]]; then
            echo "❌ Deployment cancelled" >&2
            echo "CANCELLED"  # Return special value instead of exit
            return 1
        elif [[ "$choice" -ge 1 && "$choice" -lt "$option_num" ]]; then
            local selected_option="${options[$choice]}"
            
            case "$selected_option" in
                "shared_existing")
                    echo "✅ Selected: Use existing shared database (agent-postgres)" >&2
                    echo "shared"  # Return the selection type
                    return 0
                    ;;
                "shared_new")
                    echo "✅ Selected: Use shared database (agent-postgres) - will create if needed" >&2
                    { setup_database_with_template "$shared_db" "shared"; } >&2
                    echo "shared"  # Return the selection type
                    return 0
                    ;;
                "personal_existing")
                    echo "✅ Selected: Use existing personal database ($personal_db)" >&2
                    echo "personal"  # Return the selection type
                    return 0
                    ;;
                "personal_new")
                    echo "✅ Selected: Use personal database ($personal_db) - will create if needed" >&2
                    { setup_database_with_template "$personal_db" "personal"; } >&2
                    echo "personal"  # Return the selection type
                    return 0
                    ;;
            esac
        else
            echo "❌ Invalid choice. Please enter 0-$((option_num-1))" >&2
        fi
    done
} 

# =============================================================================
# Template Database System
# =============================================================================

# Check if template database exists and is ready
check_template_database() {
    local template_name="agent-postgres-template"
    
    if gcloud sql instances describe "$template_name" --format="value(state)" --quiet >/dev/null 2>&1; then
        local template_state=$(gcloud sql instances describe "$template_name" --format="value(state)" --quiet 2>/dev/null)
        if [[ "$template_state" == "RUNNABLE" ]]; then
            return 0
        fi
    fi
    return 1
}

# Create optimized template database (admin setup)
create_template_database() {
    local template_name="agent-postgres-template"
    local db_name="agents"
    local db_user="agents"
    local db_password="agents"
    
    echo "🏗️  Creating optimized template database: $template_name"
    echo "💰 Cost: ~\$7-12/month (one-time setup for faster cloning)"
    echo ""
    
    if check_template_database; then
        echo "✅ Template database already exists and is ready"
        return 0
    fi
    
    echo "📦 Creating template instance with optimized settings..."
    echo "⏳ This will take 3-5 minutes (one-time setup)..."
    echo ""
    
    # Build the create command optimized for speed (no IP allocation, better tier, 10GB minimum)  
    echo "🔒 Using Cloud SQL proxy only (no public IP) - fastest and most secure template setup"
    local create_cmd="gcloud sql instances create \"$template_name\" \
        --database-version=POSTGRES_14 \
        --tier=db-custom-1-3840 \
        --region=\"$REGION\" \
        --root-password=\"$db_password\" \
        --storage-type=SSD \
        --storage-size=10GB \
        --storage-auto-increase \
        --backup-start-time=03:00 \
        --maintenance-window-day=SUN \
        --maintenance-window-hour=04 \
        --no-assign-ip \
        --tags=purpose=template,component=agent-platform"
    
    echo "🛡️  Security: Template will be securely accessible for cloning"
    echo ""
    
    # Create template with optimal settings for cloning
    if ! eval "$create_cmd"; then
        
        echo "❌ Failed to create template database"
        return 1
    fi
    
    echo "✅ Template instance created"
    
    # Wait for template to be ready
    wait_for_database_ready "$template_name"
    
    # Set up database and user in template
    echo "🔧 Setting up template database structure..."
    
    if gcloud sql databases create "$db_name" --instance="$template_name"; then
        echo "✅ Template database '$db_name' created"
    else
        echo "❌ Failed to create template database"
        return 1
    fi
    
    if gcloud sql users create "$db_user" --instance="$template_name" --password="$db_password"; then
        echo "✅ Template user '$db_user' created"
    else
        echo "❌ Failed to create template user"
        return 1
    fi
    
    # Template metadata is set during creation via --tags flag
    
    echo "✅ Template database setup complete!"
    echo "🚀 Future database creation will now take 90-120 seconds instead of 450 seconds"
    echo ""
    
    return 0
}

# Clone database from template (90-120 seconds vs 450 seconds)
clone_from_template() {
    local new_instance="$1"
    local template_name="agent-postgres-template"
    
    echo "🚀 Cloning database from template: $new_instance"
    echo "⏳ Template cloning: 90-120 seconds (vs 450s from scratch)"
    echo ""
    
    if ! check_template_database; then
        echo "⚠️  Template database not available, creating from scratch..."
        return 1
    fi
    
    # Clone from template (using correct gcloud syntax)
    if ! gcloud sql instances clone "$template_name" "$new_instance"; then
        
        echo "❌ Failed to clone from template"
        return 1
    fi
    
    echo "✅ Database cloned from template"
    
    # Wait for clone to be ready
    wait_for_database_ready "$new_instance"
    
    echo "🎉 Template clone complete! (90-120 seconds vs 450s from scratch)"
    return 0
}

# Setup database with template support (replaces setup_database for new deployments)
setup_database_with_template() {
    local db_instance="$1"
    local db_type="${2:-personal}"  # personal, shared, or demo
    
    echo "🗄️  Setting up database with template optimization: $db_instance"
    echo "🔧 Type: $db_type"
    
    # Check if instance already exists
    if gcloud sql instances describe "$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "✅ Database instance '$db_instance' already exists"
        
        # Still ensure database and user exist
        ensure_database_and_user "$db_instance"
        return 0
    fi
    
    # For personal isolated databases, try template cloning first (with fallback)
    if [[ "$db_type" == "personal" ]]; then
        echo "🎯 Personal database detected - attempting template clone..."
        
        # Try template clone with proper timeout handling
        echo "🚀 Attempting template clone (will fallback to standard creation if failed)..."
        if clone_from_template "$db_instance"; then
            echo "✅ Template clone successful!"
            return 0
        else
            echo "⚠️  Template clone failed, using standard creation..."
        fi
    fi
    
    # For shared/demo databases, check if template can be used as fallback
    if [[ "$db_type" == "shared" || "$db_type" == "demo" ]]; then
        echo "🌐 Shared/demo database - checking template availability..."
        
        if check_template_database; then
            echo "📋 Template available - using clone for faster setup..."
            if clone_from_template "$db_instance"; then
                echo "✅ Template clone successful for shared database!"
                return 0
            else
                echo "⚠️  Template clone failed for shared database, using standard creation..."
            fi
        else
            echo "ℹ️  No template available - using standard creation..."
        fi
    fi
    
    # Fallback to standard creation
    echo "📦 Using standard database creation..."
    setup_database_fast "$db_instance" "development"
}

# Ensure database and user exist (for existing instances)
ensure_database_and_user() {
    local db_instance="$1"
    local db_name="${2:-agents}"
    local db_user="${3:-agents}"
    local db_password="${4:-agents}"
    
    echo "🔍 Ensuring database and user exist in: $db_instance"
    
    # Check and create database
    if gcloud sql databases describe "$db_name" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "✅ Database '$db_name' exists"
    else
        echo "📦 Creating database '$db_name'..."
        if gcloud sql databases create "$db_name" --instance="$db_instance"; then
            echo "✅ Database '$db_name' created"
        else
            echo "❌ Failed to create database '$db_name'"
            return 1
        fi
    fi
    
    # Check and create/update user
    if gcloud sql users describe "$db_user" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "🔄 Updating password for user '$db_user'..."
        if gcloud sql users set-password "$db_user" --instance="$db_instance" --password="$db_password"; then
            echo "✅ Password updated for user '$db_user'"
        else
            echo "⚠️  Warning: Failed to update password"
        fi
    else
        echo "📦 Creating user '$db_user'..."
        if gcloud sql users create "$db_user" --instance="$db_instance" --password="$db_password"; then
            echo "✅ User '$db_user' created"
        else
            echo "❌ Failed to create user '$db_user'"
            return 1
        fi
    fi
    
    return 0
}

# Verify database setup is complete (useful for debugging)
verify_database_setup() {
    local db_instance="$1"
    local db_name="${2:-agents}"
    local db_user="${3:-agents}"
    
    echo "🔍 Verifying database setup for: $db_instance"
    echo ""
    
    # Check instance status
    local instance_state=$(gcloud sql instances describe "$db_instance" --format="value(state)" --quiet 2>/dev/null || echo "NOT_FOUND")
    echo "   Instance State: $instance_state"
    
    if [[ "$instance_state" != "RUNNABLE" ]]; then
        echo "   ❌ Instance is not in RUNNABLE state"
        return 1
    fi
    
    # Check if database exists
    if gcloud sql databases describe "$db_name" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "   ✅ Database '$db_name' exists"
    else
        echo "   ❌ Database '$db_name' missing"
        return 1
    fi
    
    # Check if user exists
    if gcloud sql users describe "$db_user" --instance="$db_instance" --format="value(name)" --quiet >/dev/null 2>&1; then
        echo "   ✅ User '$db_user' exists"
    else
        echo "   ❌ User '$db_user' missing"
        return 1
    fi
    
    # Get connection info
    local instance_ip=$(gcloud sql instances describe "$db_instance" --format="value(ipAddresses[0].ipAddress)" --quiet 2>/dev/null)
    local connection_name=$(gcloud sql instances describe "$db_instance" --format="value(connectionName)" --quiet 2>/dev/null)
    
    echo ""
    echo "📊 Connection Details:"
    echo "   🗄️  Instance: $db_instance"
    echo "   🌐 Public IP: $instance_ip"
    echo "   🔗 Connection: $connection_name"
    echo "   💾 Database: $db_name"
    echo "   👤 User: $db_user"
    echo ""
    echo "✅ Database setup verification complete"
    
    return 0
} 