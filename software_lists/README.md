# Software Lists for Saidata Generation

This directory contains comprehensive lists of software names organized by category and use case. Each file contains hundreds of software packages that can be used to generate saidata metadata.

## File Structure

### Core Development Categories
- **`web_development.txt`** - Frontend/backend frameworks, build tools, testing tools, web servers
- **`programming_languages.txt`** - Language runtimes, package managers, development tools
- **`devops_infrastructure.txt`** - Containers, orchestration, CI/CD, monitoring, IaC tools
- **`databases.txt`** - SQL/NoSQL databases, tools, clients, migration utilities
- **`mobile_development.txt`** - iOS/Android native, cross-platform frameworks, testing

### System and Security
- **`system_administration.txt`** - System monitoring, process management, file tools, networking
- **`security_tools.txt`** - Penetration testing, vulnerability scanners, forensics, cryptography

### Creative and Productivity
- **`multimedia_graphics.txt`** - Image/video editing, 3D modeling, CAD, game development
- **`productivity_office.txt`** - Office suites, note-taking, project management, communication
- **`gaming_entertainment.txt`** - Game engines, emulators, streaming, VR/AR development

### Data and Analytics
- **`data_science_ml.txt`** - Python data stack, ML frameworks, visualization, big data tools

## Usage with saidata-gen

### Generate for entire categories:
```bash
# Generate saidata for all web development tools
saidata-gen generate --batch --input-file software_lists/web_development.txt

# Generate for multiple categories
saidata-gen generate --batch --input-file software_lists/devops_infrastructure.txt
saidata-gen generate --batch --input-file software_lists/databases.txt
```

### Generate for specific sections:
```bash
# Extract specific sections and generate
grep -A 20 "## Frontend Frameworks" software_lists/web_development.txt | saidata-gen generate --batch --stdin

# Generate for Python-specific tools
grep -E "(python|pip|conda|jupyter)" software_lists/programming_languages.txt | saidata-gen generate --batch --stdin
```

### Parallel processing:
```bash
# Process multiple categories in parallel
parallel -j 4 saidata-gen generate --batch --input-file {} ::: software_lists/*.txt
```

## File Format

Each file follows this structure:
- Comments start with `#` and provide section organization
- Software names are listed one per line
- Sections are organized by `##` headers for easy parsing
- Related tools are grouped together logically

## Statistics

Total estimated packages across all categories: **~3,000+ software packages**

### Breakdown by category:
- Web Development: ~300 packages
- DevOps/Infrastructure: ~400 packages  
- Programming Languages: ~250 packages
- Databases: ~200 packages
- System Administration: ~350 packages
- Security Tools: ~300 packages
- Multimedia/Graphics: ~250 packages
- Productivity/Office: ~200 packages
- Mobile Development: ~300 packages
- Gaming/Entertainment: ~250 packages
- Data Science/ML: ~200 packages

## Customization

You can easily:
1. Add new software names to existing categories
2. Create new category files following the same format
3. Remove or comment out packages you don't need
4. Create filtered subsets for specific use cases

## Provider Coverage

These lists include packages available across multiple package managers:
- **apt** (Debian/Ubuntu)
- **dnf/yum** (RHEL/Fedora)
- **brew** (macOS/Linux)
- **winget** (Windows)
- **pkg** (FreeBSD)
- **pacman** (Arch Linux)
- **npm** (Node.js packages)
- **pip** (Python packages)
- **gem** (Ruby packages)
- **cargo** (Rust packages)

## Quality Considerations

When generating saidata for these packages:
1. Some packages may not be available in all repositories
2. Package names may vary between providers (e.g., `nodejs` vs `node`)
3. Consider using provider-specific overrides for better accuracy
4. Validate generated metadata for critical packages
5. Use batch processing with error handling for large lists

## Contributing

To add new software categories or packages:
1. Follow the existing file format
2. Group related software logically
3. Use descriptive section headers
4. Include both popular and niche tools in each category
5. Consider cross-platform availability when possible