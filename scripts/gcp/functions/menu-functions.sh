#!/bin/bash

# Menu Functions Module
# Handles interactive menu systems and user interface

# IAP Management Menu
show_iap_management_menu() {
    echo ""
    echo "🛡️  IAP Management"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # Check current IAP status with better diagnostics
    local agent_iap_status="Unknown"
    local workroom_iap_status="Unknown"
    
    echo "🔍 Checking IAP and ingress status..."
    
    if gcloud run services describe "$AGENT_SERVER_SERVICE" --region="$REGION" --quiet >/dev/null 2>&1; then
        local agent_iap=$(gcloud beta run services describe "$AGENT_SERVER_SERVICE" \
            --region="$REGION" \
            --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
            --quiet 2>/dev/null || echo "unknown")
        local agent_ingress=$(gcloud run services describe "$AGENT_SERVER_SERVICE" \
            --region="$REGION" \
            --format="value(spec.template.metadata.annotations['run.googleapis.com/ingress'])" \
            --quiet 2>/dev/null || echo "all")
        
        local iap_part=""
        case "$agent_iap" in
            "true") iap_part="IAP: ✅" ;;
            "false"|"") iap_part="IAP: ❌" ;;
            *) iap_part="IAP: ⚠️ ($agent_iap)" ;;
        esac
        
        local ingress_part=""
        case "$agent_ingress" in
            "internal") ingress_part="🏠 Internal" ;;
            "all"|"") ingress_part="🌐 Public" ;;
            *) ingress_part="⚠️ ($agent_ingress)" ;;
        esac
        
        agent_iap_status="$iap_part, $ingress_part"
    else
        agent_iap_status="❌ Not deployed"
    fi
    
    if gcloud run services describe "$WORKROOM_SERVICE" --region="$REGION" --quiet >/dev/null 2>&1; then
        local workroom_iap=$(gcloud beta run services describe "$WORKROOM_SERVICE" \
            --region="$REGION" \
            --format="value(metadata.annotations['run.googleapis.com/iap-enabled'])" \
            --quiet 2>/dev/null || echo "unknown")
        local workroom_ingress=$(gcloud run services describe "$WORKROOM_SERVICE" \
            --region="$REGION" \
            --format="value(spec.template.metadata.annotations['run.googleapis.com/ingress'])" \
            --quiet 2>/dev/null || echo "all")
        
        local iap_part=""
        case "$workroom_iap" in
            "true") iap_part="IAP: ✅" ;;
            "false"|"") iap_part="IAP: ❌" ;;
            *) iap_part="IAP: ⚠️ ($workroom_iap)" ;;
        esac
        
        local ingress_part=""
        case "$workroom_ingress" in
            "internal") ingress_part="🏠 Internal" ;;
            "all"|"") ingress_part="🌐 Public" ;;
            *) ingress_part="⚠️ ($workroom_ingress)" ;;
        esac
        
        workroom_iap_status="$iap_part, $ingress_part"
    else
        workroom_iap_status="❌ Not deployed"
    fi
    
    echo "📊 Current Service Status:"
    echo "   🖥️  Agent Server: $agent_iap_status"
    echo "   🎨 Workroom: $workroom_iap_status"
    echo ""
    echo "💡 Recommended architecture:"
    echo "   🎨 Workroom: IAP ✅, Public 🌐 (user-facing with authentication)"
    echo "   🖥️  Agent Server: IAP ❌, Internal 🏠 (backend only, accessed via workroom)"
    echo ""
    
    echo "🛡️  What would you like to do?"
    echo ""
    echo " 1) 🔐 Enable IAP on Workroom (recommended for user access)"
    echo " 2) 🔓 Disable IAP on Workroom"
    echo " 3) 🔐 Enable IAP on Agent Server"
    echo " 4) 🔓 Disable IAP on Agent Server"
    echo " 5) 🎯 Quick Setup: Secure Architecture (Workroom: IAP+Public, Agent: Internal)"
    echo " 6) 🏠 Make Agent Server Internal (recommended for security)"
    echo " 7) 🌐 Make Agent Server Public"
    echo " 8) 👥 Manage IAP Access (add/remove users)"
    echo " 9) 📊 Show detailed IAP status"
    echo " 0) ⬅️  Back to main menu"
    echo ""
    
    while true; do
        read -p "Select IAP option (0-9): " iap_choice
        
        case $iap_choice in
            1)
                echo "🔐 Enabling IAP on Workroom..."
                enable_iap_on_service "$WORKROOM_SERVICE" "Workroom"
                echo ""
                echo "⏱️  IAP action complete. Refreshing status in 2 seconds..."
                sleep 2
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            2)
                echo "🔓 Disabling IAP on Workroom..."
                disable_iap_on_service "$WORKROOM_SERVICE" "Workroom"
                echo ""
                echo "⏱️  IAP action complete. Refreshing status in 2 seconds..."
                sleep 2
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            3)
                echo "🔐 Enabling IAP on Agent Server..."
                enable_iap_on_service "$AGENT_SERVER_SERVICE" "Agent Server"
                echo ""
                echo "⏱️  IAP action complete. Refreshing status in 2 seconds..."
                sleep 2
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            4)
                echo "🔓 Disabling IAP on Agent Server..."
                disable_iap_on_service "$AGENT_SERVER_SERVICE" "Agent Server"
                echo ""
                echo "⏱️  IAP action complete. Refreshing status in 2 seconds..."
                sleep 2
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            5)
                echo "🎯 Setting up secure architecture..."
                setup_secure_architecture
                echo ""
                echo "⏱️  Setup complete. Refreshing status in 3 seconds..."
                sleep 3
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            6)
                echo "🏠 Making Agent Server Internal..."
                make_agent_server_internal
                echo ""
                echo "⏱️  IAP action complete. Refreshing status in 2 seconds..."
                sleep 2
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            7)
                echo "🌐 Making Agent Server Public..."
                make_agent_server_public
                echo ""
                echo "⏱️  IAP action complete. Refreshing status in 2 seconds..."
                sleep 2
                # Re-call the function to refresh status and show menu again
                show_iap_management_menu
                return
                ;;
            8)
                echo "👥 Opening IAP Access Management..."
                "$SCRIPT_DIR/manage-iap-access.sh" list
                echo ""
                echo "💡 Use ./scripts/gcp/manage-iap-access.sh to add/remove users"
                echo ""
                read -p "Press Enter to continue..."
                echo ""
                # Re-call the function to show menu again
                show_iap_management_menu
                return
                ;;
            9)
                echo "📊 Showing detailed IAP status..."
                "$SCRIPT_DIR/manage-iap-access.sh" status
                echo ""
                read -p "Press Enter to continue..."
                echo ""
                # Re-call the function to show menu again
                show_iap_management_menu
                return
                ;;
            0)
                echo "⬅️  Returning to main menu..."
                return 0
                ;;
            *)
                echo "❌ Invalid choice. Please enter 0-9"
                ;;
        esac
    done
}

# Simple deployment action menu
show_deployment_actions() {
    echo "What to deploy:"
    echo ""
    echo " 1) Both services (recommended)"
    echo " 2) Agent Server only" 
    echo " 3) Workroom only"
    echo " 4) Config update only"
    echo " 5) Force rebuild all"
    echo ""
    echo "💡 Tip: Options 2-3 will prompt to force rebuild if no changes detected"
    echo ""
    
    while true; do
        read -p "Select [1-5]: " choice
        
        case $choice in
            1)
                echo "✅ Deploying both services"
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                break
                ;;
            2)
                echo "✅ Deploying agent-server"
                DEPLOY_AGENT_SERVER=true
                break
                ;;
            3)
                echo "✅ Deploying workroom"
                DEPLOY_WORKROOM=true
                break
                ;;
            4)
                echo "✅ Updating configuration"
                CONFIG_ONLY=true
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                break
                ;;
            5)
                echo "✅ Force rebuilding all"
                FORCE_BUILD=true
                DEPLOY_ALL=true
                DEPLOY_AGENT_SERVER=true
                DEPLOY_WORKROOM=true
                break
                ;;
            *)
                echo "Please enter 1-5"
                ;;
        esac
    done
    echo ""
} 