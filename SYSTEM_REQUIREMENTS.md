# 🔍 System Requirements & Auto-Installation Guide

## 📋 Comprehensive System Requirements Check

The QGen RAG setup system now includes **comprehensive system requirements checking** with **automatic dependency installation** for a seamless setup experience.

## 🎯 What Gets Checked

### **🐳 Docker & Docker Compose**
- **Docker CLI**: Installation and version detection
- **Docker Daemon**: Running status verification
- **Docker Compose**: Availability check (both standalone and plugin)
- **Cross-platform support**: Windows Desktop, macOS, Linux Engine

### **🗄️ Database Components**
- **PostgreSQL**: Availability via package managers
- **pgvector**: Vector extension availability (via Docker image)
- **Redis**: Installation check (Docker-based deployment)

### **🛠️ Development Tools**
- **Git**: Version control system
- **Node.js**: Frontend build requirements
- **npm**: Package manager for Node.js
- **Python**: Version and package requirements

### **💻 Hardware Requirements**
- **CPU**: Core count detection
- **Memory**: RAM availability (minimum 4GB recommended)
- **Storage**: Free disk space (minimum 10GB required)
- **GPU**: Comprehensive GPU detection:
  - **NVIDIA GPUs** (Linux/Windows) with CUDA support
  - **Apple Silicon GPUs** (M1, M2, M3, M4, M5 series) with Neural Engine
  - **AMD GPUs** (Linux/macOS) with ROCm support
  - **GPU optimization recommendations** for ML workloads

### **🌐 Network Connectivity**
- **Internet**: Basic connectivity check
- **Docker Hub**: Container registry access
- **GitHub**: Source code repository access

## 🚀 Automatic Installation Features

### **📦 What Can Be Auto-Installed**

#### **Docker**
- **Windows**: Guides to Docker Desktop installation
- **macOS**: Automatic via Homebrew (`brew install --cask docker`)
- **Linux**: Full installation with proper configuration
  - Ubuntu/Debian: Official Docker repository setup
  - CentOS/RHEL: YUM repository configuration
  - User group configuration for sudo-less usage

#### **Git**
- **Windows**: Download guidance
- **macOS**: `brew install git`
- **Linux**: Package manager installation (apt, yum, pacman)

#### **Node.js & npm**
- **Windows**: Download guidance
- **macOS**: `brew install node`
- **Linux**: Package manager installation

#### **Python Packages**
- **Cross-platform**: Automatic pip installation
- **Platform-specific**: Windows WMI support
- **Required packages**: FastAPI, Uvicorn, Jinja2, aiofiles, psutil

### **🔧 Installation Process**

1. **Detection Phase**
   ```bash
   🔍 Checking system requirements...
   ✅ Docker: Docker version 24.0.6
   ❌ Git is not installed
   ❌ Node.js is not installed
   ```

2. **Issue Identification**
   ```bash
   ❌ Critical Issues (must be resolved):
      ❌ Git is not installed
      ❌ Node.js is not installed
   
   🔧 Found 2 installable issues.
   Would you like me to install these automatically? (y/n):
   ```

3. **Automatic Installation**
   ```bash
   🔧 Installing missing dependencies...
   
   📦 Installing Git...
   ✅ Git installed
   
   📦 Installing Node.js...
   ✅ Node.js installed
   
   ✅ Successfully installed: Git, Node.js
   ```

## 🎛️ Platform-Specific Installation

### **Windows Support**
```powershell
# Docker Desktop
# Download and install from: https://docs.docker.com/docker-for-windows/install/

# Git for Windows  
# Download and install from: https://git-scm.com/download/win

# Node.js
# Download and install from: https://nodejs.org/

# Python packages (automatic)
pip install fastapi uvicorn jinja2 aiofiles psutil wmi
```

### **macOS Support**
```bash
# Docker Desktop (via Homebrew)
brew install --cask docker

# Git (via Homebrew)
brew install git

# Node.js (via Homebrew)
brew install node

# Python packages (automatic)
pip install fastapi uvicorn jinja2 aiofiles psutil
```

### **Linux Support**

#### **Ubuntu/Debian**
```bash
# Docker (official repository)
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER

# Git
sudo apt install -y git

# Node.js
sudo apt install -y nodejs npm
```

#### **CentOS/RHEL**
```bash
# Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Git
sudo yum install -y git

# Node.js
sudo yum install -y nodejs npm
```

#### **Arch Linux**
```bash
# Docker
sudo pacman -S --noconfirm docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Git
sudo pacman -S --noconfirm git

# Node.js
sudo pacman -S --noconfirm nodejs npm
```

## ⚠️ Important Notes

### **Docker Installation**
- **Linux**: After installation, you must **log out and log back in** to use Docker without sudo
- **Alternative**: Run `newgrp docker` to apply group changes immediately
- **Windows/macOS**: Docker Desktop must be started manually after installation

### **Hardware Requirements**
- **Minimum RAM**: 4GB (8GB+ recommended for ML workloads)
- **Minimum Storage**: 10GB free space (50GB+ recommended)
- **GPU**: Optional but recommended for ML acceleration
- **CPU**: Multi-core recommended for better performance

### **Network Requirements**
- **Internet**: Required for downloading Docker images and dependencies
- **Docker Hub**: Required for container downloads
- **GitHub**: Required for repository cloning

## 🔍 Detailed Requirement Check Output

### **Successful Check**
```bash
🚀 QGen RAG Interactive Setup Launcher
==================================================
Platform: Darwin arm64
Python: 3.11.15
Package Manager: homebrew

🔍 Checking system requirements...
✅ Docker: Docker version 24.0.6, build ed843a4
✅ Docker Compose: docker-compose version 1.29.2
✅ PostgreSQL: Available via Homebrew
✅ Redis: Available via Docker
✅ pgvector: Available via Docker pgvector/pgvector image
✅ Git: git version 2.39.0
✅ Node.js: v18.17.0
✅ npm: 9.6.7
✅ Python: 3.11.15
✅ CPU: 8 cores
✅ Memory: 16.0GB
✅ Disk Space: 45.2GB free
✅ GPU: Apple M5
✅ Neural Engine: Available
   🚀 Apple Silicon GPU optimized for ML workloads
✅ Internet connectivity
✅ Docker Hub accessible
✅ GitHub accessible

✅ System requirements check passed!
```

### **Different GPU Types**
```bash
# NVIDIA GPU (Linux/Windows)
✅ GPU: NVIDIA GeForce RTX 4090
   🎮 CUDA acceleration available

# Apple Silicon (macOS)
✅ GPU: Apple M4 Pro
✅ Neural Engine: Available
   🚀 Apple Silicon GPU optimized for ML workloads

# AMD GPU (Linux/macOS)
✅ GPU: AMD Radeon RX 7900 XTX
   🔄 AMD GPU acceleration available
```

### **Issues Detected**
```bash
❌ Critical Issues (must be resolved):
   ❌ Docker is not installed
   ❌ Git is not installed

🔧 Found 2 installable issues.
Would you like me to install these automatically? (y/n):
```

## 🎯 Usage Examples

### **Basic Usage**
```bash
# Run the launcher with automatic checking
python launch_setup.py
```

### **Manual Requirements Check**
```python
from launch_setup import check_system_requirements

requirements = check_system_requirements()
print(f"Docker installed: {requirements['docker']['installed']}")
print(f"Git installed: {requirements['git']['installed']}")
print(f"Node.js installed: {requirements['nodejs']['installed']}")
```

### **Install Missing Dependencies**
```python
from launch_setup import check_system_requirements, install_missing_dependencies

requirements = check_system_requirements()
install_missing_dependencies(requirements)
```

## 🎉 Benefits

### **🔍 Comprehensive Detection**
- **All major dependencies** checked automatically
- **Hardware capabilities** assessed for optimization
- **Network connectivity** verified for downloads
- **Platform-specific** requirements handled

### **🔧 Automatic Installation**
- **One-command installation** for missing dependencies
- **Platform-aware** installation methods
- **Proper configuration** (user groups, permissions)
- **Clear instructions** for manual steps

### **💡 User-Friendly**
- **Clear feedback** on what's missing
- **Optional installation** with user consent
- **Detailed error messages** for troubleshooting
- **Progress indicators** during installation

### **🛡️ Safe and Reliable**
- **Non-destructive** checks only
- **User confirmation** before any installation
- **Rollback-friendly** installation methods
- **Detailed logging** for debugging

---

## 🚀 Ready to Use!

The enhanced setup system now provides:
- **🔍 Complete system analysis**
- **🔧 Automatic dependency installation**
- **🎯 Platform-specific optimization**
- **💡 User-friendly guidance**
- **🛡️ Safe installation process**

Just run `python launch_setup.py` and let the system handle everything automatically! 🎉
