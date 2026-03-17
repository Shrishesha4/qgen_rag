# QGen RAG Complete Customizable Setup Wizard

## Overview

The QGen RAG Complete Customizable Setup Wizard provides a comprehensive, multi-step web interface for setting up your entire QGen RAG system with full customization options. This wizard allows you to choose deployment modes, configure all settings, and customize every aspect of your installation.

## Features

### 🚀 Complete Setup Automation
- **Multi-step wizard** with clear progression tracking
- **System requirements checking** with detailed hardware/software detection
- **Deployment mode selection** for each service component
- **Full configuration customization** for all settings
- **Automated installation** of dependencies and services
- **Progress tracking** with real-time feedback

### 🏗️ Deployment Mode Flexibility
Choose how to deploy each service component:

#### Database Deployment
- **Docker**: Containerized PostgreSQL with pgvector and Redis (Recommended)
- **Baremetal**: Direct system installation for maximum performance

#### Backend Deployment  
- **Docker**: Containerized FastAPI application with worker processes
- **Baremetal**: Systemd service with direct system access

#### Frontend Deployment
- **Docker**: Containerized trainer-web application
- **Nginx**: Web server with reverse proxy configuration
- **Node.js**: Direct Node.js server for development

### ⚙️ Complete Configuration Customization

#### Basic Settings
- **Installation Directory**: Choose where to install QGen RAG
- **Domain**: Configure your domain name
- **Environment**: Production, Development, or Staging

#### Database Configuration
- **PostgreSQL Settings**: Database name, user, password, port
- **Redis Settings**: Password and port configuration
- **Data Volumes**: Custom volume paths for persistence

#### Service Ports
- **Backend Port**: API server port (default: 8000)
- **Frontend Port**: Web interface port (default: 5173)
- **Nginx Port**: Web server port (default: 80)

#### API Keys
- **OpenAI API Key**: For GPT model integration
- **DeepSeek API Key**: For DeepSeek model access
- **Anthropic API Key**: For Claude model integration

#### Model Configuration
- **Base Model**: Choose from multiple pre-trained models
- **Max Tokens**: Configure token limits
- **Temperature**: Adjust model creativity

#### Directory Paths
- **Model Cache**: Location for downloaded models
- **Training Data**: Directory for training datasets
- **Upload Directory**: File upload location

#### SSL Configuration
- **SSL Type**: Self-signed, Let's Encrypt, or custom certificates
- **SSL Email**: Email for certificate management
- **SSL Days**: Certificate validity period

#### Monitoring & Logging
- **Metrics**: Enable/disable performance metrics
- **Log Level**: DEBUG, INFO, WARNING, ERROR
- **Sentry DSN**: Error tracking configuration

## Wizard Steps

### 1. Welcome 🚀
- Introduction to QGen RAG system
- Overview of features and capabilities
- What the wizard will accomplish

### 2. System Requirements 🔍
- Comprehensive system detection
- Hardware analysis (CPU, RAM, GPU, Storage)
- Software verification (Docker, Git, Node.js, etc.)
- Network connectivity checks
- Requirements assessment with warnings and suggestions

### 3. Deployment Mode 🏗️
- Choose deployment mode for each service
- Docker vs Baremetal options
- Frontend deployment strategy
- Service architecture decisions

### 4. Configuration ⚙️
- Complete settings customization
- All system parameters configurable
- Real-time configuration validation
- Save and load configurations

### 5. Virtual Environment 🐍
- Python virtual environment setup
- Package installation and management
- Environment isolation and security

### 6. Dependencies 📦
- System package installation
- Platform-specific dependency handling
- Automatic dependency resolution

### 7. Source Code 📥
- Repository cloning and setup
- Version control configuration
- Source code management

### 8. Database Setup 🗄️
- PostgreSQL with pgvector configuration
- Redis cache setup
- Database initialization and migration
- Connection testing

### 9. Frontend Setup 🎨
- Trainer-web application configuration
- Client application setup
- Frontend build and optimization

### 10. Services 🚀
- Backend service startup
- Worker process configuration
- Service health checking
- Load balancing setup

### 11. SSL Configuration 🔒
- Certificate generation and setup
- Security configuration
- HTTPS enforcement

### 12. Data Initialization 📊
- Sample data setup
- Database seeding
- Initial configuration

### 13. Training Pipeline 🤖
- ML model configuration
- Training pipeline setup
- Model optimization settings

### 14. Setup Complete ✅
- Final review and summary
- Access links and credentials
- Next steps and guidance

## Usage

### Starting the Wizard

1. **Run the launcher script**:
   ```bash
   python launch_setup.py
   ```

2. **Open your browser** and navigate to the displayed URL (usually http://localhost:8080)

3. **Follow the wizard steps** in order

### Configuration Management

The wizard saves your configuration as you progress:
- **Auto-save**: Configuration is saved automatically
- **Manual save**: Save configuration at any time
- **Load previous**: Resume from saved configuration

### Step Execution

Each setup step can be:
- **Executed automatically** by clicking the execute button
- **Monitored in real-time** with progress feedback
- **Retried** if execution fails
- **Skipped** (where applicable)

## Deployment Examples

### Docker-Based Deployment (Recommended)
```yaml
# All services in Docker containers
Database: Docker (PostgreSQL + pgvector, Redis)
Backend: Docker (FastAPI + Workers)
Frontend: Docker (Trainer-web)
SSL: Self-signed certificates
```

### Baremetal Deployment
```yaml
# Direct system installation
Database: Baremetal (System PostgreSQL + Redis)
Backend: Baremetal (Systemd service)
Frontend: Nginx (Web server)
SSL: Let's Encrypt certificates
```

### Hybrid Deployment
```yaml
# Mixed deployment modes
Database: Docker (Easy management)
Backend: Baremetal (Maximum performance)
Frontend: Nginx (Production-ready)
SSL: Custom certificates
```

## Configuration Files

The wizard generates several configuration files:

### Backend Environment (.env)
```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://qgen_user:qgen_password@localhost:5432/qgen_rag
REDIS_URL=redis://localhost:6379/0

# Application Configuration
SECRET_KEY=your-secret-key
DOMAIN=your-domain.com
ENVIRONMENT=production

# API Keys
OPENAI_API_KEY=your-openai-key
DEEPSEEK_API_KEY=your-deepseek-key
```

### Frontend Environment (.env.local)
```bash
# API Configuration
PUBLIC_API_URL=http://your-domain.com:8000
PUBLIC_WS_URL=ws://your-domain.com:8000

# Application Configuration
PUBLIC_APP_NAME=QGen RAG
PUBLIC_APP_VERSION=1.0.0
```

### Docker Compose Files
- `docker-compose.database.yml` - Database services
- `docker-compose.backend.yml` - Backend services
- `docker-compose.frontend.yml` - Frontend services

### Training Configuration (training_config.json)
```json
{
  "model_config": {
    "base_model": "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    "max_sequence_length": 4096
  },
  "training_config": {
    "batch_size": 4,
    "learning_rate": 2e-4
  }
}
```

## System Requirements

### Minimum Requirements
- **OS**: Linux, macOS, or Windows
- **CPU**: 4+ cores recommended
- **RAM**: 8GB+ recommended
- **Storage**: 20GB+ free space
- **Network**: Internet connection for downloads

### Recommended Requirements
- **OS**: Linux (Ubuntu 20.04+) or macOS (Apple Silicon)
- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Storage**: 50GB+ SSD
- **GPU**: NVIDIA GPU with CUDA or Apple Silicon

### Software Dependencies
- **Docker**: For containerized deployment
- **Git**: For source code management
- **Node.js**: For frontend applications
- **Python**: 3.8+ (handled by wizard)
- **PostgreSQL**: For baremetal deployment
- **Redis**: For baremetal deployment

## Troubleshooting

### Common Issues

#### Port Conflicts
- **Problem**: Services fail to start due to port conflicts
- **Solution**: Change port numbers in the configuration step

#### Permission Errors
- **Problem**: Permission denied during installation
- **Solution**: Run wizard with appropriate permissions or use Docker deployment

#### Network Issues
- **Problem**: Cannot download dependencies
- **Solution**: Check internet connection and proxy settings

#### Docker Issues
- **Problem**: Docker services fail to start
- **Solution**: Ensure Docker is running and has sufficient resources

### Getting Help

1. **Check system requirements** in the wizard
2. **Review error messages** in the step output
3. **Consult logs** in the installation directory
4. **Verify configuration** settings
5. **Restart services** if needed

## Advanced Features

### Custom SSL Certificates
1. Select "Custom Certificate" in SSL configuration
2. Place certificates in the SSL directory
3. Configure certificate paths

### Custom Models
1. Choose custom model in configuration
2. Configure model parameters
3. Set up model cache directory

### Monitoring Integration
1. Enable metrics in configuration
2. Configure Sentry DSN for error tracking
3. Set up log aggregation

### Performance Optimization
1. Configure worker processes
2. Set up load balancing
3. Optimize database connections
4. Configure caching

## Security Considerations

### Default Security
- **Random secret keys** generated automatically
- **Secure passwords** for database services
- **SSL certificates** for HTTPS
- **Firewall rules** for service ports

### Additional Security
- **API key management** through environment variables
- **Database encryption** with pgcrypto
- **Access control** through authentication
- **Audit logging** for compliance

## Migration and Updates

### Updating Configuration
1. Run the wizard again
2. Load existing configuration
3. Modify settings as needed
4. Re-run affected steps

### Migrating Deployments
1. Export current configuration
2. Run wizard on new system
3. Import configuration
4. Execute setup steps

### Backup and Recovery
1. **Configuration backup**: Save wizard configuration
2. **Data backup**: Database and file system backups
3. **Service recovery**: Restart services from configuration

## Support and Documentation

### Documentation
- **System Requirements**: Detailed hardware/software requirements
- **Configuration Guide**: Complete configuration reference
- **Deployment Guide**: Step-by-step deployment instructions
- **Troubleshooting**: Common issues and solutions

### Community Support
- **GitHub Issues**: Report bugs and request features
- **Discussions**: Community help and guidance
- **Wiki**: Additional documentation and guides

### Professional Support
- **Enterprise Support**: Dedicated support for organizations
- **Consulting**: Custom deployment and optimization
- **Training**: Team training and best practices

---

## Quick Start

1. **Download and extract** QGen RAG
2. **Run the setup wizard**:
   ```bash
   python launch_setup.py
   ```
3. **Open your browser** to the displayed URL
4. **Follow the wizard steps** to configure your system
5. **Access your application** at the provided URLs

The wizard will guide you through every step of the setup process, ensuring a smooth and successful deployment of your QGen RAG system.
