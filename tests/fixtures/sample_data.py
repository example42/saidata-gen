"""
Sample data fixtures for testing.
"""

import json
from typing import Dict, Any

# Sample package data from different repositories
SAMPLE_APT_PACKAGE = {
    "Package": "nginx",
    "Version": "1.18.0-6ubuntu14.4",
    "Architecture": "amd64",
    "Maintainer": "Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>",
    "Installed-Size": "3584",
    "Depends": "nginx-core (<< 1.18.0-6ubuntu14.4.1~) | nginx-full (<< 1.18.0-6ubuntu14.4.1~) | nginx-light (<< 1.18.0-6ubuntu14.4.1~) | nginx-extras (<< 1.18.0-6ubuntu14.4.1~), nginx-core (>= 1.18.0-6ubuntu14.4) | nginx-full (>= 1.18.0-6ubuntu14.4) | nginx-light (>= 1.18.0-6ubuntu14.4) | nginx-extras (>= 1.18.0-6ubuntu14.4)",
    "Homepage": "http://nginx.org",
    "Priority": "optional",
    "Section": "httpd",
    "Filename": "pool/main/n/nginx/nginx_1.18.0-6ubuntu14.4_all.deb",
    "Size": "3588",
    "MD5sum": "f2ca1bb6c7e907d06dafe4687e579fce76b37e4e93b7605022da52e6ccc26fd2",
    "SHA1": "adc83b19e793491b1c6ea0fd8b46cd9f32e592fc",
    "SHA256": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
    "Description": "small, powerful, scalable web/proxy server\n Nginx (\"engine X\") is a high-performance web and reverse proxy server\n created by Igor Sysoev. It can be used both as a standalone web server\n and as a proxy to reduce the load on back-end HTTP or mail servers."
}

SAMPLE_BREW_PACKAGE = {
    "name": "nginx",
    "full_name": "nginx",
    "tap": "homebrew/core",
    "oldname": None,
    "aliases": [],
    "versioned_formulae": [],
    "desc": "HTTP(S) server and reverse proxy, and IMAP/POP3 proxy server",
    "license": "BSD-2-Clause",
    "homepage": "https://nginx.org/",
    "versions": {
        "stable": "1.25.3",
        "head": "HEAD",
        "bottle": True
    },
    "urls": {
        "stable": {
            "url": "https://nginx.org/download/nginx-1.25.3.tar.gz",
            "tag": None,
            "revision": None,
            "checksum": "64c5b975ca287939e828303fa857d22f142b251f17808dfe41733512d9cded86"
        }
    },
    "revision": 0,
    "version_scheme": 0,
    "bottle": {
        "stable": {
            "rebuild": 0,
            "root_url": "https://ghcr.io/v2/homebrew/core",
            "files": {
                "arm64_sonoma": {
                    "cellar": "/opt/homebrew/Cellar",
                    "url": "https://ghcr.io/v2/homebrew/core/nginx/blobs/sha256:abc123",
                    "sha256": "abc123"
                }
            }
        }
    },
    "pour_bottle_only_if": None,
    "keg_only": False,
    "keg_only_reason": None,
    "options": [],
    "build_dependencies": [],
    "dependencies": ["pcre2"],
    "test_dependencies": [],
    "recommended_dependencies": [],
    "optional_dependencies": [],
    "uses_from_macos": ["libxcrypt"],
    "uses_from_macos_bounds": [],
    "requirements": [],
    "conflicts_with": [],
    "conflicts_with_reasons": [],
    "link_overwrite": [],
    "caveats": None,
    "installed": [],
    "linked_keg": None,
    "pinned": False,
    "outdated": False,
    "deprecated": False,
    "deprecation_date": None,
    "deprecation_reason": None,
    "disabled": False,
    "disable_date": None,
    "disable_reason": None,
    "post_install_defined": False,
    "service": {
        "run": ["/opt/homebrew/bin/nginx", "-g", "daemon off;"],
        "keep_alive": True,
        "log_path": "/opt/homebrew/var/log/nginx/access.log",
        "error_log_path": "/opt/homebrew/var/log/nginx/error.log"
    },
    "tap_git_head": "abc123",
    "ruby_source_path": "Formula/nginx.rb",
    "ruby_source_checksum": {
        "sha256": "def456"
    }
}

SAMPLE_NPM_PACKAGE = {
    "name": "express",
    "version": "4.18.2",
    "description": "Fast, unopinionated, minimalist web framework",
    "main": "index.js",
    "directories": {
        "lib": "./lib",
        "test": "./test"
    },
    "scripts": {
        "test": "mocha --require test/support/env --reporter spec --bail --check-leaks test/ test/acceptance/",
        "test-ci": "nyc --reporter=lcovonly --reporter=text npm test",
        "test-cov": "nyc --reporter=html --reporter=text npm test",
        "test-tap": "mocha --require test/support/env --reporter tap --check-leaks test/ test/acceptance/"
    },
    "repository": {
        "type": "git",
        "url": "git+https://github.com/expressjs/express.git"
    },
    "keywords": [
        "express",
        "framework",
        "sinatra",
        "web",
        "http",
        "rest",
        "restful",
        "router",
        "app",
        "api"
    ],
    "author": "TJ Holowaychuk <tj@vision-media.ca>",
    "license": "MIT",
    "bugs": {
        "url": "https://github.com/expressjs/express/issues"
    },
    "homepage": "http://expressjs.com/",
    "dependencies": {
        "accepts": "~1.3.8",
        "array-flatten": "1.1.1",
        "body-parser": "1.20.1",
        "content-disposition": "0.5.4",
        "content-type": "~1.0.4",
        "cookie": "0.5.0",
        "cookie-signature": "1.0.6",
        "debug": "2.6.9",
        "depd": "2.0.0",
        "encodeurl": "~1.0.2",
        "escape-html": "~1.0.3",
        "etag": "~1.8.1",
        "finalhandler": "1.2.0",
        "fresh": "0.5.2",
        "http-errors": "2.0.0",
        "merge-descriptors": "1.0.1",
        "methods": "~1.1.2",
        "on-finished": "2.4.1",
        "parseurl": "~1.3.3",
        "path-to-regexp": "0.1.7",
        "proxy-addr": "~2.0.7",
        "qs": "6.11.0",
        "range-parser": "~1.2.1",
        "safe-buffer": "5.2.1",
        "send": "0.18.0",
        "serve-static": "1.15.0",
        "setprototypeof": "1.2.0",
        "statuses": "2.0.1",
        "type-is": "~1.6.18",
        "utils-merge": "1.0.1",
        "vary": "~1.1.2"
    },
    "devDependencies": {
        "after": "0.8.2",
        "connect-redis": "3.4.2",
        "cookie-parser": "1.4.6",
        "cookie-session": "2.0.0",
        "ejs": "3.1.8",
        "eslint": "8.24.0",
        "express-session": "1.17.3",
        "hbs": "4.2.0",
        "marked": "4.1.1",
        "method-override": "3.0.0",
        "mocha": "10.0.0",
        "morgan": "1.10.0",
        "multiparty": "4.2.3",
        "nyc": "15.1.0",
        "pbkdf2-password": "1.2.1",
        "should": "13.2.3",
        "supertest": "6.3.0",
        "vhost": "~3.0.2"
    },
    "engines": {
        "node": ">= 0.10.0"
    },
    "files": [
        "LICENSE",
        "History.md",
        "Readme.md",
        "index.js",
        "lib/"
    ],
    "dist": {
        "shasum": "5de93fcb8d3e1fbbadf7c0e9b4a1edda151d5a86",
        "tarball": "https://registry.npmjs.org/express/-/express-4.18.2.tgz",
        "fileCount": 16,
        "unpackedSize": 208736,
        "signatures": [
            {
                "keyid": "SHA256:jl3bwswu80PjjokCgh0o2w5c2U4LhQAE57gj9cz1kzA",
                "sig": "MEUCIQDHSuZiSBacaQjx..."
            }
        ]
    }
}

SAMPLE_PYPI_PACKAGE = {
    "info": {
        "author": "Armin Ronacher",
        "author_email": "armin.ronacher@active-4.com",
        "bugtrack_url": None,
        "classifiers": [
            "Development Status :: 5 - Production/Stable",
            "Environment :: Web Environment",
            "Framework :: Flask",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: BSD License",
            "Operating System :: OS Independent",
            "Programming Language :: Python",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.8",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
            "Topic :: Internet :: WWW/HTTP :: WSGI",
            "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
            "Topic :: Software Development :: Libraries :: Application Frameworks",
            "Topic :: Software Development :: Libraries :: Python Modules"
        ],
        "description": "A simple framework for building complex web applications.",
        "description_content_type": "text/x-rst",
        "download_url": "",
        "downloads": {
            "last_day": -1,
            "last_month": -1,
            "last_week": -1
        },
        "home_page": "https://palletsprojects.com/p/flask/",
        "keywords": "wsgi web http server framework",
        "license": "BSD-3-Clause",
        "maintainer": "Pallets",
        "maintainer_email": "contact@palletsprojects.com",
        "name": "Flask",
        "package_url": "https://pypi.org/project/Flask/",
        "platform": None,
        "project_url": "https://pypi.org/project/Flask/",
        "project_urls": {
            "Changelog": "https://flask.palletsprojects.com/changes/",
            "Chat": "https://discord.gg/pallets",
            "Documentation": "https://flask.palletsprojects.com/",
            "Funding": "https://palletsprojects.com/donate",
            "Issue Tracker": "https://github.com/pallets/flask/issues/",
            "Source Code": "https://github.com/pallets/flask/",
            "Twitter": "https://twitter.com/PalletsTeam"
        },
        "release_url": "https://pypi.org/project/Flask/2.3.3/",
        "requires_dist": [
            "Werkzeug >=2.3.7",
            "Jinja2 >=3.1.2",
            "itsdangerous >=2.1.2",
            "click >=8.1.3",
            "blinker >=1.6.2",
            "importlib-metadata >=3.6.0 ; python_version < \"3.10\"",
            "asgiref >=3.2 ; extra == 'async'",
            "python-dotenv ; extra == 'dotenv'"
        ],
        "requires_python": ">=3.8",
        "summary": "A simple framework for building complex web applications.",
        "version": "2.3.3",
        "yanked": False,
        "yanked_reason": None
    },
    "last_serial": 19403321,
    "releases": {
        "2.3.3": [
            {
                "comment_text": "",
                "digests": {
                    "blake2b_256": "af47c4c2cf3c95e1948e396b9b0a0e66d5e4a2f8c7e8b8e8b8e8b8e8b8e8b8e8",
                    "md5": "f2ca1bb6c7e907d06dafe4687e579fce",
                    "sha256": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"
                },
                "downloads": -1,
                "filename": "Flask-2.3.3-py3-none-any.whl",
                "has_sig": False,
                "md5_digest": "f2ca1bb6c7e907d06dafe4687e579fce",
                "packagetype": "bdist_wheel",
                "python_version": "py3",
                "requires_python": ">=3.8",
                "size": 96774,
                "upload_time": "2023-08-21T14:00:00",
                "upload_time_iso_8601": "2023-08-21T14:00:00.000000Z",
                "url": "https://files.pythonhosted.org/packages/af/47/c4c2cf3c95e1948e396b9b0a0e66d5e4a2f8c7e8b8e8b8e8b8e8b8e8b8e8/Flask-2.3.3-py3-none-any.whl",
                "yanked": False,
                "yanked_reason": None
            }
        ]
    },
    "urls": [
        {
            "comment_text": "",
            "digests": {
                "blake2b_256": "af47c4c2cf3c95e1948e396b9b0a0e66d5e4a2f8c7e8b8e8b8e8b8e8b8e8b8e8",
                "md5": "f2ca1bb6c7e907d06dafe4687e579fce",
                "sha256": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b"
            },
            "downloads": -1,
            "filename": "Flask-2.3.3-py3-none-any.whl",
            "has_sig": False,
            "md5_digest": "f2ca1bb6c7e907d06dafe4687e579fce",
            "packagetype": "bdist_wheel",
            "python_version": "py3",
            "requires_python": ">=3.8",
            "size": 96774,
            "upload_time": "2023-08-21T14:00:00",
            "upload_time_iso_8601": "2023-08-21T14:00:00.000000Z",
            "url": "https://files.pythonhosted.org/packages/af/47/c4c2cf3c95e1948e396b9b0a0e66d5e4a2f8c7e8b8e8b8e8b8e8b8e8b8e8/Flask-2.3.3-py3-none-any.whl",
            "yanked": False,
            "yanked_reason": None
        }
    ],
    "vulnerabilities": []
}

# Sample saidata metadata
SAMPLE_SAIDATA_METADATA = {
    "version": "0.1",
    "description": "HTTP(S) server and reverse proxy server",
    "language": "c",
    "license": "BSD-2-Clause",
    "platforms": ["linux", "macos", "windows"],
    "packages": {
        "apt": {
            "name": "nginx",
            "version": "1.18.0-6ubuntu14.4"
        },
        "brew": {
            "name": "nginx",
            "version": "1.25.3"
        },
        "winget": {
            "name": "nginx.nginx",
            "version": "1.25.3"
        }
    },
    "services": {
        "default": {
            "name": "nginx",
            "enabled": True,
            "config_files": ["/etc/nginx/nginx.conf"]
        }
    },
    "urls": {
        "website": "https://nginx.org/",
        "documentation": "https://nginx.org/en/docs/",
        "source": "https://github.com/nginx/nginx",
        "issues": "https://trac.nginx.org/nginx/"
    },
    "category": {
        "default": "Web",
        "sub": "Server",
        "tags": ["http", "proxy", "server", "web"]
    },
    "ports": {
        "http": {
            "port": 80,
            "protocol": "tcp",
            "description": "HTTP port"
        },
        "https": {
            "port": 443,
            "protocol": "tcp",
            "description": "HTTPS port"
        }
    }
}

# Mock API responses
MOCK_APT_PACKAGES_GZ = """Package: nginx
Version: 1.18.0-6ubuntu14.4
Architecture: amd64
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Installed-Size: 3584
Depends: nginx-core (<< 1.18.0-6ubuntu14.4.1~) | nginx-full (<< 1.18.0-6ubuntu14.4.1~)
Homepage: http://nginx.org
Priority: optional
Section: httpd
Filename: pool/main/n/nginx/nginx_1.18.0-6ubuntu14.4_all.deb
Size: 3588
MD5sum: f2ca1bb6c7e907d06dafe4687e579fce76b37e4e93b7605022da52e6ccc26fd2
SHA1: adc83b19e793491b1c6ea0fd8b46cd9f32e592fc
SHA256: 01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b
Description: small, powerful, scalable web/proxy server
 Nginx ("engine X") is a high-performance web and reverse proxy server
 created by Igor Sysoev. It can be used both as a standalone web server
 and as a proxy to reduce the load on back-end HTTP or mail servers.

Package: apache2
Version: 2.4.41-4ubuntu3.15
Architecture: amd64
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Installed-Size: 544
Depends: apache2-bin (= 2.4.41-4ubuntu3.15), apache2-data (= 2.4.41-4ubuntu3.15)
Homepage: https://httpd.apache.org/
Priority: optional
Section: httpd
Filename: pool/main/a/apache2/apache2_2.4.41-4ubuntu3.15_amd64.deb
Size: 95420
Description: Apache HTTP Server
 The Apache HTTP Server Project's goal is to build a secure, efficient and
 extensible HTTP server as standards-compliant open source software.
"""

MOCK_DNF_REPOMD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo" xmlns:rpm="http://linux.duke.edu/metadata/rpm">
  <revision>1640995200</revision>
  <data type="primary">
    <checksum type="sha256">abc123def456</checksum>
    <open-checksum type="sha256">def456abc123</open-checksum>
    <location href="repodata/abc123def456-primary.xml.gz"/>
    <timestamp>1640995200</timestamp>
    <size>1234567</size>
    <open-size>5678901</open-size>
  </data>
</repomd>
"""

MOCK_DNF_PRIMARY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="2">
  <package type="rpm">
    <name>nginx</name>
    <arch>x86_64</arch>
    <version epoch="1" ver="1.20.1" rel="14.el9"/>
    <checksum type="sha256" pkgid="YES">abc123def456</checksum>
    <summary>A high performance web server and reverse proxy server</summary>
    <description>Nginx is a web server and a reverse proxy server for HTTP, SMTP, POP3 and IMAP protocols, with a strong focus on high concurrency, performance and low memory usage.</description>
    <packager>Red Hat, Inc. &lt;http://bugzilla.redhat.com/bugzilla&gt;</packager>
    <url>http://nginx.org/</url>
    <time file="1640995200" build="1640995100"/>
    <size package="1234567" installed="5678901" archive="2345678"/>
    <location href="Packages/n/nginx-1.20.1-14.el9.x86_64.rpm"/>
    <format>
      <rpm:license>BSD</rpm:license>
      <rpm:vendor>Red Hat, Inc.</rpm:vendor>
      <rpm:group>System Environment/Daemons</rpm:group>
      <rpm:buildhost>x86-64-01.build.eng.bos.redhat.com</rpm:buildhost>
      <rpm:sourcerpm>nginx-1.20.1-14.el9.src.rpm</rpm:sourcerpm>
      <rpm:header-range start="4504" end="7890"/>
      <rpm:provides>
        <rpm:entry name="nginx" flags="EQ" epoch="1" ver="1.20.1" rel="14.el9"/>
        <rpm:entry name="webserver"/>
      </rpm:provides>
      <rpm:requires>
        <rpm:entry name="/bin/sh"/>
        <rpm:entry name="systemd"/>
      </rpm:requires>
    </format>
  </package>
</metadata>
"""

# Expected outputs for testing
EXPECTED_NGINX_METADATA = {
    "version": "0.1",
    "description": "HTTP(S) server and reverse proxy server",
    "language": "c",
    "license": "BSD-2-Clause",
    "platforms": ["linux", "macos", "windows"],
    "packages": {
        "apt": {"name": "nginx"},
        "brew": {"name": "nginx"},
        "dnf": {"name": "nginx"}
    },
    "urls": {
        "website": "https://nginx.org/",
        "documentation": "https://nginx.org/en/docs/"
    },
    "category": {
        "default": "Web",
        "sub": "Server",
        "tags": ["http", "proxy", "server"]
    }
}

def get_sample_package_data(provider: str, package_name: str = "nginx") -> Dict[str, Any]:
    """Get sample package data for a specific provider."""
    samples = {
        "apt": SAMPLE_APT_PACKAGE,
        "brew": SAMPLE_BREW_PACKAGE,
        "npm": SAMPLE_NPM_PACKAGE,
        "pypi": SAMPLE_PYPI_PACKAGE
    }
    return samples.get(provider, {})

def get_mock_api_response(provider: str, endpoint: str = "") -> str:
    """Get mock API response for a specific provider and endpoint."""
    responses = {
        "apt_packages": MOCK_APT_PACKAGES_GZ,
        "dnf_repomd": MOCK_DNF_REPOMD_XML,
        "dnf_primary": MOCK_DNF_PRIMARY_XML
    }
    return responses.get(f"{provider}_{endpoint}", "")