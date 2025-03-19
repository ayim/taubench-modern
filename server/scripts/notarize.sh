#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Usage: ./script/notarize.sh <path_to_executable> <output_directory>

TARGET_EXECUTABLE="$1"
OUTPUT_DIRECTORY="$2"

if [ -z "$TARGET_EXECUTABLE" ]; then
  echo "Error: No target executable provided."
  echo "Usage: $0 <path_to_executable> <output_directory>"
  exit 1
fi

if [ -z "$OUTPUT_DIRECTORY" ]; then
  echo "Error: No output directory provided."
  echo "Usage: $0 <path_to_executable> <output_directory>"
  exit 1
fi

# Check if the output directory exists, create if it doesn't
if [ ! -d "$OUTPUT_DIRECTORY" ]; then
  mkdir -p "$OUTPUT_DIRECTORY"
  echo "Created output directory: $OUTPUT_DIRECTORY"
fi

# Verify the code signature and the contained executables
echo "Verifying code signature..."
codesign --verify --verbose=2 --deep "$TARGET_EXECUTABLE"
# Display the signature information
codesign --verify --verbose=2 --display "$TARGET_EXECUTABLE"

# Notarize (zipped because notarization does not allow executable files)
echo "Submitting for notarization..."
zip temp_signing.zip "$TARGET_EXECUTABLE"
xcrun notarytool submit --apple-id "$APPLEID" --team-id "$APPLETEAMID" --password "$APPLEIDPASS" temp_signing.zip
unzip temp_signing.zip -d "$OUTPUT_DIRECTORY"

echo "Notarization process completed."