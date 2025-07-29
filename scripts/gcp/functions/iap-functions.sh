#!/bin/bash

# IAP Functions Module
# Handles Identity-Aware Proxy configuration and management

# Make Agent Server Internal (not publicly accessible)
make_agent_server_internal() {
    local service="$AGENT_SERVER_SERVICE"
    local display_name="Agent Server"
    
    # Check if service exists
    if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
        echo "❌ $display_name service not found. Deploy it first."
        return 1
    fi
    
    echo "🔒 Setting $display_name to internal access only..."
    echo "💡 This means only other GCP services (like Workroom) can access it"
    
    local temp_output
    temp_output=$(mktemp)
    
    if gcloud run services update "$service" \
        --region="$REGION" \
        --ingress=internal \
        --quiet 2>"$temp_output"; then
        echo "✅ $display_name is now internal-only"
        echo "🏠 Only accessible from within your GCP project"
        echo "🔗 Workroom can still proxy requests to it"
        
        # Show service URL for reference
        local service_url=$(gcloud run services describe "$service" \
            --region="$REGION" \
            --format="value(status.url)" \
            --quiet 2>/dev/null || echo "")
        
        if [[ -n "$service_url" ]]; then
            echo ""
            echo "🌐 Internal URL: $service_url"
            echo "⚠️  This URL is NOT accessible from the public internet"
        fi
    else
        echo "❌ Failed to make $display_name internal"
        echo "🔍 Error details:"
        cat "$temp_output" | sed 's/^/   /'
    fi
    
    rm -f "$temp_output"
}

# Make Agent Server Public (publicly accessible)
make_agent_server_public() {
    local service="$AGENT_SERVER_SERVICE"
    local display_name="Agent Server"
    
    # Check if service exists
    if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
        echo "❌ $display_name service not found. Deploy it first."
        return 1
    fi
    
    echo "⚠️  WARNING: Making $display_name publicly accessible!"
    echo "🌐 Anyone on the internet will be able to access it without authentication"
    read -p "Are you sure you want to continue? [y/N]: " confirm
    
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        return 0
    fi
    
    echo "🌐 Setting $display_name to public access..."
    
    local temp_output
    temp_output=$(mktemp)
    
    if gcloud run services update "$service" \
        --region="$REGION" \
        --ingress=all \
        --allow-unauthenticated \
        --quiet 2>"$temp_output"; then
        echo "✅ $display_name is now publicly accessible"
        echo "⚠️  Anyone can access it without authentication"
        
        # Show service URL
        local service_url=$(gcloud run services describe "$service" \
            --region="$REGION" \
            --format="value(status.url)" \
            --quiet 2>/dev/null || echo "")
        
        if [[ -n "$service_url" ]]; then
            echo ""
            echo "🌐 Public URL: $service_url"
            echo "💡 Consider using IAP for security if you need public access"
        fi
        
        echo ""
        echo "⏱️  Important: Ingress changes can take 2-5 minutes to propagate"
    else
        echo "❌ Failed to make $display_name public"
        echo "🔍 Error details:"
        cat "$temp_output" | sed 's/^/   /'
    fi
    
    rm -f "$temp_output"
}

# Enable IAP on a specific service
enable_iap_on_service() {
    local service="$1"
    local display_name="$2"
    
    # Check if service exists
    if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
        echo "❌ $display_name service not found. Deploy it first."
        return 1
    fi
    
    # Check current IAP status first
    local current_iap_status
    current_iap_status=$(gcloud beta run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
        --quiet 2>/dev/null || echo "unknown")
    
    if [[ "$current_iap_status" == "true" ]]; then
        echo "ℹ️  IAP is already enabled on $display_name"
        return 0
    fi
    
    # Enable IAP API
    echo "🔧 Ensuring IAP API is enabled..."
    if ! gcloud services enable iap.googleapis.com --quiet; then
        echo "❌ Failed to enable IAP API. Check your permissions."
        return 1
    fi
    
    # First, ensure clean IAP state by clearing any existing IAP configuration
    echo "🔄 Refreshing IAP service agents..."
    gcloud beta run services update "$service" \
        --region="$REGION" \
        --no-iap \
        --quiet >/dev/null 2>&1 || true
    
    # Brief pause to let the disable take effect
    sleep 2
    
    # Enable IAP on the service (show errors)
    echo "🔐 Enabling IAP on $display_name..."
    local temp_output
    temp_output=$(mktemp)
    
    if gcloud beta run services update "$service" \
        --region="$REGION" \
        --iap \
        --quiet 2>"$temp_output"; then
        echo "✅ IAP enabled on $display_name"
        
        # Verify IAP was actually enabled
        local new_iap_status
        new_iap_status=$(gcloud beta run services describe "$service" \
            --region="$REGION" \
            --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
            --quiet 2>/dev/null || echo "unknown")
        
        if [[ "$new_iap_status" == "true" ]]; then
            echo "✅ IAP status confirmed: Enabled"
        else
            echo "⚠️  IAP command succeeded but status is unclear: $new_iap_status"
        fi
        
        # Grant access to current user
        local current_user_email=$(gcloud config get-value account)
        echo "👤 Granting IAP access to: $current_user_email"
        
        # Brief pause to ensure IAP is fully enabled before adding access
        sleep 2
        
        if gcloud beta iap web add-iam-policy-binding \
            --member="user:$current_user_email" \
            --role=roles/iap.httpsResourceAccessor \
            --region="$REGION" \
            --resource-type=cloud-run \
            --service="$service" \
            --quiet 2>/dev/null; then
            echo "✅ Access granted to $current_user_email"
            echo "⏱️  Note: Access changes may take 2-10 minutes to propagate"
        else
            echo "⚠️  Failed to grant access automatically. Add it manually:"
            echo "   ./scripts/gcp/manage-iap-access.sh add $current_user_email"
        fi
        
        echo ""
        echo "🎉 $display_name is now protected by IAP!"
        echo ""
        echo "⏱️  Important: IAP changes can take 2-10 minutes to propagate"
        echo "🔍 If you get 'access denied' errors:"
        echo "   • Wait 3-5 minutes for full propagation"
        echo "   • Try incognito/private browsing mode"
        echo "   • Clear browser cache for *.run.app domains"
        echo "   • Make sure you're signed into the correct Google account"
        echo ""
        echo "💡 Use ./scripts/gcp/manage-iap-access.sh to manage user access"
        
        # Show service URL for testing
        local service_url=$(gcloud run services describe "$service" \
            --region="$REGION" \
            --format="value(status.url)" \
            --quiet 2>/dev/null || echo "")
        
        if [[ -n "$service_url" ]]; then
            echo ""
            echo "🌐 Test your IAP-protected service:"
            echo "   $service_url"
            echo "   $service_url/debug/iap/page (debug endpoint)"
        fi
        
        # Small delay to let IAP changes start propagating
        echo ""
        echo "⏳ Waiting 3 seconds for initial propagation..."
        sleep 3
    else
        echo "❌ Failed to enable IAP on $display_name"
        echo "🔍 Error details:"
        cat "$temp_output" | sed 's/^/   /'
        echo ""
        echo "💡 Common issues:"
        echo "   • Project must be in a Google Cloud organization"
        echo "   • You need IAP admin permissions"
        echo "   • Check: gcloud auth list"
    fi
    
    rm -f "$temp_output"
}

# Disable IAP on a specific service
disable_iap_on_service() {
    local service="$1"
    local display_name="$2"
    
    # Check if service exists
    if ! gcloud run services describe "$service" --region="$REGION" --quiet >/dev/null 2>&1; then
        echo "❌ $display_name service not found."
        return 1
    fi
    
    # Check current IAP status first
    local current_iap_status
    current_iap_status=$(gcloud beta run services describe "$service" \
        --region="$REGION" \
        --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
        --quiet 2>/dev/null || echo "unknown")
    
    if [[ "$current_iap_status" == "false" || "$current_iap_status" == "" ]]; then
        echo "ℹ️  IAP is already disabled on $display_name (service is public)"
        return 0
    fi
    
    if [[ "$current_iap_status" == "unknown" ]]; then
        echo "⚠️  Cannot determine current IAP status for $display_name"
        echo "🔍 Service may not support IAP or there may be a permissions issue"
    fi
    
    echo "⚠️  WARNING: Disabling IAP will make $display_name publicly accessible!"
    read -p "Are you sure you want to continue? [y/N]: " confirm
    
    if [[ ! $confirm =~ ^[Yy]$ ]]; then
        echo "❌ Cancelled"
        return 0
    fi
    
    # Disable IAP on the service (show errors)
    echo "🔓 Disabling IAP on $display_name..."
    local temp_output
    temp_output=$(mktemp)
    
    if gcloud beta run services update "$service" \
        --region="$REGION" \
        --no-iap \
        --quiet 2>"$temp_output"; then
        echo "✅ IAP disabled on $display_name"
        
        # Verify IAP was actually disabled
        local new_iap_status
        new_iap_status=$(gcloud beta run services describe "$service" \
            --region="$REGION" \
            --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
            --quiet 2>/dev/null || echo "unknown")
        
        if [[ "$new_iap_status" == "false" || "$new_iap_status" == "" ]]; then
            echo "✅ IAP status confirmed: Disabled"
        else
            echo "⚠️  IAP command succeeded but status is unclear: $new_iap_status"
        fi
        
        echo "⚠️  $display_name is now publicly accessible"
        echo ""
        echo "⏱️  Important: IAP changes can take 2-5 minutes to propagate"
        echo "🌐 The service should be accessible without authentication shortly"
    else
        echo "❌ Failed to disable IAP on $display_name"
        echo "🔍 Error details:"
        cat "$temp_output" | sed 's/^/   /'
        echo ""
        echo "💡 This may be normal if IAP was already disabled"
    fi
    
    rm -f "$temp_output"
}

# Quick Setup: Configure secure architecture
setup_secure_architecture() {
    echo "🎯 Configuring secure architecture..."
    echo "🔧 This will:"
    echo "   • Enable IAP on Workroom (user-facing with authentication)"  
    echo "   • Make Agent Server internal-only (backend, accessed via workroom)"
    echo ""
    
    local has_errors=false
    
    # Step 1: Enable IAP on Workroom
    echo "Step 1/2: 🔐 Enabling IAP on Workroom..."
    if enable_iap_on_service "$WORKROOM_SERVICE" "Workroom"; then
        echo "✅ Workroom IAP enabled"
    else
        echo "❌ Failed to enable IAP on Workroom"
        has_errors=true
    fi
    
    echo ""
    
    # Step 2: Make Agent Server internal
    echo "Step 2/2: 🏠 Making Agent Server internal..."
    if make_agent_server_internal; then
        echo "✅ Agent Server is now internal-only"
    else
        echo "❌ Failed to make Agent Server internal"
        has_errors=true
    fi
    
    echo ""
    
    if [[ "$has_errors" == "false" ]]; then
        echo "🎉 Secure architecture setup complete!"
        echo ""
        echo "✅ Your setup:"
        echo "   🎨 Workroom: Protected by IAP, accessible to users"
        echo "   🖥️  Agent Server: Internal-only, accessible via workroom proxy"
        echo ""
        echo "🌐 Users access: https://workroom-$(gcloud config get-value account | cut -d'@' -f1 | tr '.' '-')-3opijib4zq-ew.a.run.app"
        echo "🔒 Agent Server: Not directly accessible from internet (secure!)"
        echo ""
        echo "⏱️  Changes may take 2-10 minutes to fully propagate"
    else
        echo "⚠️  Setup completed with some errors. Check the output above."
    fi
}

# Setup IAP for deployed services with intelligent access management
setup_iap_permissions() {
    echo "🔐 Setting up IAP..."
    
    # Enable IAP API if not already enabled
    echo "🔧 Enabling IAP API..."
    gcloud services enable iap.googleapis.com --quiet
    
    # Configure services based on IAP security model:
    # - Workroom: Enable IAP (user-facing frontend with Google auth)
    # - Agent-server: Public but JWT authenticated (workroom signs tokens to access it)
    
    # Agent-server doesn't need IAP (it uses JWT authentication from workroom)
    if [[ "$DEPLOY_AGENT_SERVER" == "true" ]]; then
        echo "ℹ️  Agent-server: Public with JWT authentication (workroom has signing key)"
        echo "✅ Agent-server authentication is configured during deployment"
    fi
    
    # Enable IAP only on workroom (user-facing service)
    if [[ "$DEPLOY_WORKROOM" == "true" ]]; then
        echo "🔐 Enabling IAP on workroom (user-facing service)..."
        if gcloud beta run services update "$WORKROOM_SERVICE" \
            --region="$REGION" \
            --iap \
            --quiet 2>/dev/null; then
            echo "✅ IAP enabled on workroom"
        else
            echo "⚠️  Failed to enable IAP on workroom"
        fi
    fi
    
    # Get current user email for permissions
    local current_user_email=$(gcloud config get-value account)
    
    if [[ -z "$current_user_email" ]]; then
        echo "❌ Unable to get current user email"
        return 1
    fi
    
    # Determine access strategy based on deployment type
    local access_strategy=""
    local user_domain=$(echo "$current_user_email" | cut -d'@' -f2)
    
    case "$DEPLOYMENT_TARGET" in
        "shared")
            echo "🌐 Shared/Demo deployment detected"
            access_strategy="domain"
            ;;
        "personal")
            echo "👤 Personal deployment detected"
            access_strategy="user"
            ;;
        *)
            echo "❓ Unknown deployment target, defaulting to user access"
            access_strategy="user"
            ;;
    esac
    
    # Apply access policy only to workroom (only service with IAP)
    if [[ "$DEPLOY_WORKROOM" == "true" ]]; then
        echo "🔒 Setting IAP access policy for workroom..."
        
        case "$access_strategy" in
            "domain")
                echo "🏢 Granting domain-wide access to: @$user_domain"
                if gcloud beta iap web add-iam-policy-binding \
                    --member="domain:$user_domain" \
                    --role=roles/iap.httpsResourceAccessor \
                    --region="$REGION" \
                    --resource-type=cloud-run \
                    --service="$WORKROOM_SERVICE" \
                    --quiet 2>/dev/null; then
                    echo "✅ Domain access granted to workroom (@$user_domain)"
                else
                    echo "⚠️  Failed to grant domain access, falling back to user access..."
                    # Fallback to user access
                    gcloud beta iap web add-iam-policy-binding \
                        --member="user:$current_user_email" \
                        --role=roles/iap.httpsResourceAccessor \
                        --region="$REGION" \
                        --resource-type=cloud-run \
                        --service="$WORKROOM_SERVICE" \
                        --quiet 2>/dev/null || true
                fi
                ;;
            "user")
                echo "👤 Granting user access to: $current_user_email"
                if gcloud beta iap web add-iam-policy-binding \
                    --member="user:$current_user_email" \
                    --role=roles/iap.httpsResourceAccessor \
                    --region="$REGION" \
                    --resource-type=cloud-run \
                    --service="$WORKROOM_SERVICE" \
                    --quiet 2>/dev/null; then
                    echo "✅ User access granted to workroom"
                else
                    echo "⚠️  Access may already exist for workroom"
                fi
                ;;
        esac
    fi
    
    echo ""
    echo "✅ IAP setup complete"
    echo ""
    echo "🏗️  Architecture Summary:"
    echo "   📱 Workroom: IAP-protected (Google authentication for users)"
    echo "   🔧 Agent-server: Public + JWT authenticated (workroom signs tokens)"
    echo ""
    
    # Show appropriate management commands based on deployment type
    case "$access_strategy" in
        "domain")
            echo "🏢 Domain-wide access configured for @$user_domain"
            echo ""
            echo "🔗 To manage access:"
            echo "   ./scripts/gcp/admin-iap.sh list-users shared    # Show current access"
            echo "   ./scripts/gcp/admin-iap.sh add-user user@$user_domain shared  # Add specific user"
            ;;
        "user")
            echo "👤 Personal instance access configured"
            echo ""
            echo "🔗 To manage your instance access:"
            echo "   ./scripts/gcp/manage-my-iap.sh list             # Show current access"
            echo "   ./scripts/gcp/manage-my-iap.sh add colleague@$user_domain  # Add colleague"
            ;;
    esac
    echo ""
} 