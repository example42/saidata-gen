#!/bin/bash

# CI/CD Pipeline Integration Script for Saidata Generator
# Designed for automated environments with proper error handling and reporting

set -e

# Environment variables with defaults
SAIDATA_CONFIG="${SAIDATA_CONFIG:-examples/configs/ci-cd.yaml}"
SAIDATA_OUTPUT_DIR="${SAIDATA_OUTPUT_DIR:-./saidata-output}"
SAIDATA_LOG_LEVEL="${SAIDATA_LOG_LEVEL:-INFO}"
SAIDATA_PROVIDERS="${SAIDATA_PROVIDERS:-apt,brew,pypi,npm,docker}"
SAIDATA_CONFIDENCE_THRESHOLD="${SAIDATA_CONFIDENCE_THRESHOLD:-0.7}"
SOFTWARE_LIST="${SOFTWARE_LIST:-software-inventory.txt}"
MAX_FAILURES="${MAX_FAILURES:-20}"  # Maximum percentage of failures allowed

# Colors for output (if terminal supports it)
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if saidata-gen is available
    if ! command -v saidata-gen &> /dev/null; then
        log_error "saidata-gen command not found. Please install the package."
        exit 3
    fi
    
    # Check if software list exists
    if [ ! -f "$SOFTWARE_LIST" ]; then
        log_error "Software list file not found: $SOFTWARE_LIST"
        exit 3
    fi
    
    # Check configuration file
    if [ ! -f "$SAIDATA_CONFIG" ]; then
        log_error "Configuration file not found: $SAIDATA_CONFIG"
        exit 3
    fi
    
    log_success "Prerequisites check passed"
}

# Function to setup environment
setup_environment() {
    log_info "Setting up environment..."
    
    # Create output directories
    mkdir -p "$SAIDATA_OUTPUT_DIR"
    mkdir -p "$SAIDATA_OUTPUT_DIR/metadata"
    mkdir -p "$SAIDATA_OUTPUT_DIR/logs"
    mkdir -p "$SAIDATA_OUTPUT_DIR/reports"
    
    # Export environment variables
    export SAIDATA_CACHE_DIR="$SAIDATA_OUTPUT_DIR/cache"
    export SAIDATA_LOG_FILE="$SAIDATA_OUTPUT_DIR/logs/saidata-gen.log"
    
    log_success "Environment setup completed"
}

# Function to validate configuration
validate_configuration() {
    log_info "Validating configuration..."
    
    # Test configuration by running a dry-run
    if saidata-gen --config "$SAIDATA_CONFIG" config validate > /dev/null 2>&1; then
        log_success "Configuration validation passed"
    else
        log_error "Configuration validation failed"
        exit 3
    fi
}

# Function to process software list
process_software_list() {
    log_info "Processing software list: $SOFTWARE_LIST"
    
    local total_count=$(wc -l < "$SOFTWARE_LIST")
    local success_count=0
    local failure_count=0
    local start_time=$(date +%s)
    
    log_info "Total packages to process: $total_count"
    
    # Initialize results tracking
    echo "timestamp,software,status,duration,file_size,validation_result" > "$SAIDATA_OUTPUT_DIR/reports/processing-results.csv"
    
    # Process each software package
    while IFS= read -r software; do
        # Skip empty lines and comments
        [[ -z "$software" || "$software" =~ ^#.*$ ]] && continue
        
        local package_start_time=$(date +%s)
        local output_file="$SAIDATA_OUTPUT_DIR/metadata/${software}.yaml"
        local log_file="$SAIDATA_OUTPUT_DIR/logs/${software}.log"
        
        log_info "Processing: $software"
        
        # Generate metadata
        if saidata-gen --config "$SAIDATA_CONFIG" generate "$software" \
            --output "$output_file" \
            --providers "$SAIDATA_PROVIDERS" \
            --confidence-threshold "$SAIDATA_CONFIDENCE_THRESHOLD" \
            > "$log_file" 2>&1; then
            
            # Validate generated file
            if saidata-gen validate "$output_file" >> "$log_file" 2>&1; then
                local package_end_time=$(date +%s)
                local duration=$((package_end_time - package_start_time))
                local file_size=$(stat -f%z "$output_file" 2>/dev/null || stat -c%s "$output_file" 2>/dev/null || echo "0")
                
                success_count=$((success_count + 1))
                log_success "$software - Generated and validated (${duration}s, ${file_size} bytes)"
                
                echo "$(date -Iseconds),$software,success,$duration,$file_size,passed" >> "$SAIDATA_OUTPUT_DIR/reports/processing-results.csv"
            else
                failure_count=$((failure_count + 1))
                log_warning "$software - Generated but validation failed"
                
                echo "$(date -Iseconds),$software,validation_failed,0,0,failed" >> "$SAIDATA_OUTPUT_DIR/reports/processing-results.csv"
            fi
        else
            failure_count=$((failure_count + 1))
            log_error "$software - Generation failed"
            
            echo "$(date -Iseconds),$software,generation_failed,0,0,n/a" >> "$SAIDATA_OUTPUT_DIR/reports/processing-results.csv"
        fi
        
        # Check failure rate
        local failure_rate=$((failure_count * 100 / (success_count + failure_count)))
        if [ "$failure_rate" -gt "$MAX_FAILURES" ]; then
            log_error "Failure rate ($failure_rate%) exceeded maximum allowed ($MAX_FAILURES%)"
            exit 1
        fi
        
    done < "$SOFTWARE_LIST"
    
    local end_time=$(date +%s)
    local total_duration=$((end_time - start_time))
    
    # Generate summary
    generate_summary_report "$total_count" "$success_count" "$failure_count" "$total_duration"
    
    # Determine exit code based on results
    local failure_rate=$((failure_count * 100 / total_count))
    if [ "$failure_count" -eq 0 ]; then
        log_success "All packages processed successfully"
        exit 0
    elif [ "$failure_rate" -le "$MAX_FAILURES" ]; then
        log_warning "Some packages failed but within acceptable limits ($failure_rate% <= $MAX_FAILURES%)"
        exit 1
    else
        log_error "Too many failures ($failure_rate% > $MAX_FAILURES%)"
        exit 5
    fi
}

# Function to generate summary report
generate_summary_report() {
    local total_count=$1
    local success_count=$2
    local failure_count=$3
    local duration=$4
    
    local success_rate=$((success_count * 100 / total_count))
    local failure_rate=$((failure_count * 100 / total_count))
    
    cat > "$SAIDATA_OUTPUT_DIR/reports/summary.json" << EOF
{
  "pipeline_run": {
    "timestamp": "$(date -Iseconds)",
    "duration_seconds": $duration,
    "configuration": "$SAIDATA_CONFIG",
    "software_list": "$SOFTWARE_LIST"
  },
  "results": {
    "total_packages": $total_count,
    "successful": $success_count,
    "failed": $failure_count,
    "success_rate_percent": $success_rate,
    "failure_rate_percent": $failure_rate
  },
  "environment": {
    "output_directory": "$SAIDATA_OUTPUT_DIR",
    "providers": "$SAIDATA_PROVIDERS",
    "confidence_threshold": "$SAIDATA_CONFIDENCE_THRESHOLD",
    "log_level": "$SAIDATA_LOG_LEVEL"
  },
  "artifacts": {
    "metadata_files": "$SAIDATA_OUTPUT_DIR/metadata/",
    "logs": "$SAIDATA_OUTPUT_DIR/logs/",
    "reports": "$SAIDATA_OUTPUT_DIR/reports/",
    "processing_results": "$SAIDATA_OUTPUT_DIR/reports/processing-results.csv"
  }
}
EOF

    log_info "Summary Report Generated:"
    log_info "  Total Packages: $total_count"
    log_info "  Successful: $success_count ($success_rate%)"
    log_info "  Failed: $failure_count ($failure_rate%)"
    log_info "  Duration: ${duration}s"
    log_info "  Report: $SAIDATA_OUTPUT_DIR/reports/summary.json"
}

# Main execution
main() {
    log_info "Starting Saidata Generator CI/CD Pipeline"
    log_info "Configuration: $SAIDATA_CONFIG"
    log_info "Output Directory: $SAIDATA_OUTPUT_DIR"
    log_info "Software List: $SOFTWARE_LIST"
    
    check_prerequisites
    setup_environment
    validate_configuration
    process_software_list
}

# Trap to ensure cleanup on exit
cleanup() {
    log_info "Pipeline execution completed"
}
trap cleanup EXIT

# Run main function
main "$@"