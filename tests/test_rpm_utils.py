"""
Unit tests for the RPM utilities module.
"""

import gzip
import io
import unittest
from unittest.mock import MagicMock, patch

from saidata_gen.fetcher.rpm_utils import (
    fetch_primary_location, decompress_gzip_content, parse_primary_xml, parse_metalink_xml
)


class TestRPMUtils(unittest.TestCase):
    """
    Test cases for the RPM utilities module.
    """
    
    def test_fetch_primary_location(self):
        """Test fetching the primary.xml location from repomd.xml."""
        # Sample repomd.xml content
        repomd_xml = """<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo">
  <data type="primary">
    <checksum type="sha256">abcdef1234567890</checksum>
    <location href="repodata/primary.xml.gz"/>
  </data>
  <data type="filelists">
    <checksum type="sha256">0987654321fedcba</checksum>
    <location href="repodata/filelists.xml.gz"/>
  </data>
</repomd>
"""
        
        # Get the primary.xml location
        location = fetch_primary_location(repomd_xml)
        
        # Check that the location is correct
        self.assertEqual(location, "repodata/primary.xml.gz")
    
    def test_fetch_primary_location_not_found(self):
        """Test fetching the primary.xml location when it's not found."""
        # Sample repomd.xml content without primary data
        repomd_xml = """<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo">
  <data type="filelists">
    <checksum type="sha256">0987654321fedcba</checksum>
    <location href="repodata/filelists.xml.gz"/>
  </data>
</repomd>
"""
        
        # Check that a ValueError is raised
        with self.assertRaises(ValueError):
            fetch_primary_location(repomd_xml)
    
    def test_decompress_gzip_content(self):
        """Test decompressing gzipped content."""
        # Create some gzipped content
        original_content = b"This is a test"
        gzipped_content = io.BytesIO()
        with gzip.GzipFile(fileobj=gzipped_content, mode="wb") as f:
            f.write(original_content)
        
        # Decompress the content
        decompressed = decompress_gzip_content(gzipped_content.getvalue())
        
        # Check that the decompressed content matches the original
        self.assertEqual(decompressed, original_content)
    
    def test_parse_primary_xml(self):
        """Test parsing primary.xml content."""
        # Sample primary.xml content
        primary_xml = """<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="2">
  <package type="rpm">
    <name>test-package</name>
    <arch>x86_64</arch>
    <version epoch="0" ver="1.0.0" rel="1"/>
    <checksum type="sha256" pkgid="YES">abcdef1234567890</checksum>
    <summary>Test package summary</summary>
    <description>Test package description</description>
    <url>https://example.com/test-package</url>
    <format>
      <rpm:license>MIT</rpm:license>
      <rpm:sourcerpm>test-package-1.0.0-1.src.rpm</rpm:sourcerpm>
      <rpm:requires>
        <rpm:entry name="lib1"/>
        <rpm:entry name="lib2"/>
        <rpm:entry name="rpmlib(CompressedFileNames)" flags="LE" epoch="0" ver="3.0.4" rel="1"/>
      </rpm:requires>
    </format>
  </package>
  <package type="rpm">
    <name>another-package</name>
    <arch>x86_64</arch>
    <version epoch="1" ver="2.0.0" rel="1"/>
    <checksum type="sha256" pkgid="YES">0987654321fedcba</checksum>
    <summary>Another test package</summary>
    <description>Another package with test in the description</description>
    <url>https://example.com/another-package</url>
    <format>
      <rpm:license>GPL-2.0</rpm:license>
      <rpm:sourcerpm>another-package-2.0.0-1.src.rpm</rpm:sourcerpm>
      <rpm:requires>
        <rpm:entry name="lib3"/>
        <rpm:entry name="/bin/sh"/>
      </rpm:requires>
    </format>
  </package>
</metadata>
"""
        
        # Parse the primary.xml content
        result = parse_primary_xml(primary_xml)
        
        # Check that the packages are parsed correctly
        self.assertEqual(len(result), 2)
        
        # Check first package
        self.assertEqual(result["test-package"]["name"], "test-package")
        self.assertEqual(result["test-package"]["version"], "1.0.0-1")
        self.assertEqual(result["test-package"]["summary"], "Test package summary")
        self.assertEqual(result["test-package"]["description"], "Test package description")
        self.assertEqual(result["test-package"]["url"], "https://example.com/test-package")
        self.assertEqual(result["test-package"]["license"], "MIT")
        self.assertEqual(result["test-package"]["source_rpm"], "test-package-1.0.0-1.src.rpm")
        self.assertEqual(result["test-package"]["checksum"], "abcdef1234567890")
        self.assertEqual(result["test-package"]["checksum_type"], "sha256")
        
        # Check dependencies
        self.assertEqual(len(result["test-package"]["requires"]), 2)
        self.assertEqual(result["test-package"]["requires"][0], "lib1")
        self.assertEqual(result["test-package"]["requires"][1], "lib2")
        
        # Check second package
        self.assertEqual(result["another-package"]["name"], "another-package")
        self.assertEqual(result["another-package"]["version"], "1:2.0.0-1")  # Note the epoch
        self.assertEqual(result["another-package"]["summary"], "Another test package")
        self.assertEqual(result["another-package"]["description"], "Another package with test in the description")
        
        # Check dependencies (should only include lib3, not /bin/sh)
        self.assertEqual(len(result["another-package"]["requires"]), 1)
        self.assertEqual(result["another-package"]["requires"][0], "lib3")
    
    def test_parse_metalink_xml(self):
        """Test parsing metalink XML content."""
        # Sample metalink XML content (v3)
        metalink_xml = """<?xml version="1.0" encoding="UTF-8"?>
<metalink version="3.0">
  <files>
    <file name="repomd.xml">
      <resources>
        <url protocol="https" type="https">https://mirror1.example.com/repo/repodata/repomd.xml</url>
        <url protocol="http" type="http">http://mirror2.example.com/repo/repodata/repomd.xml</url>
        <url protocol="ftp" type="ftp">ftp://mirror3.example.com/repo/repodata/repomd.xml</url>
      </resources>
    </file>
  </files>
</metalink>
"""
        
        # Parse the metalink XML content
        mirrors = parse_metalink_xml(metalink_xml)
        
        # Check that the mirrors are parsed correctly
        self.assertEqual(len(mirrors), 2)
        self.assertEqual(mirrors[0], "https://mirror1.example.com/repo/repodata/repomd.xml")
        self.assertEqual(mirrors[1], "http://mirror2.example.com/repo/repodata/repomd.xml")
    
    def test_parse_metalink_xml_v4(self):
        """Test parsing metalink XML v4 content."""
        # Sample metalink XML content (v4)
        metalink_xml = """<?xml version="1.0" encoding="UTF-8"?>
<metalink xmlns="http://www.metalinker.org/">
  <files>
    <file name="repomd.xml">
      <resources>
        <url protocol="https" type="https">https://mirror1.example.com/repo/repodata/repomd.xml</url>
        <url protocol="http" type="http">http://mirror2.example.com/repo/repodata/repomd.xml</url>
        <url protocol="ftp" type="ftp">ftp://mirror3.example.com/repo/repodata/repomd.xml</url>
      </resources>
    </file>
  </files>
</metalink>
"""
        
        # Parse the metalink XML content
        mirrors = parse_metalink_xml(metalink_xml)
        
        # Check that the mirrors are parsed correctly
        self.assertEqual(len(mirrors), 2)
        self.assertEqual(mirrors[0], "https://mirror1.example.com/repo/repodata/repomd.xml")
        self.assertEqual(mirrors[1], "http://mirror2.example.com/repo/repodata/repomd.xml")
    
    def test_parse_metalink_xml_no_mirrors(self):
        """Test parsing metalink XML content with no mirrors."""
        # Sample metalink XML content with no mirrors
        metalink_xml = """<?xml version="1.0" encoding="UTF-8"?>
<metalink version="3.0">
  <files>
    <file name="repomd.xml">
      <resources>
      </resources>
    </file>
  </files>
</metalink>
"""
        
        # Check that a ValueError is raised
        with self.assertRaises(ValueError):
            parse_metalink_xml(metalink_xml)


if __name__ == "__main__":
    unittest.main()