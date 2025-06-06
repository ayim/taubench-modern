#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Usage: ./script/sign_and_notarize.sh <path_to_executable> <output_directory> <entitlements_file>

TARGET_EXECUTABLE="$1"
OUTPUT_DIRECTORY="$2"
ENTITLEMENTS_FILE="$3"

if [ -z "$TARGET_EXECUTABLE" ]; then
  echo "Error: No target executable provided."
  echo "Usage: $0 <path_to_executable> <output_directory> <entitlements_file>"
  exit 1
fi

if [ -z "$OUTPUT_DIRECTORY" ]; then
  echo "Error: No output directory provided."
  echo "Usage: $0 <path_to_executable> <output_directory> <entitlements_file>"
  exit 1
fi

# Check if the output directory exists, create if it doesn't
if [ ! -d "$OUTPUT_DIRECTORY" ]; then
  mkdir -p "$OUTPUT_DIRECTORY"
  echo "Created output directory: $OUTPUT_DIRECTORY"
fi

# Sign MacOS binary
echo "Signing MacOS binary..."
security create-keychain -p "$MACOS_SIGNING_CERT_PASSWORD" build.keychain
security default-keychain -s build.keychain
security unlock-keychain -p "$MACOS_SIGNING_CERT_PASSWORD" build.keychain
echo "$MACOS_SIGNING_CERT" | base64 --decode -o cert.p12
security import cert.p12 -A -P "$MACOS_SIGNING_CERT_PASSWORD"
security set-key-partition-list -S apple-tool:,apple: -s -k "$MACOS_SIGNING_CERT_PASSWORD" build.keychain

# Sign MacOS X86 binary
codesign --verbose=4 --entitlements "$ENTITLEMENTS_FILE" --deep --force -o runtime -s "$MACOS_SIGNING_CERT_NAME" --timestamp "$TARGET_EXECUTABLE"
# Verify the code signature and the contained executables
codesign --verify --verbose=2 --deep "$TARGET_EXECUTABLE"
# Display the signature information
codesign --verify --verbose=2 --display "$TARGET_EXECUTABLE"

# Notarize (zipped because notarization does not allow executable files)
zip temp_signing.zip "$TARGET_EXECUTABLE"
xcrun notarytool submit --apple-id "$APPLEID" --team-id "$APPLETEAMID" --password "$APPLEIDPASS" temp_signing.zip
unzip temp_signing.zip -d "$OUTPUT_DIRECTORY"

echo "Signing and notarization process completed."