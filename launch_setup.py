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
import psutil
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

def check_system_requirements():
    """Check comprehensive system requirements."""
    requirements = {
        "docker": check_docker_requirements(),
        "postgresql": check_postgresql_requirements(),
        "redis": check_redis_requirements(),
        "pgvector": check_pgvector_requirements(),
        "git": check_git_requirements(),
        "nodejs": check_nodejs_requirements(),
        "python": check_python_requirements(),
        "hardware": check_hardware_requirements(),
        "network": check_network_requirements()
    }
    
    return requirements

def check_docker_requirements():
    """Check Docker installation and configuration."""
    docker_info = {
        "installed": False,
        "version": None,
        "running": False,
        "compose_available": False,
        "version_info": None,
        "issues": []
    }
    
    try:
        # Check Docker CLI
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            docker_info["installed"] = True
            docker_info["version"] = result.stdout.strip()
            
            # Check if Docker is running
            try:
                info_result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
                if info_result.returncode == 0:
                    docker_info["running"] = True
                    
                    # Parse Docker info for version details
                    info_lines = info_result.stdout.split('\n')
                    for line in info_lines:
                        if "Server Version:" in line:
                            docker_info["version_info"] = line.split(":")[1].strip()
                            break
                else:
                    docker_info["issues"].append("Docker is installed but not running")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                docker_info["issues"].append("Cannot check Docker status - service may not be running")
        else:
            docker_info["issues"].append("Docker CLI not found")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        docker_info["issues"].append("Docker is not installed")
    
    # Check Docker Compose
    compose_commands = ["docker-compose", "docker compose"]
    for cmd in compose_commands:
        try:
            if " " in cmd:
                parts = cmd.split()
                result = subprocess.run(parts, capture_output=True, text=True, timeout=10)
            else:
                result = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                docker_info["compose_available"] = True
                break
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            continue
    
    if not docker_info["compose_available"]:
        docker_info["issues"].append("Docker Compose is not available")
    
    return docker_info

def check_postgresql_requirements():
    """Check PostgreSQL requirements."""
    pg_info = {
        "installed": False,
        "version": None,
        "pgvector_available": False,
        "issues": []
    }
    
    # Check if PostgreSQL is available (will be installed via Docker)
    # For now, check if we can install it via package manager
    system_name = platform.system()
    
    if system_name == "Linux":
        pm = detect_linux_package_manager()
        if pm == "apt":
            try:
                result = subprocess.run(["apt-cache", "policy", "postgresql"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    pg_info["installed"] = True  # Available for installation
                    pg_info["version"] = "Available via apt"
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pg_info["issues"].append("PostgreSQL not available via apt")
        elif pm == "yum":
            try:
                result = subprocess.run(["yum", "list", "postgresql"], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    pg_info["installed"] = True
                    pg_info["version"] = "Available via yum"
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pg_info["issues"].append("PostgreSQL not available via yum")
    elif system_name == "Darwin":
        # Check if PostgreSQL is available via Homebrew
        try:
            result = subprocess.run(["brew", "info", "postgresql"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                pg_info["installed"] = True
                pg_info["version"] = "Available via Homebrew"
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pg_info["issues"].append("Homebrew not available for PostgreSQL installation")
    elif system_name == "Windows":
        # PostgreSQL will be installed via Docker
        pg_info["installed"] = True
        pg_info["version"] = "Available via Docker"
    
    # Check pgvector availability
    pg_info["pgvector_available"] = True  # Will be installed via Docker pgvector image
    
    return pg_info

def check_redis_requirements():
    """Check Redis requirements."""
    redis_info = {
        "installed": False,
        "version": None,
        "issues": []
    }
    
    # Redis will be installed via Docker, but check if it's available locally
    try:
        result = subprocess.run(["redis-server", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            redis_info["installed"] = True
            redis_info["version"] = result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # Redis not installed locally, but will be available via Docker
        redis_info["installed"] = True
        redis_info["version"] = "Available via Docker"
    
    return redis_info

def check_pgvector_requirements():
    """Check pgvector extension requirements."""
    pgvector_info = {
        "available": False,
        "version": None,
        "issues": []
    }
    
    # pgvector will be installed via Docker pgvector/pgvector image
    pgvector_info["available"] = True
    pgvector_info["version"] = "Available via Docker pgvector/pgvector image"
    
    return pgvector_info

def check_git_requirements():
    """Check Git installation."""
    git_info = {
        "installed": False,
        "version": None,
        "issues": []
    }
    
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            git_info["installed"] = True
            git_info["version"] = result.stdout.strip()
        else:
            git_info["issues"].append("Git command failed")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        git_info["issues"].append("Git is not installed")
    
    return git_info

def check_nodejs_requirements():
    """Check Node.js installation."""
    node_info = {
        "installed": False,
        "version": None,
        "npm_available": False,
        "npm_version": None,
        "issues": []
    }
    
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            node_info["installed"] = True
            node_info["version"] = result.stdout.strip()
            
            # Check npm
            try:
                npm_result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=10)
                if npm_result.returncode == 0:
                    node_info["npm_available"] = True
                    node_info["npm_version"] = npm_result.stdout.strip()
                else:
                    node_info["issues"].append("npm is not available")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                node_info["issues"].append("npm command failed")
        else:
            node_info["issues"].append("Node.js command failed")
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        node_info["issues"].append("Node.js is not installed")
    
    return node_info

def check_hardware_requirements():
    """Check hardware requirements."""
    hardware_info = {
        "cpu_cores": psutil.cpu_count(logical=True),
        "memory_gb": psutil.virtual_memory().total / (1024**3),
        "disk_space_gb": psutil.disk_usage('/').free / (1024**3),
        "gpu_available": False,
        "gpu_info": None,
        "issues": []
    }
    
    # Check minimum requirements
    if hardware_info["memory_gb"] < 4:
        hardware_info["issues"].append("Less than 4GB RAM - may impact performance")
    
    if hardware_info["disk_space_gb"] < 10:
        hardware_info["issues"].append("Less than 10GB free disk space - insufficient for installation")
    
    # Check GPU availability
    try:
        result = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            hardware_info["gpu_available"] = True
            hardware_info["gpu_info"] = result.stdout.strip().split('\n')[0]
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        pass  # GPU not available
    
    return hardware_info

def check_network_requirements():
    """Check network connectivity and requirements."""
    network_info = {
        "internet_available": False,
        "docker_hub_accessible": False,
        "github_accessible": False,
        "issues": []
    }
    
    try:
        # Check basic internet connectivity
        import urllib.request
        urllib.request.urlopen('https://www.google.com', timeout=5)
        network_info["internet_available"] = True
        
        # Check Docker Hub accessibility
        urllib.request.urlopen('https://hub.docker.com', timeout=5)
        network_info["docker_hub_accessible"] = True
        
        # Check GitHub accessibility
        urllib.request.urlopen('https://github.com', timeout=5)
        network_info["github_accessible"] = True
        
    except Exception as e:
        network_info["issues"].append(f"Network connectivity issue: {e}")
    
    return network_info

def install_missing_dependencies(requirements):
    """Install missing dependencies based on requirements check."""
    platform_info = detect_platform()
    system_name = platform_info["system"]
    
    print("🔧 Installing missing dependencies...")
    
    installations = []
    
    # Install Docker if missing
    if not requirements["docker"]["installed"]:
        print("\n📦 Installing Docker...")
        if system_name == "Windows":
            print("Please download and install Docker Desktop for Windows:")
            print("https://docs.docker.com/docker-for-windows/install/")
            print("After installation, please restart this launcher.")
            return False
        elif system_name == "Darwin":
            print("Installing Docker Desktop for Mac via Homebrew...")
            try:
                subprocess.run(["brew", "install", "--cask", "docker"], check=True, timeout=600)
                print("✅ Docker Desktop installed. Please start it manually.")
                installations.append("Docker Desktop")
            except subprocess.CalledProcessError:
                print("❌ Failed to install Docker via Homebrew")
                print("Please install manually: https://docs.docker.com/docker-for-mac/install/")
                return False
        elif system_name == "Linux":
            pm = detect_linux_package_manager()
            if pm == "apt":
                try:
                    subprocess.run(["sudo", "apt", "update"], check=True, timeout=300)
                    subprocess.run(["sudo", "apt", "install", "-y", "ca-certificates", "curl", "gnupg"], check=True, timeout=300)
                    
                    # Add Docker's official GPG key
                    subprocess.run(["sudo", "install", "-m", "0755", "-d", "/etc/apt/keyrings"], check=True, timeout=60)
                    subprocess.run(["curl", "-fsSL", "https://download.docker.com/linux/ubuntu/gpg", "-o", "/etc/apt/keyrings/docker.asc"], check=True, timeout=300)
                    subprocess.run(["sudo", "chmod", "a+r", "/etc/apt/keyrings/docker.asc"], check=True, timeout=60)
                    
                    # Add Docker repository
                    echo_cmd = 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null'
                    subprocess.run(echo_cmd, shell=True, check=True, timeout=300)
                    
                    subprocess.run(["sudo", "apt", "update"], check=True, timeout=300)
                    subprocess.run(["sudo", "apt", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"], check=True, timeout=600)
                    
                    # Add user to docker group
                    subprocess.run(["sudo", "usermod", "-aG", "docker", os.environ.get("USER", "root")], check=True, timeout=60)
                    
                    print("✅ Docker installed. Please log out and log back in to use Docker without sudo.")
                    installations.append("Docker")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to install Docker: {e}")
                    return False
            elif pm == "yum":
                try:
                    subprocess.run(["sudo", "yum", "install", "-y", "yum-utils"], check=True, timeout=300)
                    subprocess.run(["sudo", "yum-config-manager", "--add-repo", "https://download.docker.com/linux/centos/docker-ce.repo"], check=True, timeout=300)
                    subprocess.run(["sudo", "yum", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io", "docker-compose-plugin"], check=True, timeout=600)
                    subprocess.run(["sudo", "systemctl", "start", "docker"], check=True, timeout=60)
                    subprocess.run(["sudo", "systemctl", "enable", "docker"], check=True, timeout=60)
                    subprocess.run(["sudo", "usermod", "-aG", "docker", os.environ.get("USER", "root")], check=True, timeout=60)
                    
                    print("✅ Docker installed. Please log out and log back in to use Docker without sudo.")
                    installations.append("Docker")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to install Docker: {e}")
                    return False
            else:
                print(f"❌ Automatic Docker installation not supported for {pm}")
                print("Please install Docker manually: https://docs.docker.com/engine/install/")
                return False
    
    # Install Git if missing
    if not requirements["git"]["installed"]:
        print("\n📦 Installing Git...")
        if system_name == "Windows":
            print("Please download and install Git for Windows:")
            print("https://git-scm.com/download/win")
            return False
        elif system_name == "Darwin":
            try:
                subprocess.run(["brew", "install", "git"], check=True, timeout=300)
                print("✅ Git installed")
                installations.append("Git")
            except subprocess.CalledProcessError:
                print("❌ Failed to install Git via Homebrew")
                return False
        elif system_name == "Linux":
            pm = detect_linux_package_manager()
            try:
                if pm == "apt":
                    subprocess.run(["sudo", "apt", "install", "-y", "git"], check=True, timeout=300)
                elif pm == "yum":
                    subprocess.run(["sudo", "yum", "install", "-y", "git"], check=True, timeout=300)
                elif pm == "pacman":
                    subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "git"], check=True, timeout=300)
                else:
                    print(f"❌ Git installation not supported for {pm}")
                    return False
                
                print("✅ Git installed")
                installations.append("Git")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install Git: {e}")
                return False
    
    # Install Node.js if missing
    if not requirements["nodejs"]["installed"]:
        print("\n📦 Installing Node.js...")
        if system_name == "Windows":
            print("Please download and install Node.js:")
            print("https://nodejs.org/")
            return False
        elif system_name == "Darwin":
            try:
                subprocess.run(["brew", "install", "node"], check=True, timeout=300)
                print("✅ Node.js installed")
                installations.append("Node.js")
            except subprocess.CalledProcessError:
                print("❌ Failed to install Node.js via Homebrew")
                return False
        elif system_name == "Linux":
            pm = detect_linux_package_manager()
            try:
                if pm == "apt":
                    subprocess.run(["sudo", "apt", "install", "-y", "nodejs", "npm"], check=True, timeout=300)
                elif pm == "yum":
                    subprocess.run(["sudo", "yum", "install", "-y", "nodejs", "npm"], check=True, timeout=300)
                elif pm == "pacman":
                    subprocess.run(["sudo", "pacman", "-S", "--noconfirm", "nodejs", "npm"], check=True, timeout=300)
                else:
                    print(f"❌ Node.js installation not supported for {pm}")
                    return False
                
                print("✅ Node.js installed")
                installations.append("Node.js")
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install Node.js: {e}")
                return False
    
    # Install Python packages if missing
    if not requirements["python"]["requirements_met"]:
        print("\n📦 Installing Python packages...")
        if not install_python_requirements():
            return False
        installations.append("Python packages")
    
    if installations:
        print(f"\n✅ Successfully installed: {', '.join(installations)}")
        
        # Special instructions for Docker
        if "Docker" in installations and system_name == "Linux":
            print("\n⚠️  IMPORTANT: Please log out and log back in to use Docker without sudo.")
            print("   Or run: newgrp docker")
        
        return True
    else:
        print("\n✅ All dependencies already installed")
        return True
    """Check Python requirements."""
    python_info = {
        "installed": True,  # We're running this script
        "version": platform.python_version(),
        "executable": sys.executable,
        "requirements_met": False,
        "missing_packages": [],
        "issues": []
    }
    
    # Check Python version
    version_parts = platform.python_version().split('.')
    major, minor = int(version_parts[0]), int(version_parts[1])
    
    if major < 3 or (major == 3 and minor < 9):
        python_info["issues"].append(f"Python {major}.{minor} detected - Python 3.9+ required")
        return python_info
    
    # Check required packages
    required_packages = [
        "fastapi",
        "uvicorn", 
        "jinja2",
        "aiofiles",
        "psutil"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    python_info["missing_packages"] = missing_packages
    python_info["requirements_met"] = len(missing_packages) == 0
    
    if missing_packages:
        python_info["issues"].append(f"Missing packages: {', '.join(missing_packages)}")
    
    return python_info

def check_python_requirements():
    """Check Python requirements."""
    python_info = {
        "installed": True,  # We're running this script
        "version": platform.python_version(),
        "executable": sys.executable,
        "requirements_met": False,
        "missing_packages": [],
        "issues": []
    }
    
    # Check Python version
    version_parts = platform.python_version().split('.')
    major, minor = int(version_parts[0]), int(version_parts[1])
    
    if major < 3 or (major == 3 and minor < 9):
        python_info["issues"].append(f"Python {major}.{minor} detected - Python 3.9+ required")
        return python_info
    
    # Check required packages
    required_packages = [
        "fastapi",
        "uvicorn", 
        "jinja2",
        "aiofiles",
        "psutil"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    python_info["missing_packages"] = missing_packages
    python_info["requirements_met"] = len(missing_packages) == 0
    
    if missing_packages:
        python_info["issues"].append(f"Missing packages: {', '.join(missing_packages)}")
    
    return python_info

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
    
    # Check platform-specific dependencies
    if platform_info["system"] == "Windows":
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "wmi>=1.5.1"], 
                         check=True, capture_output=True)
            print("✅ Installed wmi (Windows support)")
        except subprocess.CalledProcessError:
            print("⚠️  Could not install wmi (Windows support limited)")
    
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
    
    # Comprehensive system requirements check
    print("🔍 Checking system requirements...")
    requirements = check_system_requirements()
    
    # Display requirement status
    critical_issues = []
    warnings = []
    
    # Check Docker (critical)
    docker = requirements["docker"]
    if not docker["installed"]:
        critical_issues.append("❌ Docker is not installed")
    elif not docker["running"]:
        critical_issues.append("❌ Docker is installed but not running")
    elif not docker["compose_available"]:
        critical_issues.append("❌ Docker Compose is not available")
    else:
        print(f"✅ Docker: {docker['version']}")
    
    # Check PostgreSQL
    postgresql = requirements["postgresql"]
    if postgresql["installed"]:
        print(f"✅ PostgreSQL: {postgresql['version']}")
    else:
        warnings.append(f"⚠️  PostgreSQL: {', '.join(postgresql['issues'])}")
    
    # Check Redis
    redis = requirements["redis"]
    if redis["installed"]:
        print(f"✅ Redis: {redis['version']}")
    else:
        warnings.append(f"⚠️  Redis: {', '.join(redis['issues'])}")
    
    # Check pgvector
    pgvector = requirements["pgvector"]
    if pgvector["available"]:
        print(f"✅ pgvector: {pgvector['version']}")
    else:
        warnings.append(f"⚠️  pgvector: {', '.join(pgvector['issues'])}")
    
    # Check Git
    git = requirements["git"]
    if git["installed"]:
        print(f"✅ Git: {git['version']}")
    else:
        critical_issues.append(f"❌ Git: {', '.join(git['issues'])}")
    
    # Check Node.js
    nodejs = requirements["nodejs"]
    if nodejs["installed"]:
        print(f"✅ Node.js: {nodejs['version']}")
        if nodejs["npm_available"]:
            print(f"✅ npm: {nodejs['npm_version']}")
        else:
            warnings.append("⚠️  npm is not available")
    else:
        warnings.append(f"⚠️  Node.js: {', '.join(nodejs['issues'])}")
    
    # Check Python
    python = requirements["python"]
    if python["requirements_met"]:
        print(f"✅ Python: {python['version']}")
    else:
        if python["missing_packages"]:
            warnings.append(f"⚠️  Python missing packages: {', '.join(python['missing_packages'])}")
        if python["issues"]:
            warnings.append(f"⚠️  Python: {', '.join(python['issues'])}")
    
    # Check Hardware
    hardware = requirements["hardware"]
    print(f"✅ CPU: {hardware['cpu_cores']} cores")
    print(f"✅ Memory: {hardware['memory_gb']:.1f}GB")
    print(f"✅ Disk Space: {hardware['disk_space_gb']:.1f}GB free")
    
    if hardware["gpu_available"]:
        print(f"✅ GPU: {hardware['gpu_info']}")
    else:
        warnings.append("⚠️  No GPU detected - CPU-only mode")
    
    if hardware["issues"]:
        warnings.extend([f"⚠️  {issue}" for issue in hardware["issues"]])
    
    # Check Network
    network = requirements["network"]
    if network["internet_available"]:
        print("✅ Internet connectivity")
        if network["docker_hub_accessible"]:
            print("✅ Docker Hub accessible")
        if network["github_accessible"]:
            print("✅ GitHub accessible")
    else:
        critical_issues.append("❌ No internet connectivity")
    
    # Display critical issues and warnings
    if critical_issues:
        print("\n❌ Critical Issues (must be resolved):")
        for issue in critical_issues:
            print(f"   {issue}")
        
        # Offer to install missing dependencies
        installable_issues = [issue for issue in critical_issues if any(x in issue for x in ["Docker", "Git", "Node.js", "Python"])]
        
        if installable_issues:
            print(f"\n🔧 Found {len(installable_issues)} installable issues.")
            response = input("Would you like me to install these automatically? (y/n): ").lower().strip()
            
            if response in ['y', 'yes']:
                if install_missing_dependencies(requirements):
                    print("\n✅ Dependencies installed successfully!")
                    print("Please restart the launcher to continue.")
                    return False
                else:
                    print("\n❌ Failed to install some dependencies.")
                    print("Please install them manually and restart the launcher.")
                    return False
            else:
                print("\nPlease install the missing dependencies manually:")
                for issue in installable_issues:
                    print(f"   - {issue}")
                print("\nThen restart this launcher.")
                return False
        else:
            print("\nPlease resolve these issues before proceeding.")
            return False
    
    if warnings:
        print("\n⚠️  Warnings (may impact performance):")
        for warning in warnings:
            print(f"   {warning}")
        print()
    
    print("✅ System requirements check passed!")
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
    if not requirements["python"]["requirements_met"]:
        print("📦 Installing Python requirements...")
        if not install_python_requirements():
            print("❌ Failed to install Python requirements")
            return False
    
    # Create virtual environment
    python_executable = create_virtual_environment()
    
    # Find the setup script
    script_dir = Path(__file__).parent
    setup_script = script_dir / "scripts" / "interactive_setup.py"
    
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
