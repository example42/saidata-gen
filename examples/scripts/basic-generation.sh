#!/bin/bash

# Basic Saidata Generation Script
# This script demonstrates basic usage of the saidata generator

set -e  # Exit on any error

# Configuration
SOFTWARE_NAME="${1:-nginx}"
OUTPUT_DIR="${2:-./output}"
CONFIG_FILE="${3:-examples/configs/basic.yaml}"

echo "=== Saidata Generator - Basic Generation ==="
echo "Software: $SOFTWARE_NAME"
echo "Output Directory: $OUTPUT_DIR"
echo "Configuration: $CONFIG_FILE"
echo

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

# Step 1: Generate metadata (creates structured directory)
echo "Step 1: Generating metadata for $SOFTWARE_NAME..."
# Use comprehensive provider list covering all major package managers
PROVIDERS="apt,brew,yum,dnf,zypper,pacman,apk,snap,flatpak,winget,choco,scoop,npm,pypi,cargo,gem,composer,nuget,maven,gradle,go,docker,helm,nix,nixpkgs,guix,spack,portage,emerge,xbps,slackpkg,opkg,pkg"

saidata-gen --config "$CONFIG_FILE" generate "$SOFTWARE_NAME" \
    --output "$OUTPUT_DIR" \
    --providers "$PROVIDERS"

if [ $? -eq 0 ]; then
    echo "✓ Metadata generation completed successfully"
else
    echo "✗ Metadata generation failed"
    exit 1
fi

# Step 2: Validate the generated files
echo
echo "Step 2: Validating generated metadata..."
saidata-gen validate "$OUTPUT_DIR/${SOFTWARE_NAME}/defaults.yaml"

# Validate provider files if they exist
if [ -d "$OUTPUT_DIR/${SOFTWARE_NAME}/providers" ]; then
    echo "Validating provider-specific files..."
    find "$OUTPUT_DIR/${SOFTWARE_NAME}/providers" -name "*.yaml" -exec saidata-gen validate {} \;
fi

if [ $? -eq 0 ]; then
    echo "✓ Validation passed"
else
    echo "✗ Validation failed"
    exit 1
fi

# Step 3: Display summary
echo
echo "=== Generation Summary ==="
echo "Generated directory: $OUTPUT_DIR/${SOFTWARE_NAME}/"
echo "Main config: $OUTPUT_DIR/${SOFTWARE_NAME}/defaults.yaml"
echo "Main config size: $(du -h "$OUTPUT_DIR/${SOFTWARE_NAME}/defaults.yaml" | cut -f1)"
echo "Main config lines: $(wc -l < "$OUTPUT_DIR/${SOFTWARE_NAME}/defaults.yaml")"

# Count provider files
PROVIDER_COUNT=0
if [ -d "$OUTPUT_DIR/${SOFTWARE_NAME}/providers" ]; then
    PROVIDER_COUNT=$(find "$OUTPUT_DIR/${SOFTWARE_NAME}/providers" -name "*.yaml" | wc -l)
fi
echo "Provider override files: $PROVIDER_COUNT"

# Step 4: Show directory structure and content preview
echo
echo "=== Generated Directory Structure ==="
tree "$OUTPUT_DIR/${SOFTWARE_NAME}/" 2>/dev/null || ls -la "$OUTPUT_DIR/${SOFTWARE_NAME}/"

echo
echo "=== Generated Content Preview ==="
head -20 "$OUTPUT_DIR/${SOFTWARE_NAME}/defaults.yaml"
echo "..."

echo
echo "✓ Basic generation completed successfully!"
echo "Generated directory: $OUTPUT_DIR/${SOFTWARE_NAME}/"