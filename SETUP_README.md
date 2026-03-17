# 🚀 QGen RAG Interactive Setup

An intelligent web-based setup system that automatically detects your hardware, OS, and software configuration, then guides you through deploying the QGen RAG SLM/LLM training system.

## ✨ Features

### 🔍 **Automatic System Detection**
- **Operating System**: Linux, macOS, Windows with WSL2
- **Hardware**: CPU cores, memory, disk space, GPU detection
- **Manufacturer**: Dell, HP, Lenovo, Apple Silicon, custom builds
- **Architecture**: x86_64, ARM64, GPU acceleration support
- **Software**: Docker, Git, Node.js, Python, NVIDIA drivers

### 🎯 **Smart Recommendations**
- **Deployment Type**: Docker, GPU-accelerated, DGX Spark
- **Resource Allocation**: Memory, storage, GPU configuration
- **Installation Path**: Automatic dependency installation
- **Performance Tuning**: System-specific optimizations

### 🌐 **Interactive Web Interface**
- **Step-by-Step Guidance**: Visual progress tracking
- **Real-time Feedback**: Live command output and status
- **Configuration Forms**: User-friendly input validation
- **Error Handling**: Clear error messages and recovery

### 🔄 **One-Click Deployment**
- **Dependencies**: Auto-install Docker, Git, and requirements
- **Repository**: Clone and setup the project automatically
- **Database**: PostgreSQL with pgvector setup
- **Services**: All containers started and configured
- **SSL**: Automatic certificate generation
- **Monitoring**: Grafana and Prometheus setup

## 🚀 Quick Start

### Method 1: Automated Launcher (Recommended)

```bash
# Download and run the setup launcher
curl -fsSL https://raw.githubusercontent.com/your-org/qgen_rag/main/scripts/setup.sh | bash

# Or if you have the repository:
./scripts/setup.sh
```

### Method 2: Manual Setup

```bash
# 1. Install Python requirements
pip install -r scripts/setup_requirements.txt

# 2. Run the interactive setup
python3 scripts/interactive_setup.py
```

### Method 3: Docker Setup

```bash
# Run the setup in a container
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd):/workspace \
  -p 8080:8080 \
  qgen/setup:latest
```

## 📋 Setup Process

### **Phase 1: System Detection**
The setup automatically detects:
- ✅ Operating system and version
- ✅ Hardware specifications
- ✅ GPU capabilities (CUDA, memory)
- ✅ Network configuration
- ✅ Installed software
- ✅ Available ports

### **Phase 2: Configuration**
You'll be prompted for:
- 📁 Installation directory
- 🌐 Domain name (for production)
- 📧 SSL certificate email
- 🔑 API keys (OpenAI, DeepSeek)
- 📦 Repository URL
- 🤖 Base model selection

### **Phase 3: Automated Installation**
The setup handles:
- 📦 Dependency installation (Docker, Git, etc.)
- 📥 Repository cloning
- ⚙️ Environment configuration
- 🗄️ Database setup with migrations
- 🚀 Service startup
- 🔒 SSL certificate generation
- 🎯 Data initialization

### **Phase 4: Completion**
You'll get:
- ✅ System ready for use
- 🔗 Access URLs for all services
- 📊 Monitoring dashboard
- 📚 Next steps guidance

## 🖥️ System Requirements

### **Minimum Requirements**
- **OS**: Linux (Ubuntu 20.04+), macOS (11+), Windows 10+ with WSL2
- **CPU**: 4+ cores
- **Memory**: 8GB RAM
- **Storage**: 50GB free space
- **Network**: Internet connection for model downloads

### **Recommended Requirements**
- **OS**: Linux with NVIDIA drivers
- **CPU**: 8+ cores
- **Memory**: 32GB+ RAM
- **GPU**: NVIDIA GPU with 8GB+ VRAM
- **Storage**: 500GB+ SSD
- **Network**: 10Gbps+ for large model downloads

### **DGX Spark Requirements**
- **Hardware**: NVIDIA DGX Spark or equivalent
- **GPU**: 4+ NVIDIA GPUs (A100/H100)
- **Memory**: 128GB+ RAM
- **Storage**: 1TB+ NVMe SSD
- **Network**: InfiniBand or 100Gbps Ethernet

## 📊 Supported Configurations

### **Development Setup**
- **Local Machine**: Laptop or workstation
- **GPU**: Optional (CPU-only mode available)
- **Database**: SQLite (for development)
- **Monitoring**: Basic logging

### **Production Setup**
- **Server**: Dedicated or cloud server
- **GPU**: Recommended for performance
- **Database**: PostgreSQL with pgvector
- **Monitoring**: Full Grafana/Prometheus stack

### **DGX Spark Setup**
- **Hardware**: NVIDIA DGX Spark
- **GPU**: Multi-GPU training
- **Database**: Optimized PostgreSQL
- **Monitoring**: Advanced GPU monitoring

## 🔧 Advanced Configuration

### **Custom Environment Variables**
```bash
# Override default settings
export QGEN_INSTALL_DIR="/custom/path"
export QGEN_DOMAIN="custom.domain.com"
export QGEN_GPU_MEMORY_FRACTION="0.8"
export QGEN_BATCH_SIZE="8"
```

### **Custom Models**
```bash
# Use different base models
export QGEN_BASE_MODEL="microsoft/DialoGPT-large"
export QGEN_EMBEDDING_MODEL="sentence-transformers/all-MiniLM-L6-v2"
```

### **Network Configuration**
```bash
# Custom ports
export QGEN_FRONTEND_PORT="3000"
export QGEN_BACKEND_PORT="8000"
export QGEN_SETUP_PORT="8080"
```

## 🐛 Troubleshooting

### **Common Issues**

#### **Port Already in Use**
```bash
# Check what's using the port
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
export SETUP_PORT=8081
python3 scripts/interactive_setup.py
```

#### **Docker Not Running**
```bash
# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Check status
sudo systemctl status docker
```

#### **Permission Denied**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Logout and login again
# or use newgrp
newgrp docker
```

#### **GPU Not Detected**
```bash
# Check NVIDIA driver
nvidia-smi

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt update
sudo apt install -y nvidia-docker2
sudo systemctl restart docker
```

#### **Memory Issues**
```bash
# Enable swap space
sudo fallocate -l 8G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Add to fstab
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### **Debug Mode**
```bash
# Enable debug logging
export QGEN_DEBUG=true
export QGEN_LOG_LEVEL=DEBUG

# Run with verbose output
python3 scripts/interactive_setup.py --verbose
```

### **Reset Setup**
```bash
# Remove all configuration
rm -f ~/.qgen_setup.json
rm -rf /opt/qgen

# Start fresh
./scripts/setup.sh
```

## 📱 Mobile Access

The setup interface is mobile-responsive and can be accessed from:
- 📱 **Smartphones**: iOS Safari, Android Chrome
- 💻 **Tablets**: iPad, Android tablets
- 🖥️ **Desktop**: All modern browsers

## 🔒 Security Features

### **SSL/TLS**
- Automatic Let's Encrypt certificates
- HTTPS redirection
- Security headers

### **Authentication**
- Admin account creation
- Role-based access control
- API key management

### **Network Security**
- Firewall configuration
- Port security
- Container isolation

## 📈 Performance Optimization

### **GPU Acceleration**
- CUDA optimization
- Memory management
- Batch processing

### **Database Optimization**
- Connection pooling
- Index optimization
- Query caching

### **Network Optimization**
- CDN configuration
- Load balancing
- Compression

## 🔄 Updates and Maintenance

### **System Updates**
```bash
# Update the setup script
curl -fsSL https://raw.githubusercontent.com/your-org/qgen_rag/main/scripts/setup.sh -o setup.sh
chmod +x setup.sh

# Run update
./setup.sh --update
```

### **Backup Configuration**
```bash
# Backup setup configuration
cp ~/.qgen_setup.json ~/qgen_setup_backup.json

# Restore configuration
cp ~/qgen_setup_backup.json ~/.qgen_setup.json
```

### **Health Checks**
```bash
# Check system health
curl http://localhost:8080/api/health

# Check service status
docker-compose ps
```

## 📚 Documentation

- **[DGX Spark Deployment Guide](docs/DGX_SPARK_DEPLOYMENT.md)**
- **[API Documentation](docs/API_REFERENCE.md)**
- **[Training Guide](docs/TRAINING_GUIDE.md)**
- **[Troubleshooting](docs/TROUBLESHOOTING.md)**

## 🤝 Support

### **Community**
- **GitHub Issues**: Report bugs and request features
- **Discussions**: Ask questions and share experiences
- **Wiki**: Community-maintained documentation

### **Professional Support**
- **Email**: support@qgen.ai
- **Slack**: Join our community Slack
- **Consulting**: Setup and optimization services

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🎉 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

---

**🚀 Ready to start? Run `./scripts/setup.sh` and follow the web interface!**
