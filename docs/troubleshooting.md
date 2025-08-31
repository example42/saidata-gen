# Troubleshooting Guide

This guide helps you troubleshoot common issues with saidata-gen, including the new directory structure output, provider defaults system, and enhanced fetcher reliability.

## Common Issues and Solutions

### 1. Directory Structure Issues

#### Problem: Expected single YAML file but got directory structure

**Symptoms:**
```bash
$ saidata-gen generate nginx
# Creates nginx/ directory instead of nginx.yaml file
```

**Solution:**
This is the new default behavior. saidata-gen now always generates structured directory output:

```
nginx/
├── defaults.yaml              # Software-specific base configuration
└── providers/                 # Provider-specific overrides
    ├── apt.yaml              # Only if different from defaults
    └── brew.yaml             # Only if different from defaults
```

To work with the new structure:
```bash
# Validate the main configuration
saidata-gen validate nginx/defaults.yaml

# View the generated structure
ls -la nginx/
cat nginx/defaults.yaml
```

#### Problem: Empty providers directory

**Symptoms:**
```
nginx/
├── defaults.yaml
└── providers/                 # Empty directory
```

**Solution:**
This is normal behavior. Provider-specific files are only created when they differ from the defaults in `provider_defaults.yaml`. If all providers use default configurations, no provider files are generated.

To force provider file generation for debugging:
```bash
# Enable verbose logging to see why files weren't created
saidata-gen generate nginx --verbose
```

### 2. Provider Configuration Issues

#### Problem: Provider not found or unsupported

**Symptoms:**
```
ERROR: Provider 'xyz' is not supported
ERROR: Invalid providers specified: xyz
```

**Solutions:**

1. **Check available providers:**
   ```bash
   saidata-gen list-providers
   ```

2. **Verify provider name spelling:**
   ```bash
   # Common provider names
   apt, dnf, yum, zypper, pacman, apk, emerge, portage
   brew, winget, choco, scoop
   flatpak, snap, nix, nixpkgs, guix
   npm, pypi, cargo, gem, go, composer, nuget, maven
   docker, helm
   ```

3. **Check if provider has template:**
   ```bash
   ls saidata_gen/templates/providers/
   ```

#### Problem: Provider defaults not loading

**Symptoms:**
```
WARNING: Failed to load provider defaults
ERROR: provider_defaults.yaml not found
```

**Solutions:**

1. **Verify provider_defaults.yaml exists:**
   ```bash
   ls saidata_gen/templates/provider_defaults.yaml
   ```

2. **Check file permissions:**
   ```bash
   chmod 644 saidata_gen/templates/provider_defaults.yaml
   ```

3. **Validate YAML syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('saidata_gen/templates/provider_defaults.yaml'))"
   ```

### 3. Fetcher Reliability Issues

#### Problem: Network connection failures

**Symptoms:**
```
ERROR: Failed to fetch from https://packages.ubuntu.com/
ConnectionError: HTTPSConnectionPool(...): Max retries exceeded
```

**Solutions:**

1. **Check network connectivity:**
   ```bash
   curl -I https://packages.ubuntu.com/
   ping packages.ubuntu.com
   ```

2. **Configure proxy if needed:**
   ```bash
   export HTTP_PROXY=http://proxy.company.com:8080
   export HTTPS_PROXY=http://proxy.company.com:8080
   saidata-gen generate nginx
   ```

3. **Use alternative providers:**
   ```bash
   # Skip problematic providers
   saidata-gen generate nginx --providers brew,winget,docker
   ```

4. **Enable retry logic debugging:**
   ```bash
   export SAIDATA_GEN_LOG_LEVEL=DEBUG
   saidata-gen generate nginx --verbose
   ```

#### Problem: SSL certificate verification errors

**Symptoms:**
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
ERROR: SSL verification failed for https://...
```

**Solutions:**

1. **Update certificates:**
   ```bash
   # macOS
   brew install ca-certificates
   
   # Ubuntu/Debian
   sudo apt-get update && sudo apt-get install ca-certificates
   
   # RHEL/CentOS
   sudo yum update ca-certificates
   ```

2. **Check system time:**
   ```bash
   # Ensure system time is correct
   date
   sudo ntpdate -s time.nist.gov  # Linux
   sudo sntp -sS time.apple.com   # macOS
   ```

3. **Use alternative endpoints:**
   ```bash
   # The system will automatically try fallback URLs
   # Enable verbose logging to see fallback attempts
   saidata-gen generate nginx --verbose
   ```

4. **Temporary SSL bypass (not recommended for production):**
   ```bash
   export PYTHONHTTPSVERIFY=0
   saidata-gen generate nginx
   ```

#### Problem: Repository data parsing errors

**Symptoms:**
```
ERROR: Failed to parse repository data
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**Solutions:**

1. **Check repository status:**
   ```bash
   curl -s https://packages.ubuntu.com/search?keywords=nginx | head -20
   ```

2. **Clear cache and retry:**
   ```bash
   rm -rf ~/.saidata-gen/cache/
   saidata-gen generate nginx
   ```

3. **Use alternative data sources:**
   ```bash
   # Try different providers
   saidata-gen generate nginx --providers brew,docker
   ```

4. **Enable graceful degradation:**
   ```bash
   # The system automatically handles malformed data
   # Check logs for degradation events
   saidata-gen generate nginx --verbose
   ```

### 4. System Dependency Issues

#### Problem: Missing package manager commands

**Symptoms:**
```
WARNING: Command 'emerge' not found, skipping emerge provider
ERROR: Required system command not available: guix
```

**Solutions:**

1. **Install missing package managers:**
   ```bash
   # Homebrew (macOS/Linux)
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
   # Nix (multi-platform)
   curl -L https://nixos.org/nix/install | sh
   
   # Guix (Linux)
   wget https://git.savannah.gnu.org/cgit/guix.git/plain/etc/guix-install.sh
   chmod +x guix-install.sh && sudo ./guix-install.sh
   ```

2. **Skip unavailable providers:**
   ```bash
   # Explicitly specify available providers
   saidata-gen generate nginx --providers apt,brew,docker
   ```

3. **Check system PATH:**
   ```bash
   echo $PATH
   which emerge  # Should show path if installed
   ```

4. **Use system-specific providers:**
   ```bash
   # Linux
   saidata-gen generate nginx --providers apt,dnf,flatpak,snap
   
   # macOS
   saidata-gen generate nginx --providers brew
   
   # Windows
   saidata-gen generate nginx --providers winget,choco,scoop
   ```

### 5. AI Enhancement Issues

#### Problem: AI enhancement not working

**Symptoms:**
```
WARNING: AI provider openai is not available
ERROR: Enhancement failed: API key not found
```

**Solutions:**

1. **Set up API keys:**
   ```bash
   # OpenAI
   export OPENAI_API_KEY="your-api-key-here"
   
   # Anthropic
   export ANTHROPIC_API_KEY="your-api-key-here"
   
   # Verify key is set
   echo $OPENAI_API_KEY
   ```

2. **Check API key validity:**
   ```bash
   curl -H "Authorization: Bearer $OPENAI_API_KEY" \
        https://api.openai.com/v1/models
   ```

3. **Use local AI models:**
   ```bash
   # Install Ollama
   curl -fsSL https://ollama.ai/install.sh | sh
   ollama pull llama2
   
   # Use local provider
   saidata-gen generate nginx --ai --ai-provider local
   ```

4. **Check rate limits:**
   ```bash
   # Reduce confidence threshold to require less AI processing
   saidata-gen generate nginx --ai --confidence-threshold 0.5
   ```

#### Problem: AI enhancement produces poor results

**Symptoms:**
```
Generated description: "This is a software package"
Low confidence scores for AI-enhanced fields
```

**Solutions:**

1. **Adjust confidence threshold:**
   ```bash
   # Require higher confidence
   saidata-gen generate nginx --ai --confidence-threshold 0.8
   ```

2. **Try different AI providers:**
   ```bash
   # Try Anthropic instead of OpenAI
   saidata-gen generate nginx --ai --ai-provider anthropic
   ```

3. **Provide more context:**
   ```bash
   # Use specific providers that give more context
   saidata-gen generate nginx --providers apt,brew,docker --ai
   ```

### 6. Validation and Schema Issues

#### Problem: Schema validation failures

**Symptoms:**
```
ValidationError: 'version' is a required property
ValidationError: Additional properties are not allowed ('unsupported_key')
```

**Solutions:**

1. **Check required fields:**
   ```yaml
   # Ensure version is always present
   version: 0.1
   
   # For unsupported providers
   version: 0.1
   supported: false
   ```

2. **Remove invalid properties:**
   ```bash
   # Use validation to identify issues
   saidata-gen validate nginx/defaults.yaml --verbose
   ```

3. **Update schema if needed:**
   ```bash
   # Check schema version
   grep version schemas/saidata-0.1.schema.json
   ```

4. **Skip validation temporarily:**
   ```bash
   saidata-gen generate nginx --no-validate
   ```

### 7. Performance Issues

#### Problem: Slow generation times

**Symptoms:**
- Long processing times (>30 seconds for single package)
- High memory usage
- Frequent cache misses

**Solutions:**

1. **Enable caching:**
   ```bash
   export SAIDATA_GEN_CACHE_DIR=~/.saidata-gen/cache
   mkdir -p ~/.saidata-gen/cache
   ```

2. **Limit providers:**
   ```bash
   # Use only essential providers
   saidata-gen generate nginx --providers apt,brew,docker
   ```

3. **Use batch processing:**
   ```bash
   # Process multiple packages together
   echo -e "nginx\napache2\nmysql" > packages.txt
   saidata-gen batch --input packages.txt --output ./generated/
   ```

4. **Monitor resource usage:**
   ```bash
   # Monitor while running
   top -p $(pgrep -f saidata-gen)
   ```

5. **Clear cache if corrupted:**
   ```bash
   rm -rf ~/.saidata-gen/cache/
   ```

### 8. Configuration File Issues

#### Problem: Configuration file not loaded

**Symptoms:**
```
WARNING: Configuration file not found: ~/.saidata-gen/config.yaml
Using default configuration
```

**Solutions:**

1. **Create configuration file:**
   ```bash
   mkdir -p ~/.saidata-gen
   cat > ~/.saidata-gen/config.yaml << EOF
   providers:
     - apt
     - brew
     - docker
   ai:
     enabled: false
   output:
     format: yaml
   EOF
   ```

2. **Specify custom config:**
   ```bash
   saidata-gen generate nginx --config /path/to/config.yaml
   ```

3. **Validate configuration syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('~/.saidata-gen/config.yaml'))"
   ```

## Debugging Tips

### Enable Debug Logging

```bash
# Enable debug logging for all modules
export SAIDATA_GEN_LOG_LEVEL=DEBUG
saidata-gen generate nginx --verbose

# Enable for specific modules
export SAIDATA_GEN_LOG_LEVEL=INFO
python -c "
import logging
logging.getLogger('saidata_gen.fetcher').setLevel(logging.DEBUG)
logging.getLogger('saidata_gen.generator').setLevel(logging.DEBUG)
"
```

### Inspect Generated Files

```bash
# Check directory structure
tree nginx/

# Validate all generated files
find nginx/ -name "*.yaml" -exec saidata-gen validate {} \;

# Compare with defaults
diff nginx/providers/apt.yaml saidata_gen/templates/provider_defaults.yaml
```

### Test Individual Components

```bash
# Test fetcher for specific provider
python -c "
from saidata_gen.fetcher.factory import FetcherFactory
factory = FetcherFactory()
fetcher = factory.create_fetcher('apt')
result = fetcher.fetch_package_info('nginx')
print(result)
"

# Test configuration loading
python -c "
from saidata_gen.core.configuration import ConfigurationManager
manager = ConfigurationManager()
config = manager.get_provider_config('apt', 'nginx')
print(config)
"
```

### Network Debugging

```bash
# Test connectivity to repositories
curl -I https://packages.ubuntu.com/
curl -I https://brew.sh/
curl -I https://hub.docker.com/

# Check DNS resolution
nslookup packages.ubuntu.com
dig packages.ubuntu.com

# Test with different DNS servers
export SAIDATA_GEN_DNS_SERVER=8.8.8.8
```

## Error Reference

### Common Error Codes

| Error Code | Description | Solution |
|------------|-------------|----------|
| `PROVIDER_NOT_FOUND` | Provider not supported | Check provider name and availability |
| `NETWORK_ERROR` | Network connectivity issue | Check internet connection and proxy |
| `SSL_ERROR` | SSL certificate problem | Update certificates or use fallback |
| `PARSE_ERROR` | Data parsing failure | Check repository data format |
| `VALIDATION_ERROR` | Schema validation failure | Fix configuration or update schema |
| `DEPENDENCY_ERROR` | Missing system dependency | Install required package manager |
| `CONFIG_ERROR` | Configuration file issue | Fix YAML syntax or file permissions |
| `CACHE_ERROR` | Cache corruption or access | Clear cache directory |
| `AI_ERROR` | AI enhancement failure | Check API keys and rate limits |
| `PERMISSION_ERROR` | File system permission | Fix file/directory permissions |

### Exit Codes

- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Network error
- `4` - Validation error
- `5` - Dependency error

## Getting Help

### Log Analysis

When reporting issues, include:

1. **Command used:**
   ```bash
   saidata-gen generate nginx --providers apt,brew --ai --verbose
   ```

2. **Environment information:**
   ```bash
   saidata-gen --version
   python --version
   uname -a
   ```

3. **Debug logs:**
   ```bash
   export SAIDATA_GEN_LOG_LEVEL=DEBUG
   saidata-gen generate nginx --verbose > debug.log 2>&1
   ```

4. **Configuration:**
   ```bash
   cat ~/.saidata-gen/config.yaml
   env | grep SAIDATA_GEN
   ```

### Support Channels

- **Documentation**: This guide and [API Reference](api-reference.md)
- **GitHub Issues**: [Report bugs and feature requests](https://github.com/sai/saidata-gen/issues)
- **GitHub Discussions**: [Community support and questions](https://github.com/sai/saidata-gen/discussions)
- **Examples**: Check the `examples/` directory for working configurations

### Before Reporting Issues

1. **Search existing issues** - Your problem might already be reported
2. **Try latest version** - Update to the latest release
3. **Test with minimal config** - Isolate the problem
4. **Check network connectivity** - Verify internet access
5. **Review logs carefully** - Look for specific error messages

## Migration from Legacy System

### Migrating from Single File Output

If you're migrating from the old single-file output system:

#### Before (Legacy)
```bash
saidata-gen generate nginx --output nginx.yaml
# Created: nginx.yaml
```

#### After (New Directory Structure)
```bash
saidata-gen generate nginx --output ./
# Creates: nginx/defaults.yaml and nginx/providers/*.yaml
```

#### Migration Steps

1. **Update scripts and automation:**
   ```bash
   # Old way
   saidata-gen validate nginx.yaml
   
   # New way
   saidata-gen validate nginx/defaults.yaml
   find nginx/providers/ -name "*.yaml" -exec saidata-gen validate {} \;
   ```

2. **Update file references:**
   ```bash
   # Old way
   cat nginx.yaml
   
   # New way
   cat nginx/defaults.yaml
   ls nginx/providers/
   ```

3. **Update CI/CD pipelines:**
   ```yaml
   # Old pipeline
   - name: Generate metadata
     run: saidata-gen generate nginx --output nginx.yaml
   - name: Validate
     run: saidata-gen validate nginx.yaml
   
   # New pipeline
   - name: Generate metadata
     run: saidata-gen generate nginx --output ./generated/
   - name: Validate
     run: |
       saidata-gen validate generated/nginx/defaults.yaml
       find generated/nginx/providers/ -name "*.yaml" -exec saidata-gen validate {} \;
   ```

### Deprecated CLI Options

The following CLI options have been removed:

- `--directory-structure` - Directory structure is now always generated
- `--comprehensive` - Comprehensive generation is now the default
- `--use-rag` - Replaced with `--ai`
- `--rag-provider` - Replaced with `--ai-provider`

#### Migration Examples

```bash
# Old (deprecated)
saidata-gen generate nginx --directory-structure --comprehensive
saidata-gen generate nginx --use-rag --rag-provider openai

# New (current)
saidata-gen generate nginx  # Directory structure is default
saidata-gen generate nginx --ai --ai-provider openai
```

## Preventive Measures

### Regular Maintenance

```bash
# Update saidata-gen regularly
pip install --upgrade saidata-gen

# Clear old cache periodically
find ~/.saidata-gen/cache -mtime +7 -delete

# Validate configurations regularly
find . -name "*.yaml" -exec saidata-gen validate {} \;
```

### Monitoring

```bash
# Set up health checks
saidata-gen generate nginx --providers apt --no-validate --format json > /dev/null
echo $?  # Should be 0 for success

# Monitor cache size
du -sh ~/.saidata-gen/cache/

# Check for deprecated features
saidata-gen generate nginx 2>&1 | grep -i deprecat
```

### Best Practices

1. **Use version control** - Track configuration changes
2. **Test in staging** - Validate changes before production
3. **Monitor resources** - Watch CPU, memory, and disk usage
4. **Keep backups** - Backup important configurations
5. **Document customizations** - Record why custom configs were needed
6. **Regular updates** - Keep saidata-gen and dependencies current
7. **Network monitoring** - Monitor repository availability
8. **Error handling** - Implement proper error handling in scripts