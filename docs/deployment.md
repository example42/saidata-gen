# Deployment Guide

This guide covers various deployment options for saidata-gen in different environments.

## Table of Contents

- [PyPI Package](#pypi-package)
- [Docker Container](#docker-container)
- [Standalone Binary](#standalone-binary)
- [CI/CD Integration](#cicd-integration)
- [Cloud Deployment](#cloud-deployment)
- [Enterprise Deployment](#enterprise-deployment)

## PyPI Package

### Standard Installation

The recommended way to install saidata-gen:

```bash
pip install saidata-gen
```

### Virtual Environment

For isolated installations:

```bash
python -m venv saidata-env
source saidata-env/bin/activate  # On Windows: saidata-env\Scripts\activate
pip install saidata-gen[rag,ml]
```

### System-wide Installation

For system administrators:

```bash
sudo pip install saidata-gen
```

## Docker Container

### Quick Start

Run saidata-gen in a container:

```bash
# Pull the latest image
docker pull saidata/saidata-gen:latest

# Generate metadata for nginx
docker run --rm -v $(pwd):/workspace saidata/saidata-gen:latest generate nginx

# Interactive shell
docker run -it --rm -v $(pwd):/workspace saidata/saidata-gen:latest bash
```

### Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  saidata-gen:
    image: saidata/saidata-gen:latest
    volumes:
      - ./workspace:/workspace
      - ./cache:/cache
      - ./config:/config
    environment:
      - SAIDATA_GEN_CACHE_DIR=/cache
      - SAIDATA_GEN_CONFIG_DIR=/config
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    working_dir: /workspace
    command: ["--help"]

  # Batch processing service
  batch-processor:
    image: saidata/saidata-gen:latest
    volumes:
      - ./input:/input
      - ./output:/output
      - ./cache:/cache
    environment:
      - SAIDATA_GEN_CACHE_DIR=/cache
    command: ["batch", "--input", "/input/software_list.txt", "--output", "/output"]
```

Run with:

```bash
docker-compose run saidata-gen generate nginx
docker-compose run batch-processor
```

### Custom Docker Image

Build your own image with custom configuration:

```dockerfile
FROM saidata/saidata-gen:latest

# Copy custom configuration
COPY config/ /config/
COPY templates/ /templates/

# Set environment variables
ENV SAIDATA_GEN_CONFIG_DIR=/config
ENV SAIDATA_GEN_TEMPLATE_DIR=/templates

# Default command
CMD ["generate", "--help"]
```

## Standalone Binary

### Download and Install

Download the appropriate binary for your platform:

```bash
# Linux
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-linux-x86_64 -o saidata-gen
chmod +x saidata-gen
sudo mv saidata-gen /usr/local/bin/

# macOS
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-darwin-x86_64 -o saidata-gen
chmod +x saidata-gen
sudo mv saidata-gen /usr/local/bin/

# Windows (PowerShell)
Invoke-WebRequest -Uri "https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-windows-x86_64.exe" -OutFile "saidata-gen.exe"
```

### Portable Installation

For portable use without installation:

```bash
# Create portable directory
mkdir saidata-gen-portable
cd saidata-gen-portable

# Download binary
curl -L https://github.com/sai/saidata-gen/releases/latest/download/saidata-gen-linux-x86_64 -o saidata-gen
chmod +x saidata-gen

# Create wrapper script
cat > run.sh << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SAIDATA_GEN_CONFIG_DIR="$SCRIPT_DIR/config"
export SAIDATA_GEN_CACHE_DIR="$SCRIPT_DIR/cache"
"$SCRIPT_DIR/saidata-gen" "$@"
EOF
chmod +x run.sh

# Initialize configuration
./run.sh config init
```

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/metadata-generation.yml`:

```yaml
name: Generate Software Metadata

on:
  push:
    paths:
      - 'software-inventory.txt'
  schedule:
    - cron: '0 2 * * 0'  # Weekly on Sunday at 2 AM

jobs:
  generate-metadata:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Generate metadata
      uses: docker://saidata/saidata-gen:latest
      with:
        args: batch --input software-inventory.txt --output metadata/
      env:
        OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
    
    - name: Commit generated metadata
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add metadata/
        git diff --staged --quiet || git commit -m "Update software metadata"
        git push
```

### GitLab CI

Add to `.gitlab-ci.yml`:

```yaml
stages:
  - generate
  - validate

generate-metadata:
  stage: generate
  image: saidata/saidata-gen:latest
  script:
    - saidata-gen batch --input software-inventory.txt --output metadata/
  artifacts:
    paths:
      - metadata/
    expire_in: 1 week
  only:
    changes:
      - software-inventory.txt

validate-metadata:
  stage: validate
  image: saidata/saidata-gen:latest
  script:
    - saidata-gen validate metadata/*.yaml
  dependencies:
    - generate-metadata
```

### Jenkins Pipeline

Create a `Jenkinsfile`:

```groovy
pipeline {
    agent any
    
    environment {
        OPENAI_API_KEY = credentials('openai-api-key')
    }
    
    stages {
        stage('Generate Metadata') {
            steps {
                script {
                    docker.image('saidata/saidata-gen:latest').inside {
                        sh 'saidata-gen batch --input software-inventory.txt --output metadata/'
                    }
                }
            }
        }
        
        stage('Validate') {
            steps {
                script {
                    docker.image('saidata/saidata-gen:latest').inside {
                        sh 'saidata-gen validate metadata/*.yaml'
                    }
                }
            }
        }
        
        stage('Archive') {
            steps {
                archiveArtifacts artifacts: 'metadata/*.yaml', fingerprint: true
            }
        }
    }
}
```

## Cloud Deployment

### AWS Lambda

Deploy as a serverless function:

```python
# lambda_function.py
import json
import os
from saidata_gen import SaidataEngine

def lambda_handler(event, context):
    engine = SaidataEngine()
    
    software_name = event.get('software_name')
    if not software_name:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'software_name is required'})
        }
    
    try:
        result = engine.generate_metadata(software_name)
        return {
            'statusCode': 200,
            'body': json.dumps({
                'software_name': software_name,
                'metadata': result.metadata
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
```

### Google Cloud Run

Deploy with Cloud Run:

```dockerfile
FROM saidata/saidata-gen:latest

# Install additional dependencies for Cloud Run
RUN pip install gunicorn flask

# Copy Flask app
COPY app.py /app/app.py
WORKDIR /app

# Expose port
EXPOSE 8080

# Run with gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

### Azure Container Instances

Deploy with Azure CLI:

```bash
az container create \
  --resource-group myResourceGroup \
  --name saidata-gen \
  --image saidata/saidata-gen:latest \
  --cpu 1 \
  --memory 2 \
  --environment-variables OPENAI_API_KEY=$OPENAI_API_KEY \
  --command-line "saidata-gen batch --input /input/software_list.txt --output /output"
```

## Enterprise Deployment

### Kubernetes

Deploy with Kubernetes:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: saidata-gen
spec:
  replicas: 3
  selector:
    matchLabels:
      app: saidata-gen
  template:
    metadata:
      labels:
        app: saidata-gen
    spec:
      containers:
      - name: saidata-gen
        image: saidata/saidata-gen:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai
        volumeMounts:
        - name: config
          mountPath: /config
        - name: cache
          mountPath: /cache
      volumes:
      - name: config
        configMap:
          name: saidata-gen-config
      - name: cache
        persistentVolumeClaim:
          claimName: saidata-gen-cache

---
apiVersion: v1
kind: Service
metadata:
  name: saidata-gen-service
spec:
  selector:
    app: saidata-gen
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer
```

### Helm Chart

Create a Helm chart for easy deployment:

```yaml
# Chart.yaml
apiVersion: v2
name: saidata-gen
description: A Helm chart for saidata-gen
version: 0.1.0
appVersion: "0.1.0"

# values.yaml
replicaCount: 3

image:
  repository: saidata/saidata-gen
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80

ingress:
  enabled: false

resources:
  limits:
    cpu: 500m
    memory: 1Gi
  requests:
    cpu: 250m
    memory: 512Mi

config:
  cacheDir: /cache
  configDir: /config

secrets:
  openaiApiKey: ""
  anthropicApiKey: ""
```

### Docker Swarm

Deploy with Docker Swarm:

```yaml
# docker-stack.yml
version: '3.8'

services:
  saidata-gen:
    image: saidata/saidata-gen:latest
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
      resources:
        limits:
          cpus: '0.5'
          memory: 1G
        reservations:
          cpus: '0.25'
          memory: 512M
    environment:
      - OPENAI_API_KEY_FILE=/run/secrets/openai_api_key
    secrets:
      - openai_api_key
    volumes:
      - cache:/cache
      - config:/config

secrets:
  openai_api_key:
    external: true

volumes:
  cache:
  config:
```

Deploy with:

```bash
docker stack deploy -c docker-stack.yml saidata-gen
```

## Configuration Management

### Environment Variables

Key environment variables:

```bash
# Core configuration
export SAIDATA_GEN_CONFIG_DIR=/path/to/config
export SAIDATA_GEN_CACHE_DIR=/path/to/cache
export SAIDATA_GEN_LOG_LEVEL=INFO

# API keys
export OPENAI_API_KEY=your-openai-key
export ANTHROPIC_API_KEY=your-anthropic-key

# Repository settings
export SAIDATA_GEN_CACHE_TTL=3600
export SAIDATA_GEN_CONCURRENT_REQUESTS=5
```

### Configuration Files

Create configuration files for different environments:

```yaml
# config/production.yaml
cache:
  ttl: 3600
  directory: /var/cache/saidata-gen

repositories:
  concurrent_requests: 10
  timeout: 30
  retry_count: 3

rag:
  provider: openai
  model: gpt-4
  temperature: 0.1

logging:
  level: INFO
  format: json
```

## Monitoring and Logging

### Prometheus Metrics

Enable metrics collection:

```yaml
# config/monitoring.yaml
metrics:
  enabled: true
  port: 9090
  path: /metrics

logging:
  level: INFO
  format: json
  output: stdout
```

### Log Aggregation

Configure log forwarding:

```yaml
# docker-compose.yml
version: '3.8'

services:
  saidata-gen:
    image: saidata/saidata-gen:latest
    logging:
      driver: "fluentd"
      options:
        fluentd-address: localhost:24224
        tag: saidata-gen
```

## Security Considerations

### API Key Management

- Use environment variables or secret management systems
- Rotate API keys regularly
- Limit API key permissions where possible

### Network Security

- Use HTTPS for all external communications
- Implement proper firewall rules
- Consider using VPN for internal communications

### Container Security

- Use non-root users in containers
- Scan images for vulnerabilities
- Keep base images updated

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure proper file permissions and user context
2. **Network Issues**: Check firewall rules and proxy settings
3. **Memory Issues**: Increase memory limits for large batch operations
4. **API Rate Limits**: Configure appropriate rate limiting and retry logic

### Debug Mode

Enable debug logging:

```bash
export SAIDATA_GEN_LOG_LEVEL=DEBUG
saidata-gen generate nginx --verbose
```

### Health Checks

Implement health checks:

```bash
# Simple health check
saidata-gen --version

# Comprehensive health check
saidata-gen config validate
saidata-gen fetch --dry-run
```