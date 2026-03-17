#!/usr/bin/env python3
"""
Cross-Platform Setup Launcher for QGen RAG System

This script automatically detects the platform and launches the appropriate
setup method for the QGen RAG interactive setup system.
"""

import os
import sys
import platform
import subprocess
import tempfile
import urllib.request
import zipfile
import json
from pathlib import Path

def detect_platform():
    """Detect the current platform and return platform info."""
    system = platform.system()
    machine = platform.machine()
    version = platform.version()
    
    platform_info = {
        "system": system,
        "machine": machine,
        "version": version,
        "python_version": platform.python_version(),
        "is_64bit": sys.maxsize > 2**32
    }
    
    # Platform-specific details
    if system == "Windows":
        platform_info.update({
            "is_windows": True,
            "package_manager": "chocolatey" if check_chocolatey() else "winget",
            "shell": "powershell",
            "path_separator": "\\",
            "exec_extension": ".exe"
        })
    elif system == "Darwin":  # macOS
        platform_info.update({
            "is_macos": True,
            "is_apple_silicon": machine in ("arm64", "aarch64"),
            "package_manager": "homebrew",
            "shell": "zsh",
            "path_separator": "/",
            "exec_extension": ""
        })
    elif system == "Linux":
        platform_info.update({
            "is_linux": True,
            "package_manager": detect_linux_package_manager(),
            "shell": "bash",
            "path_separator": "/",
            "exec_extension": ""
        })
    else:
        platform_info.update({
            "is_unknown": True,
            "package_manager": "unknown",
            "shell": "sh",
            "path_separator": "/",
            "exec_extension": ""
        })
    
    return platform_info

def check_chocolatey():
    """Check if Chocolatey is installed on Windows."""
    try:
        result = subprocess.run(["choco", "--version"], capture_output=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return False

def detect_linux_package_manager():
    """Detect the Linux package manager."""
    package_managers = {
        "apt": ["apt-get", "apt"],
        "yum": ["yum", "dnf"],
        "pacman": ["pacman"],
        "zypper": ["zypper"],
        "emerge": ["emerge"],
        "xbps": ["xbps-install"]
    }
    
    for pm_name, pm_commands in package_managers.items():
        for cmd in pm_commands:
            try:
                subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                return pm_name
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
    
    return "unknown"

def check_python_requirements():
    """Check if Python requirements are met."""
    try:
        import fastapi
        import uvicorn
        import jinja2
        import aiofiles
        import psutil
        return True
    except ImportError:
        return False

def install_python_requirements():
    """Install Python requirements."""
    print("📦 Installing Python requirements...")
    
    requirements = [
        "fastapi>=0.104.1",
        "uvicorn>=0.24.0",
        "jinja2>=3.1.2",
        "aiofiles>=23.2.1",
        "psutil>=5.9.6"
    ]
    
    platform_info = detect_platform()
    
    # Platform-specific installation
    if platform_info["system"] == "Windows":
        # On Windows, use pip
        for req in requirements:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", req], 
                             check=True, capture_output=True)
                print(f"✅ Installed {req}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {req}: {e}")
                return False
    else:
        # On Unix-like systems, use pip
        for req in requirements:
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", req], 
                             check=True, capture_output=True)
                print(f"✅ Installed {req}")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install {req}: {e}")
                return False
    
    print("✅ Python requirements installed successfully")
    return True

def create_virtual_environment():
    """Create a virtual environment if it doesn't exist."""
    platform_info = detect_platform()
    
    # Check if we're already in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print("✅ Already in virtual environment")
        return True
    
    venv_dir = Path(__file__).parent / "venv"
    
    if not venv_dir.exists():
        print("🔧 Creating virtual environment...")
        
        try:
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], 
                         check=True, capture_output=True)
            print("✅ Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False
    
    # Activate virtual environment
    if platform_info["system"] == "Windows":
        activate_script = venv_dir / "Scripts" / "activate.bat"
        python_executable = venv_dir / "Scripts" / "python.exe"
    else:
        activate_script = venv_dir / "bin" / "activate"
        python_executable = venv_dir / "bin" / "python"
    
    if python_executable.exists():
        print(f"✅ Using virtual environment Python: {python_executable}")
        return str(python_executable)
    else:
        print("❌ Virtual environment Python not found")
        return sys.executable

def setup_windows():
    """Setup for Windows platform."""
    print("🪟 Detected Windows platform")
    
    # Check for admin privileges
    try:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        if not is_admin:
            print("⚠️  Warning: Running without administrator privileges")
            print("   Some features may require admin access")
    except:
        pass
    
    # Check for WSL2
    try:
        result = subprocess.run(["wsl", "--list"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ WSL2 is available")
            print("💡 Consider using WSL2 for better compatibility")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  WSL2 not available - Docker Desktop may be required")
    
    return True

def setup_macos():
    """Setup for macOS platform."""
    platform_info = detect_platform()
    
    print("🍎 Detected macOS platform")
    
    if platform_info.get("is_apple_silicon"):
        print("🚀 Apple Silicon Mac detected")
        print("💡 Using optimized setup for Apple Silicon")
    else:
        print("🖥️  Intel Mac detected")
    
    # Check for Homebrew
    try:
        subprocess.run(["brew", "--version"], capture_output=True, timeout=5)
        print("✅ Homebrew is available")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        print("📦 Installing Homebrew...")
        try:
            install_cmd = '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
            subprocess.run(install_cmd, shell=True, check=True, timeout=300)
            print("✅ Homebrew installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install Homebrew: {e}")
            print("Please install Homebrew manually: https://brew.sh")
    
    return True

def setup_linux():
    """Setup for Linux platform."""
    platform_info = detect_platform()
    package_manager = platform_info["package_manager"]
    
    print("🐧 Detected Linux platform")
    print(f"📦 Package manager: {package_manager}")
    
    # Check for Docker
    try:
        subprocess.run(["docker", "--version"], capture_output=True, timeout=5)
        print("✅ Docker is available")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        print("📦 Docker not found - will be installed during setup")
    
    # Check for sudo access
    try:
        subprocess.run(["sudo", "--version"], capture_output=True, timeout=5)
        print("✅ Sudo access available")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        print("⚠️  Sudo not available - some features may be limited")
    
    return True

def launch_setup():
    """Launch the interactive setup."""
    platform_info = detect_platform()
    
    print(f"\n🚀 QGen RAG Interactive Setup Launcher")
    print("=" * 50)
    print(f"Platform: {platform_info['system']} {platform_info['machine']}")
    print(f"Python: {platform_info['python_version']}")
    print(f"Package Manager: {platform_info['package_manager']}")
    print()
    
    # Platform-specific setup
    if platform_info["system"] == "Windows":
        setup_windows()
    elif platform_info["system"] == "Darwin":
        setup_macos()
    elif platform_info["system"] == "Linux":
        setup_linux()
    else:
        print(f"⚠️  Unknown platform: {platform_info['system']}")
        print("Proceeding with generic setup...")
    
    # Check and install Python requirements
    if not check_python_requirements():
        print("📦 Installing Python requirements...")
        if not install_python_requirements():
            print("❌ Failed to install Python requirements")
            return False
    
    # Create virtual environment
    python_executable = create_virtual_environment()
    
    # Find the setup script
    script_dir = Path(__file__).parent
    setup_script = script_dir / "interactive_setup.py"
    
    if not setup_script.exists():
        print("❌ Setup script not found")
        return False
    
    # Find available port
    import socket
    port = 8080
    
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('localhost', port))
            break
        except OSError:
            port += 1
    
    print(f"\n🌐 Starting web setup on port {port}")
    print(f"📋 Open your browser and go to: http://localhost:{port}")
    print("\n⚠️  Press Ctrl+C to stop the setup server")
    print()
    
    # Launch the setup script
    try:
        env = os.environ.copy()
        env["SETUP_PORT"] = str(port)
        
        subprocess.run([python_executable, str(setup_script)], env=env)
        
    except KeyboardInterrupt:
        print("\n👋 Setup cancelled by user")
    except Exception as e:
        print(f"❌ Failed to launch setup: {e}")
        return False
    
    return True

def main():
    """Main entry point."""
    try:
        success = launch_setup()
        if success:
            print("\n✅ Setup completed successfully!")
        else:
            print("\n❌ Setup failed!")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Setup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
