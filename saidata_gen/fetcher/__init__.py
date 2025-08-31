"""
Repository fetcher module for saidata-gen.

This module provides functionality to fetch package metadata from various
package repositories.
"""

from saidata_gen.fetcher.base import (
    GitRepositoryFetcher, HttpRepositoryFetcher, RepositoryFetcher
)
from saidata_gen.fetcher.factory import FetcherFactory, fetcher_factory
from saidata_gen.fetcher.error_handler import FetcherErrorHandler, ErrorContext, RetryResult
from saidata_gen.fetcher.apt import APTFetcher, APTDistribution
from saidata_gen.fetcher.dnf import DNFFetcher, DNFDistribution
from saidata_gen.fetcher.yum import YumFetcher, YumDistribution
from saidata_gen.fetcher.zypper import ZypperFetcher, ZypperDistribution
from saidata_gen.fetcher.brew import BrewFetcher, BrewRepository
from saidata_gen.fetcher.winget import WingetFetcher, WingetRepository
from saidata_gen.fetcher.scoop import ScoopFetcher, ScoopBucket
from saidata_gen.fetcher.choco import ChocoFetcher, ChocoRepository
from saidata_gen.fetcher.nuget import NuGetFetcher, NuGetFeed
from saidata_gen.fetcher.docker import DockerFetcher, DockerRegistry
from saidata_gen.fetcher.helm import HelmFetcher, HelmRepository
from saidata_gen.fetcher.snap import SnapFetcher, SnapStore
from saidata_gen.fetcher.flatpak import FlatpakFetcher, FlatpakRepository
from saidata_gen.fetcher.pypi import PyPIFetcher, PyPIRepository
from saidata_gen.fetcher.npm import NPMFetcher, NPMRegistry
from saidata_gen.fetcher.cargo import CargoFetcher, CargoRegistry
# Import additional Linux package manager fetchers
from saidata_gen.fetcher.pacman import PacmanFetcher, PacmanRepository
from saidata_gen.fetcher.apk import ApkFetcher, ApkRepository
from saidata_gen.fetcher.portage import PortageFetcher, PortageRepository
from saidata_gen.fetcher.xbps import XbpsFetcher, XbpsRepository
from saidata_gen.fetcher.slackpkg import SlackpkgFetcher, SlackpkgRepository
from saidata_gen.fetcher.opkg import OpkgFetcher, OpkgRepository
from saidata_gen.fetcher.emerge import EmergeFetcher
from saidata_gen.fetcher.guix import GuixFetcher
from saidata_gen.fetcher.nix import NixFetcher
from saidata_gen.fetcher.nixpkgs import NixpkgsFetcher, NixpkgsRepository
from saidata_gen.fetcher.spack import SpackFetcher, SpackRepository
from saidata_gen.fetcher.pkg import PkgFetcher, PkgRepository

# Register fetchers
fetcher_factory.register_fetcher("apt", APTFetcher)
fetcher_factory.register_fetcher("dnf", DNFFetcher)
fetcher_factory.register_fetcher("yum", YumFetcher)
fetcher_factory.register_fetcher("zypper", ZypperFetcher)
fetcher_factory.register_fetcher("brew", BrewFetcher)
fetcher_factory.register_fetcher("winget", WingetFetcher)
fetcher_factory.register_fetcher("scoop", ScoopFetcher)
fetcher_factory.register_fetcher("choco", ChocoFetcher)
fetcher_factory.register_fetcher("nuget", NuGetFetcher)
fetcher_factory.register_fetcher("docker", DockerFetcher)
fetcher_factory.register_fetcher("helm", HelmFetcher)
fetcher_factory.register_fetcher("snap", SnapFetcher)
fetcher_factory.register_fetcher("flatpak", FlatpakFetcher)
fetcher_factory.register_fetcher("pypi", PyPIFetcher)
fetcher_factory.register_fetcher("npm", NPMFetcher)
fetcher_factory.register_fetcher("cargo", CargoFetcher)
# Register additional Linux package manager fetchers
fetcher_factory.register_fetcher("pacman", PacmanFetcher)
fetcher_factory.register_fetcher("apk", ApkFetcher)
fetcher_factory.register_fetcher("portage", PortageFetcher)
fetcher_factory.register_fetcher("xbps", XbpsFetcher)
fetcher_factory.register_fetcher("slackpkg", SlackpkgFetcher)
fetcher_factory.register_fetcher("opkg", OpkgFetcher)
fetcher_factory.register_fetcher("emerge", EmergeFetcher)
fetcher_factory.register_fetcher("guix", GuixFetcher)
fetcher_factory.register_fetcher("nix", NixFetcher)
fetcher_factory.register_fetcher("nixpkgs", NixpkgsFetcher)
fetcher_factory.register_fetcher("spack", SpackFetcher)
fetcher_factory.register_fetcher("pkg", PkgFetcher)

__all__ = [
    "RepositoryFetcher",
    "HttpRepositoryFetcher",
    "GitRepositoryFetcher",
    "FetcherFactory",
    "fetcher_factory",
    "FetcherErrorHandler",
    "ErrorContext",
    "RetryResult",
    "APTFetcher",
    "APTDistribution",
    "DNFFetcher",
    "DNFDistribution",
    "YumFetcher",
    "YumDistribution",
    "ZypperFetcher",
    "ZypperDistribution",
    "BrewFetcher",
    "BrewRepository",
    "WingetFetcher",
    "WingetRepository",
    "ScoopFetcher",
    "ScoopBucket",
    "ChocoFetcher",
    "ChocoRepository",
    "NuGetFetcher",
    "NuGetFeed",
    "DockerFetcher",
    "DockerRegistry",
    "HelmFetcher",
    "HelmRepository",
    "SnapFetcher",
    "SnapStore",
    "FlatpakFetcher",
    "FlatpakRepository",
    "PyPIFetcher",
    "PyPIRepository",
    "NPMFetcher",
    "NPMRegistry",
    "CargoFetcher",
    "CargoRegistry",
    # Additional Linux package manager fetchers
    "PacmanFetcher",
    "PacmanRepository",
    "ApkFetcher",
    "ApkRepository",
    "PortageFetcher",
    "PortageRepository",
    "XbpsFetcher",
    "XbpsRepository",
    "SlackpkgFetcher",
    "SlackpkgRepository",
    "OpkgFetcher",
    "OpkgRepository",
    "EmergeFetcher",
    "GuixFetcher",
    "NixFetcher",
    "NixpkgsFetcher",
    "NixpkgsRepository",
    "SpackFetcher",
    "SpackRepository",
    "PkgFetcher",
    "PkgRepository"
]