#!/bin/bash

# Store current directory and change to script directory
SCRIPT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
pushd "$SCRIPT_PATH" > /dev/null

RCC_PATH="$SCRIPT_PATH/rcc"
CONDA_YAML="$SCRIPT_PATH/develop.yaml"
ACTIVATE_PATH="$SCRIPT_PATH/activate.sh"

echo

# Get RCC binary
RCC_URL="https://cdn.sema4.ai/rcc/releases/v19.0.2/linux64/rcc"
if [[ "$(uname)" == "Darwin" ]]; then
    RCC_URL="https://cdn.sema4.ai/rcc/releases/v19.0.2/macos-arm64/rcc"
fi

if [ ! -f "$RCC_PATH" ]; then
    curl -o "$RCC_PATH" "$RCC_URL" --fail || {
        echo -e "\nDevelopment environment setup failed!"
        exit 1
    }
    chmod +x "$RCC_PATH"
fi

# Check if environment exists and ask for clean environment
if [ -f "$ACTIVATE_PATH" ]; then
    echo "Detected existing development environment."
    echo "Do you want to create a clean environment? [Y/N]"
    read -p "Select [Y]es (clean environment) or [N]o (use existing): " choice
    case "$choice" in
        [Nn]* ) ;;
        * )
            echo "Creating a clean environment..."
            echo "command: $RCC_PATH ht vars $CONDA_YAML --space data-server-cli-development --sema4ai > $ACTIVATE_PATH"
            $RCC_PATH ht vars "$CONDA_YAML" --space data-server-cli-development --sema4ai > "$ACTIVATE_PATH"
            ;;
    esac
else
    echo "Creating a clean environment..."
    echo "command: $RCC_PATH ht vars $CONDA_YAML --space data-server-cli-development --sema4ai > $ACTIVATE_PATH"
    $RCC_PATH ht vars "$CONDA_YAML" --space data-server-cli-development --sema4ai > "$ACTIVATE_PATH"
fi

# Activate the virtual environment
echo "calling: source $ACTIVATE_PATH"
source "$ACTIVATE_PATH"

echo -e "\nDeveloper env. ready!"

# Cleanup
unset RCC_PATH
unset CONDA_YAML
unset SCRIPT_PATH
popd > /dev/null 
