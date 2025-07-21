#!/bin/bash

# Check GCP permissions for Cloud Build deployment
# Usage: ./scripts/check-gcp-permissions.sh [PROJECT_ID] [REGION]

set -e

# Default values (can be overridden by command line args)
PROJECT_ID=${1:-"sema4-portable-agent-runtime"}
REGION=${2:-"europe-west1"}

echo "🔍 Checking GCP permissions for Cloud Build deployment..."
echo "📧 Project: $PROJECT_ID"
echo "🌍 Region: $REGION"
echo ""

# Get current user
CURRENT_USER=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" --quiet)
if [ -z "$CURRENT_USER" ]; then
  echo "❌ No authenticated user found. Run: gcloud auth login"
  exit 1
fi

echo "👤 Current user: $CURRENT_USER"
echo ""

# Check if project exists and user has access
echo "🏗️ Checking project access..."
if ! gcloud projects describe "$PROJECT_ID" --quiet >/dev/null 2>&1; then
  echo "❌ Cannot access project '$PROJECT_ID' or project doesn't exist"
  exit 1
fi
echo "✅ Project access confirmed"

# Check for high-level permissions first (owner/editor)
BROAD_ROLES=("roles/owner" "roles/editor")
SPECIFIC_ROLES=("roles/cloudsql.admin" "roles/run.admin" "roles/secretmanager.admin" "roles/artifactregistry.admin")

echo ""
echo "🔐 Checking user permissions..."
HAS_BROAD_PERMISSION=false
HAS_SPECIFIC_PERMISSIONS=true
USER_ROLES=()
MISSING_SPECIFIC=()

# Check for broad permissions (owner/editor)
for role in "${BROAD_ROLES[@]}"; do
  if gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten="bindings[].members" \
    --format="value(bindings.role)" \
    --filter="bindings.members:$CURRENT_USER AND bindings.role:$role" \
    --quiet 2>/dev/null | grep -q "$role"; then
    echo "✅ Has $role (covers all specific permissions)"
    HAS_BROAD_PERMISSION=true
    USER_ROLES+=("$role")
    break
  fi
done

# If no broad permissions, check specific ones
if [ "$HAS_BROAD_PERMISSION" = "false" ]; then
  echo "⚠️  No broad permissions (owner/editor), checking specific roles..."
  
  for role in "${SPECIFIC_ROLES[@]}"; do
    if gcloud projects get-iam-policy "$PROJECT_ID" \
      --flatten="bindings[].members" \
      --format="value(bindings.role)" \
      --filter="bindings.members:$CURRENT_USER AND bindings.role:$role" \
      --quiet 2>/dev/null | grep -q "$role"; then
      echo "✅ Has $role"
      USER_ROLES+=("$role")
    else
      echo "❌ Missing $role"
      MISSING_SPECIFIC+=("$role")
      HAS_SPECIFIC_PERMISSIONS=false
    fi
  done
fi

# Exit early if insufficient permissions
if [ "$HAS_BROAD_PERMISSION" = "false" ] && [ "$HAS_SPECIFIC_PERMISSIONS" = "false" ]; then
  echo ""
  echo "❌ INSUFFICIENT PERMISSIONS!"
  echo ""
  echo "You need either:"
  echo "  Option 1 (Recommended): roles/owner or roles/editor"
  echo "  Option 2: All specific roles: ${MISSING_SPECIFIC[*]}"
  echo ""
  echo "Ask your admin to grant permissions:"
  echo "  # Option 1 (Recommended):"
  echo "  gcloud projects add-iam-policy-binding $PROJECT_ID --member='user:$CURRENT_USER' --role='roles/editor'"
  echo ""
  echo "  # Option 2 (Specific roles):"
  for role in "${MISSING_SPECIFIC[@]}"; do
    echo "  gcloud projects add-iam-policy-binding $PROJECT_ID --member='user:$CURRENT_USER' --role='$role'"
  done
  exit 1
fi

echo ""
echo "🔧 Checking APIs..."
REQUIRED_APIS=(
  "sqladmin.googleapis.com"
  "run.googleapis.com"
  "cloudbuild.googleapis.com"
  "monitoring.googleapis.com"
  "logging.googleapis.com"
  "artifactregistry.googleapis.com"
  "compute.googleapis.com"
)

MISSING_APIS=()
for api in "${REQUIRED_APIS[@]}"; do
  if gcloud services list --enabled --filter="name:$api" --format="value(name)" --quiet | grep -q "$api"; then
    echo "✅ $api enabled"
  else
    echo "❌ $api not enabled"
    MISSING_APIS+=("$api")
  fi
done

if [ ${#MISSING_APIS[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  Some APIs are not enabled. Enable them with:"
  echo "gcloud services enable ${MISSING_APIS[*]} --project=$PROJECT_ID"
fi

echo ""
echo "🏗️ Checking Artifact Registry..."
if gcloud artifacts repositories describe cloud-run-source-deploy --location="$REGION" --quiet >/dev/null 2>&1; then
  echo "✅ Artifact Registry repository 'cloud-run-source-deploy' exists"
else
  echo "❌ Artifact Registry repository 'cloud-run-source-deploy' doesn't exist"
  echo "   It will be created during the build process"
fi

echo ""
echo "🔍 Checking npmrc secret..."
if gcloud secrets describe npmrc-secret --project="$PROJECT_ID" --quiet >/dev/null 2>&1; then
  echo "✅ npmrc-secret exists"
else
  echo "❌ Missing npmrc-secret!"
  echo "   Create it with: gcloud secrets create npmrc-secret --data-file=~/.npmrc --project=$PROJECT_ID"
  exit 1
fi

echo ""
echo "🤖 Checking Cloud Build service account..."
BUILD_SA="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' --quiet)-compute@developer.gserviceaccount.com"
echo "📧 Build service account: $BUILD_SA"

REQUIRED_SA_ROLES=(
  "roles/secretmanager.secretAccessor"
  "roles/cloudsql.client"
  "roles/artifactregistry.writer"
)

echo "Checking service account permissions..."
SA_MISSING_ROLES=()
for role in "${REQUIRED_SA_ROLES[@]}"; do
  if gcloud projects get-iam-policy "$PROJECT_ID" \
    --flatten="bindings[].members" \
    --format="value(bindings.role)" \
    --filter="bindings.members:serviceAccount:$BUILD_SA AND bindings.role:$role" \
    --quiet 2>/dev/null | grep -q "$role"; then
    echo "✅ Service account has $role"
  else
    echo "❌ Service account missing $role"
    SA_MISSING_ROLES+=("$role")
  fi
done

if [ ${#SA_MISSING_ROLES[@]} -gt 0 ]; then
  echo ""
  echo "🔧 Granting missing service account permissions..."
  for role in "${SA_MISSING_ROLES[@]}"; do
    echo "Granting $role to $BUILD_SA..."
    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:$BUILD_SA" \
      --role="$role" \
      --quiet; then
      echo "✅ Granted $role"
    else
      echo "❌ Failed to grant $role (you might need higher permissions)"
    fi
  done
fi

echo ""
echo "=================================================================="
echo "🎯 PERMISSION CHECK SUMMARY"
echo "=================================================================="
echo "👤 User: $CURRENT_USER"
echo "🏗️ Project: $PROJECT_ID"
echo "🌍 Region: $REGION"
echo ""

# Check if we're ready for Cloud Build
READY_FOR_BUILD=false
if [ "$HAS_BROAD_PERMISSION" = "true" ] || [ "$HAS_SPECIFIC_PERMISSIONS" = "true" ]; then
  if [ ${#MISSING_APIS[@]} -eq 0 ]; then
    READY_FOR_BUILD=true
  fi
fi

if [ "$READY_FOR_BUILD" = "true" ]; then
  echo "✅ Ready to run Cloud Build!"
  echo ""
  echo "🚀 To deploy, run:"
  echo "   gcloud builds submit --config=cloudbuild.yaml ."
else
  echo "❌ Not ready for Cloud Build. Fix the issues above first."
  exit 1
fi

echo "==================================================================" 