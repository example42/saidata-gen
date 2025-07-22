#!/bin/bash

# Batch Processing Script for Saidata Generator
# Processes multiple software packages efficiently

set -e

# Configuration
SOFTWARE_LIST="${1:-examples/data/software-list.txt}"
OUTPUT_DIR="${2:-./batch-output}"
CONFIG_FILE="${3:-examples/configs/ci-cd.yaml}"
PARALLEL_JOBS="${4:-4}"

echo "=== Saidata Generator - Batch Processing ==="
echo "Software List: $SOFTWARE_LIST"
echo "Output Directory: $OUTPUT_DIR"
echo "Configuration: $CONFIG_FILE"
echo "Parallel Jobs: $PARALLEL_JOBS"
echo

# Create necessary directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/logs"
mkdir -p "$OUTPUT_DIR/reports"

# Create default software list if it doesn't exist
if [ ! -f "$SOFTWARE_LIST" ]; then
    echo "Creating example software list..."
    mkdir -p "$(dirname "$SOFTWARE_LIST")"
    cat > "$SOFTWARE_LIST" << EOF
nginx
apache2
mysql-server
postgresql
redis-server
docker
git
python3
nodejs
vim
curl
wget
htop
tmux
openssh-server
EOF
    echo "Created example software list at $SOFTWARE_LIST"
fi

# Function to process a single software package
process_software() {
    local software="$1"
    local output_file="$OUTPUT_DIR/${software}.yaml"
    local log_file="$OUTPUT_DIR/logs/${software}.log"
    
    echo "Processing: $software"
    
    # Generate metadata with logging
    if saidata-gen generate "$software" \
        --config "$CONFIG_FILE" \
        --output "$output_file" \
        --providers apt,brew,pypi,npm,docker \
        > "$log_file" 2>&1; then
        
        # Validate the generated file
        if saidata-gen validate "$output_file" >> "$log_file" 2>&1; then
            echo "✓ $software - Success"
            echo "$software,success,$(date)" >> "$OUTPUT_DIR/reports/results.csv"
        else
            echo "✗ $software - Validation failed"
            echo "$software,validation_failed,$(date)" >> "$OUTPUT_DIR/reports/results.csv"
        fi
    else
        echo "✗ $software - Generation failed"
        echo "$software,generation_failed,$(date)" >> "$OUTPUT_DIR/reports/results.csv"
    fi
}

# Export function for parallel execution
export -f process_software
export OUTPUT_DIR CONFIG_FILE

# Initialize results file
echo "software,status,timestamp" > "$OUTPUT_DIR/reports/results.csv"

# Start batch processing
echo "Starting batch processing with $PARALLEL_JOBS parallel jobs..."
echo "Progress will be shown below:"
echo

# Process software list in parallel
cat "$SOFTWARE_LIST" | xargs -n 1 -P "$PARALLEL_JOBS" -I {} bash -c 'process_software "$@"' _ {}

# Generate summary report
echo
echo "=== Batch Processing Summary ==="

total_count=$(wc -l < "$SOFTWARE_LIST")
success_count=$(grep -c ",success," "$OUTPUT_DIR/reports/results.csv" || echo "0")
validation_failed=$(grep -c ",validation_failed," "$OUTPUT_DIR/reports/results.csv" || echo "0")
generation_failed=$(grep -c ",generation_failed," "$OUTPUT_DIR/reports/results.csv" || echo "0")

echo "Total packages processed: $total_count"
echo "Successful: $success_count"
echo "Validation failed: $validation_failed"
echo "Generation failed: $generation_failed"
echo "Success rate: $(( success_count * 100 / total_count ))%"

# Create detailed report
cat > "$OUTPUT_DIR/reports/summary.txt" << EOF
Saidata Generator Batch Processing Report
Generated: $(date)

Configuration:
- Software List: $SOFTWARE_LIST
- Output Directory: $OUTPUT_DIR
- Configuration File: $CONFIG_FILE
- Parallel Jobs: $PARALLEL_JOBS

Results:
- Total Packages: $total_count
- Successful: $success_count
- Validation Failed: $validation_failed
- Generation Failed: $generation_failed
- Success Rate: $(( success_count * 100 / total_count ))%

Output Files:
- Generated YAML files: $OUTPUT_DIR/*.yaml
- Individual logs: $OUTPUT_DIR/logs/*.log
- Results CSV: $OUTPUT_DIR/reports/results.csv
- This summary: $OUTPUT_DIR/reports/summary.txt

Failed Packages:
EOF

# Add failed packages to report
if [ "$validation_failed" -gt 0 ] || [ "$generation_failed" -gt 0 ]; then
    echo "Validation Failures:" >> "$OUTPUT_DIR/reports/summary.txt"
    grep ",validation_failed," "$OUTPUT_DIR/reports/results.csv" | cut -d',' -f1 >> "$OUTPUT_DIR/reports/summary.txt" || true
    echo >> "$OUTPUT_DIR/reports/summary.txt"
    echo "Generation Failures:" >> "$OUTPUT_DIR/reports/summary.txt"
    grep ",generation_failed," "$OUTPUT_DIR/reports/results.csv" | cut -d',' -f1 >> "$OUTPUT_DIR/reports/summary.txt" || true
fi

echo
echo "✓ Batch processing completed!"
echo "Summary report: $OUTPUT_DIR/reports/summary.txt"
echo "Detailed results: $OUTPUT_DIR/reports/results.csv"