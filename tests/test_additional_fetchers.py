"""
Tests for additional Linux package manager fetchers.

This module contains tests for the additional Linux package manager fetchers
implemented in task 3.8.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from saidata_gen.core.interfaces import FetcherConfig
from saidata_gen.fetcher import (
    PacmanFetcher, PacmanRepository,
    ApkFetcher, ApkRepository,
    PortageFetcher, PortageRepository,
    XbpsFetcher, XbpsRepository,
    SlackpkgFetcher, SlackpkgRepository,
    OpkgFetcher, OpkgRepository,
    EmergeFetcher,
    GuixFetcher,
    NixFetcher,
    NixpkgsFetcher, NixpkgsRepository,
    SpackFetcher, SpackRepository,
    PkgFetcher, PkgRepository
)


class TestPacmanFetcher:
    """Tests for the PacmanFetcher class."""

    def test_init(self):
        """Test initialization of PacmanFetcher."""
        fetcher = PacmanFetcher()
        assert fetcher.get_repository_name() == "pacman"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.pacman.PacmanFetcher._fetch_repository_database')
    @patch('saidata_gen.fetcher.pacman.PacmanFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_repository_database):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_fetch_repository_database.return_value = {"test-package": {"VERSION": "1.0", "DESC": "Test package"}}
        
        fetcher = PacmanFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert len(mock_fetch_repository_database.call_args_list) > 0


class TestApkFetcher:
    """Tests for the ApkFetcher class."""

    def test_init(self):
        """Test initialization of ApkFetcher."""
        fetcher = ApkFetcher()
        assert fetcher.get_repository_name() == "apk"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.apk.ApkFetcher._fetch_apkindex')
    @patch('saidata_gen.fetcher.apk.ApkFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_apkindex):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_fetch_apkindex.return_value = {"test-package": {"V": "1.0", "T": "Test package"}}
        
        fetcher = ApkFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert len(mock_fetch_apkindex.call_args_list) > 0


class TestPortageFetcher:
    """Tests for the PortageFetcher class."""

    def test_init(self):
        """Test initialization of PortageFetcher."""
        fetcher = PortageFetcher()
        assert fetcher.get_repository_name() == "portage"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.portage.PortageFetcher._clone_or_pull_repository')
    @patch('saidata_gen.fetcher.portage.PortageFetcher._parse_portage_repository')
    @patch('saidata_gen.fetcher.portage.PortageFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_parse_portage_repository, mock_clone_or_pull_repository):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_clone_or_pull_repository.return_value = True
        mock_parse_portage_repository.return_value = ({"test-package": {"PV": "1.0", "DESCRIPTION": "Test package"}}, ["category"])
        
        fetcher = PortageFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert mock_clone_or_pull_repository.called is True
        assert mock_parse_portage_repository.called is True


class TestXbpsFetcher:
    """Tests for the XbpsFetcher class."""

    def test_init(self):
        """Test initialization of XbpsFetcher."""
        fetcher = XbpsFetcher()
        assert fetcher.get_repository_name() == "xbps"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.xbps.XbpsFetcher._fetch_repository_index')
    @patch('saidata_gen.fetcher.xbps.XbpsFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_repository_index):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_fetch_repository_index.return_value = {"test-package": {"version": "1.0", "short_desc": "Test package"}}
        
        fetcher = XbpsFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert len(mock_fetch_repository_index.call_args_list) > 0


class TestSlackpkgFetcher:
    """Tests for the SlackpkgFetcher class."""

    def test_init(self):
        """Test initialization of SlackpkgFetcher."""
        fetcher = SlackpkgFetcher()
        assert fetcher.get_repository_name() == "slackpkg"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.slackpkg.SlackpkgFetcher._fetch_packages_file')
    @patch('saidata_gen.fetcher.slackpkg.SlackpkgFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_packages_file):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_fetch_packages_file.return_value = {"test-package": {"version": "1.0", "description": "Test package"}}
        
        fetcher = SlackpkgFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert len(mock_fetch_packages_file.call_args_list) > 0


class TestOpkgFetcher:
    """Tests for the OpkgFetcher class."""

    def test_init(self):
        """Test initialization of OpkgFetcher."""
        fetcher = OpkgFetcher()
        assert fetcher.get_repository_name() == "opkg"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.opkg.OpkgFetcher._fetch_packages_file')
    @patch('saidata_gen.fetcher.opkg.OpkgFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_packages_file):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_fetch_packages_file.return_value = {"test-package": {"Version": "1.0", "Description": "Test package"}}
        
        fetcher = OpkgFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert len(mock_fetch_packages_file.call_args_list) > 0


class TestEmergeFetcher:
    """Tests for the EmergeFetcher class."""

    def test_init(self):
        """Test initialization of EmergeFetcher."""
        fetcher = EmergeFetcher()
        assert fetcher.get_repository_name() == "emerge"

    @patch('saidata_gen.fetcher.emerge.EmergeFetcher._is_emerge_available')
    @patch('saidata_gen.fetcher.emerge.EmergeFetcher._fetch_categories')
    @patch('saidata_gen.fetcher.emerge.EmergeFetcher._fetch_category_packages')
    @patch('saidata_gen.fetcher.emerge.EmergeFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_category_packages, mock_fetch_categories, mock_is_emerge_available):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_is_emerge_available.return_value = True
        mock_fetch_categories.return_value = ["category1", "category2"]
        mock_fetch_category_packages.return_value = {"test-package": {"version": "1.0", "description": "Test package"}}
        
        fetcher = EmergeFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert mock_is_emerge_available.called is True
        assert mock_fetch_categories.called is True
        assert mock_fetch_category_packages.called is True


class TestGuixFetcher:
    """Tests for the GuixFetcher class."""

    def test_init(self):
        """Test initialization of GuixFetcher."""
        fetcher = GuixFetcher()
        assert fetcher.get_repository_name() == "guix"

    @patch('saidata_gen.fetcher.guix.GuixFetcher._is_guix_available')
    @patch('saidata_gen.fetcher.guix.GuixFetcher._fetch_packages')
    @patch('saidata_gen.fetcher.guix.GuixFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_packages, mock_is_guix_available):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_is_guix_available.return_value = True
        mock_fetch_packages.return_value = {"test-package": {"version": "1.0", "description": "Test package"}}
        
        fetcher = GuixFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert mock_is_guix_available.called is True
        assert mock_fetch_packages.called is True


class TestNixFetcher:
    """Tests for the NixFetcher class."""

    def test_init(self):
        """Test initialization of NixFetcher."""
        fetcher = NixFetcher()
        assert fetcher.get_repository_name() == "nix"

    @patch('saidata_gen.fetcher.nix.NixFetcher._is_nix_available')
    @patch('saidata_gen.fetcher.nix.NixFetcher._fetch_packages')
    @patch('saidata_gen.fetcher.nix.NixFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_packages, mock_is_nix_available):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_is_nix_available.return_value = True
        mock_fetch_packages.return_value = {"test-package": {"version": "1.0", "description": "Test package"}}
        
        fetcher = NixFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert mock_is_nix_available.called is True
        assert mock_fetch_packages.called is True


class TestNixpkgsFetcher:
    """Tests for the NixpkgsFetcher class."""

    def test_init(self):
        """Test initialization of NixpkgsFetcher."""
        fetcher = NixpkgsFetcher()
        assert fetcher.get_repository_name() == "nixpkgs"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.nixpkgs.NixpkgsFetcher._clone_or_pull_repository')
    @patch('saidata_gen.fetcher.nixpkgs.NixpkgsFetcher._parse_nixpkgs_repository')
    @patch('saidata_gen.fetcher.nixpkgs.NixpkgsFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_parse_nixpkgs_repository, mock_clone_or_pull_repository):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_clone_or_pull_repository.return_value = True
        mock_parse_nixpkgs_repository.return_value = {"test-package": {"version": "1.0", "description": "Test package"}}
        
        fetcher = NixpkgsFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert mock_clone_or_pull_repository.called is True
        assert mock_parse_nixpkgs_repository.called is True


class TestSpackFetcher:
    """Tests for the SpackFetcher class."""

    def test_init(self):
        """Test initialization of SpackFetcher."""
        fetcher = SpackFetcher()
        assert fetcher.get_repository_name() == "spack"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.spack.SpackFetcher._clone_or_pull_repository')
    @patch('saidata_gen.fetcher.spack.SpackFetcher._parse_spack_repository')
    @patch('saidata_gen.fetcher.spack.SpackFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_parse_spack_repository, mock_clone_or_pull_repository):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_clone_or_pull_repository.return_value = True
        mock_parse_spack_repository.return_value = {"test-package": {"latest_version": "1.0", "description": "Test package"}}
        
        fetcher = SpackFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert mock_clone_or_pull_repository.called is True
        assert mock_parse_spack_repository.called is True


class TestPkgFetcher:
    """Tests for the PkgFetcher class."""

    def test_init(self):
        """Test initialization of PkgFetcher."""
        fetcher = PkgFetcher()
        assert fetcher.get_repository_name() == "pkg"
        assert len(fetcher.repositories) > 0

    @patch('saidata_gen.fetcher.pkg.PkgFetcher._fetch_packagesite')
    @patch('saidata_gen.fetcher.pkg.PkgFetcher._get_from_cache')
    def test_fetch_repository_data(self, mock_get_from_cache, mock_fetch_packagesite):
        """Test fetching repository data."""
        mock_get_from_cache.return_value = None
        mock_fetch_packagesite.return_value = {"test-package": {"version": "1.0", "comment": "Test package"}}
        
        fetcher = PkgFetcher()
        result = fetcher.fetch_repository_data()
        
        assert result.success is True
        assert len(mock_fetch_packagesite.call_args_list) > 0