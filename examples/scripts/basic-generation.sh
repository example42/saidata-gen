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

# Step 1: Generate metadata
echo "Step 1: Generating metadata for $SOFTWARE_NAME..."
# Use comprehensive provider list covering all major package managers
PROVIDERS="apt,brew,yum,dnf,zypper,pacman,apk,snap,flatpak,winget,choco,scoop,npm,pypi,cargo,gem,composer,nuget,maven,gradle,go,docker,helm,nix,nixpkgs,guix,spack,portage,emerge,xbps,slackpkg,opkg,pkg"

saidata-gen --config "$CONFIG_FILE" generate "$SOFTWARE_NAME" \
    --output "$OUTPUT_DIR/${SOFTWARE_NAME}.yaml" \
    --providers "$PROVIDERS"

if [ $? -eq 0 ]; then
    echo "✓ Metadata generation completed successfully"
else
    echo "✗ Metadata generation failed"
    exit 1
fi

# Step 2: Validate the generated file
echo
echo "Step 2: Validating generated metadata..."
saidata-gen validate "$OUTPUT_DIR/${SOFTWARE_NAME}.yaml"

if [ $? -eq 0 ]; then
    echo "✓ Validation passed"
else
    echo "✗ Validation failed"
    exit 1
fi

# Step 3: Display summary
echo
echo "=== Generation Summary ==="
echo "Generated file: $OUTPUT_DIR/${SOFTWARE_NAME}.yaml"
echo "File size: $(du -h "$OUTPUT_DIR/${SOFTWARE_NAME}.yaml" | cut -f1)"
echo "Lines: $(wc -l < "$OUTPUT_DIR/${SOFTWARE_NAME}.yaml")"

# Step 4: Show first few lines of output
echo
echo "=== Generated Content Preview ==="
head -20 "$OUTPUT_DIR/${SOFTWARE_NAME}.yaml"
echo "..."

echo
echo "✓ Basic generation completed successfully!"
echo "Generated file: $OUTPUT_DIR/${SOFTWARE_NAME}.yaml"