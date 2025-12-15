# MySQL Client Setup for Local Development

This guide explains how to install MySQL client libraries required for building the `mysqlclient` Python package, which is used by the agent platform for MySQL data connections.

## Why Is This Required?

The agent platform uses `ibis-framework[mysql]` for MySQL data connections. This dependency requires `mysqlclient`, a Python package with native C extensions that need MySQL client libraries to compile.

**Note:** This setup is only required for **local development**. Docker deployments are already configured with the necessary libraries.

---

## macOS Setup

### Prerequisites

- Homebrew package manager installed

### Installation Steps

```bash
# Install MySQL client libraries and pkg-config
brew install mysql-client pkg-config

# Add mysql-client to PATH (needed because it's installed as "keg-only")
export PATH="$(brew --prefix)/opt/mysql-client/bin:$PATH"

# Set PKG_CONFIG_PATH environment variable
export PKG_CONFIG_PATH="$(brew --prefix)/opt/mysql-client/lib/pkgconfig"

# Make both permanent by adding to your shell profile
echo 'export PATH="$(brew --prefix)/opt/mysql-client/bin:$PATH"' >> ~/.zshrc
echo 'export PKG_CONFIG_PATH="$(brew --prefix)/opt/mysql-client/lib/pkgconfig"' >> ~/.zshrc

# Reload your shell configuration
source ~/.zshrc

# Now install project dependencies
make sync
```

**Note:** Homebrew installs `mysql-client` as "keg-only" to avoid conflicts with full MySQL server installations. This means the binaries are not automatically linked, so we need to add them to PATH manually.

### Verification

```bash
# Verify mysql_config is available
mysql_config --version
# Should output something like: 9.5.0

# Verify pkg-config can find MySQL
pkg-config --exists mysqlclient && echo "✅ MySQL client found" || echo "❌ MySQL client not found"
```

---

Alternative without brew:

Download mysql for Mac OS (from https://dev.mysql.com/downloads/mysql/), extract it
and set the env vars below (pointing to the location where the package was extracted):

export MYSQL_HOME=/usr/local/mysql-9.5.0-macos15-arm64/include
export MYSQLCLIENT_CFLAGS="-I/usr/local/mysql-9.5.0-macos15-arm64/include"
export MYSQLCLIENT_LDFLAGS="-L/usr/local/mysql-9.5.0-macos15-arm64/lib -lmysqlclient"

---

## Linux Setup

### Ubuntu / Debian

```bash
# Install MySQL client development libraries
sudo apt-get update
sudo apt-get install -y \
    default-libmysqlclient-dev \
    pkg-config \
    build-essential

# Install project dependencies
make sync
```

### Fedora / RHEL / CentOS

```bash
# Install MySQL client development libraries
sudo dnf install -y \
    mysql-devel \
    pkgconfig \
    gcc \
    python3-devel

# Or for older versions using yum
sudo yum install -y \
    mysql-devel \
    pkgconfig \
    gcc \
    python3-devel

# Install project dependencies
make sync
```

### Arch Linux

```bash
# Install MySQL client libraries
sudo pacman -S \
    mariadb-libs \
    pkgconf \
    base-devel

# Install project dependencies
make sync
```

### Alpine Linux

```bash
# Install MySQL client development libraries
apk add --no-cache \
    mariadb-dev \
    pkgconfig \
    gcc \
    musl-dev \
    python3-dev

# Install project dependencies
make sync
```

---

## Windows Setup

### Option 1: Using Windows Subsystem for Linux (WSL) - Recommended

1. Install WSL2 if you haven't already:

   ```powershell
   wsl --install
   ```

2. Inside your WSL distribution (Ubuntu), follow the [Ubuntu / Debian](#ubuntu--debian) instructions above.

### Option 2: Native Windows

1. **Install MySQL Server** (includes client libraries):

   - Download MySQL Installer from [MySQL Downloads](https://dev.mysql.com/downloads/installer/)
   - Run the installer and choose "Developer Default" or "Custom"
   - Make sure to include "MySQL Server" and "Connector/C++"

2. **Set Environment Variables**:

   - Add MySQL bin directory to PATH: `C:\Program Files\MySQL\MySQL Server X.X\bin`
   - Set `MYSQLCLIENT_CFLAGS` and `MYSQLCLIENT_LDFLAGS` if needed

3. **Install Visual C++ Build Tools**:

   - Download from [Microsoft Visual Studio](https://visualstudio.microsoft.com/downloads/)
   - Install "Desktop development with C++" workload

4. **Install project dependencies**:
   ```powershell
   make sync
   ```

---

## Docker Setup

**No action required!** The Docker configuration in `Dockerfile.spar` already includes the necessary MySQL client libraries:

- **Build stage**: Installs `default-libmysqlclient-dev` and `pkg-config` for compiling
- **Runtime stage**: Includes `libmariadb3` for runtime execution

Simply build and run:

```bash
docker compose build
docker compose up
```

---

## Troubleshooting

### Issue: `pkg-config: command not found`

**Solution**: Install `pkg-config`:

- macOS: `brew install pkg-config`
- Ubuntu/Debian: `sudo apt-get install pkg-config`
- Fedora/RHEL: `sudo dnf install pkgconfig`

### Issue: `mysql_config not found` or `command not found: mysql_config`

**Solution**: MySQL client libraries are not installed or not in PATH.

For macOS, you need to add mysql-client to your PATH (it's installed as "keg-only"):

```bash
export PATH="$(brew --prefix)/opt/mysql-client/bin:$PATH"
echo 'export PATH="$(brew --prefix)/opt/mysql-client/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

- Linux: Install the appropriate `-dev` or `-devel` package for your distribution

### Issue: `Can not find valid pkg-config name`

**Solution**: The `PKG_CONFIG_PATH` environment variable is not set correctly.

For macOS:

```bash
export PKG_CONFIG_PATH="$(brew --prefix)/opt/mysql-client/lib/pkgconfig"
```

Verify it's set:

```bash
echo $PKG_CONFIG_PATH
```

### Issue: Build fails with "Python.h not found"

**Solution**: Install Python development headers:

- Ubuntu/Debian: `sudo apt-get install python3-dev`
- Fedora/RHEL: `sudo dnf install python3-devel`
- macOS: Usually included with Python installation

### Issue: Permission denied errors

**Solution**: Some directories may require elevated permissions. Try:

```bash
# On Linux
sudo apt-get install default-libmysqlclient-dev

# Don't use sudo for make sync - run as your regular user
make sync
```

---

## Alternative: Using PyMySQL (Not Recommended)

If you absolutely cannot install MySQL client libraries, you can use PyMySQL (pure Python implementation) but this is **not officially supported** and may have performance implications:

1. The configuration would require custom uv overrides
2. Performance is significantly slower (~5-10x) for data operations
3. Not recommended for production use

**We strongly recommend installing MySQL client libraries for the best experience.**

---

## Verification

After installation, verify everything works:

```bash
# 1. Check dependencies installed successfully
make sync

# 2. Check that mysqlclient is installed
uv run --project agent_platform_server python -c "import MySQLdb; print('mysqlclient installed successfully')"

# 3. Test MySQL connection (if you have a test MySQL server)
# This will be tested via the agent platform's data connection inspection feature
```

---

## CI/CD Considerations

For CI/CD pipelines, ensure MySQL client libraries are installed before running tests:

### GitHub Actions Example

```yaml
- name: Install MySQL Client Libraries
  run: |
    sudo apt-get update
    sudo apt-get install -y default-libmysqlclient-dev pkg-config
```

### GitLab CI Example

```yaml
before_script:
  - apt-get update -qq
  - apt-get install -y default-libmysqlclient-dev pkg-config
```

---

## Questions or Issues?

If you encounter any issues not covered in this guide:

1. Check the troubleshooting section above
2. Consult the [mysqlclient documentation](https://github.com/PyMySQL/mysqlclient)
3. Contact the platform engineering team

---

## Summary by OS

| Operating System   | Package Manager | Required Packages                                             | Additional Setup             |
| ------------------ | --------------- | ------------------------------------------------------------- | ---------------------------- |
| macOS              | Homebrew        | `mysql-client`, `pkg-config`                                  | Set PATH and PKG_CONFIG_PATH |
| Ubuntu/Debian      | apt             | `default-libmysqlclient-dev`, `pkg-config`, `build-essential` | -                            |
| Fedora/RHEL/CentOS | dnf/yum         | `mysql-devel`, `pkgconfig`, `gcc`, `python3-devel`            | -                            |
| Arch Linux         | pacman          | `mariadb-libs`, `pkgconf`, `base-devel`                       | -                            |
| Alpine Linux       | apk             | `mariadb-dev`, `pkgconfig`, `gcc`, `musl-dev`, `python3-dev`  | -                            |
| Windows            | WSL2            | Follow Ubuntu instructions in WSL                             | -                            |
| Docker             | N/A             | ✅ Already configured in Dockerfile                           | -                            |
