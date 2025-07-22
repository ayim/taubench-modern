# GCP Deployment Scripts

Modular, fast, and intelligent deployment scripts for the Agent Platform on Google Cloud Platform.

## 🚀 **Features**

- **🎯 Smart Build Skipping**: Only rebuilds changed services
- **⚡ Parallel Operations**: Docker builds run in parallel when possible
- **🛠 Comprehensive Setup**: Handles everything from prerequisites to deployment
- **🔧 Modular Design**: Deploy specific services or everything at once
- **📊 Status Monitoring**: Real-time deployment status and logs
- **🏢 Enterprise Ready**: Zero-trust environments, service accounts, multi-project support

## 📋 **Prerequisites**

The scripts will automatically check and install prerequisites, but you can also install manually:

### **Automatic Installation (macOS)**

```bash
./scripts/gcp/setup.sh --all
```

### **Manual Installation**

- **macOS**: Homebrew
- **gcloud CLI**: Google Cloud SDK
- **Docker**: Docker Desktop (must be running)
- **GCP Project**: With billing enabled
- **Authentication**: Personal account or service account

## 🏗 **Scripts Overview**

| Script      | Purpose                   | Key Features                                           |
| ----------- | ------------------------- | ------------------------------------------------------ |
| `setup.sh`  | Initial environment setup | Project selection, API enablement, zero-trust support  |
| `deploy.sh` | Service deployment        | Smart builds, parallel operations, incremental updates |
| `status.sh` | Deployment monitoring     | Service status, logs, console links                    |
| `common.sh` | Shared utilities          | Logging, prerequisites, authentication                 |

## 🆕 **New User Experience**

### **Step 1: First Time Setup**

```bash
# Clone the repository
git clone <your-repo>
cd agent-platform

# Run interactive setup (no flags needed!)
./scripts/gcp/setup.sh
```

### **What Happens During Setup:**

1. **🖥 OS Detection**: Detects your operating system
2. **🍺 Tool Installation**: Auto-installs Homebrew, gcloud CLI, Docker (macOS)
3. **🔐 Authentication**: Multiple options:
   - Personal account (`gcloud auth login`)
   - Service account key file
   - Existing authentication check
4. **📁 Project Selection**: Interactive project picker or creation
5. **🏢 Enterprise Support**: Zero-trust API handling, permission requests
6. **🗄️ Database Setup**: Cloud SQL PostgreSQL instance
7. **🔑 Secrets Management**: NPM authentication token storage

### **Enterprise/Zero-Trust Environment**

For users in restricted environments where they can't enable APIs directly:

```bash
# The script will detect permission issues and provide admin instructions
./scripts/gcp/setup.sh --all

# Output example:
# ⚠️  Zero-trust environment detected!
# 🔒 Some APIs couldn't be enabled automatically. Request your GCP admin to enable:
#   ❌ cloudbuild.googleapis.com
#   ❌ run.googleapis.com
#
# 📋 Copy this message for your admin:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# gcloud services enable cloudbuild.googleapis.com --project=PROJECT_ID
# gcloud services enable run.googleapis.com --project=PROJECT_ID
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### **Service Account Authentication**

For CI/CD or enterprise environments:

```bash
# Method 1: Environment variable
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
./scripts/gcp/setup.sh --all

# Method 2: Interactive setup
./scripts/gcp/setup.sh --all
# Choose option 2 when prompted for authentication method
```

### **Multiple Projects Support**

```bash
# Interactive project selection
./scripts/gcp/setup.sh --all

# Output example:
# Available projects:
#  1) my-dev-project-123        Development Environment
#  2) my-prod-project-456       Production Environment
#  3) my-staging-project-789    Staging Environment
#  0) Create new project
#  q) Quit
#
# Select project (number): 1
```

## 🚀 **Quick Start**

### **Complete Fresh Setup**

```bash
# Everything from scratch (takes 10-15 minutes first time)
./scripts/gcp/setup.sh              # Interactive menu - choose option 1 or 2
./scripts/gcp/deploy.sh             # Interactive menu - choose option 1
```

### **Development Workflow**

```bash
# Interactive menu (NEW!)
./scripts/gcp/deploy.sh
# Shows menu with current status and deployment options

# Deploy only changed services (much faster)
./scripts/gcp/deploy.sh --agent-server
./scripts/gcp/deploy.sh --workroom

# Check deployment status
./scripts/gcp/status.sh

# Deploy everything
./scripts/gcp/deploy.sh --all
```

## ⚙️ **Configuration**

### **🗄️ Cloud SQL Database (Automatic)**

The database is **completely automated**:

1. **Setup Phase**: `./scripts/gcp/setup.sh --all`

   - ✅ Creates Cloud SQL PostgreSQL instance (`agent-postgres`)
   - ✅ Creates database (`agents`) and user (`agents`)
   - ✅ Configures networking and security
   - ✅ Takes 3-5 minutes (one-time only)

2. **Deploy Phase**: `./scripts/gcp/deploy.sh`
   - ✅ Auto-detects existing Cloud SQL instance
   - ✅ Gets database IP and connection details
   - ✅ Configures agent-server with correct environment variables
   - ✅ Sets up Cloud SQL proxy connection

**No manual configuration needed!** The scripts handle everything:

```bash
# This is all automatic:
POSTGRES_HOST=35.241.207.219    # Auto-detected
POSTGRES_PORT=5432              # Standard
POSTGRES_DB=agents              # Auto-created
POSTGRES_USER=agents            # Auto-created
POSTGRES_PASSWORD=agents        # Auto-set
```

### **🎯 Interactive Menu (NEW!)**

When you run `./scripts/gcp/deploy.sh` without arguments, you get an interactive menu:

```bash
🚀 Agent Platform GCP Deployment
📍 Project: my-project-123
🌍 Region: europe-west1

📊 Current Status:
   Agent Server: Running         (deployed 2 hours ago)
   Workroom:     Not deployed

🎯 What would you like to deploy?

 1) 🌐 Everything (agent-server + workroom)
 2) 🖥️  Agent Server only (backend API)
 3) 🎨 Workroom only (frontend UI)
 4) ⚙️  Configuration only (env vars, no build)
 5) 🔄 Force rebuild everything
 6) 📊 Show current status
 0) ❌ Exit

Select option (0-6): 3
✅ Selected: Deploy workroom only
```

**Benefits:**

- 📊 Shows current deployment status and ages
- 🎯 Clear options with descriptions
- ⚡ Quick status refresh (option 6)
- 🚫 Easy exit without deploying

### **Environment Variables**

```bash
export GCLOUD_PROJECT="your-project-id"           # GCP project (auto-selected if not set)
export REGION="europe-west1"                      # GCP region (default: europe-west1)
export GOOGLE_APPLICATION_CREDENTIALS="key.json"  # Service account key (optional)
```

### **Required APIs** (Auto-enabled)

- Cloud Build API (`cloudbuild.googleapis.com`)
- Cloud Run API (`run.googleapis.com`)
- Cloud SQL Admin API (`sqladmin.googleapis.com`)
- Secret Manager API (`secretmanager.googleapis.com`)
- Artifact Registry API (`artifactregistry.googleapis.com`)
- Identity and Access Management API (`iam.googleapis.com`)
- Cloud Resource Manager API (`cloudresourcemanager.googleapis.com`)

### **Required IAM Roles** (Auto-granted to build service account)

- `roles/secretmanager.secretAccessor`
- `roles/cloudsql.client`
- `roles/artifactregistry.writer`

## 📊 **Usage Examples**

### **Setup Commands**

```bash
# Interactive setup (recommended - no flags needed!)
./scripts/gcp/setup.sh

# Quick status check
./scripts/gcp/setup.sh --check

# Setup only missing components
./scripts/gcp/setup.sh --missing-only

# Complete setup (non-interactive)
./scripts/gcp/setup.sh --all

# Individual components (advanced)
./scripts/gcp/setup.sh --database-only
./scripts/gcp/setup.sh --secrets-only
./scripts/gcp/setup.sh --permissions
```

### **Deployment Commands**

```bash
# Interactive menu (NEW! - most user-friendly)
./scripts/gcp/deploy.sh
# Shows current status and deployment options

# Deploy everything (smart build detection)
./scripts/gcp/deploy.sh --all

# Deploy specific services
./scripts/gcp/deploy.sh --agent-server
./scripts/gcp/deploy.sh --workroom

# Force rebuild everything
./scripts/gcp/deploy.sh --all --force-build

# Update configuration only (no build)
./scripts/gcp/deploy.sh --all --config-only

# Skip tests during deployment
./scripts/gcp/deploy.sh --all --skip-tests
```

### **Monitoring Commands**

```bash
# Check service status
./scripts/gcp/status.sh

# View recent logs
gcloud run services logs read workroom --region=europe-west1 --limit=50
gcloud run services logs read agent-server --region=europe-west1 --limit=50
```

## 🔧 **Troubleshooting**

### **Common Issues**

**🐳 Docker not running**

```bash
# macOS: Start Docker Desktop
open /Applications/Docker.app
# Wait for Docker to start, then re-run setup
```

**🔐 Authentication issues**

```bash
# Re-authenticate
gcloud auth login
# Or use service account
gcloud auth activate-service-account --key-file=key.json
```

**📁 Project not found/accessible**

```bash
# List accessible projects
gcloud projects list
# Set specific project
gcloud config set project YOUR_PROJECT_ID
```

**🏢 Zero-trust/Permission issues**

```bash
# Request admin to enable APIs and grant roles
# The setup script provides exact commands for your admin
```

### **Build Issues**

**📦 Slow builds**

```bash
# Use parallel builds (already default)
./scripts/gcp/deploy.sh --all

# Skip unchanged services (already default)
./scripts/gcp/deploy.sh --agent-server  # only if changed
```

**🗄️ Database connection issues**

```bash
# Check database status
gcloud sql instances describe agent-postgres

# Verify network access
gcloud sql instances patch agent-postgres --authorized-networks=0.0.0.0/0
```

## 🎯 **Smart Features Explained**

### **Change Detection**

The scripts track file changes to avoid unnecessary rebuilds:

- Uses file checksums and timestamps
- Compares with last successful deployment
- Only rebuilds when source code changes
- Dramatically reduces deployment time (30 seconds vs 5+ minutes)

### **Parallel Operations**

- Docker builds run in parallel when deploying multiple services
- API calls are batched where possible
- Build and deploy operations overlap when safe

### **Prerequisite Management**

- Automatically detects missing tools
- Provides auto-installation on supported platforms (macOS)
- Gives clear manual installation instructions for other platforms
- Validates authentication and project access

### **Enterprise Support**

- Handles zero-trust environments gracefully
- Provides admin request templates for API/permission issues
- Supports service account authentication
- Multi-project workspace support

## 🗂 **File Structure**

```
scripts/gcp/
├── setup.sh          # Initial environment setup
├── deploy.sh          # Service deployment
├── status.sh          # Status monitoring
├── common.sh          # Shared utilities
└── README.md          # This file
```

## 🤝 **Contributing**

When modifying these scripts:

1. Test on a fresh project/environment
2. Ensure enterprise scenarios still work
3. Update this README with new features
4. Test the new user experience (no gcloud, no project, etc.)

## 🆘 **Support**

For issues or questions:

1. Check the troubleshooting section above
2. Run `./scripts/gcp/status.sh` to gather environment info
3. Check GCP Console logs and Cloud Build history
4. Verify all prerequisites are properly installed and configured
