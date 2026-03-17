#!/usr/bin/env python3
"""
Complete Multi-Page Setup Wizard for QGen RAG System

Comprehensive installation wizard with step-by-step guidance from
initial setup to final training data collection.
"""

import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
import uuid
import stat
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
import socket
import psutil
import shutil
import tempfile
import urllib.request
import zipfile
import tarfile

try:
    import aiofiles
    from fastapi import FastAPI, HTTPException, Request, Form
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
    import uvicorn
except ImportError as e:
    print(f"Missing required dependencies: {e}")
    print("Please install: pip install fastapi uvicorn jinja2 aiofiles psutil")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SystemDetector:
    """Enhanced system detection with comprehensive analysis."""
    
    def __init__(self):
        self.system_info = {}
        self.detect_all()
    
    def detect_all(self):
        """Perform comprehensive system detection."""
        self.system_info = {
            "os": self._detect_os(),
            "hardware": self._detect_hardware(),
            "software": self._detect_software(),
            "network": self._detect_network(),
            "recommendations": self._generate_recommendations()
        }
    
    def _detect_os(self):
        """Detect operating system information."""
        return {
            "name": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture()[0],
            "is_apple_silicon": platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64")
        }
    
    def _detect_hardware(self):
        """Detect hardware information."""
        # CPU
        cpu_info = {
            "cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "usage_percent": psutil.cpu_percent(interval=1)
        }
        
        # Memory
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": memory.total / (1024**3),
            "available_gb": memory.available / (1024**3),
            "used_gb": memory.used / (1024**3),
            "percent": memory.percent
        }
        
        # Storage
        disk = psutil.disk_usage('/')
        storage_info = {
            "total_gb": disk.total / (1024**3),
            "free_gb": disk.free / (1024**3),
            "used_gb": disk.used / (1024**3),
            "percent": (disk.used / disk.total) * 100
        }
        
        # GPU Detection
        gpu_info = self._detect_gpu()
        
        return {
            "cpu": cpu_info,
            "memory": memory_info,
            "storage": storage_info,
            "gpu": gpu_info
        }
    
    def _detect_gpu(self):
        """Detect GPU information."""
        gpu_info = {
            "available": False,
            "type": None,
            "name": None,
            "cuda_available": False,
            "neural_engine": False,
            "details": {}
        }
        
        system_name = platform.system()
        
        # NVIDIA GPU detection
        try:
            result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                gpu_info["available"] = True
                gpu_info["type"] = "NVIDIA"
                gpu_info["cuda_available"] = True
                gpu_info["name"] = lines[0].split(',')[0] if lines else "NVIDIA GPU"
                gpu_info["details"]["memory_mb"] = int(lines[0].split(',')[1]) if len(lines[0].split(',')) > 1 else None
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Apple Silicon GPU detection
        if not gpu_info["available"] and system_name == "Darwin":
            try:
                result = subprocess.run(["system_profiler", "SPDisplaysDataType"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    output = result.stdout
                    if "Apple" in output and any(chip in output for chip in ["M1", "M2", "M3", "M4", "M5"]):
                        lines = output.split('\n')
                        gpu_name = "Apple Silicon"
                        for line in lines:
                            if "Chipset Model:" in line:
                                gpu_name = line.split("Chipset Model:")[1].strip()
                                break
                        
                        gpu_info["available"] = True
                        gpu_info["type"] = "Apple Silicon"
                        gpu_info["name"] = gpu_name
                        gpu_info["neural_engine"] = "Neural Engine" in output
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
        
        return gpu_info
    
    def _detect_software(self):
        """Detect installed software."""
        software_info = {
            "python": {
                "version": platform.python_version(),
                "executable": sys.executable,
                "virtual_env": hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
            },
            "docker": self._check_docker(),
            "git": self._check_git(),
            "nodejs": self._check_nodejs(),
            "browser": self._check_browser()
        }
        
        return software_info
    
    def _check_docker(self):
        """Check Docker installation and status."""
        try:
            result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                
                # Check if Docker is running
                try:
                    info_result = subprocess.run(["docker", "info"], capture_output=True, text=True, timeout=10)
                    running = info_result.returncode == 0
                except:
                    running = False
                
                return {
                    "installed": True,
                    "version": version,
                    "running": running
                }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return {"installed": False, "version": None, "running": False}
    
    def _check_git(self):
        """Check Git installation."""
        try:
            result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {
                    "installed": True,
                    "version": result.stdout.strip()
                }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return {"installed": False, "version": None}
    
    def _check_nodejs(self):
        """Check Node.js installation."""
        try:
            result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                version = result.stdout.strip()
                
                # Check npm
                try:
                    npm_result = subprocess.run(["npm", "--version"], capture_output=True, text=True, timeout=10)
                    npm_version = npm_result.stdout.strip() if npm_result.returncode == 0 else None
                except:
                    npm_version = None
                
                return {
                    "installed": True,
                    "version": version,
                    "npm_version": npm_version
                }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return {"installed": False, "version": None, "npm_version": None}
    
    def _check_browser(self):
        """Check browser availability."""
        browsers = []
        
        if platform.system() == "Darwin":
            # macOS browsers
            browser_checks = [
                ("/Applications/Safari.app", "Safari"),
                ("/Applications/Google Chrome.app", "Chrome"),
                ("/Applications/Firefox.app", "Firefox")
            ]
        elif platform.system() == "Windows":
            # Windows browsers
            browser_checks = [
                ("C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "Chrome"),
                ("C:\\Program Files\\Mozilla Firefox\\firefox.exe", "Firefox"),
                ("C:\\Program Files\\Internet Explorer\\iexplore.exe", "Internet Explorer")
            ]
        else:
            # Linux browsers
            browser_checks = [
                ("/usr/bin/google-chrome", "Chrome"),
                ("/usr/bin/firefox", "Firefox"),
                ("/usr/bin/safari", "Safari")
            ]
        
        for path, name in browser_checks:
            if Path(path).exists():
                browsers.append(name)
        
        return browsers
    
    def _detect_network(self):
        """Detect network connectivity."""
        network_info = {
            "connected": False,
            "internet_accessible": False,
            "github_accessible": False,
            "docker_hub_accessible": False
        }
        
        try:
            # Check basic connectivity
            import urllib.request
            urllib.request.urlopen('https://www.google.com', timeout=5)
            network_info["connected"] = True
            network_info["internet_accessible"] = True
            
            # Check GitHub
            urllib.request.urlopen('https://github.com', timeout=5)
            network_info["github_accessible"] = True
            
            # Check Docker Hub
            urllib.request.urlopen('https://hub.docker.com', timeout=5)
            network_info["docker_hub_accessible"] = True
            
        except Exception:
            pass
        
        return network_info
    
    def _generate_recommendations(self):
        """Generate system recommendations."""
        recommendations = {
            "warnings": [],
            "suggestions": [],
            "requirements_met": True
        }
        
        # Memory check
        if self.system_info["hardware"]["memory"]["total_gb"] < 8:
            recommendations["warnings"].append("Less than 8GB RAM may impact performance")
            recommendations["requirements_met"] = False
        
        # Storage check
        if self.system_info["hardware"]["storage"]["free_gb"] < 20:
            recommendations["warnings"].append("Less than 20GB free storage may be insufficient")
            recommendations["requirements_met"] = False
        
        # Docker check
        if not self.system_info["software"]["docker"]["installed"]:
            recommendations["warnings"].append("Docker is required for containerized deployment")
            recommendations["requirements_met"] = False
        elif not self.system_info["software"]["docker"]["running"]:
            recommendations["warnings"].append("Docker is installed but not running")
        
        # GPU recommendations
        if not self.system_info["hardware"]["gpu"]["available"]:
            recommendations["suggestions"].append("Consider using a system with GPU for better ML performance")
        elif self.system_info["hardware"]["gpu"]["type"] == "Apple Silicon":
            recommendations["suggestions"].append("Apple Silicon GPU provides excellent ML performance")
        
        # Network check
        if not self.system_info["network"]["internet_accessible"]:
            recommendations["warnings"].append("Internet connection required for downloading dependencies")
            recommendations["requirements_met"] = False
        
        return recommendations

class SetupManager:
    """Manages the complete setup process with step-by-step execution."""
    
    def __init__(self):
        self.setup_config = {}
        self.setup_progress = {}
        self.current_step = 0
        self.total_steps = 10  # Total number of wizard steps
        
    def get_setup_config(self):
        """Get current setup configuration."""
        return self.setup_config
    
    def save_setup_config(self, config: Dict[str, Any]):
        """Save setup configuration."""
        self.setup_config.update(config)
        return True
    
    async def run_setup_step(self, step: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific setup step."""
        self.setup_config.update(config)
        
        step_methods = {
            "virtual_env": self._setup_virtual_environment,
            "dependencies": self._install_dependencies,
            "repository": self._clone_repository,
            "environment": self._setup_environment,
            "database": self._setup_database,
            "frontend": self._setup_frontend,
            "services": self._start_services,
            "ssl": self._setup_ssl,
            "data_initialization": self._initialize_data,
            "training_setup": self._setup_training_pipeline
        }
        
        if step not in step_methods:
            return {"success": False, "error": f"Unknown step: {step}"}
        
        try:
            self.setup_progress[step] = {"status": "running", "started_at": datetime.now().isoformat()}
            result = await step_methods[step](config)
            self.setup_progress[step].update(result)
            return result
        except Exception as e:
            self.setup_progress[step] = {"status": "error", "error": str(e)}
            return {"success": False, "error": str(e)}
    
    async def _setup_virtual_environment(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup Python virtual environment."""
        install_dir = config.get("install_dir", "/opt/qgen")
        venv_path = Path(install_dir) / "venv"
        
        try:
            # Create installation directory if it doesn't exist
            Path(install_dir).mkdir(parents=True, exist_ok=True)
            
            # Create virtual environment
            if not venv_path.exists():
                subprocess.run([sys.executable, "-m", "venv", str(venv_path)], 
                             check=True, capture_output=True, text=True)
            
            # Install requirements in virtual environment
            python_exe = venv_path / "bin" / "python" if platform.system() != "Windows" else venv_path / "Scripts" / "python.exe"
            
            requirements = [
                "fastapi>=0.104.1",
                "uvicorn>=0.24.0",
                "jinja2>=3.1.2",
                "aiofiles>=23.2.1",
                "psutil>=5.9.6",
                "sqlalchemy>=2.0.0",
                "alembic>=1.12.0",
                "asyncpg>=0.29.0",
                "redis>=5.0.0",
                "python-multipart>=0.0.6",
                "python-jose[cryptography]>=3.3.0",
                "passlib[bcrypt]>=1.7.4",
                "python-dotenv>=1.0.0",
                "httpx>=0.25.0",
                "transformers>=4.35.0",
                "torch>=2.1.0",
                "sentence-transformers>=2.2.0",
                "numpy>=1.24.0",
                "pandas>=2.1.0"
            ]
            
            for req in requirements:
                subprocess.run([str(python_exe), "-m", "pip", "install", req], 
                             check=True, capture_output=True, text=True, timeout=120)
            
            return {
                "success": True,
                "message": f"Virtual environment created at {venv_path}",
                "python_executable": str(python_exe)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _install_dependencies(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Install system dependencies."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            system_name = platform.system()
            installed_packages = []
            
            if system_name == "Darwin":
                # macOS dependencies via Homebrew
                packages = ["docker", "git", "node", "postgresql", "redis"]
                for package in packages:
                    try:
                        subprocess.run(["brew", "install", package], check=True, timeout=300)
                        installed_packages.append(package)
                    except subprocess.CalledProcessError:
                        pass  # Package might already be installed
            
            elif system_name == "Linux":
                # Linux dependencies
                pm = self._detect_package_manager()
                if pm == "apt":
                    packages = ["docker.io", "git", "nodejs", "npm", "postgresql", "redis-server"]
                    for package in packages:
                        try:
                            subprocess.run(["sudo", "apt", "install", "-y", package], check=True, timeout=300)
                            installed_packages.append(package)
                        except subprocess.CalledProcessError:
                            pass
            
            return {
                "success": True,
                "message": f"Installed system dependencies: {', '.join(installed_packages)}",
                "installed_packages": installed_packages
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _detect_package_manager(self):
        """Detect Linux package manager."""
        try:
            subprocess.run(["apt", "--version"], capture_output=True, timeout=5)
            return "apt"
        except:
            pass
        
        try:
            subprocess.run(["yum", "--version"], capture_output=True, timeout=5)
            return "yum"
        except:
            pass
        
        return "unknown"
    
    async def _clone_repository(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Clone the QGen RAG repository."""
        install_dir = config.get("install_dir", "/opt/qgen")
        repo_url = config.get("repository_url", "https://github.com/your-org/qgen_rag.git")
        
        try:
            # Clone repository
            if not Path(install_dir).joinpath(".git").exists():
                subprocess.run(["git", "clone", repo_url, install_dir], 
                             check=True, capture_output=True, text=True, timeout=300)
            else:
                # Pull latest changes
                subprocess.run(["git", "pull"], cwd=install_dir, 
                             check=True, capture_output=True, text=True, timeout=120)
            
            return {
                "success": True,
                "message": f"Repository cloned/updated at {install_dir}",
                "repository_path": install_dir
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_environment(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup environment configuration."""
        install_dir = config.get("install_dir", "/opt/qgen")
        domain = config.get("domain", "localhost")
        
        try:
            # Create .env file
            env_content = f"""# QGen RAG Environment Configuration
# Generated on {datetime.now().isoformat()}

# Database Configuration
DATABASE_URL=postgresql+asyncpg://qgen_user:qgen_password@localhost:5432/qgen_rag
REDIS_URL=redis://localhost:6379/0

# Application Configuration
SECRET_KEY={uuid.uuid4().hex}
DOMAIN={domain}
ENVIRONMENT={config.get('environment', 'production')}

# API Keys
OPENAI_API_KEY={config.get('openai_api_key', '')}
DEEPSEEK_API_KEY={config.get('deepseek_api_key', '')}

# Model Configuration
BASE_MODEL={config.get('base_model', 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B')}
MODEL_CACHE_DIR={install_dir}/models

# Training Configuration
TRAINING_DATA_DIR={install_dir}/training_data
LORA_ADAPTERS_DIR={install_dir}/lora_adapters
BATCH_SIZE=4
MAX_BATCH_SIZE=8
LEARNING_RATE=2e-4

# SSL Configuration
SSL_EMAIL={config.get('ssl_email', 'admin@example.com')}
SSL_CERT_DIR={install_dir}/ssl

# Logging
LOG_LEVEL=INFO
LOG_FILE={install_dir}/logs/qgen.log
"""
            
            env_file = Path(install_dir) / ".env"
            env_file.write_text(env_content)
            
            # Create necessary directories
            directories = [
                "models",
                "training_data", 
                "lora_adapters",
                "logs",
                "ssl",
                "uploads"
            ]
            
            for dir_name in directories:
                (Path(install_dir) / dir_name).mkdir(exist_ok=True)
            
            return {
                "success": True,
                "message": "Environment configuration created",
                "env_file": str(env_file)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_database(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup PostgreSQL database."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Start PostgreSQL and Redis using Docker
            docker_compose_content = f"""version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: qgen_postgres
    environment:
      POSTGRES_DB: qgen_rag
      POSTGRES_USER: qgen_user
      POSTGRES_PASSWORD: qgen_password
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    ports:
      - "5432:5432"
    networks:
      - qgen_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U qgen_user -d qgen_rag"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: qgen_redis
    command: redis-server --appendonly yes --requirepass redis_password
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    networks:
      - qgen_network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  postgres_data:
  redis_data:

networks:
  qgen_network:
    driver: bridge
"""
            
            docker_compose_file = Path(install_dir) / "docker-compose.yml"
            docker_compose_file.write_text(docker_compose_content)
            
            # Start services
            subprocess.run(["docker-compose", "up", "-d"], cwd=install_dir, 
                         check=True, capture_output=True, text=True, timeout=120)
            
            # Wait for database to be ready
            import time
            time.sleep(30)
            
            # Run database migrations
            venv_python = Path(install_dir) / "venv" / "bin" / "python"
            if platform.system() == "Windows":
                venv_python = Path(install_dir) / "venv" / "Scripts" / "python.exe"
            
            subprocess.run([str(venv_python), "-m", "alembic", "upgrade", "head"], 
                         cwd=Path(install_dir) / "backend", check=True, capture_output=True, text=True, timeout=120)
            
            return {
                "success": True,
                "message": "Database setup completed",
                "services": ["PostgreSQL", "Redis"]
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_frontend(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup frontend trainer-web application."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            trainer_web_dir = Path(install_dir) / "trainer-web"
            
            if not trainer_web_dir.exists():
                return {"success": False, "error": "trainer-web directory not found"}
            
            # Install Node.js dependencies
            subprocess.run(["npm", "install"], cwd=trainer_web_dir, 
                         check=True, capture_output=True, text=True, timeout=300)
            
            # Build frontend
            subprocess.run(["npm", "run", "build"], cwd=trainer_web_dir, 
                         check=True, capture_output=True, text=True, timeout=300)
            
            return {
                "success": True,
                "message": "Frontend setup completed",
                "frontend_path": str(trainer_web_dir)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_services(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start all services."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Start backend service
            backend_service_content = f"""version: '3.8'

services:
  backend:
    build: ./backend
    container_name: qgen_backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://qgen_user:qgen_password@postgres:5432/qgen_rag
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY={uuid.uuid4().hex}
      - DOMAIN={config.get('domain', 'localhost')}
    ports:
      - "8000:8000"
    networks:
      - qgen_network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  frontend:
    build: ./trainer-web
    container_name: qgen_frontend
    environment:
      - PUBLIC_API_URL=http://localhost:8000
      - PUBLIC_WS_URL=ws://localhost:8000
    ports:
      - "5173:5173"
    networks:
      - qgen_network
    depends_on:
      - backend
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5173"]
      interval: 30s
      timeout: 10s
      retries: 3

  training_worker:
    build: ./backend
    container_name: qgen_training_worker
    command: python -m app.workers.training_worker
    environment:
      - DATABASE_URL=postgresql+asyncpg://qgen_user:qgen_password@postgres:5432/qgen_rag
      - REDIS_URL=redis://redis:6379/0
      - MODEL_CACHE_DIR=/app/models
      - TRAINING_DATA_DIR=/app/training_data
      - LORA_ADAPTERS_DIR=/app/lora_adapters
    volumes:
      - ./models:/app/models
      - ./training_data:/app/training_data
      - ./lora_adapters:/app/lora_adapters
      - ./logs:/app/logs
    networks:
      - qgen_network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
"""
            
            services_file = Path(install_dir) / "docker-compose.services.yml"
            services_file.write_text(backend_service_content)
            
            # Start services
            subprocess.run(["docker-compose", "-f", "docker-compose.yml", "-f", "docker-compose.services.yml", "up", "-d"], 
                         cwd=install_dir, check=True, capture_output=True, text=True, timeout=180)
            
            # Wait for services to be ready
            import time
            time.sleep(45)
            
            return {
                "success": True,
                "message": "All services started successfully",
                "services": {
                    "backend": f"http://{config.get('domain', 'localhost')}:8000",
                    "frontend": f"http://{config.get('domain', 'localhost')}:5173",
                    "api_docs": f"http://{config.get('domain', 'localhost')}:8000/docs"
                }
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_ssl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup SSL certificates."""
        install_dir = config.get("install_dir", "/opt/qgen")
        domain = config.get("domain", "localhost")
        ssl_email = config.get("ssl_email", "admin@example.com")
        
        try:
            if domain == "localhost":
                # Generate self-signed certificate for localhost
                ssl_dir = Path(install_dir) / "ssl"
                ssl_dir.mkdir(exist_ok=True)
                
                # Generate private key
                subprocess.run([
                    "openssl", "genrsa", "-out", "key.pem", "2048"
                ], cwd=ssl_dir, check=True, capture_output=True, text=True, timeout=60)
                
                # Generate certificate
                subprocess.run([
                    "openssl", "req", "-new", "-x509", "-key", "key.pem", 
                    "-out", "cert.pem", "-days", "365",
                    "-subj", f"/C=US/ST=State/L=City/O=Organization/CN={domain}"
                ], cwd=ssl_dir, check=True, capture_output=True, text=True, timeout=60)
                
                return {
                    "success": True,
                    "message": "Self-signed SSL certificate generated",
                    "certificate_path": str(ssl_dir / "cert.pem"),
                    "key_path": str(ssl_dir / "key.pem")
                }
            else:
                # Setup Let's Encrypt for production domains
                return {
                    "success": True,
                    "message": f"SSL setup instructions for {domain}",
                    "instructions": [
                        f"1. Point DNS for {domain} to this server",
                        f"2. Run: certbot --nginx -d {domain}",
                        f"3. Contact email: {ssl_email}"
                    ]
                }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _initialize_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize sample data."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            venv_python = Path(install_dir) / "venv" / "bin" / "python"
            if platform.system() == "Windows":
                venv_python = Path(install_dir) / "venv" / "Scripts" / "python.exe"
            
            # Run data initialization script
            result = subprocess.run([
                str(venv_python), "scripts/init_data_collection.py"
            ], cwd=install_dir, capture_output=True, text=True, timeout=300)
            
            return {
                "success": result.returncode == 0,
                "message": "Data initialization completed",
                "output": result.stdout,
                "error": result.stderr if result.returncode != 0 else None
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_training_pipeline(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup training pipeline configuration."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Create training configuration
            training_config = {
                "model_config": {
                    "base_model": config.get("base_model", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"),
                    "max_sequence_length": 4096,
                    "torch_dtype": "float16",
                    "device_map": "auto"
                },
                "training_config": {
                    "batch_size": 4,
                    "gradient_accumulation_steps": 8,
                    "learning_rate": 2e-4,
                    "num_epochs": 3,
                    "warmup_steps": 100,
                    "save_steps": 500,
                    "eval_steps": 500,
                    "logging_steps": 10
                },
                "lora_config": {
                    "r": 16,
                    "lora_alpha": 32,
                    "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
                    "lora_dropout": 0.1,
                    "bias": "none",
                    "task_type": "CAUSAL_LM"
                },
                "data_config": {
                    "train_test_split": 0.8,
                    "max_samples_per_subject": 1000,
                    "quality_threshold": 0.7,
                    "diversity_threshold": 0.6
                },
                "evaluation_config": {
                    "metrics": ["accuracy", "f1", "bleu", "rouge"],
                    "evaluation_frequency": "epoch",
                    "save_best_model": True,
                    "early_stopping_patience": 3
                }
            }
            
            config_file = Path(install_dir) / "training_config.json"
            config_file.write_text(json.dumps(training_config, indent=2))
            
            return {
                "success": True,
                "message": "Training pipeline configuration created",
                "config_file": str(config_file),
                "training_config": training_config
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}

# FastAPI Application
app = FastAPI(title="QGen RAG Complete Setup Wizard", version="2.0.0")

# Templates
templates = Jinja2Templates(directory="templates")

# Global instances
detector = SystemDetector()
setup_manager = SetupManager()

# Wizard step definitions
WIZARD_STEPS = [
    {
        "id": "welcome",
        "title": "Welcome",
        "description": "Introduction to QGen RAG Setup Wizard",
        "icon": "🚀"
    },
    {
        "id": "system_check",
        "title": "System Requirements",
        "description": "Verify system meets requirements",
        "icon": "🔍"
    },
    {
        "id": "virtual_env",
        "title": "Virtual Environment",
        "description": "Setup Python virtual environment",
        "icon": "🐍"
    },
    {
        "id": "dependencies",
        "title": "Dependencies",
        "description": "Install system dependencies",
        "icon": "📦"
    },
    {
        "id": "repository",
        "title": "Source Code",
        "description": "Clone QGen RAG repository",
        "icon": "📥"
    },
    {
        "id": "environment",
        "title": "Environment Configuration",
        "description": "Configure application settings",
        "icon": "⚙️"
    },
    {
        "id": "database",
        "title": "Database Setup",
        "description": "Setup PostgreSQL and Redis",
        "icon": "🗄️"
    },
    {
        "id": "frontend",
        "title": "Frontend Setup",
        "description": "Setup trainer-web application",
        "icon": "🎨"
    },
    {
        "id": "services",
        "title": "Services",
        "description": "Start all application services",
        "icon": "🚀"
    },
    {
        "id": "ssl",
        "title": "SSL Configuration",
        "description": "Setup SSL certificates",
        "icon": "🔒"
    },
    {
        "id": "data_initialization",
        "title": "Data Initialization",
        "description": "Initialize sample data",
        "icon": "📊"
    },
    {
        "id": "training_setup",
        "title": "Training Pipeline",
        "description": "Configure ML training pipeline",
        "icon": "🤖"
    },
    {
        "id": "completion",
        "title": "Setup Complete",
        "description": "Review and access your application",
        "icon": "✅"
    }
]

@app.get("/", response_class=HTMLResponse)
async def wizard_home(request: Request):
    """Main wizard page."""
    return HTMLResponse(COMPLETE_WIZARD_TEMPLATE)

@app.get("/api/system-info")
async def get_system_info():
    """Get system information."""
    return detector.system_info

@app.get("/api/setup-config")
async def get_setup_config():
    """Get setup configuration."""
    return setup_manager.get_setup_config()

@app.post("/api/setup-config")
async def save_setup_config(config: Dict[str, Any]):
    """Save setup configuration."""
    success = setup_manager.save_setup_config(config)
    return {"success": success}

@app.post("/api/setup-step/{step}")
async def run_setup_step(step: str, config: Dict[str, Any]):
    """Run a setup step."""
    result = await setup_manager.run_setup_step(step, config)
    return result

@app.get("/api/setup-progress")
async def get_setup_progress():
    """Get setup progress."""
    return setup_manager.setup_progress

# Complete HTML Template with Multi-Page Wizard
COMPLETE_WIZARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QGen RAG Complete Setup Wizard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <script src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js" defer></script>
    <style>
        .step-card { @apply bg-white rounded-lg shadow-md p-6 mb-4; }
        .step-active { @apply border-l-4 border-blue-500 bg-blue-50; }
        .step-completed { @apply border-l-4 border-green-500 bg-green-50; }
        .step-error { @apply border-l-4 border-red-500 bg-red-50; }
        .progress-bar { @apply bg-blue-500 h-2 rounded-full transition-all duration-500; }
        .wizard-container { @apply max-w-4xl mx-auto; }
        .step-navigation { @apply flex justify-between items-center mt-6; }
        .feature-card { @apply bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200; }
        .system-info-card { @apply bg-gray-50 rounded-lg p-4 border border-gray-200; }
    </style>
</head>
<body class="bg-gray-100" x-data="wizardApp()">
    <div class="min-h-screen py-8">
        <!-- Header -->
        <header class="text-center mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">🚀 QGen RAG Setup Wizard</h1>
            <p class="text-gray-600">Complete setup for your SLM/LLM training system</p>
        </header>

        <!-- Progress Bar -->
        <div class="wizard-container mb-8">
            <div class="bg-white rounded-lg shadow-md p-4">
                <div class="flex justify-between items-center mb-2">
                    <span class="text-sm font-medium text-gray-700">Setup Progress</span>
                    <span class="text-sm font-medium text-gray-700" x-text="`${currentStepIndex + 1} of ${totalSteps}`"></span>
                </div>
                <div class="w-full bg-gray-200 rounded-full h-2">
                    <div class="progress-bar" :style="`width: ${(currentStepIndex / (totalSteps - 1)) * 100}%`"></div>
                </div>
            </div>
        </div>

        <!-- Step Navigation -->
        <div class="wizard-container mb-6">
            <div class="bg-white rounded-lg shadow-md p-4">
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2">
                    <template x-for="(step, index) in steps" :key="step.id">
                        <button 
                            @click="goToStep(index)"
                            :class="{
                                'step-completed': index < currentStepIndex,
                                'step-active': index === currentStepIndex,
                                'opacity-50 cursor-not-allowed': index > currentStepIndex + 1
                            }"
                            class="p-2 rounded text-center text-sm font-medium transition-all"
                            :disabled="index > currentStepIndex + 1">
                            <div x-text="step.icon" class="text-lg mb-1"></div>
                            <div x-text="step.title" class="hidden md:block"></div>
                        </button>
                    </template>
                </div>
            </div>
        </div>

        <!-- Current Step Content -->
        <div class="wizard-container">
            <div class="step-card">
                <!-- Welcome Step -->
                <div x-show="currentStep.id === 'welcome'" class="space-y-6">
                    <div class="text-center">
                        <h2 class="text-3xl font-bold text-gray-800 mb-4">Welcome to QGen RAG</h2>
                        <p class="text-lg text-gray-600 mb-6">Your complete SLM/LLM training system setup wizard</p>
                    </div>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        <div class="feature-card">
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">🤖 AI-Powered</h3>
                            <p class="text-gray-600">State-of-the-art language models for question generation</p>
                        </div>
                        <div class="feature-card">
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">📚 Educational Focus</h3>
                            <p class="text-gray-600">Designed specifically for educational content creation</p>
                        </div>
                        <div class="feature-card">
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">🎯 Quality Assured</h3>
                            <p class="text-gray-600">Built-in vetting and quality control systems</p>
                        </div>
                        <div class="feature-card">
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">🚀 Easy Setup</h3>
                            <p class="text-gray-600">Automated installation and configuration</p>
                        </div>
                        <div class="feature-card">
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">📊 Analytics</h3>
                            <p class="text-gray-600">Comprehensive tracking and reporting</p>
                        </div>
                        <div class="feature-card">
                            <h3 class="text-xl font-semibold text-gray-800 mb-2">🔒 Secure</h3>
                            <p class="text-gray-600">Enterprise-grade security and data protection</p>
                        </div>
                    </div>
                    
                    <div class="bg-blue-50 border-l-4 border-blue-400 p-4">
                        <h3 class="font-semibold text-blue-800 mb-2">What This Wizard Will Do</h3>
                        <ul class="list-disc list-inside text-blue-700 space-y-1">
                            <li>Check system requirements and compatibility</li>
                            <li>Setup Python virtual environment</li>
                            <li>Install all necessary dependencies</li>
                            <li>Configure database and services</li>
                            <li>Setup frontend and backend applications</li>
                            <li>Initialize training data and pipeline</li>
                            <li>Configure SSL and security</li>
                        </ul>
                    </div>
                </div>

                <!-- System Requirements Step -->
                <div x-show="currentStep.id === 'system_check'" class="space-y-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">🔍 System Requirements Check</h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Operating System</h3>
                            <p class="text-sm text-gray-600" x-text="systemInfo.os.name + ' ' + systemInfo.os.version"></p>
                        </div>
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Hardware</h3>
                            <p class="text-sm text-gray-600" x-text="`${systemInfo.hardware.cpu.cores} cores, ${systemInfo.hardware.memory.total_gb.toFixed(1)}GB RAM`"></p>
                        </div>
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">GPU</h3>
                            <p class="text-sm text-gray-600">
                                <template x-if="systemInfo.hardware.gpu.available">
                                    <span x-text="systemInfo.hardware.gpu.name"></span>
                                </template>
                                <template x-if="!systemInfo.hardware.gpu.available">
                                    <span>No GPU detected</span>
                                </template>
                            </p>
                        </div>
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Storage</h3>
                            <p class="text-sm text-gray-600" x-text="`${systemInfo.hardware.storage.free_gb.toFixed(1)}GB free`"></p>
                        </div>
                    </div>
                    
                    <div class="space-y-4">
                        <template x-if="systemInfo.recommendations.warnings.length > 0">
                            <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4">
                                <h3 class="font-semibold text-yellow-800 mb-2">⚠️ Warnings</h3>
                                <ul class="list-disc list-inside text-yellow-700">
                                    <template x-for="warning in systemInfo.recommendations.warnings">
                                        <li x-text="warning"></li>
                                    </template>
                                </ul>
                            </div>
                        </template>
                        
                        <template x-if="systemInfo.recommendations.suggestions.length > 0">
                            <div class="bg-blue-50 border-l-4 border-blue-400 p-4">
                                <h3 class="font-semibold text-blue-800 mb-2">💡 Suggestions</h3>
                                <ul class="list-disc list-inside text-blue-700">
                                    <template x-for="suggestion in systemInfo.recommendations.suggestions">
                                        <li x-text="suggestion"></li>
                                    </template>
                                </ul>
                            </div>
                        </template>
                    </div>
                </div>

                <!-- Configuration Steps (Virtual Environment, Dependencies, etc.) -->
                <div x-show="['virtual_env', 'dependencies', 'repository', 'environment', 'database', 'frontend', 'services', 'ssl', 'data_initialization', 'training_setup'].includes(currentStep.id)" class="space-y-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4" x-text="currentStep.icon + ' ' + currentStep.title"></h2>
                    <p class="text-gray-600 mb-4" x-text="currentStep.description"></p>
                    
                    <!-- Configuration Form -->
                    <form x-show="currentStep.id === 'environment'" @submit.prevent="saveConfig" class="space-y-4">
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Installation Directory</label>
                                <input type="text" x-model="config.install_dir" value="/opt/qgen" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Domain</label>
                                <input type="text" x-model="config.domain" value="localhost" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">SSL Email</label>
                                <input type="email" x-model="config.ssl_email" value="admin@example.com" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Environment</label>
                                <select x-model="config.environment" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="production">Production</option>
                                    <option value="development">Development</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">OpenAI API Key</label>
                                <input type="password" x-model="config.openai_api_key" placeholder="sk-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">DeepSeek API Key</label>
                                <input type="password" x-model="config.deepseek_api_key" placeholder="sk-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Repository URL</label>
                                <input type="url" x-model="config.repository_url" value="https://github.com/your-org/qgen_rag.git" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Base Model</label>
                                <select x-model="config.base_model" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="deepseek-ai/DeepSeek-R1-Distill-Llama-8B">DeepSeek-R1-8B (Recommended)</option>
                                    <option value="deepseek-ai/DeepSeek-R1-Distill-Llama-70B">DeepSeek-R1-70B (Large)</option>
                                </select>
                            </div>
                        </div>
                        <button type="submit" class="bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 transition-colors">
                            Save Configuration
                        </button>
                    </form>
                    
                    <!-- Step Execution -->
                    <div x-show="!stepExecuted && currentStep.id !== 'environment'">
                        <button @click="executeStep(currentStep.id)" class="w-full bg-blue-500 text-white py-3 px-4 rounded-md hover:bg-blue-600 transition-colors font-medium">
                            Execute <span x-text="currentStep.title"></span>
                        </button>
                    </div>
                    
                    <!-- Step Progress -->
                    <div x-show="stepExecuting" class="space-y-4">
                        <div class="bg-blue-50 border-l-4 border-blue-400 p-4">
                            <h3 class="font-semibold text-blue-800">Executing...</h3>
                            <div class="mt-2">
                                <div class="bg-blue-200 rounded-full h-2">
                                    <div class="progress-bar" style="width: 60%"></div>
                                </div>
                            </div>
                        </div>
                        <div class="bg-gray-900 text-green-400 p-4 rounded text-sm font-mono max-h-64 overflow-y-auto">
                            <div x-text="stepOutput"></div>
                        </div>
                    </div>
                    
                    <!-- Step Result -->
                    <div x-show="stepExecuted && !stepExecuting" class="space-y-4">
                        <div class="bg-green-50 border-l-4 border-green-400 p-4">
                            <h3 class="font-semibold text-green-800">✅ Step Completed Successfully</h3>
                            <p class="text-green-700 mt-2" x-text="stepResult.message"></p>
                        </div>
                    </div>
                </div>

                <!-- Completion Step -->
                <div x-show="currentStep.id === 'completion'" class="space-y-6">
                    <div class="text-center">
                        <h2 class="text-3xl font-bold text-gray-800 mb-4">🎉 Setup Complete!</h2>
                        <p class="text-lg text-gray-600 mb-6">Your QGen RAG system is ready to use</p>
                    </div>
                    
                    <div class="bg-green-50 border-l-4 border-green-400 p-6">
                        <h3 class="font-semibold text-green-800 mb-4">Access Your Application</h3>
                        <div class="space-y-2">
                            <div>
                                <strong>🎨 Frontend:</strong> 
                                <a :href="`http://${config.domain}:5173`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:5173`"></a>
                            </div>
                            <div>
                                <strong>🔧 Backend API:</strong> 
                                <a :href="`http://${config.domain}:8000`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:8000`"></a>
                            </div>
                            <div>
                                <strong>📚 API Documentation:</strong> 
                                <a :href="`http://${config.domain}:8000/docs`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:8000/docs`"></a>
                            </div>
                            <div>
                                <strong>👤 Admin Panel:</strong> 
                                <a :href="`http://${config.domain}:5173/admin`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:5173/admin`"></a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-blue-50 border-l-4 border-blue-400 p-6">
                        <h3 class="font-semibold text-blue-800 mb-4">Next Steps</h3>
                        <ol class="list-decimal list-inside text-blue-700 space-y-2">
                            <li>Create admin and user accounts</li>
                            <li>Upload reference documents</li>
                            <li>Start generating questions</li>
                            <li>Begin vetting process</li>
                            <li>Monitor system performance</li>
                            <li>Train custom models</li>
                        </ol>
                    </div>
                    
                    <div class="text-center">
                        <button @click="openApplication" class="bg-blue-500 text-white py-3 px-6 rounded-md hover:bg-blue-600 transition-colors font-medium">
                            🚀 Launch Application
                        </button>
                    </div>
                </div>
            </div>

            <!-- Step Navigation -->
            <div class="step-navigation">
                <button 
                    @click="previousStep" 
                    :disabled="currentStepIndex === 0"
                    class="bg-gray-500 text-white py-2 px-4 rounded-md hover:bg-gray-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    ← Previous
                </button>
                
                <button 
                    @click="nextStep" 
                    :disabled="currentStepIndex === totalSteps - 1"
                    class="bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                    Next →
                </button>
            </div>
        </div>
    </div>

    <script>
        function wizardApp() {
            return {
                steps: [
                    {"id": "welcome", "title": "Welcome", "description": "Introduction to QGen RAG Setup Wizard", "icon": "🚀"},
                    {"id": "system_check", "title": "System Requirements", "description": "Verify system meets requirements", "icon": "🔍"},
                    {"id": "virtual_env", "title": "Virtual Environment", "description": "Setup Python virtual environment", "icon": "🐍"},
                    {"id": "dependencies", "title": "Dependencies", "description": "Install system dependencies", "icon": "📦"},
                    {"id": "repository", "title": "Source Code", "description": "Clone QGen RAG repository", "icon": "📥"},
                    {"id": "environment", "title": "Environment Configuration", "description": "Configure application settings", "icon": "⚙️"},
                    {"id": "database", "title": "Database Setup", "description": "Setup PostgreSQL and Redis", "icon": "🗄️"},
                    {"id": "frontend", "title": "Frontend Setup", "description": "Setup trainer-web application", "icon": "🎨"},
                    {"id": "services", "title": "Services", "description": "Start all application services", "icon": "🚀"},
                    {"id": "ssl", "title": "SSL Configuration", "description": "Setup SSL certificates", "icon": "🔒"},
                    {"id": "data_initialization", "title": "Data Initialization", "description": "Initialize sample data", "icon": "📊"},
                    {"id": "training_setup", "title": "Training Pipeline", "description": "Configure ML training pipeline", "icon": "🤖"},
                    {"id": "completion", "title": "Setup Complete", "description": "Review and access your application", "icon": "✅"}
                ],
                currentStepIndex: 0,
                systemInfo: {},
                config: {
                    install_dir: '/opt/qgen',
                    domain: 'localhost',
                    ssl_email: 'admin@example.com',
                    environment: 'production',
                    openai_api_key: '',
                    deepseek_api_key: '',
                    repository_url: 'https://github.com/your-org/qgen_rag.git',
                    base_model: 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B'
                },
                stepExecuting: false,
                stepExecuted: false,
                stepOutput: '',
                stepResult: {},
                
                get currentStep() {
                    return this.steps[this.currentStepIndex];
                },
                
                get totalSteps() {
                    return this.steps.length;
                },
                
                init() {
                    this.loadSystemInfo();
                    this.loadConfig();
                },
                
                async loadSystemInfo() {
                    try {
                        const response = await fetch('/api/system-info');
                        this.systemInfo = await response.json();
                    } catch (error) {
                        console.error('Failed to load system info:', error);
                    }
                },
                
                async loadConfig() {
                    try {
                        const response = await fetch('/api/setup-config');
                        const config = await response.json();
                        this.config = { ...this.config, ...config };
                    } catch (error) {
                        console.error('Failed to load config:', error);
                    }
                },
                
                async saveConfig() {
                    try {
                        const response = await fetch('/api/setup-config', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(this.config)
                        });
                        
                        if (response.ok) {
                            this.nextStep();
                        }
                    } catch (error) {
                        console.error('Failed to save config:', error);
                    }
                },
                
                goToStep(index) {
                    if (index <= this.currentStepIndex + 1) {
                        this.currentStepIndex = index;
                        this.stepExecuted = false;
                        this.stepOutput = '';
                    }
                },
                
                nextStep() {
                    if (this.currentStepIndex < this.totalSteps - 1) {
                        this.currentStepIndex++;
                        this.stepExecuted = false;
                        this.stepOutput = '';
                    }
                },
                
                previousStep() {
                    if (this.currentStepIndex > 0) {
                        this.currentStepIndex--;
                        this.stepExecuted = false;
                        this.stepOutput = '';
                    }
                },
                
                async executeStep(stepId) {
                    this.stepExecuting = true;
                    this.stepOutput = 'Starting execution...\\n';
                    
                    try {
                        const response = await fetch(`/api/setup-step/${stepId}`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(this.config)
                        });
                        
                        const result = await response.json();
                        
                        if (result.success) {
                            this.stepOutput += '✅ ' + result.message + '\\n';
                            this.stepResult = result;
                            this.stepExecuted = true;
                        } else {
                            this.stepOutput += '❌ Error: ' + result.error + '\\n';
                        }
                    } catch (error) {
                        this.stepOutput += '❌ Network error: ' + error.message + '\\n';
                    } finally {
                        this.stepExecuting = false;
                    }
                },
                
                openApplication() {
                    window.open(`http://${this.config.domain}:5173`, '_blank');
                }
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.environ.get("SETUP_PORT", 8080))
    
    print(f"🌐 Starting QGen RAG Complete Setup Wizard on port {port}")
    print(f"📋 Open your browser and go to: http://localhost:{port}")
    print("⚠️  Press Ctrl+C to stop the setup server")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
