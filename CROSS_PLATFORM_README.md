# 🌍 Cross-Platform QGen RAG Setup

A truly cross-platform interactive setup system that works seamlessly on **Windows**, **macOS**, and **Linux** with automatic platform detection and optimization.

## 🚀 Quick Start (Any Platform)

### **Method 1: Universal Launcher (Recommended)**
```bash
# Works on all platforms
python3 launch_setup.py

# Or if you have the repository:
python launch_setup.py
```

### **Method 2: Platform-Specific Launchers**

#### **Windows**
```cmd
# Double-click or run from command prompt
scripts\setup_windows.bat

# Or directly with Python
python launch_setup.py
```

#### **macOS & Linux**  
```bash
# Run the Unix launcher
./scripts/setup_unix.sh

# Or directly with Python
python3 launch_setup.py
```

## 🖥️ Platform Support

### **Windows Support**
- ✅ **Windows 10/11** (x64)
- ✅ **Windows Server** (2019+)
- ✅ **WSL2** (Windows Subsystem for Linux)
- ✅ **PowerShell** and **Command Prompt**
- ✅ **Docker Desktop** integration
- ✅ **Chocolatey** package manager support
- ✅ **Administrator privilege** detection

### **macOS Support**
- ✅ **macOS 11+** (Big Sur and later)
- ✅ **Apple Silicon** (M1/M2/M3) optimization
- ✅ **Intel Mac** support
- ✅ **Homebrew** package manager
- ✅ **Docker Desktop** integration
- ✅ **Zsh** and **Bash** shell support

### **Linux Support**
- ✅ **Ubuntu** (18.04+)
- ✅ **CentOS/RHEL** (7+)
- ✅ **Fedora** (30+)
- ✅ **Arch Linux**
- ✅ **Debian** (10+)
- ✅ **openSUSE** (15+)
- ✅ **Package manager** auto-detection (apt, yum, pacman, zypper)
- ✅ **Docker** Engine support
- ✅ **Systemd** service management

## 🔧 Automatic Features

### **System Detection**
- **Operating System**: Windows, macOS, Linux with version detection
- **Hardware**: CPU, memory, storage, GPU (NVIDIA, AMD, Intel, Apple Silicon)
- **Architecture**: x86_64, ARM64, Apple Silicon optimization
- **Manufacturer**: Dell, HP, Lenovo, Apple, custom builds
- **Software**: Docker, Git, Python, Node.js, Nginx detection

### **Platform Optimization**
- **Windows**: 
  - PowerShell command execution
  - Administrator privilege handling
  - WSL2 detection and guidance
  - Windows path handling
- **macOS**:
  - Apple Silicon optimization
  - Homebrew integration
  - System profiler data extraction
  - macOS-specific GPU detection
- **Linux**:
  - Package manager auto-detection
  - Systemd service management
  - DMI/SMBIOS hardware detection
  - Distribution-specific commands

### **Dependency Management**
- **Automatic Installation**: Docker, Git, Node.js based on platform
- **Package Managers**: 
  - Windows: Chocolatey, Winget
  - macOS: Homebrew
  - Linux: apt, yum, pacman, zypper, emerge
- **Virtual Environment**: Cross-platform venv creation
- **Python Packages**: Platform-specific dependency resolution

## 📋 Setup Process by Platform

### **Windows Setup**
1. **System Check**: Detect Windows version, admin privileges, WSL2
2. **Dependency Check**: Docker Desktop, Git for Windows
3. **Installation Guide**: 
   - Install Docker Desktop (if missing)
   - Install Git for Windows (if missing)
   - Enable WSL2 (recommended)
4. **Path Handling**: Windows path conversion (`C:\opt\` vs `/opt/`)
5. **Service Setup**: Windows service configuration

### **macOS Setup**
1. **System Check**: macOS version, Apple Silicon vs Intel
2. **Dependency Check**: Homebrew, Docker Desktop
3. **Installation Guide**:
   - Install Homebrew (if missing)
   - Install Docker Desktop (if missing)
   - Apple Silicon optimization
4. **GPU Detection**: Apple Silicon GPU, Intel GPU
5. **Service Setup**: macOS launchd configuration

### **Linux Setup**
1. **System Check**: Distribution, package manager, kernel version
2. **Dependency Check**: Docker Engine, Git, sudo access
3. **Package Manager Detection**: apt, yum, pacman, zypper
4. **Installation Guide**:
   - Install Docker Engine (distribution-specific)
   - Install Git (distribution-specific)
   - Configure user groups
5. **Service Setup**: Systemd service configuration

## 🎯 Platform-Specific Features

### **Windows Features**
- **Administrator Detection**: Automatically checks for admin rights
- **WSL2 Integration**: Detects and guides WSL2 setup
- **PowerShell Support**: Native PowerShell command execution
- **Windows Services**: Configures Windows services
- **Registry Integration**: Windows registry access for system info

### **macOS Features**
- **Apple Silicon Optimization**: M1/M2/M3 specific optimizations
- **Homebrew Integration**: Automatic Homebrew installation and usage
- **System Profiler**: Detailed macOS hardware detection
- **Launchd Services**: macOS service configuration
- **Sandbox Support**: macOS sandbox compatibility

### **Linux Features**
- **Distribution Detection**: Automatic Linux distribution identification
- **Package Manager Support**: Support for multiple package managers
- **Systemd Integration**: Systemd service management
- **DMI/SMBIOS**: Hardware information extraction
- **SELinux/AppArmor**: Security framework compatibility

## 🐛 Troubleshooting by Platform

### **Windows Issues**
```cmd
# Check Python installation
python --version

# Check Docker Desktop
docker --version

# Run as Administrator
# Right-click -> "Run as administrator"

# Check WSL2
wsl --list
```

### **macOS Issues**
```bash
# Check Python installation
python3 --version

# Check Homebrew
brew --version

# Check Docker Desktop
docker --version

# Apple Silicon specific
arch -arm64 brew --version
```

### **Linux Issues**
```bash
# Check Python installation
python3 --version

# Check package manager
apt --version  # Ubuntu/Debian
yum --version  # CentOS/RHEL
pacman --version  # Arch Linux

# Check Docker
docker --version

# Check sudo access
sudo --version
```

## 🔧 Advanced Configuration

### **Environment Variables**
```bash
# Windows
SET QGEN_INSTALL_DIR=C:\qgen
SET QGEN_DOMAIN=windows.local

# macOS/Linux
export QGEN_INSTALL_DIR=/opt/qgen
export QGEN_DOMAIN=macos.local
```

### **Platform Overrides**
```python
# Custom platform detection
def detect_custom_platform():
    if os.path.exists("/custom/platform"):
        return "custom"
    return platform.system()
```

### **Hardware Acceleration**
- **Windows**: NVIDIA GPU, Intel GPU, AMD GPU
- **macOS**: Apple Silicon GPU, Intel GPU
- **Linux**: NVIDIA CUDA, AMD ROCm, Intel GPU

## 📱 Mobile and Remote Access

### **Remote Setup**
- **SSH**: Remote server setup with terminal interface
- **RDP**: Windows Remote Desktop support
- **VNC**: Cross-platform remote desktop
- **Web Interface**: Browser-based setup from any device

### **Mobile Support**
- **iOS**: Safari browser support
- **Android**: Chrome browser support
- **Tablets**: Full tablet interface support

## 🔄 Updates and Maintenance

### **Cross-Platform Updates**
```bash
# Update setup script
curl -fsSL https://raw.githubusercontent.com/your-org/qgen_rag/main/scripts/launch_setup.py -o launch_setup.py

# Platform-specific updates
./scripts/setup_unix.sh --update  # macOS/Linux
scripts\setup_windows.bat --update  # Windows
```

### **Backup and Restore**
```bash
# Cross-platform backup
python3 scripts/launch_setup.py --backup

# Platform-specific backup
./scripts/setup_unix.sh --backup
scripts\setup_windows.bat --backup
```

## 📊 Performance Comparison

### **Setup Time by Platform**
- **Windows**: ~5-10 minutes (with Docker Desktop)
- **macOS**: ~3-7 minutes (with Homebrew)
- **Linux**: ~2-5 minutes (with package manager)

### **Resource Usage**
- **Memory**: ~512MB (setup process)
- **Disk**: ~2GB (Docker images + dependencies)
- **Network**: ~500MB (downloads)

## 🎯 Platform Recommendations

### **Development**
- **Windows**: Use WSL2 for best compatibility
- **macOS**: Use Apple Silicon for performance
- **Linux**: Use Ubuntu 20.04+ for stability

### **Production**
- **Windows**: Windows Server with Docker Desktop
- **macOS**: macOS Server with Docker Desktop
- **Linux**: Ubuntu LTS with Docker Engine

### **High Performance**
- **DGX Spark**: Linux with NVIDIA drivers
- **Apple Silicon**: macOS with optimized containers
- **Workstation**: Windows/Linux with multi-GPU

## 🤝 Community Support

### **Platform-Specific Issues**
- **Windows**: GitHub Issues with `[windows]` tag
- **macOS**: GitHub Issues with `[macos]` tag
- **Linux**: GitHub Issues with `[linux]` tag

### **Contributions**
- **Platform Testing**: Test on your platform
- **Bug Reports**: Report platform-specific issues
- **Documentation**: Improve platform documentation

---

## 🎉 One Command to Rule Them All

Regardless of your platform, just run:

```bash
python3 scripts/launch_setup.py
```

And let the cross-platform magic happen! 🚀
