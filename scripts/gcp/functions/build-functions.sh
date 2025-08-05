#!/bin/bash

# Build Functions Module
# Handles Docker building and Cloud Run deployment

# Get database choice for profile consistency (no database creation)
get_database_choice_for_profile() {
    # If DATABASE_CHOICE is already set, use it
    if [[ -n "$DATABASE_CHOICE" ]]; then
        return 0
    fi

    # Auto-discover from existing deployments or set default
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"

    # Check what databases exist
    local shared_exists personal_exists

    if gcloud sql instances describe "$shared_db" --quiet >/dev/null 2>&1; then
        shared_exists="true"
    else
        shared_exists="false"
    fi

    if gcloud sql instances describe "$personal_db" --quiet >/dev/null 2>&1; then
        personal_exists="true"
    else
        personal_exists="false"
    fi

    # Set DATABASE_CHOICE based on what exists or deployment target
    if [[ "$DEPLOYMENT_TARGET" == "shared" ]]; then
        DATABASE_CHOICE="shared"
    elif [[ "$personal_exists" == "true" ]]; then
        DATABASE_CHOICE="personal"
    elif [[ "$shared_exists" == "true" ]]; then
        DATABASE_CHOICE="shared"
    else
        # Default for new deployments
        DATABASE_CHOICE="personal"
    fi

    echo "📋 Database choice for profile: $DATABASE_CHOICE (workroom uses this for profile consistency only)"
}

# Smart database discovery - finds available databases and creates them if needed
discover_and_set_database_choice() {
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"

    # If DATABASE_CHOICE is already set and the database exists, keep it
    if [[ -n "$DATABASE_CHOICE" ]]; then
        case "$DATABASE_CHOICE" in
            "shared")
                if gcloud sql instances describe "$shared_db" --quiet >/dev/null 2>&1; then
                    echo "✅ Confirmed database choice: shared ($shared_db exists)"
                    return 0
                else
                    echo "⚠️  Shared database '$shared_db' not found, will create it..."
                    # Always use optimized template-based setup for shared databases
                    setup_database_with_template "$shared_db" "shared" "false"
                    echo "✅ Created shared database: $shared_db"
                    return 0
                fi
                ;;
            "personal")
                if gcloud sql instances describe "$personal_db" --quiet >/dev/null 2>&1; then
                    echo "✅ Confirmed database choice: personal ($personal_db exists)"
                    return 0
                else
                    echo "⚠️  Personal database '$personal_db' not found, will create it..."
                    # Always use optimized template-based setup (sync for reliability)
                    setup_database_with_template "$personal_db" "personal" "false"
                    echo "✅ Created personal database: $personal_db"
                    return 0
                fi
                ;;
        esac
    fi

    # Auto-discover available databases (check for existence in any state)
    local shared_exists personal_exists shared_state personal_state

    # Check shared database
    if shared_state=$(gcloud sql instances describe "$shared_db" --format="value(state)" --quiet 2>/dev/null); then
        shared_exists="true"
        echo "🔍 Found shared database: $shared_db (state: $shared_state)"
    else
        shared_exists="false"
        shared_state="NOT_FOUND"
    fi

    # Check personal database
    if personal_state=$(gcloud sql instances describe "$personal_db" --format="value(state)" --quiet 2>/dev/null); then
        personal_exists="true"
        echo "🔍 Found personal database: $personal_db (state: $personal_state)"
    else
        personal_exists="false"
        personal_state="NOT_FOUND"
    fi

    echo "🔍 Database discovery results:"
    echo "   • Shared database ($shared_db): $([ "$shared_exists" == "true" ] && echo "✅ $shared_state" || echo "❌ Not found")"
    echo "   • Personal database ($personal_db): $([ "$personal_exists" == "true" ] && echo "✅ $personal_state" || echo "❌ Not found")"

    # Handle different scenarios - prioritize existing databases (even if not ready)
    if [[ "$shared_exists" == "true" && "$personal_exists" == "true" ]]; then
        # Both exist - prefer the one that matches deployment target
        if [[ "$DEPLOYMENT_TARGET" == "shared" ]]; then
            DATABASE_CHOICE="shared"
            echo "📍 Auto-selected: shared database (matches shared deployment target)"
            if [[ "$shared_state" != "RUNNABLE" ]]; then
                echo "⏳ Shared database is $shared_state, will wait for it to be ready"
                wait_for_database_ready "$shared_db"
            fi
        else
            # For personal deployments, prefer shared database for team collaboration by default
            DATABASE_CHOICE="shared"
            echo "📍 Auto-selected: shared database (recommended for team collaboration)"
            if [[ "$shared_state" != "RUNNABLE" ]]; then
                echo "⏳ Shared database is $shared_state, will wait for it to be ready"
                wait_for_database_ready "$shared_db"
            fi
        fi
    elif [[ "$shared_exists" == "true" ]]; then
        DATABASE_CHOICE="shared"
        echo "📍 Auto-selected: shared database (only available option)"
        if [[ "$shared_state" != "RUNNABLE" ]]; then
            echo "⏳ Shared database is $shared_state, will wait for it to be ready"
            wait_for_database_ready "$shared_db"
        fi
    elif [[ "$personal_exists" == "true" ]]; then
        DATABASE_CHOICE="personal"
        echo "📍 Auto-selected: personal database (only available option)"
        if [[ "$personal_state" != "RUNNABLE" ]]; then
            echo "⏳ Personal database is $personal_state, will wait for it to be ready"
            wait_for_database_ready "$personal_db"
        fi
    else
        # No databases exist - create based on deployment profile preference
        echo "🔧 No databases found, creating based on deployment profile..."

        # Determine which database to create based on deployment target and user preference
        if [[ "$DEPLOYMENT_TARGET" == "shared" ]]; then
            echo "📦 Creating shared database for shared deployment..."
            DATABASE_CHOICE="shared"
            setup_database_with_template "$shared_db" "shared" "false"
            echo "✅ Created shared database: $shared_db"
        else
            # For personal deployments, ask user preference or use smart default
            echo ""
            echo "🤔 No databases exist. Which would you like to create?"
            echo " 1) 🌐 Shared database ($shared_db) - collaborate with team"
            echo " 2) 👤 Personal database ($personal_db) - isolated development"
            echo ""

            # Smart default: shared for better collaboration
            echo "💡 Recommendation: Shared database for team collaboration"
            read -p "Create database (1=shared, 2=personal, Enter=shared): " choice

            case "$choice" in
                "2")
                    echo "📦 Creating personal database for isolated development..."
                    DATABASE_CHOICE="personal"
                    setup_database_with_template "$personal_db" "personal" "false"
                    echo "✅ Created personal database: $personal_db"
                    ;;
                "1"|"")
                    echo "📦 Creating shared database for team collaboration..."
                    DATABASE_CHOICE="shared"
                    setup_database_with_template "$shared_db" "shared" "false"
                    echo "✅ Created shared database: $shared_db"
                    ;;
                *)
                    echo "❌ Invalid choice, defaulting to shared database"
                    DATABASE_CHOICE="shared"
                    setup_database_with_template "$shared_db" "shared" "false"
                    echo "✅ Created shared database: $shared_db"
                    ;;
            esac
        fi
    fi

    echo ""
}

# Check deployment logs for startup errors
check_deployment_logs() {
    local service="$1"
    local region="$2"

    echo "📋 Recent logs from $service:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Get recent logs, focusing on errors and startup issues
    gcloud run services logs read "$service" \
        --region="$region" \
        --limit=20 \
        --format="table(timestamp,severity,textPayload)" 2>/dev/null | \
        grep -E "(ERROR|WARN|FATAL|startup|connection|database|port)" || \
        echo "No error logs found. Check full logs with: gcloud run services logs read $service --region=$region"

    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Check for code changes since last deployment
check_changes() {
    local service="$1"
    local watch_paths="$2"

    if [[ "$FORCE_BUILD" == "true" ]]; then
        echo "🔨 Force build requested for $service"
        return 0
    fi

    # Get current git state
    local current_commit=""
    local repo_status="clean"

    if git rev-parse --git-dir >/dev/null 2>&1; then
        current_commit=$(git rev-parse HEAD 2>/dev/null || echo "")

        # Check if working tree is dirty in watched paths only
        if ! git diff-index --quiet HEAD -- $watch_paths 2>/dev/null; then
            repo_status="dirty"
        fi
    else
        echo "⚠️  Not in a git repository - will always rebuild"
        return 0
    fi

    if [[ -z "$current_commit" ]]; then
        echo "⚠️  Cannot determine git commit - will rebuild"
        return 0
    fi

    # Get deployed git commit from Cloud Run labels
    local deployed_commit
    deployed_commit=$(gcloud run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.labels.git-commit)" \
        2>/dev/null || echo "")

    if [[ -z "$deployed_commit" ]]; then
        echo "📦 $service not found or no git commit stored, building..."
        return 0
    fi

    # Check for uncommitted changes in watched paths
    if [[ "$repo_status" == "dirty" ]]; then
        echo "📝 Uncommitted changes detected in watched paths ($watch_paths), will rebuild..."
        if [[ "$VERBOSE" == "true" ]]; then
            echo "   💡 Tip: Commit your changes for more reliable change detection"
        fi
        return 0
    fi

    # Check if any files in the watched paths changed between commits
    local path_changes=0
    if [[ "$current_commit" != "$deployed_commit" ]]; then
        # Count changes in the specific paths we care about
        path_changes=$(git diff --name-only "$deployed_commit..$current_commit" -- $watch_paths 2>/dev/null | wc -l | tr -d ' ')
    fi

    # Compare git commits for watched paths only
    if [[ "$path_changes" -gt 0 ]]; then
        echo "📝 Git changes detected in $service paths: ${deployed_commit:0:8} → ${current_commit:0:8}"
        if [[ "$VERBOSE" == "true" ]]; then
            echo "   📊 $path_changes file(s) changed in: $watch_paths"
            echo "   📋 Changed files:"
            git diff --name-only "$deployed_commit..$current_commit" -- $watch_paths 2>/dev/null | sed 's/^/      • /' || echo "      (unable to show file details)"
        fi
        return 0
    fi

    echo "✅ No git changes in $service paths since last deploy (commit: ${current_commit:0:8})"

    # Interactive prompt to rebuild anyway (only in interactive mode)
    if [[ -t 0 && -t 1 ]]; then  # Check if running in interactive terminal
        read -p "No changes detected. Force rebuild $service? [y/N]: " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "🔨 Force rebuilding $service"
            return 0
        else
            echo "⏭️  Skipping $service build"
            return 1
        fi
    else
        # Non-interactive mode - always skip
        echo "⏭️  Skipping build (non-interactive mode)"
        return 1
    fi
}

# Show build optimization info
show_build_optimization() {
    local service="$1"
    local region="$2"

    local deployed_hash=$(gcloud run services describe "$service" \
        --region="$region" \
        --format="value(metadata.labels.source-hash)" \
        2>/dev/null || echo "")

    if [[ -n "$deployed_hash" ]]; then
        echo "   🔍 Deployed version: ${deployed_hash:0:12}..."

        # Calculate how many developers are using this project
        local developer_count=$(gcloud run services list \
            --region="$region" \
            --format="value(metadata.name)" \
            --filter="metadata.name~'^(agent-server|workroom)-'" 2>/dev/null |
            sed 's/.*-\([^-]*\)$/\1/' | sort -u | wc -l | tr -d ' ')

        if [[ "$developer_count" -gt 1 ]]; then
            echo "   👥 $developer_count developers using this project"
        fi
    fi
}

# Show authentication configuration summary
show_authentication_summary() {
    echo ""
    echo "🔐 Authentication Configuration Summary"
    echo "======================================"

    if [[ "$ENABLE_IAP" == "true" ]]; then
        echo "✅ IAP Security: ENABLED"
        echo ""
        echo "🛡️  Your services are protected by Google IAP:"
        echo "   • Only authenticated users can access your instances"
        echo "   • Authentication handled by Google accounts"
        echo "   • JWT tokens passed securely between services"
        echo ""

        case "$DEPLOYMENT_TARGET" in
            "shared")
                local current_user_email=$(gcloud config get-value account)
                local user_domain=$(echo "$current_user_email" | cut -d'@' -f2)
                echo "🌐 Shared/Demo Instance Access:"
                echo "   • Domain-wide access: Anyone from @$user_domain"
                echo "   • Manage: ./scripts/gcp/admin-iap.sh list-users shared"
                ;;
            "personal")
                echo "👤 Personal Instance Access:"
                echo "   • Owner access: You control who can access"
                echo "   • Manage: ./scripts/gcp/manage-my-iap.sh list"
                ;;
        esac

        echo ""
        echo "⚠️  First access may take 2-10 minutes for IAP to propagate"
        echo "💡 If you get 'access denied', try incognito mode or wait a few minutes"

    else
        echo "🌐 IAP Security: DISABLED"
        echo ""
        echo "⚠️  Your services are PUBLIC (no authentication):"
        echo "   • Anyone with the URL can access your instances"
        echo "   • No JWT authentication between services"
        echo "   • Suitable for development/testing only"
        echo ""
        echo "🔒 To enable security: ./scripts/gcp/manage-my-iap.sh enable"
    fi

    echo ""
}

# Deploy agent-server
deploy_agent_server() {
    echo "🖥️ Agent Server"

    # Ensure we have a valid database choice and create database if needed
    # Note: Only agent-server creates databases to avoid race conditions
    discover_and_set_database_choice

    local should_build=true

    # Get database IP (database choice is already set by discover_and_set_database_choice)
    local sql_ip db_instance
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"

    case "$DATABASE_CHOICE" in
        "shared")
            db_instance="$shared_db"
            ;;
        "personal")
            db_instance="$personal_db"
            ;;
        *)
            echo "❌ Invalid database choice: '$DATABASE_CHOICE'"
            exit 1
            ;;
    esac

    # Check if agent-server is already deployed and working
    local skip_build_but_deploy=false
    if [[ "$CONFIG_ONLY" == "false" && "$FORCE_BUILD" == "false" ]]; then
        local existing_url
        existing_url=$(get_service_url "$AGENT_SERVER_SERVICE" "$REGION")

        if [[ -n "$existing_url" ]]; then
            # Service exists, check database switch and code changes
            local db_switch_status=$(check_database_switch "$AGENT_SERVER_SERVICE" "$REGION" "$db_instance")
            local has_code_changes=false

            # Check for code changes in agent-server specific paths
            if check_changes "$AGENT_SERVER_SERVICE" "$PROJECT_ROOT/server $PROJECT_ROOT/core $PROJECT_ROOT/Dockerfile"; then
                echo "📝 Agent-server code changes detected, will rebuild..."
                has_code_changes=true
            fi

            case "$db_switch_status" in
                "SWITCH")
                    local current_db=$(get_current_database "$AGENT_SERVER_SERVICE" "$REGION")
                    echo "🔄 Database switch detected: $current_db → $db_instance"

                    if [[ "$has_code_changes" == "true" ]]; then
                        echo "📝 Code changes + database switch: will rebuild and redeploy..."
                        should_build=true
                    else
                        echo "🔄 Database-only change: reusing existing image, updating deployment..."
                        should_build=false
                        skip_build_but_deploy=true
                    fi
                    ;;
                "SAME")
                    if [[ "$has_code_changes" == "true" ]]; then
                        should_build=true
                    else
                        echo "✅ Agent-server already deployed with same database and no code changes"
                        should_build=false
                    fi
                    ;;
                "NEW")
                    echo "📦 First-time database configuration, will deploy..."
                    should_build=true
                    ;;
            esac
        else
            echo "Agent-server not deployed yet, will build..."
        fi
    elif [[ "$CONFIG_ONLY" == "true" ]]; then
        should_build=false
        skip_build_but_deploy=true
    fi

    # Ensure database is ready before getting IP
    echo "🔍 Checking database status..."
    local db_state=$(gcloud sql instances describe "$db_instance" \
        --format="value(state)" \
        --quiet 2>/dev/null || echo "NOT_FOUND")

    if [[ "$db_state" != "RUNNABLE" ]]; then
        echo "⚠️  Database '$db_instance' is not ready (state: $db_state)"

        # Check if there's an async database creation in progress
        if [[ "$db_state" == "NOT_FOUND" && -f "/tmp/async-db-${db_instance}.status" ]]; then
            echo "🔄 Async database creation detected, waiting for completion..."
            if wait_for_async_database "$db_instance"; then
                echo "✅ Async database creation completed!"
            else
                echo "❌ Async database creation failed!"
                exit 1
            fi
        else
            echo "⏳ Waiting for database to become operational..."
            wait_for_database_ready "$db_instance"
        fi
    fi

    # Get database IP for direct connection (database has public IP and allows connections)
    local sql_ip=$(gcloud sql instances describe "$db_instance" \
        --format="value(ipAddresses[0].ipAddress)" \
        --quiet 2>/dev/null || echo "")

    if [[ -z "$sql_ip" ]]; then
        echo "❌ Could not get database IP for $db_instance"
        return 1
    fi

    echo "✅ Database connection: $db_instance ($sql_ip) - direct IP connection"

    # Build if needed
    if [[ "$should_build" == "true" ]]; then
        show_progress "Building agent-server"

        # Get current git commit for labeling
        local git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        local short_commit=${git_commit:0:8}
        [[ "$VERBOSE" == "true" ]] && echo "   📋 Git commit: ${short_commit}..."

        if [[ "$VERBOSE" == "true" ]]; then
            docker build \
                --platform linux/amd64 \
                --label "build-id=$short_commit" \
                --label "last-deploy=$(date +%s)" \
                --label "git-commit=$git_commit" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:$BUILD_ID" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest" \
                -f Dockerfile .
        else
            docker build \
                --platform linux/amd64 \
                --label "build-id=$short_commit" \
                --label "last-deploy=$(date +%s)" \
                --label "git-commit=$git_commit" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:$BUILD_ID" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest" \
                -f Dockerfile . >/dev/null 2>&1
        fi

        show_progress "Pushing agent-server to registry"
        if [[ "$VERBOSE" == "true" ]]; then
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:$BUILD_ID"
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest"
        else
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:$BUILD_ID" >/dev/null 2>&1
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest" >/dev/null 2>&1
        fi
    else
        # Get git commit even when not building for deployment labels
        local git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        local short_commit=${git_commit:0:8}
    fi

    # Deploy only if we built or need to update (database switch, config changes)
    if [[ "$should_build" == "true" || "$skip_build_but_deploy" == "true" ]]; then
        echo "Deploying agent-server to Cloud Run..."

    # Set deployment profile label
    local desired_profile=""
    case "$DEPLOYMENT_TARGET-$DATABASE_CHOICE" in
        "personal-personal") desired_profile="personal-isolated" ;;
        "personal-shared") desired_profile="personal-shared" ;;
        "shared-shared") desired_profile="team-production" ;;
    esac

    # Build gcloud command (always use stable gcloud for deployment)
    local deploy_cmd="gcloud run deploy \"$AGENT_SERVER_SERVICE\" \
        --image=\"$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/agent-server:latest\" \
        --platform=managed \
        --region=\"$REGION\""

    # Agent-server is always public - when IAP is enabled, it uses JWT authentication from workroom
    deploy_cmd="$deploy_cmd \
        --allow-unauthenticated"

    # Build environment variables for direct database connection
    local env_vars="SEMA4AI_AGENT_SERVER_OTEL_ENABLED=true,SEMA4AI_AGENT_SERVER_ENABLE_WORKITEMS=true,SEMA4AI_OPTIMIZE_FOR_CONTAINER=1,SEMA4AI_AGENT_SERVER_DB_TYPE=postgres,POSTGRES_HOST=$sql_ip,POSTGRES_PORT=5432,POSTGRES_DB=agents,POSTGRES_USER=agents,POSTGRES_PASSWORD=agents,SEMA4AI_AGENT_SERVER_LOG_LEVEL=DEBUG,SEMA4AI_AGENT_SERVER_HOST=0.0.0.0,SEMA4AI_AGENT_SERVER_PORT=8000,LOG_LEVEL=DEBUG,FORWARDED_ALLOW_IPS=*,USE_FORWARDED_HOST=true,SECURE_SCHEME_HEADERS=X-Forwarded-Proto:https"

    # Always add JWT authentication variables for secure service communication on GCP
    local jwt_env_vars="AUTH_TYPE=jwt_local,JWT_ALG=ES256,JWT_AUD=agent_server,JWT_ISS=spar"
    local jwt_decode_key="JWT_DECODE_KEY_B64=LS0tLS1CRUdJTiBQVUJMSUMgS0VZLS0tLS0KTUZrd0V3WUhLb1pJemowQ0FRWUlLb1pJemowREFRY0RRZ0FFZGpZdnZIcFpnY2FQUy9TOHdJanVjYzlYcUJIYgpyUVNpOGhxSngySGhybzlDZzg3cHdnSGNpWDkwT20xUDFTTEpHaVFVL1lUeG4wbllEQllaU1AwMU9RPT0KLS0tLS1FTkQgUFVCTElDIEtFWS0tLS0tCg=="

    if [[ "$ENABLE_IAP" == "true" ]]; then
        echo "🔐 Agent-server: Public with JWT authentication (IAP-protected workroom)"
    else
        echo "🔐 Agent-server: Public with JWT authentication (public workroom)"
    fi

    deploy_cmd="$deploy_cmd \
        --ingress=all \
        --port=8000 \
        --memory=2Gi \
        --cpu=2 \
        --min-instances=0 \
        --max-instances=10 \
        --timeout=900 \
        --cpu-boost \
        --execution-environment=gen2 \
        --set-env-vars=\"$env_vars\" \
        --set-env-vars=\"$jwt_env_vars\" \
        --set-env-vars=\"$jwt_decode_key\""

    deploy_cmd="$deploy_cmd \
        --update-labels=\"last-deploy=\$(date +%s),deployed-by=$CURRENT_USER,build-id=$short_commit,git-commit=$git_commit,deployment-profile=$desired_profile\""

        echo "🖥️ Deploying Agent Server..."

        # Execute the deployment command
        if eval $deploy_cmd; then
            echo "✅ Agent Server deployed"
        else
            echo "❌ Agent Server deployment failed"
            echo "💡 Check logs: make gcp status --logs agent-server"
            return 1
        fi
    else
        echo "⏭️  No changes detected"
    fi
}

# Deploy workroom
deploy_workroom() {
    echo "🎨 Workroom"

    # Get database choice for profile consistency only (no database creation)
    get_database_choice_for_profile

    # Determine database instance for workroom database switch detection
    local personal_db="agent-postgres-${CURRENT_USER}"
    local shared_db="agent-postgres"
    local db_instance

    case "$DATABASE_CHOICE" in
        "shared")
            db_instance="$shared_db"
            ;;
        "personal")
            db_instance="$personal_db"
            ;;
        *)
            echo "❌ Invalid database choice: '$DATABASE_CHOICE'"
            exit 1
            ;;
    esac

    local should_build=true

    # Check if workroom is already deployed and working
    local skip_build_but_deploy=false
    if [[ "$CONFIG_ONLY" == "false" && "$FORCE_BUILD" == "false" ]]; then
        local existing_url
        existing_url=$(get_service_url "$WORKROOM_SERVICE" "$REGION")

        if [[ -n "$existing_url" ]]; then
            # Service exists, check for database changes and code changes
            local has_code_changes=false

            # Check for code changes in workroom-specific paths
            if check_changes "$WORKROOM_SERVICE" "$PROJECT_ROOT/workroom"; then
                echo "📝 Workroom code changes detected, will rebuild..."
                has_code_changes=true
            fi

                         # Check for deployment profile change (check both workroom and agent-server profiles)
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

             # Smart profile inheritance: if agent-server has the desired profile and workroom doesn't,
             # inherit silently instead of asking the user
             local profile_change_needed=false

             if [[ -n "$agent_profile" && -z "$workroom_profile" && "$agent_profile" == "$desired_profile" ]]; then
                 # Agent-server has correct profile, workroom has none - inherit silently
                 echo "📋 Inheriting deployment profile from agent-server: $(explain_profile "$desired_profile")"
                 profile_change_needed=true  # Still need to update workroom, but no user confirmation needed
             elif [[ "$workroom_profile" != "$desired_profile" || "$agent_profile" != "$desired_profile" ]]; then
                 profile_change_needed=true
                 echo "🔄 Deployment profile update detected:"
                 echo ""
                 echo "   📊 Current deployment profiles:"
                 echo "      • Workroom: $(explain_profile "$workroom_profile")"
                 echo "      • Agent-server: $(explain_profile "$agent_profile")"
                 echo ""
                 echo "   🎯 Target deployment profile:"
                 echo "      • $(explain_profile "$desired_profile")"
                 echo ""
                 echo "   💡 Note: Both services will be updated to maintain consistency"
                 echo "      The agent-server and workroom must use the same database configuration."
                 echo ""
             fi

                           if [[ "$profile_change_needed" == "true" ]]; then
                  if [[ "$has_code_changes" == "true" ]]; then
                      echo "Code changes + profile change: will rebuild and redeploy..."
                      should_build=true
                  else
                      echo "Profile-only change: reusing existing image, updating deployment..."
                      should_build=false
                      skip_build_but_deploy=true
                  fi
             else
                 if [[ "$has_code_changes" == "true" ]]; then
                     should_build=true
                 else
                     echo "Workroom already deployed with correct profile ($desired_profile), skipping build..."
                     should_build=false
                 fi
             fi
        else
            echo "Workroom not deployed yet, will build..."
        fi
    elif [[ "$CONFIG_ONLY" == "true" ]]; then
        should_build=false
        skip_build_but_deploy=true
    fi

    # Get agent server URL (agent server should be deployed by now)
    echo "🔍 Looking for agent server: $AGENT_SERVER_SERVICE"
    local agent_server_url=$(gcloud run services describe "$AGENT_SERVER_SERVICE" \
        --region="$REGION" \
        --format="value(status.url)" \
        --quiet 2>/dev/null || echo "")

    if [[ -z "$agent_server_url" ]]; then
        echo "❌ Agent server not found!"
        echo ""
        echo "💡 This shouldn't happen if agent server was deployed first"
        echo "🔧 Deploy agent server first: $0 --agent-server"
        exit 1
    fi

    echo "✅ Found agent server: $agent_server_url"
    local agent_server_host=$(echo "$agent_server_url" | sed 's|https://||')

    # Build if needed
    if [[ "$should_build" == "true" ]]; then
        show_progress "Building workroom"

        # Get current git commit for labeling
        local git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        local short_commit=${git_commit:0:8}

        # Handle npmrc authentication - prioritize local development
        local npmrc_source=""

        # Option 1: Try local .npmrc first (for development)
        if [[ -f "$HOME/.npmrc" ]]; then
            echo "✅ Using local ~/.npmrc for npm authentication"
            npmrc_source="$HOME/.npmrc"
        else
            # Option 2: Try GCP secret (for deployment)
            echo "🔍 Local ~/.npmrc not found, trying GCP secret..."
            if gcloud secrets versions access latest --secret=npmrc-secret > /tmp/.npmrc 2>/dev/null; then
                echo "✅ Using GCP npmrc-secret for npm authentication"
                npmrc_source="/tmp/.npmrc"
            else
                echo "❌ No npm authentication found!"
                echo ""
                echo "For local development, create ~/.npmrc with:"
                echo "  @sema4ai:registry=https://npm.pkg.github.com"
                echo "  //npm.pkg.github.com/:_authToken=YOUR_GITHUB_TOKEN"
                echo ""
                echo "For deployment, create GCP secret:"
                echo "  gcloud secrets create npmrc-secret --data-file=~/.npmrc"
                echo ""
                echo "See README for GitHub token setup instructions."
                exit 1
            fi
        fi

        if [[ "$VERBOSE" == "true" ]]; then
            docker build \
                --platform linux/amd64 \
                --secret id=npmrc,src="$npmrc_source" \
                --build-arg NODE_ENV=production \
                --label "build-id=$short_commit" \
                --label "last-deploy=$(date +%s)" \
                --label "git-commit=$git_commit" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:$BUILD_ID" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest" \
                -f workroom/Dockerfile ./workroom
        else
            docker build \
                --platform linux/amd64 \
                --secret id=npmrc,src="$npmrc_source" \
                --build-arg NODE_ENV=production \
                --label "build-id=$short_commit" \
                --label "last-deploy=$(date +%s)" \
                --label "git-commit=$git_commit" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:$BUILD_ID" \
                -t "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest" \
                -f workroom/Dockerfile ./workroom >/dev/null 2>&1
        fi

        show_progress "Pushing workroom to registry"
        if [[ "$VERBOSE" == "true" ]]; then
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:$BUILD_ID"
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest"
        else
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:$BUILD_ID" >/dev/null 2>&1
            docker push "$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest" >/dev/null 2>&1
        fi

        # Clean up temporary npmrc if we created one
        if [[ "$npmrc_source" == "/tmp/.npmrc" ]]; then
            rm -f /tmp/.npmrc
        fi
    else
        # Get git commit even when not building for deployment labels
        local git_commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
        local short_commit=${git_commit:0:8}
    fi

    # Deploy only if we built or need to update (config changes)
    if [[ "$should_build" == "true" || "$skip_build_but_deploy" == "true" ]]; then
        echo "🎨 Deploying Workroom..."

    # Build gcloud command (always use stable gcloud for deployment)
    local deploy_cmd="gcloud run deploy \"$WORKROOM_SERVICE\" \
        --image=\"$REGION-docker.pkg.dev/$PROJECT_ID/cloud-run-source-deploy/workroom:latest\" \
        --platform=managed \
        --region=\"$REGION\""

    if [[ "$ENABLE_IAP" == "true" ]]; then
        echo "🔐 Deploying workroom for IAP (will enable IAP after deployment)..."
        deploy_cmd="$deploy_cmd \
        --no-allow-unauthenticated"
    else
        deploy_cmd="$deploy_cmd \
        --allow-unauthenticated"
    fi

    # Set deployment profile label
    local desired_profile=""
    case "$DEPLOYMENT_TARGET-$DATABASE_CHOICE" in
        "personal-personal") desired_profile="personal-isolated" ;;
        "personal-shared") desired_profile="personal-shared" ;;
        "shared-shared") desired_profile="team-production" ;;
    esac

    # Build environment variables for workroom
    local workroom_env_vars="AGENT_SERVER_URL=$agent_server_url,AGENT_SERVER_HOST=$agent_server_host,DEPLOYMENT_TYPE=spar,NODE_ENV=production"

    # Always add JWT authentication for secure service communication on GCP
    workroom_env_vars="$workroom_env_vars,AUTH_MODE=google,JWT_PRIVATE_KEY_B64=LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JR0hBZ0VBTUJNR0J5cUdTTTQ5QWdFR0NDcUdTTTQ5QXdFSEJHMHdhd0lCQVFRZ2xIaFNPVUFLcTMxMm1zN2QKT0RKMmhqRkRqaGNnaWltSnZ4bVh1bE9BWU51aFJBTkNBQVIyTmkrOGVsbUJ4bzlMOUx6QWlPNXh6MWVvRWR1dApCS0x5R29uSFllR3VqMEtEenVuQ0FkeUpmM1E2YlUvVklza2FKQlQ5aFBHZlNkZ01GaGxJL1RVNQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg=="

    if [[ "$ENABLE_IAP" == "true" ]]; then
        echo "🔐 Workroom: IAP authentication + secure JWT communication"
    else
        echo "🌐 Workroom: Public access + secure JWT communication"
    fi

    deploy_cmd="$deploy_cmd \
        --port=3001 \
        --memory=1Gi \
        --cpu=1 \
        --timeout=300 \
        --set-env-vars=\"$workroom_env_vars\" \
        --update-labels=\"last-deploy=\$(date +%s),deployed-by=$CURRENT_USER,build-id=$short_commit,git-commit=$git_commit,deployment-profile=$desired_profile\" \
        --quiet"

        # Execute the deployment command
        if eval $deploy_cmd; then
            # Get workroom URL and update meta URLs
            local workroom_url=$(gcloud run services describe "$WORKROOM_SERVICE" \
                --region="$REGION" \
                --format="value(status.url)" \
                --quiet)

            gcloud run services update "$WORKROOM_SERVICE" \
                --region="$REGION" \
                --update-env-vars="META_URL=$workroom_url/meta,WORKROOM_URL=$workroom_url" \
                --quiet

            echo "✅ Workroom deployed"
        else
            echo "❌ Workroom deployment failed"
            echo "💡 Check logs: make gcp status --logs workroom"
            return 1
        fi
    else
        echo "⏭️  No changes detected"
    fi
}
