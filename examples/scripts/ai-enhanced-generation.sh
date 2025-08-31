#!/bin/bash

# AI-Enhanced Saidata Generation Script
# This script demonstrates AI-powered metadata enhancement using different LLM providers

set -e  # Exit on any error

# Configuration
SOFTWARE_NAME="${1:-nginx}"
OUTPUT_DIR="${2:-./ai-enhanced-output}"
AI_PROVIDER="${3:-openai}"
CONFIG_FILE="${4:-examples/configs/basic.yaml}"

echo "=== Saidata Generator - AI-Enhanced Generation ==="
echo "Software: $SOFTWARE_NAME"
echo "Output Directory: $OUTPUT_DIR"
echo "AI Provider: $AI_PROVIDER"
echo "Configuration: $CONFIG_FILE"
echo

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/comparisons"

# Comprehensive provider list covering all major package managers
PROVIDERS="apt,brew,yum,dnf,zypper,pacman,apk,snap,flatpak,winget,choco,scoop,npm,pypi,cargo,gem,composer,nuget,maven,gradle,go,docker,helm,nix,nixpkgs,guix,spack,portage,emerge,xbps,slackpkg,opkg,pkg"

# Step 1: Generate metadata without AI enhancement (baseline)
echo "Step 1: Generating baseline metadata (without AI)..."
saidata-gen --config "$CONFIG_FILE" generate "$SOFTWARE_NAME" \
    --output "$OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml" \
    --providers "$PROVIDERS"

if [ $? -eq 0 ]; then
    echo "✓ Baseline metadata generation completed successfully"
else
    echo "✗ Baseline metadata generation failed"
    exit 1
fi

# Step 2: Generate metadata with AI enhancement
echo
echo "Step 2: Generating AI-enhanced metadata using $AI_PROVIDER..."
saidata-gen --config "$CONFIG_FILE" generate "$SOFTWARE_NAME" \
    --output "$OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml" \
    --providers "$PROVIDERS" \
    --ai \
    --ai-provider "$AI_PROVIDER"

if [ $? -eq 0 ]; then
    echo "✓ AI-enhanced metadata generation completed successfully"
else
    echo "✗ AI-enhanced metadata generation failed"
    exit 1
fi

# Step 3: Validate both generated files
echo
echo "Step 3: Validating generated metadata files..."

echo "Validating baseline metadata..."
saidata-gen validate "$OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml"
baseline_validation=$?

echo "Validating AI-enhanced metadata..."
saidata-gen validate "$OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml"
ai_validation=$?

if [ $baseline_validation -eq 0 ] && [ $ai_validation -eq 0 ]; then
    echo "✓ Both files passed validation"
elif [ $baseline_validation -eq 0 ]; then
    echo "✓ Baseline passed validation, ⚠ AI-enhanced has validation issues"
elif [ $ai_validation -eq 0 ]; then
    echo "⚠ Baseline has validation issues, ✓ AI-enhanced passed validation"
else
    echo "✗ Both files have validation issues"
fi

# Step 4: Generate comparison report
echo
echo "Step 4: Generating comparison report..."

# Create a simple comparison script
cat > "$OUTPUT_DIR/comparisons/compare.py" << 'EOF'
#!/usr/bin/env python3
import yaml
import sys
import json
from pathlib import Path

def load_yaml(file_path):
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def count_fields(data, prefix=""):
    count = 0
    if isinstance(data, dict):
        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key
            if value is not None and value != "":
                count += 1
                if isinstance(value, (dict, list)):
                    count += count_fields(value, current_path)
    elif isinstance(data, list):
        for i, item in enumerate(data):
            count += count_fields(item, f"{prefix}[{i}]")
    return count

def find_differences(baseline, enhanced, path=""):
    differences = []
    
    if isinstance(baseline, dict) and isinstance(enhanced, dict):
        all_keys = set(baseline.keys()) | set(enhanced.keys())
        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            baseline_val = baseline.get(key)
            enhanced_val = enhanced.get(key)
            
            if baseline_val != enhanced_val:
                if key not in baseline:
                    differences.append({
                        "type": "added",
                        "path": current_path,
                        "enhanced_value": enhanced_val
                    })
                elif key not in enhanced:
                    differences.append({
                        "type": "removed", 
                        "path": current_path,
                        "baseline_value": baseline_val
                    })
                elif isinstance(baseline_val, (dict, list)) and isinstance(enhanced_val, (dict, list)):
                    differences.extend(find_differences(baseline_val, enhanced_val, current_path))
                else:
                    differences.append({
                        "type": "modified",
                        "path": current_path,
                        "baseline_value": baseline_val,
                        "enhanced_value": enhanced_val
                    })
    
    return differences

def main():
    if len(sys.argv) != 3:
        print("Usage: compare.py <baseline.yaml> <enhanced.yaml>")
        sys.exit(1)
    
    baseline_file = sys.argv[1]
    enhanced_file = sys.argv[2]
    
    baseline = load_yaml(baseline_file)
    enhanced = load_yaml(enhanced_file)
    
    baseline_fields = count_fields(baseline)
    enhanced_fields = count_fields(enhanced)
    
    differences = find_differences(baseline, enhanced)
    
    report = {
        "comparison_summary": {
            "baseline_file": baseline_file,
            "enhanced_file": enhanced_file,
            "baseline_field_count": baseline_fields,
            "enhanced_field_count": enhanced_fields,
            "field_difference": enhanced_fields - baseline_fields,
            "total_differences": len(differences)
        },
        "differences": differences
    }
    
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
EOF

chmod +x "$OUTPUT_DIR/comparisons/compare.py"

# Run comparison if Python is available
if command -v python3 &> /dev/null; then
    echo "Generating detailed comparison..."
    python3 "$OUTPUT_DIR/comparisons/compare.py" \
        "$OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml" \
        "$OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml" \
        > "$OUTPUT_DIR/comparisons/comparison-report.json"
    
    # Extract summary information
    if command -v jq &> /dev/null; then
        echo
        echo "=== AI Enhancement Summary ==="
        jq -r '.comparison_summary | 
            "Baseline fields: \(.baseline_field_count)",
            "Enhanced fields: \(.enhanced_field_count)", 
            "Fields added by AI: \(.field_difference)",
            "Total differences: \(.total_differences)"' \
            "$OUTPUT_DIR/comparisons/comparison-report.json"
    fi
else
    echo "Python3 not available, skipping detailed comparison"
fi

# Step 5: Display file information and preview
echo
echo "=== Generation Summary ==="
echo "Baseline file: $OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml"
echo "  Size: $(du -h "$OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml" | cut -f1)"
echo "  Lines: $(wc -l < "$OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml")"

echo "AI-enhanced file: $OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml"
echo "  Size: $(du -h "$OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml" | cut -f1)"
echo "  Lines: $(wc -l < "$OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml")"

# Step 6: Show AI-enhanced content preview
echo
echo "=== AI-Enhanced Content Preview ==="
echo "First 30 lines of AI-enhanced metadata:"
head -30 "$OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml"
echo "..."

# Step 7: Demonstrate different AI providers (if requested)
if [ "$AI_PROVIDER" = "all" ]; then
    echo
    echo "Step 7: Generating metadata with different AI providers..."
    
    for provider in openai anthropic local; do
        echo "Generating with $provider..."
        if saidata-gen --config "$CONFIG_FILE" generate "$SOFTWARE_NAME" \
            --output "$OUTPUT_DIR/${SOFTWARE_NAME}-${provider}.yaml" \
            --providers "$PROVIDERS" \
            --ai \
            --ai-provider "$provider" 2>/dev/null; then
            echo "✓ $provider generation completed"
        else
            echo "✗ $provider generation failed (provider may not be configured)"
        fi
    done
fi

echo
echo "✓ AI-enhanced generation completed successfully!"
echo
echo "Generated files:"
echo "  - Baseline: $OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml"
echo "  - AI-enhanced: $OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml"
if [ -f "$OUTPUT_DIR/comparisons/comparison-report.json" ]; then
    echo "  - Comparison report: $OUTPUT_DIR/comparisons/comparison-report.json"
fi

echo
echo "To compare the files manually:"
echo "  diff $OUTPUT_DIR/${SOFTWARE_NAME}-baseline.yaml $OUTPUT_DIR/${SOFTWARE_NAME}-ai-enhanced.yaml"
echo
echo "To try different AI providers:"
echo "  $0 $SOFTWARE_NAME $OUTPUT_DIR anthropic"
echo "  $0 $SOFTWARE_NAME $OUTPUT_DIR local"
echo "  $0 $SOFTWARE_NAME $OUTPUT_DIR all  # Try all providers"