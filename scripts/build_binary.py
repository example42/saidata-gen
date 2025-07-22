#!/usr/bin/env python3
"""
Build standalone binary using PyInstaller.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {cmd}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def check_pyinstaller():
    """Check if PyInstaller is installed."""
    result = run_command("python -m pip show pyinstaller", check=False)
    if result.returncode != 0:
        print("Installing PyInstaller...")
        run_command("python -m pip install pyinstaller")


def get_version():
    """Get version from pyproject.toml."""
    import re
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text()
    match = re.search(r'version = "([^"]+)"', content)
    if not match:
        raise ValueError("Version not found in pyproject.toml")
    return match.group(1)


def create_spec_file():
    """Create PyInstaller spec file."""
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['saidata_gen/cli/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('schemas/*.json', 'schemas'),
        ('saidata_gen/templates/*.yaml', 'saidata_gen/templates'),
        ('examples/configs/*.yaml', 'examples/configs'),
    ],
    hiddenimports=[
        'saidata_gen.core',
        'saidata_gen.fetcher',
        'saidata_gen.generator',
        'saidata_gen.validation',
        'saidata_gen.rag',
        'saidata_gen.ml',
        'saidata_gen.search',
        'pkg_resources.py2_warn',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='saidata-gen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
'''
    
    spec_path = Path("saidata-gen.spec")
    spec_path.write_text(spec_content)
    return spec_path


def build_binary(output_dir=None, onefile=True):
    """Build standalone binary."""
    version = get_version()
    system = platform.system().lower()
    arch = platform.machine().lower()
    
    if not output_dir:
        output_dir = Path("dist")
    else:
        output_dir = Path(output_dir)
    
    # Clean previous builds
    if output_dir.exists():
        shutil.rmtree(output_dir)
    
    build_dir = Path("build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    # Create spec file
    spec_file = create_spec_file()
    
    try:
        # Build with PyInstaller
        cmd_parts = ["python", "-m", "PyInstaller"]
        
        if onefile:
            cmd_parts.append("--onefile")
        
        cmd_parts.extend([
            "--clean",
            "--noconfirm",
            str(spec_file)
        ])
        
        cmd = " ".join(cmd_parts)
        run_command(cmd)
        
        # Rename binary with platform suffix
        if system == "windows":
            binary_name = "saidata-gen.exe"
            final_name = f"saidata-gen-{system}-{arch}.exe"
        else:
            binary_name = "saidata-gen"
            final_name = f"saidata-gen-{system}-{arch}"
        
        binary_path = output_dir / binary_name
        final_path = output_dir / final_name
        
        if binary_path.exists():
            binary_path.rename(final_path)
            print(f"Binary created: {final_path}")
            print(f"Size: {final_path.stat().st_size / 1024 / 1024:.1f} MB")
        else:
            raise FileNotFoundError(f"Binary not found: {binary_path}")
        
        return final_path
    
    finally:
        # Clean up spec file
        if spec_file.exists():
            spec_file.unlink()


def test_binary(binary_path):
    """Test the built binary."""
    print(f"Testing binary: {binary_path}")
    
    # Make executable on Unix systems
    if platform.system() != "Windows":
        os.chmod(binary_path, 0o755)
    
    test_commands = [
        f"{binary_path} --version",
        f"{binary_path} --help",
        f"{binary_path} config init --help",
    ]
    
    for cmd in test_commands:
        print(f"Testing: {cmd}")
        result = run_command(cmd, check=False)
        if result.returncode != 0:
            print(f"Test failed: {cmd}")
            print(f"Output: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False
    
    print("All binary tests passed!")
    return True


def main():
    """Main binary build function."""
    parser = argparse.ArgumentParser(description="Build standalone binary for saidata-gen")
    parser.add_argument("--output-dir", help="Output directory for binary")
    parser.add_argument("--onedir", action="store_true", help="Create one-directory bundle instead of one-file")
    parser.add_argument("--test", action="store_true", help="Test the built binary")
    
    args = parser.parse_args()
    
    # Change to project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)
    
    try:
        # Check PyInstaller
        check_pyinstaller()
        
        # Build binary
        binary_path = build_binary(
            output_dir=args.output_dir,
            onefile=not args.onedir
        )
        
        if args.test:
            test_binary(binary_path)
        
        print(f"Binary build completed successfully!")
        print(f"Binary location: {binary_path}")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()