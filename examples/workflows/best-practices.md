# Saidata Generator Best Practices

This document outlines recommended approaches and best practices for using the saidata generator effectively in different environments and scenarios.

## Table of Contents

1. [Configuration Management](#configuration-management)
2. [Batch Processing Optimization](#batch-processing-optimization)
3. [Quality Assurance Workflows](#quality-assurance-workflows)
4. [Performance Tuning](#performance-tuning)
5. [RAG Integration Guidelines](#rag-integration-guidelines)
6. [CI/CD Integration](#cicd-integration)
7. [Troubleshooting](#troubleshooting)

## Configuration Management

### Hierarchical Configuration Strategy

Use a layered configuration approach for maximum flexibility:

```yaml
# Base configuration (base.yaml)
cache:
  directory: "~/.saidata-gen/cache"
  ttl: 3600

# Environment-specific overrides (production.yaml)
extends: base.yaml
cache:
  directory: "/var/cache/saidata-gen"
  ttl: 7200
```

### Environment Variables

Leverage environment variables for sensitive data and deployment-specific settings:

```bash
# Required for RAG functionality
export OPENAI_API_KEY="your-api-key"
export ANTHROPIC_API_KEY="your-api-key"

# Deployment-specific settings
export SAIDATA_CACHE_DIR="/opt/saidata-cache"
export SAIDATA_LOG_LEVEL="INFO"
export SAIDATA_OUTPUT_FORMAT="yaml"
```

### Configuration Validation

Always validate your configuration before production use:

```bash
# Validate configuration file
saidata-gen config validate --config production.yaml

# Test with a single package
saidata-gen generate nginx --config production.yaml --dry-run
```

## Batch Processing Optimization

### Chunking Strategy

Process large software inventories in manageable chunks:

```bash
# Split large lists into chunks of 50
split -l 50 large-software-list.txt chunk_

# Process each chunk separately
for chunk in chunk_*; do
    saidata-gen batch --input "$chunk" --output "./output/$(basename $chunk)"
done
```

### Parallel Processing

Optimize parallel processing based on your system resources:

```yaml
# Configuration for different system sizes
performance:
  # Small systems (2-4 cores)
  max_workers: 2
  concurrent_requests: 3
  
  # Medium systems (4-8 cores)
  max_workers: 4
  concurrent_requests: 5
  
  # Large systems (8+ cores)
  max_workers: 8
  concurrent_requests: 10
```

### Error Handling in Batch Operations

Implement robust error handling for batch processing:

```bash
#!/bin/bash
# Batch processing with error recovery

FAILED_PACKAGES=()
SUCCESS_COUNT=0
TOTAL_COUNT=0

while IFS= read -r software; do
    TOTAL_COUNT=$((TOTAL_COUNT + 1))
    
    if saidata-gen generate "$software" --output "./output/${software}.yaml"; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        echo "✓ $software"
    else
        FAILED_PACKAGES+=("$software")
        echo "✗ $software"
    fi
done < software-list.txt

# Retry failed packages with different settings
if [ ${#FAILED_PACKAGES[@]} -gt 0 ]; then
    echo "Retrying ${#FAILED_PACKAGES[@]} failed packages with relaxed settings..."
    for software in "${FAILED_PACKAGES[@]}"; do
        saidata-gen generate "$software" \
            --confidence-threshold 0.5 \
            --providers apt,brew \
            --output "./output/${software}.yaml"
    done
fi
```

## Quality Assurance Workflows

### Multi-Stage Validation

Implement a comprehensive validation pipeline:

```bash
#!/bin/bash
# Multi-stage validation workflow

SOFTWARE="$1"
OUTPUT_FILE="./output/${SOFTWARE}.yaml"

# Stage 1: Generate metadata
echo "Stage 1: Generating metadata..."
saidata-gen generate "$SOFTWARE" --output "$OUTPUT_FILE"

# Stage 2: Schema validation
echo "Stage 2: Schema validation..."
saidata-gen validate "$OUTPUT_FILE"

# Stage 3: Quality checks
echo "Stage 3: Quality assessment..."
saidata-gen quality-check "$OUTPUT_FILE" --min-confidence 0.7

# Stage 4: Cross-reference validation
echo "Stage 4: Cross-reference validation..."
saidata-gen cross-validate "$OUTPUT_FILE" --sources 3

# Stage 5: Manual review flag
if saidata-gen quality-score "$OUTPUT_FILE" | grep -q "LOW"; then
    echo "⚠️  Manual review recommended for $SOFTWARE"
    mv "$OUTPUT_FILE" "./review-queue/${SOFTWARE}.yaml"
fi
```

### Confidence Scoring Guidelines

Set appropriate confidence thresholds based on use case:

```yaml
quality_thresholds:
  # Production environments
  production:
    min_confidence: 0.8
    required_sources: 3
    manual_review_threshold: 0.6
  
  # Development environments
  development:
    min_confidence: 0.5
    required_sources: 1
    manual_review_threshold: 0.3
  
  # Research/experimental
  research:
    min_confidence: 0.3
    required_sources: 1
    manual_review_threshold: 0.1
```

## Performance Tuning

### Cache Optimization

Configure caching for optimal performance:

```yaml
cache:
  # Adjust TTL based on data freshness requirements
  repository_data_ttl: 7200    # 2 hours for repository data
  api_response_ttl: 3600       # 1 hour for API responses
  generated_metadata_ttl: 86400 # 24 hours for generated metadata
  
  # Size limits
  max_cache_size: "5GB"
  cleanup_threshold: 0.8       # Clean when 80% full
  
  # Performance settings
  compression: true
  async_cleanup: true
```

### Network Optimization

Optimize network requests for better performance:

```yaml
network:
  # Connection pooling
  connection_pool_size: 20
  connection_pool_maxsize: 100
  
  # Timeouts
  connect_timeout: 10
  read_timeout: 30
  total_timeout: 60
  
  # Retry configuration
  max_retries: 3
  retry_backoff_factor: 2
  retry_status_codes: [429, 500, 502, 503, 504]
  
  # Rate limiting
  requests_per_second: 10
  burst_limit: 20
```

### Memory Management

Monitor and optimize memory usage:

```bash
# Monitor memory usage during batch processing
#!/bin/bash

monitor_memory() {
    while true; do
        ps aux | grep saidata-gen | grep -v grep | awk '{print $6}' | \
        awk '{sum+=$1} END {print "Memory usage: " sum/1024 " MB"}'
        sleep 30
    done
}

# Run monitoring in background
monitor_memory &
MONITOR_PID=$!

# Run batch processing
saidata-gen batch --input large-list.txt --output ./output/

# Stop monitoring
kill $MONITOR_PID
```

## RAG Integration Guidelines

### Model Selection Strategy

Choose appropriate models based on requirements:

```yaml
rag_strategies:
  # High accuracy, higher cost
  premium:
    provider: "openai"
    model: "gpt-4"
    temperature: 0.1
    use_cases: ["production", "critical_metadata"]
  
  # Balanced performance and cost
  standard:
    provider: "openai"
    model: "gpt-3.5-turbo"
    temperature: 0.2
    use_cases: ["development", "bulk_processing"]
  
  # Cost-effective, local processing
  local:
    provider: "local"
    model: "llama2:13b"
    temperature: 0.3
    use_cases: ["experimentation", "privacy_sensitive"]
```

### Prompt Engineering Best Practices

Design effective prompts for consistent results:

```yaml
prompt_templates:
  description_enhancement:
    system_prompt: |
      You are a technical documentation expert. Enhance software descriptions 
      to be clear, accurate, and informative while maintaining a neutral tone.
    
    user_prompt: |
      Software: {software_name}
      Current description: {current_description}
      Package details: {package_details}
      
      Provide an enhanced description that:
      1. Clearly explains the software's purpose
      2. Lists key features
      3. Identifies target users
      4. Maintains technical accuracy
      
      Keep it concise (100-200 words).
    
    validation_criteria:
      - length: [50, 300]
      - tone: "neutral"
      - technical_accuracy: true
```

### Cost Management

Implement cost controls for RAG usage:

```yaml
cost_management:
  # Daily limits
  daily_token_limit: 100000
  daily_request_limit: 1000
  
  # Per-request limits
  max_tokens_per_request: 2000
  timeout_seconds: 60
  
  # Fallback strategy
  fallback_on_limit: true
  fallback_confidence_reduction: 0.2
  
  # Monitoring
  cost_tracking: true
  alert_threshold: 0.8  # Alert at 80% of daily limit
```

## CI/CD Integration

### Pipeline Configuration

Structure your CI/CD pipeline for reliability:

```yaml
# .github/workflows/saidata-generation.yml
name: Saidata Generation Pipeline

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  generate-metadata:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install saidata-gen
      run: pip install saidata-gen
    
    - name: Generate metadata
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        SAIDATA_CONFIG: configs/ci-cd.yaml
      run: |
        ./scripts/ci-cd-pipeline.sh
    
    - name: Upload artifacts
      uses: actions/upload-artifact@v3
      with:
        name: generated-metadata
        path: ./saidata-output/
    
    - name: Notify on failure
      if: failure()
      run: |
        echo "Pipeline failed - check logs"
        # Add notification logic here
```

### Quality Gates

Implement quality gates in your pipeline:

```bash
#!/bin/bash
# Quality gate script

QUALITY_THRESHOLD=0.8
SUCCESS_RATE_THRESHOLD=0.9

# Check overall success rate
SUCCESS_RATE=$(jq -r '.results.success_rate_percent / 100' reports/summary.json)

if (( $(echo "$SUCCESS_RATE < $SUCCESS_RATE_THRESHOLD" | bc -l) )); then
    echo "❌ Success rate ($SUCCESS_RATE) below threshold ($SUCCESS_RATE_THRESHOLD)"
    exit 1
fi

# Check average quality score
QUALITY_SCORE=$(jq -r '.quality.average_confidence' reports/summary.json)

if (( $(echo "$QUALITY_SCORE < $QUALITY_THRESHOLD" | bc -l) )); then
    echo "❌ Quality score ($QUALITY_SCORE) below threshold ($QUALITY_THRESHOLD)"
    exit 1
fi

echo "✅ Quality gates passed"
```

## Troubleshooting

### Common Issues and Solutions

#### High Memory Usage

```bash
# Symptoms: Process killed by OOM killer
# Solution: Reduce batch size and enable streaming

# Configuration adjustment
batch:
  chunk_size: 5  # Reduce from default 10
  streaming_mode: true
  memory_limit: "1GB"
```

#### Network Timeouts

```bash
# Symptoms: Frequent timeout errors
# Solution: Increase timeouts and implement retry logic

network:
  connect_timeout: 30  # Increase from 10
  read_timeout: 60     # Increase from 30
  max_retries: 5       # Increase from 3
  retry_delay: 5       # Add delay between retries
```

#### Cache Issues

```bash
# Symptoms: Stale data or cache corruption
# Solution: Clear cache and rebuild

# Clear specific cache
saidata-gen cache clear --type repository_data

# Clear all cache
saidata-gen cache clear --all

# Rebuild cache
saidata-gen fetch --providers all --force-refresh
```

### Debugging Techniques

#### Enable Debug Logging

```yaml
logging:
  level: "DEBUG"
  debug_modules:
    - "saidata_gen.fetcher"
    - "saidata_gen.rag"
  debug_requests: true
  save_debug_data: true
```

#### Performance Profiling

```bash
# Profile a single generation
saidata-gen generate nginx --profile --profile-output profile.json

# Analyze profile data
saidata-gen analyze-profile profile.json
```

#### Validate Configuration

```bash
# Comprehensive configuration check
saidata-gen config check --config production.yaml --verbose

# Test connectivity to all providers
saidata-gen test-providers --config production.yaml
```

### Monitoring and Alerting

#### Health Checks

```bash
#!/bin/bash
# Health check script for monitoring systems

# Check service availability
if ! saidata-gen --version > /dev/null 2>&1; then
    echo "CRITICAL: saidata-gen not available"
    exit 2
fi

# Check cache health
CACHE_SIZE=$(saidata-gen cache info --format json | jq -r '.size_mb')
if (( $(echo "$CACHE_SIZE > 5000" | bc -l) )); then
    echo "WARNING: Cache size ($CACHE_SIZE MB) is large"
    exit 1
fi

# Check recent generation success rate
SUCCESS_RATE=$(saidata-gen stats --last-24h --format json | jq -r '.success_rate')
if (( $(echo "$SUCCESS_RATE < 0.8" | bc -l) )); then
    echo "WARNING: Success rate ($SUCCESS_RATE) is low"
    exit 1
fi

echo "OK: All health checks passed"
exit 0
```

This comprehensive best practices guide provides the foundation for successful deployment and operation of the saidata generator in various environments.