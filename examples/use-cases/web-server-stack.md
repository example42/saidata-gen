# Use Case: Web Server Stack Metadata Generation

This example demonstrates generating comprehensive metadata for a complete web server stack including nginx, database, and supporting tools.

## Scenario

You're setting up documentation for a web application stack that includes:
- Web server (nginx)
- Database (PostgreSQL)
- Cache (Redis)
- Process manager (PM2)
- Monitoring (htop)

## Configuration

Create a specialized configuration for web server components:

```yaml
# web-stack-config.yaml
cache:
  directory: "./web-stack-cache"
  ttl: 3600

fetcher:
  concurrent_requests: 5
  enabled_providers:
    - apt
    - brew
    - npm
    - docker
    - snap

generation:
  confidence_threshold: 0.7
  include_dev_packages: false
  output_format: "yaml"

# Web server specific templates
templates:
  use_defaults: true
  custom_templates_dir: "./templates/web-stack"
  provider_overrides:
    web_server:
      priority: 1
      default_ports:
        nginx: [80, 443]
        apache2: [80, 443]
      default_services:
        nginx: "nginx"
        apache2: "apache2"

quality:
  min_confidence_score: 0.6
  required_fields:
    - description
    - packages
    - services
    - ports
```

## Software List

Create a file `web-stack-software.txt`:

```
nginx
postgresql
redis-server
pm2
htop
curl
wget
certbot
ufw
fail2ban
```

## Generation Script

```bash
#!/bin/bash
# generate-web-stack.sh

set -e

CONFIG_FILE="web-stack-config.yaml"
SOFTWARE_LIST="web-stack-software.txt"
OUTPUT_DIR="./web-stack-metadata"

echo "=== Web Server Stack Metadata Generation ==="

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate metadata for each component
while IFS= read -r software; do
    echo "Generating metadata for: $software"
    
    saidata-gen generate "$software" \
        --config "$CONFIG_FILE" \
        --output "$OUTPUT_DIR/${software}.yaml" \
        --providers apt,docker,snap
    
    # Validate generated file
    if saidata-gen validate "$OUTPUT_DIR/${software}.yaml"; then
        echo "✓ $software metadata generated and validated"
    else
        echo "✗ $software validation failed"
    fi
    
done < "$SOFTWARE_LIST"

# Generate stack summary
echo "=== Stack Summary ==="
echo "Generated files:"
ls -la "$OUTPUT_DIR"/*.yaml

echo
echo "Total files: $(ls "$OUTPUT_DIR"/*.yaml | wc -l)"
echo "Total size: $(du -sh "$OUTPUT_DIR" | cut -f1)"
```

## Expected Output Structure

Each generated YAML file will follow this structure:

```yaml
# nginx.yaml
version: "0.1"
description: "High-performance HTTP server and reverse proxy"
category:
  default: "Server"
  sub: "Web Server"
  tags: ["http", "proxy", "load-balancer"]

packages:
  apt:
    name: "nginx"
    version: "latest"
  docker:
    name: "nginx"
    version: "alpine"

services:
  nginx:
    name: "nginx"
    type: "systemd"
    enabled: true

ports:
  http:
    number: 80
    protocol: "tcp"
    description: "HTTP traffic"
  https:
    number: 443
    protocol: "tcp"
    description: "HTTPS traffic"

directories:
  config:
    path: "/etc/nginx"
    purpose: "Configuration files"
  logs:
    path: "/var/log/nginx"
    purpose: "Log files"
  web_root:
    path: "/var/www/html"
    purpose: "Default web root"

urls:
  website: "https://nginx.org"
  documentation: "https://nginx.org/en/docs/"
  source: "https://github.com/nginx/nginx"
```

## Advanced Usage with RAG

For enhanced metadata generation, use RAG integration:

```bash
#!/bin/bash
# generate-web-stack-rag.sh

export OPENAI_API_KEY="your-api-key"

# Generate with RAG enhancement
while IFS= read -r software; do
    echo "Generating enhanced metadata for: $software"
    
    saidata-gen generate "$software" \
        --config "web-stack-config.yaml" \
        --output "./enhanced-metadata/${software}.yaml" \
        --use-rag \
        --rag-provider openai \
        --rag-model gpt-4
    
done < "web-stack-software.txt"
```

## Validation and Quality Assurance

```bash
#!/bin/bash
# validate-web-stack.sh

OUTPUT_DIR="./web-stack-metadata"
REPORT_FILE="validation-report.txt"

echo "=== Web Stack Validation Report ===" > "$REPORT_FILE"
echo "Generated: $(date)" >> "$REPORT_FILE"
echo >> "$REPORT_FILE"

total_files=0
valid_files=0
invalid_files=0

for yaml_file in "$OUTPUT_DIR"/*.yaml; do
    if [ -f "$yaml_file" ]; then
        total_files=$((total_files + 1))
        software=$(basename "$yaml_file" .yaml)
        
        echo "Validating: $software"
        
        if saidata-gen validate "$yaml_file" > /dev/null 2>&1; then
            valid_files=$((valid_files + 1))
            echo "✓ $software - VALID" >> "$REPORT_FILE"
        else
            invalid_files=$((invalid_files + 1))
            echo "✗ $software - INVALID" >> "$REPORT_FILE"
            
            # Get detailed validation errors
            echo "  Errors:" >> "$REPORT_FILE"
            saidata-gen validate "$yaml_file" 2>&1 | sed 's/^/    /' >> "$REPORT_FILE"
        fi
    fi
done

echo >> "$REPORT_FILE"
echo "Summary:" >> "$REPORT_FILE"
echo "  Total files: $total_files" >> "$REPORT_FILE"
echo "  Valid: $valid_files" >> "$REPORT_FILE"
echo "  Invalid: $invalid_files" >> "$REPORT_FILE"
echo "  Success rate: $(( valid_files * 100 / total_files ))%" >> "$REPORT_FILE"

echo "Validation completed. Report saved to: $REPORT_FILE"
```

## Integration with Infrastructure as Code

Use the generated metadata in your infrastructure automation:

```yaml
# ansible-playbook.yml
---
- name: Deploy Web Stack
  hosts: web_servers
  vars:
    metadata_dir: "./web-stack-metadata"
  
  tasks:
    - name: Read nginx metadata
      include_vars:
        file: "{{ metadata_dir }}/nginx.yaml"
        name: nginx_meta
    
    - name: Install nginx
      package:
        name: "{{ nginx_meta.packages.apt.name }}"
        state: present
    
    - name: Configure nginx service
      service:
        name: "{{ nginx_meta.services.nginx.name }}"
        state: started
        enabled: "{{ nginx_meta.services.nginx.enabled }}"
    
    - name: Open firewall ports
      ufw:
        rule: allow
        port: "{{ item.value.number }}"
        proto: "{{ item.value.protocol }}"
      loop: "{{ nginx_meta.ports | dict2items }}"
```

## Monitoring and Maintenance

Set up automated metadata updates:

```bash
#!/bin/bash
# update-web-stack-metadata.sh

# Cron job: 0 2 * * 0 (weekly on Sunday at 2 AM)

LOG_FILE="/var/log/saidata-web-stack-update.log"
BACKUP_DIR="/backup/web-stack-metadata"

echo "$(date): Starting web stack metadata update" >> "$LOG_FILE"

# Backup current metadata
cp -r "./web-stack-metadata" "$BACKUP_DIR/$(date +%Y%m%d)"

# Update metadata
if ./generate-web-stack.sh >> "$LOG_FILE" 2>&1; then
    echo "$(date): Metadata update completed successfully" >> "$LOG_FILE"
    
    # Validate all files
    if ./validate-web-stack.sh >> "$LOG_FILE" 2>&1; then
        echo "$(date): Validation passed" >> "$LOG_FILE"
    else
        echo "$(date): Validation failed - restoring backup" >> "$LOG_FILE"
        rm -rf "./web-stack-metadata"
        cp -r "$BACKUP_DIR/$(date +%Y%m%d)" "./web-stack-metadata"
    fi
else
    echo "$(date): Metadata update failed" >> "$LOG_FILE"
fi
```

This use case demonstrates a complete workflow for generating, validating, and maintaining metadata for a web server stack, including integration with infrastructure automation tools.