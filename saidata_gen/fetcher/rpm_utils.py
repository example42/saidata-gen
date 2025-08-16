"""
Utility functions for RPM-based repository fetchers.

This module provides common functionality for fetchers that retrieve
data from RPM-based repositories (DNF, YUM, Zypper).
"""

import gzip
import io
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def fetch_primary_location(repomd_xml: str) -> str:
    """
    Parse the repomd.xml content to get the primary.xml location.
    
    Args:
        repomd_xml: Content of the repomd.xml file.
        
    Returns:
        Location of the primary.xml file.
        
    Raises:
        ValueError: If the primary.xml location is not found.
    """
    try:
        # Parse the XML to find the primary.xml location
        root = ET.fromstring(repomd_xml)
        
        # Find the primary data element
        ns = {"repo": "http://linux.duke.edu/metadata/repo"}
        for data in root.findall(".//repo:data", ns):
            if data.get("type") == "primary":
                # Get the location
                location = data.find(".//repo:location", ns)
                if location is not None:
                    return location.get("href")
        
        # If we get here, we didn't find the primary.xml location
        raise ValueError("Primary XML location not found in repomd.xml")
    
    except Exception as e:
        logger.error(f"Failed to parse repomd.xml: {e}")
        raise ValueError(f"Failed to parse repomd.xml: {e}")


def decompress_gzip_content(content: bytes) -> bytes:
    """
    Decompress gzipped content.
    
    Args:
        content: Gzipped content.
        
    Returns:
        Decompressed content.
        
    Raises:
        ValueError: If the content cannot be decompressed.
    """
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to decompress gzipped content: {e}")
        raise ValueError(f"Failed to decompress gzipped content: {e}")


def parse_primary_xml(primary_xml: str) -> Dict[str, Dict[str, any]]:
    """
    Parse the primary.xml content.
    
    Args:
        primary_xml: Content of the primary.xml file.
        
    Returns:
        Dictionary mapping package names to their metadata.
        
    Raises:
        ValueError: If the primary.xml file cannot be parsed.
    """
    result = {}
    
    try:
        # Parse the XML
        root = ET.fromstring(primary_xml)
        
        # Define namespaces
        ns = {
            "rpm": "http://linux.duke.edu/metadata/rpm",
            "common": "http://linux.duke.edu/metadata/common"
        }
        
        # Process each package
        for package in root.findall(".//common:package", ns):
            # Get basic package info
            name_elem = package.find(".//common:name", ns)
            if name_elem is None:
                continue
            
            name = name_elem.text
            
            # Get version info
            version_elem = package.find(".//common:version", ns)
            version = None
            if version_elem is not None:
                epoch = version_elem.get("epoch", "0")
                ver = version_elem.get("ver", "")
                rel = version_elem.get("rel", "")
                
                # Format version as epoch:version-release if epoch is not 0
                if epoch != "0":
                    version = f"{epoch}:{ver}-{rel}"
                else:
                    version = f"{ver}-{rel}"
            
            # Get summary and description
            summary_elem = package.find(".//common:summary", ns)
            summary = summary_elem.text if summary_elem is not None else None
            
            description_elem = package.find(".//common:description", ns)
            description = description_elem.text if description_elem is not None else None
            
            # Get URL
            url_elem = package.find(".//common:url", ns)
            url = url_elem.text if url_elem is not None else None
            
            # Get license
            format_elem = package.find(".//common:format", ns)
            license_elem = format_elem.find(".//rpm:license", ns) if format_elem is not None else None
            license_text = license_elem.text if license_elem is not None else None
            
            # Get source RPM
            source_rpm_elem = format_elem.find(".//rpm:sourcerpm", ns) if format_elem is not None else None
            source_rpm = source_rpm_elem.text if source_rpm_elem is not None else None
            
            # Get requires
            requires = []
            if format_elem is not None:
                for entry in format_elem.findall(".//rpm:requires/rpm:entry", ns):
                    req_name = entry.get("name")
                    if req_name and not req_name.startswith("rpmlib(") and not req_name.startswith("/"):
                        requires.append(req_name)
            
            # Get checksum
            checksum_elem = package.find(".//common:checksum", ns)
            checksum = checksum_elem.text if checksum_elem is not None else None
            checksum_type = checksum_elem.get("type") if checksum_elem is not None else None
            
            # Create package data
            pkg_data = {
                "name": name,
                "version": version,
                "summary": summary,
                "description": description,
                "url": url,
                "license": license_text,
                "source_rpm": source_rpm,
                "requires": requires,
                "checksum": checksum,
                "checksum_type": checksum_type
            }
            
            result[name] = pkg_data
    
    except Exception as e:
        logger.error(f"Failed to parse primary.xml: {e}")
        raise ValueError(f"Failed to parse primary.xml: {e}")
    
    return result


def parse_metalink_xml(metalink_xml: str) -> List[str]:
    """
    Parse the metalink XML content to get mirror URLs.
    
    Args:
        metalink_xml: Content of the metalink XML file.
        
    Returns:
        List of mirror URLs.
        
    Raises:
        ValueError: If no mirrors are found.
    """
    try:
        # Parse the XML to find mirror URLs
        root = ET.fromstring(metalink_xml)
        
        # Look for mirrors in the XML
        mirrors = []
        
        # Try both metalink v3 and v4 formats
        # Metalink v3
        for url in root.findall(".//url"):
            protocol = url.get("protocol", "")
            if protocol in ["http", "https"]:
                mirrors.append(url.text)
        
        # Metalink v4
        if not mirrors:
            for url in root.findall(".//{http://www.metalinker.org/}url"):
                protocol = url.get("protocol", "")
                if protocol in ["http", "https"]:
                    mirrors.append(url.text)
        
        # If no mirrors found, raise an error
        if not mirrors:
            raise ValueError("No mirrors found in metalink")
        
        return mirrors
    
    except Exception as e:
        logger.error(f"Failed to parse metalink XML: {e}")
        raise ValueError(f"Failed to parse metalink XML: {e}")