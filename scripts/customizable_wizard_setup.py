#!/usr/bin/env python3
"""
Complete Multi-Page Setup Wizard for QGen RAG System

Comprehensive installation wizard with full customization options for
deployment modes, services, and configuration.
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
            "postgresql": self._check_postgresql(),
            "redis": self._check_redis(),
            "nginx": self._check_nginx()
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
    
    def _check_postgresql(self):
        """Check PostgreSQL installation."""
        try:
            result = subprocess.run(["psql", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {
                    "installed": True,
                    "version": result.stdout.strip()
                }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return {"installed": False, "version": None}
    
    def _check_redis(self):
        """Check Redis installation."""
        try:
            result = subprocess.run(["redis-server", "--version"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {
                    "installed": True,
                    "version": result.stdout.strip()
                }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return {"installed": False, "version": None}
    
    def _check_nginx(self):
        """Check Nginx installation."""
        try:
            result = subprocess.run(["nginx", "-v"], capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                return {
                    "installed": True,
                    "version": result.stdout.strip()
                }
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return {"installed": False, "version": None}
    
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
                packages = ["docker", "git", "node", "postgresql", "redis", "nginx"]
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
                    packages = ["docker.io", "git", "nodejs", "npm", "postgresql", "redis-server", "nginx"]
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
        """Setup environment configuration with full customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Backend .env file
            backend_env_content = f"""# QGen RAG Backend Environment Configuration
# Generated on {datetime.now().isoformat()}

# Database Configuration
DATABASE_URL={config.get('database_url', 'postgresql+asyncpg://qgen_user:qgen_password@localhost:5432/qgen_rag')}
REDIS_URL={config.get('redis_url', 'redis://localhost:6379/0')}

# Application Configuration
SECRET_KEY={config.get('secret_key', uuid.uuid4().hex)}
DOMAIN={config.get('domain', 'localhost')}
ENVIRONMENT={config.get('environment', 'production')}
DEBUG={config.get('debug', 'false')}
LOG_LEVEL={config.get('log_level', 'INFO')}

# API Configuration
API_V1_PREFIX={config.get('api_v1_prefix', '/api/v1')}
CORS_ORIGINS={config.get('cors_origins', '["http://localhost:5173", "http://localhost:3000"]')}
MAX_REQUEST_SIZE={config.get('max_request_size', '16MB')}

# Security Configuration
ACCESS_TOKEN_EXPIRE_MINUTES={config.get('access_token_expire_minutes', 30)}
REFRESH_TOKEN_EXPIRE_DAYS={config.get('refresh_token_expire_days', 7)}
ALGORITHM={config.get('algorithm', 'HS256')}

# External API Keys
OPENAI_API_KEY={config.get('openai_api_key', '')}
DEEPSEEK_API_KEY={config.get('deepseek_api_key', '')}
ANTHROPIC_API_KEY={config.get('anthropic_api_key', '')}

# Model Configuration
BASE_MODEL={config.get('base_model', 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B')}
MODEL_CACHE_DIR={config.get('model_cache_dir', f'{install_dir}/models')}
DEFAULT_MAX_TOKENS={config.get('default_max_tokens', '4096')}
DEFAULT_TEMPERATURE={config.get('default_temperature', '0.7')}

# Training Configuration
TRAINING_DATA_DIR={config.get('training_data_dir', f'{install_dir}/training_data')}
LORA_ADAPTERS_DIR={config.get('lora_adapters_dir', f'{install_dir}/lora_adapters')}
BATCH_SIZE={config.get('batch_size', '4')}
MAX_BATCH_SIZE={config.get('max_batch_size', '8')}
LEARNING_RATE={config.get('learning_rate', '2e-4')}
GRADIENT_ACCUMULATION_STEPS={config.get('gradient_accumulation_steps', '8')}

# File Upload Configuration
UPLOAD_DIR={config.get('upload_dir', f'{install_dir}/uploads')}
MAX_FILE_SIZE={config.get('max_file_size', '50MB')}
ALLOWED_EXTENSIONS={config.get('allowed_extensions', '["pdf", "docx", "txt", "csv", "xlsx"]')}

# Monitoring Configuration
ENABLE_METRICS={config.get('enable_metrics', 'true')}
METRICS_PORT={config.get('metrics_port', '9090')}
SENTRY_DSN={config.get('sentry_dsn', '')}

# SSL Configuration
SSL_CERT_PATH={config.get('ssl_cert_path', f'{install_dir}/ssl/cert.pem')}
SSL_KEY_PATH={config.get('ssl_key_path', f'{install_dir}/ssl/key.pem')}
FORCE_HTTPS={config.get('force_https', 'false')}
"""
            
            # Frontend .env file
            frontend_env_content = f"""# QGen RAG Frontend Environment Configuration
# Generated on {datetime.now().isoformat()}

# API Configuration
PUBLIC_API_URL={config.get('public_api_url', f'http://{config.get("domain", "localhost")}:8000')}
PUBLIC_WS_URL={config.get('public_ws_url', f'ws://{config.get("domain", "localhost")}:8000')}
PUBLIC_API_VERSION={config.get('public_api_version', 'v1')}

# Application Configuration
PUBLIC_APP_NAME={config.get('public_app_name', 'QGen RAG')}
PUBLIC_APP_VERSION={config.get('public_app_version', '1.0.0')}
PUBLIC_APP_DESCRIPTION={config.get('public_app_description', 'Question Generation System')}

# Feature Flags
PUBLIC_ENABLE_ANALYTICS={config.get('public_enable_analytics', 'true')}
PUBLIC_ENABLE_DARK_MODE={config.get('public_enable_dark_mode', 'true')}
PUBLIC_ENABLE_NOTIFICATIONS={config.get('public_enable_notifications', 'true')}

# UI Configuration
PUBLIC_DEFAULT_THEME={config.get('public_default_theme', 'light')}
PUBLIC_DEFAULT_LANGUAGE={config.get('public_default_language', 'en')}
PUBLIC_PAGE_SIZE={config.get('public_page_size', '20')}

# Development Configuration
PUBLIC_DEV_MODE={config.get('public_dev_mode', 'false')}
PUBLIC_LOG_LEVEL={config.get('public_log_level', 'INFO')}
"""
            
            # Trainer-web .env file
            trainer_env_content = f"""# QGen RAG Trainer Web Environment Configuration
# Generated on {datetime.now().isoformat()}

# API Configuration
PUBLIC_API_URL={config.get('trainer_api_url', f'http://{config.get("domain", "localhost")}:8000')}
PUBLIC_WS_URL={config.get('trainer_ws_url', f'ws://{config.get("domain", "localhost")}:8000')}

# Application Configuration
PUBLIC_APP_TITLE={config.get('trainer_app_title', 'QGen RAG Trainer')}
PUBLIC_APP_DESCRIPTION={config.get('trainer_app_description', 'Training Interface for QGen RAG')}

# Training Configuration
PUBLIC_DEFAULT_MODEL={config.get('trainer_default_model', config.get('base_model', 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B'))}
PUBLIC_MAX_TOKENS={config.get('trainer_max_tokens', '4096')}
PUBLIC_DEFAULT_TEMPERATURE={config.get('trainer_default_temperature', '0.7')}

# UI Configuration
PUBLIC_THEME={config.get('trainer_theme', 'default')}
PUBLIC_LANGUAGE={config.get('trainer_language', 'en')}
PUBLIC_TIMEZONE={config.get('trainer_timezone', 'UTC')}

# Feature Flags
PUBLIC_ENABLE_ADVANCED_MODE={config.get('trainer_enable_advanced_mode', 'true')}
PUBLIC_ENABLE_EXPERIMENTAL={config.get('trainer_enable_experimental', 'false')}
PUBLIC_ENABLE_DEBUG={config.get('trainer_enable_debug', 'false')}
"""
            
            # Create backend .env file
            backend_env_file = Path(install_dir) / "backend" / ".env"
            backend_env_file.parent.mkdir(parents=True, exist_ok=True)
            backend_env_file.write_text(backend_env_content)
            
            # Create frontend .env file
            frontend_env_file = Path(install_dir) / "client" / ".env.local"
            frontend_env_file.parent.mkdir(parents=True, exist_ok=True)
            frontend_env_file.write_text(frontend_env_content)
            
            # Create trainer-web .env file
            trainer_env_file = Path(install_dir) / "trainer-web" / ".env"
            trainer_env_file.parent.mkdir(parents=True, exist_ok=True)
            trainer_env_file.write_text(trainer_env_content)
            
            # Create necessary directories
            directories = [
                "models",
                "training_data", 
                "lora_adapters",
                "logs",
                "ssl",
                "uploads",
                "backups",
                "temp"
            ]
            
            for dir_name in directories:
                (Path(install_dir) / dir_name).mkdir(exist_ok=True)
            
            return {
                "success": True,
                "message": "Environment configuration created",
                "backend_env": str(backend_env_file),
                "frontend_env": str(frontend_env_file),
                "trainer_env": str(trainer_env_file)
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_database(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup database with deployment mode customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        deployment_mode = config.get("database_deployment", "docker")
        
        try:
            if deployment_mode == "docker":
                # Docker-based database setup
                docker_compose_content = f"""version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: qgen_postgres
    environment:
      POSTGRES_DB: {config.get('postgres_db', 'qgen_rag')}
      POSTGRES_USER: {config.get('postgres_user', 'qgen_user')}
      POSTGRES_PASSWORD: {config.get('postgres_password', 'qgen_password')}
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=C --lc-ctype=C"
    volumes:
      - {config.get('postgres_data_volume', 'postgres_data')}:/var/lib/postgresql/data
      - ./backend/init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    ports:
      - "{config.get('postgres_port', '5432')}:5432"
    networks:
      - qgen_network
    restart: {config.get('postgres_restart', 'unless-stopped')}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U {config.get('postgres_user', 'qgen_user')} -d {config.get('postgres_db', 'qgen_rag')}"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: qgen_redis
    command: redis-server --appendonly yes --requirepass {config.get('redis_password', 'redis_password')}
    volumes:
      - {config.get('redis_data_volume', 'redis_data')}:/data
    ports:
      - "{config.get('redis_port', '6379')}:6379"
    networks:
      - qgen_network
    restart: {config.get('redis_restart', 'unless-stopped')}
    healthcheck:
      test: ["CMD", "redis-cli", "--raw", "incr", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  {config.get('postgres_data_volume', 'postgres_data')}:
  {config.get('redis_data_volume', 'redis_data')}:

networks:
  qgen_network:
    driver: bridge
"""
                
                docker_compose_file = Path(install_dir) / "docker-compose.database.yml"
                docker_compose_file.write_text(docker_compose_content)
                
                # Start database services
                subprocess.run(["docker-compose", "-f", "docker-compose.database.yml", "up", "-d"], 
                             cwd=install_dir, check=True, capture_output=True, text=True, timeout=120)
                
            elif deployment_mode == "baremetal":
                # Baremetal database setup
                # Setup PostgreSQL
                postgres_commands = [
                    f"sudo systemctl start postgresql",
                    f"sudo -u postgres createuser {config.get('postgres_user', 'qgen_user')}",
                    f"sudo -u postgres createdb {config.get('postgres_db', 'qgen_rag')} -O {config.get('postgres_user', 'qgen_user')}",
                    f"sudo -u postgres psql -c \"ALTER USER {config.get('postgres_user', 'qgen_user')} PASSWORD '{config.get('postgres_password', 'qgen_password')}';\""
                ]
                
                for cmd in postgres_commands:
                    try:
                        subprocess.run(cmd, shell=True, check=True, timeout=60)
                    except subprocess.CalledProcessError:
                        pass  # Command might already be executed
                
                # Setup Redis
                redis_commands = [
                    "sudo systemctl start redis",
                    f"redis-cli config set requirepass {config.get('redis_password', 'redis_password')}"
                ]
                
                for cmd in redis_commands:
                    try:
                        subprocess.run(cmd, shell=True, check=True, timeout=60)
                    except subprocess.CalledProcessError:
                        pass  # Command might already be executed
            
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
                "message": f"Database setup completed ({deployment_mode} mode)",
                "deployment_mode": deployment_mode,
                "services": ["PostgreSQL", "Redis"]
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_frontend(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup frontend applications with customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Setup trainer-web
            trainer_web_dir = Path(install_dir) / "trainer-web"
            
            if trainer_web_dir.exists():
                # Install Node.js dependencies
                subprocess.run(["npm", "install"], cwd=trainer_web_dir, 
                             check=True, capture_output=True, text=True, timeout=300)
                
                # Build frontend based on configuration
                build_command = config.get('frontend_build_command', 'npm run build')
                if build_command:
                    subprocess.run(build_command.split(), cwd=trainer_web_dir, 
                                 check=True, capture_output=True, text=True, timeout=300)
            
            # Setup client (React Native)
            client_dir = Path(install_dir) / "client"
            
            if client_dir.exists() and config.get('setup_mobile_client', False):
                # Install React Native dependencies
                subprocess.run(["npm", "install"], cwd=client_dir, 
                             check=True, capture_output=True, text=True, timeout=300)
                
                # Setup mobile environment
                if config.get('mobile_platform') in ['ios', 'android']:
                    platform_setup_cmd = f"npx react-native setup-{config.get('mobile_platform')}"
                    subprocess.run(platform_setup_cmd.split(), cwd=client_dir, 
                                 check=True, capture_output=True, text=True, timeout=300)
            
            return {
                "success": True,
                "message": "Frontend setup completed",
                "trainer_web_path": str(trainer_web_dir),
                "client_path": str(client_dir) if client_dir.exists() else None
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_services(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start services with deployment mode customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        backend_deployment = config.get("backend_deployment", "docker")
        frontend_deployment = config.get("frontend_deployment", "docker")
        
        try:
            services_started = []
            service_urls = {}
            
            if backend_deployment == "docker":
                # Docker-based backend deployment
                backend_service_content = f"""version: '3.8'

services:
  backend:
    build: 
      context: ./backend
      dockerfile: {config.get('backend_dockerfile', 'Dockerfile')}
    container_name: qgen_backend
    environment:
      - DATABASE_URL={config.get('database_url', 'postgresql+asyncpg://qgen_user:qgen_password@postgres:5432/qgen_rag')}
      - REDIS_URL={config.get('redis_url', 'redis://localhost:6379/0')}
      - SECRET_KEY={config.get('secret_key', uuid.uuid4().hex)}
      - DOMAIN={config.get('domain', 'localhost')}
      - ENVIRONMENT={config.get('environment', 'production')}
    ports:
      - "{config.get('backend_port', '8000')}:8000"
    networks:
      - qgen_network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: {config.get('backend_restart', 'unless-stopped')}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    deploy:
      resources:
        limits:
          memory: {config.get('backend_memory_limit', '2G')}
          cpus: '{config.get('backend_cpu_limit', '1.0')}'
        reservations:
          memory: {config.get('backend_memory_reservation', '1G')}
          cpus: '{config.get('backend_cpu_reservation', '0.5')}'

  training_worker:
    build: 
      context: ./backend
      dockerfile: {config.get('backend_dockerfile', 'Dockerfile')}
    container_name: qgen_training_worker
    command: python -m app.workers.training_worker
    environment:
      - DATABASE_URL={config.get('database_url', 'postgresql+asyncpg://qgen_user:qgen_password@postgres:5432/qgen_rag')}
      - REDIS_URL={config.get('redis_url', 'redis://localhost:6379/0')}
      - MODEL_CACHE_DIR=/app/models
      - TRAINING_DATA_DIR=/app/training_data
      - LORA_ADAPTERS_DIR=/app/lora_adapters
    volumes:
      - {config.get('models_volume', './models')}:/app/models
      - {config.get('training_data_volume', './training_data')}:/app/training_data
      - {config.get('lora_adapters_volume', './lora_adapters')}:/app/lora_adapters
      - {config.get('logs_volume', './logs')}:/app/logs
    networks:
      - qgen_network
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: {config.get('training_worker_restart', 'unless-stopped')}
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

networks:
  qgen_network:
    driver: bridge
"""
                
                backend_services_file = Path(install_dir) / "docker-compose.backend.yml"
                backend_services_file.write_text(backend_service_content)
                
                # Start backend services
                subprocess.run(["docker-compose", "-f", "docker-compose.backend.yml", "up", "-d"], 
                             cwd=install_dir, check=True, capture_output=True, text=True, timeout=180)
                
                services_started.extend(["backend", "training_worker"])
                service_urls["backend"] = f"http://{config.get('domain', 'localhost')}:{config.get('backend_port', '8000')}"
                service_urls["api_docs"] = f"http://{config.get('domain', 'localhost')}:{config.get('backend_port', '8000')}/docs"
                
            elif backend_deployment == "baremetal":
                # Baremetal backend deployment
                venv_python = Path(install_dir) / "venv" / "bin" / "python"
                if platform.system() == "Windows":
                    venv_python = Path(install_dir) / "venv" / "Scripts" / "python.exe"
                
                # Start backend with uvicorn
                backend_cmd = [
                    str(venv_python), "-m", "uvicorn", "app.main:app",
                    "--host", config.get('backend_host', '0.0.0.0'),
                    "--port", str(config.get('backend_port', '8000')),
                    "--workers", str(config.get('backend_workers', '1'))
                ]
                
                # Create systemd service file
                systemd_service = f"""[Unit]
Description=QGen RAG Backend
After=network.target

[Service]
Type=exec
User={config.get('backend_user', 'qgen')}
Group={config.get('backend_group', 'qgen')}
WorkingDirectory={install_dir}/backend
Environment=PATH={install_dir}/venv/bin
ExecStart={str(venv_python)} -m uvicorn app.main:app --host {config.get('backend_host', '0.0.0.0')} --port {config.get('backend_port', '8000')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
                
                systemd_file = Path("/etc/systemd/system/qgen-backend.service")
                systemd_file.write_text(systemd_service)
                
                subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
                subprocess.run(["sudo", "systemctl", "start", "qgen-backend"], check=True)
                subprocess.run(["sudo", "systemctl", "enable", "qgen-backend"], check=True)
                
                services_started.append("backend")
                service_urls["backend"] = f"http://{config.get('domain', 'localhost')}:{config.get('backend_port', '8000')}"
                service_urls["api_docs"] = f"http://{config.get('domain', 'localhost')}:{config.get('backend_port', '8000')}/docs"
            
            if frontend_deployment == "docker":
                # Docker-based frontend deployment
                frontend_service_content = f"""version: '3.8'

services:
  frontend:
    build: 
      context: ./trainer-web
      dockerfile: {config.get('frontend_dockerfile', 'Dockerfile')}
    container_name: qgen_frontend
    environment:
      - PUBLIC_API_URL={config.get('public_api_url', f'http://{config.get("domain", "localhost")}:8000')}
      - PUBLIC_WS_URL={config.get('public_ws_url', f'ws://{config.get("domain", "localhost")}:8000')}
    ports:
      - "{config.get('frontend_port', '5173')}:5173"
    networks:
      - qgen_network
    depends_on:
      - backend
    restart: {config.get('frontend_restart', 'unless-stopped')}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5173"]
      interval: 30s
      timeout: 10s
      retries: 3

networks:
  qgen_network:
    driver: bridge
"""
                
                frontend_services_file = Path(install_dir) / "docker-compose.frontend.yml"
                frontend_services_file.write_text(frontend_service_content)
                
                # Start frontend services
                subprocess.run(["docker-compose", "-f", "docker-compose.frontend.yml", "up", "-d"], 
                             cwd=install_dir, check=True, capture_output=True, text=True, timeout=180)
                
                services_started.append("frontend")
                service_urls["frontend"] = f"http://{config.get('domain', 'localhost')}:{config.get('frontend_port', '5173')}"
                
            elif frontend_deployment == "nginx":
                # Nginx-based frontend deployment
                nginx_config = f"""server {{
    listen {config.get('nginx_port', '80')};
    server_name {config.get('domain', 'localhost')};
    
    root {install_dir}/trainer-web/dist;
    index index.html;
    
    location / {{
        try_files $uri $uri/ /index.html;
    }}
    
    location /api/ {{
        proxy_pass http://localhost:{config.get('backend_port', '8000')};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    
    location /ws/ {{
        proxy_pass http://localhost:{config.get('backend_port', '8000')};
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
}}
"""
                
                nginx_file = Path("/etc/nginx/sites-available/qgen-frontend")
                nginx_file.write_text(nginx_config)
                
                subprocess.run(["sudo", "ln", "-sf", "/etc/nginx/sites-available/qgen-frontend", "/etc/nginx/sites-enabled/"], check=True)
                subprocess.run(["sudo", "nginx", "-t"], check=True)
                subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
                
                services_started.append("frontend")
                service_urls["frontend"] = f"http://{config.get('domain', 'localhost')}:{config.get('nginx_port', '80')}"
            
            # Wait for services to be ready
            import time
            time.sleep(45)
            
            return {
                "success": True,
                "message": f"Services started successfully ({backend_deployment}/{frontend_deployment})",
                "services_started": services_started,
                "service_urls": service_urls,
                "deployment_modes": {
                    "backend": backend_deployment,
                    "frontend": frontend_deployment
                }
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_ssl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup SSL certificates with customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        domain = config.get("domain", "localhost")
        ssl_email = config.get("ssl_email", "admin@example.com")
        ssl_type = config.get("ssl_type", "self_signed")
        
        try:
            if ssl_type == "self_signed" or domain == "localhost":
                # Generate self-signed certificate
                ssl_dir = Path(install_dir) / "ssl"
                ssl_dir.mkdir(exist_ok=True)
                
                # Generate private key
                subprocess.run([
                    "openssl", "genrsa", "-out", "key.pem", "2048"
                ], cwd=ssl_dir, check=True, capture_output=True, text=True, timeout=60)
                
                # Generate certificate
                subprocess.run([
                    "openssl", "req", "-new", "-x509", "-key", "key.pem", 
                    "-out", "cert.pem", "-days", str(config.get('ssl_days', '365')),
                    "-subj", f"/C={config.get('ssl_country', 'US')}/ST={config.get('ssl_state', 'State')}/L={config.get('ssl_city', 'City')}/O={config.get('ssl_organization', 'Organization')}/CN={domain}"
                ], cwd=ssl_dir, check=True, capture_output=True, text=True, timeout=60)
                
                return {
                    "success": True,
                    "message": "Self-signed SSL certificate generated",
                    "certificate_path": str(ssl_dir / "cert.pem"),
                    "key_path": str(ssl_dir / "key.pem"),
                    "ssl_type": "self_signed"
                }
                
            elif ssl_type == "letsencrypt":
                # Setup Let's Encrypt
                return {
                    "success": True,
                    "message": f"SSL setup instructions for {domain}",
                    "ssl_type": "letsencrypt",
                    "instructions": [
                        f"1. Point DNS for {domain} to this server",
                        f"2. Run: certbot --nginx -d {domain} --email {ssl_email}",
                        f"3. Configure automatic renewal: crontab -e",
                        f"4. Add: 0 12 * * * /usr/bin/certbot renew --quiet"
                    ]
                }
            
            elif ssl_type == "custom":
                # Use custom certificates
                return {
                    "success": True,
                    "message": "Custom SSL certificate configuration",
                    "ssl_type": "custom",
                    "instructions": [
                        f"1. Place your certificate at: {install_dir}/ssl/cert.pem",
                        f"2. Place your private key at: {install_dir}/ssl/key.pem",
                        f"3. Ensure proper permissions: chmod 600 {install_dir}/ssl/key.pem"
                    ]
                }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _initialize_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize sample data with customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        init_sample_data = config.get("init_sample_data", True)
        
        try:
            if not init_sample_data:
                return {
                    "success": True,
                    "message": "Sample data initialization skipped (user preference)"
                }
            
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
        """Setup training pipeline configuration with full customization."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Create comprehensive training configuration
            training_config = {
                "model_config": {
                    "base_model": config.get("base_model", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"),
                    "max_sequence_length": config.get("max_sequence_length", 4096),
                    "torch_dtype": config.get("torch_dtype", "float16"),
                    "device_map": config.get("device_map", "auto"),
                    "trust_remote_code": config.get("trust_remote_code", True),
                    "use_cache": config.get("use_cache", True),
                    "attn_implementation": config.get("attn_implementation", "flash_attention_2")
                },
                "training_config": {
                    "batch_size": config.get("batch_size", 4),
                    "gradient_accumulation_steps": config.get("gradient_accumulation_steps", 8),
                    "learning_rate": config.get("learning_rate", 2e-4),
                    "num_epochs": config.get("num_epochs", 3),
                    "warmup_steps": config.get("warmup_steps", 100),
                    "save_steps": config.get("save_steps", 500),
                    "eval_steps": config.get("eval_steps", 500),
                    "logging_steps": config.get("logging_steps", 10),
                    "max_grad_norm": config.get("max_grad_norm", 1.0),
                    "weight_decay": config.get("weight_decay", 0.01),
                    "adam_epsilon": config.get("adam_epsilon", 1e-8),
                    "max_grad_norm": config.get("max_grad_norm", 1.0)
                },
                "lora_config": {
                    "r": config.get("lora_r", 16),
                    "lora_alpha": config.get("lora_alpha", 32),
                    "target_modules": config.get("lora_target_modules", ["q_proj", "v_proj", "k_proj", "o_proj"]),
                    "lora_dropout": config.get("lora_dropout", 0.1),
                    "bias": config.get("lora_bias", "none"),
                    "task_type": config.get("lora_task_type", "CAUSAL_LM"),
                    "modules_to_save": config.get("lora_modules_to_save", None)
                },
                "data_config": {
                    "train_test_split": config.get("train_test_split", 0.8),
                    "validation_split": config.get("validation_split", 0.1),
                    "max_samples_per_subject": config.get("max_samples_per_subject", 1000),
                    "quality_threshold": config.get("quality_threshold", 0.7),
                    "diversity_threshold": config.get("diversity_threshold", 0.6),
                    "min_vetting_score": config.get("min_vetting_score", 4.0),
                    "data_augmentation": config.get("data_augmentation", True),
                    "shuffle_data": config.get("shuffle_data", True)
                },
                "evaluation_config": {
                    "metrics": config.get("evaluation_metrics", ["accuracy", "f1", "bleu", "rouge"]),
                    "evaluation_frequency": config.get("evaluation_frequency", "epoch"),
                    "save_best_model": config.get("save_best_model", True),
                    "early_stopping_patience": config.get("early_stopping_patience", 3),
                    "load_best_model_at_end": config.get("load_best_model_at_end", True),
                    "greater_is_better": config.get("greater_is_better", True)
                },
                "optimization_config": {
                    "optimizer": config.get("optimizer", "adamw"),
                    "scheduler": config.get("scheduler", "cosine"),
                    "fp16": config.get("fp16", True),
                    "bf16": config.get("bf16", False),
                    "gradient_checkpointing": config.get("gradient_checkpointing", True),
                    "dataloader_num_workers": config.get("dataloader_num_workers", 4),
                    "remove_unused_columns": config.get("remove_unused_columns", True)
                },
                "logging_config": {
                    "logging_dir": f"{install_dir}/logs",
                    "logging_strategy": config.get("logging_strategy", "steps"),
                    "report_to": config.get("report_to", ["tensorboard", "wandb"]),
                    "project_name": config.get("project_name", "qgen-rag"),
                    "run_name": config.get("run_name", f"training-{datetime.now().strftime('%Y%m%d-%H%M%S')}"),
                    "log_level": config.get("log_level", "INFO")
                }
            }
            
            config_file = Path(install_dir) / "training_config.json"
            config_file.write_text(json.dumps(training_config, indent=2))
            
            # Create training scripts
            train_script = f"""#!/bin/bash
# Training Script for QGen RAG
# Generated on {datetime.now().isoformat()}

export CUDA_VISIBLE_DEVICES={config.get('cuda_visible_devices', '0')}
export PYTHONPATH={install_dir}/backend:$PYTHONPATH

cd {install_dir}

# Activate virtual environment
source venv/bin/activate

# Run training
python backend/scripts/train_model.py \\
    --config {install_dir}/training_config.json \\
    --output_dir {install_dir}/lora_adapters \\
    --logging_dir {install_dir}/logs \\
    --report_to tensorboard,wandb
"""
            
            train_script_file = Path(install_dir) / "train.sh"
            train_script_file.write_text(train_script)
            train_script_file.chmod(0o755)
            
            return {
                "success": True,
                "message": "Training pipeline configuration created",
                "config_file": str(config_file),
                "train_script": str(train_script_file),
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
        "id": "deployment_mode",
        "title": "Deployment Mode",
        "description": "Choose deployment mode for services",
        "icon": "🏗️"
    },
    {
        "id": "configuration",
        "title": "Configuration",
        "description": "Customize all system settings",
        "icon": "⚙️"
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
        "id": "database",
        "title": "Database Setup",
        "description": "Setup PostgreSQL and Redis",
        "icon": "🗄️"
    },
    {
        "id": "frontend",
        "title": "Frontend Setup",
        "description": "Setup trainer-web and client applications",
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

# Complete HTML Template with Multi-Page Wizard and Full Customization
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
        .wizard-container { @apply max-w-6xl mx-auto; }
        .step-navigation { @apply flex justify-between items-center mt-6; }
        .feature-card { @apply bg-gradient-to-br from-blue-50 to-indigo-50 rounded-lg p-6 border border-blue-200; }
        .system-info-card { @apply bg-gray-50 rounded-lg p-4 border border-gray-200; }
        .config-section { @apply bg-gray-50 rounded-lg p-4 border border-gray-200 mb-4; }
        .config-grid { @apply grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4; }
        .radio-group { @apply space-y-2; }
        .radio-option { @apply flex items-center space-x-2 p-2 rounded hover:bg-gray-100; }
        .radio-option.selected { @apply bg-blue-100 border-blue-500; }
    </style>
</head>
<body class="bg-gray-100" x-data="wizardApp()">
    <div class="min-h-screen py-8">
        <!-- Header -->
        <header class="text-center mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">🚀 QGen RAG Setup Wizard</h1>
            <p class="text-gray-600">Complete customizable setup for your SLM/LLM training system</p>
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
                <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
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
                        <p class="text-lg text-gray-600 mb-6">Your complete customizable SLM/LLM training system setup wizard</p>
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
                            <li>Let you choose deployment modes (Docker/Baremetal)</li>
                            <li>Customize all configuration options</li>
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
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
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
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Docker</h3>
                            <p class="text-sm text-gray-600">
                                <template x-if="systemInfo.software.docker.installed">
                                    <span class="text-green-600">✅ Installed</span>
                                    <template x-if="systemInfo.software.docker.running">
                                        <span class="text-green-600"> (Running)</span>
                                    </template>
                                    <template x-if="!systemInfo.software.docker.running">
                                        <span class="text-yellow-600"> (Not running)</span>
                                    </template>
                                </template>
                                <template x-if="!systemInfo.software.docker.installed">
                                    <span class="text-red-600">❌ Not installed</span>
                                </template>
                            </p>
                        </div>
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Git</h3>
                            <p class="text-sm text-gray-600">
                                <template x-if="systemInfo.software.git.installed">
                                    <span class="text-green-600">✅ Installed</span>
                                </template>
                                <template x-if="!systemInfo.software.git.installed">
                                    <span class="text-red-600">❌ Not installed</span>
                                </template>
                            </p>
                        </div>
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Node.js</h3>
                            <p class="text-sm text-gray-600">
                                <template x-if="systemInfo.software.nodejs.installed">
                                    <span class="text-green-600">✅ Installed</span>
                                </template>
                                <template x-if="!systemInfo.software.nodejs.installed">
                                    <span class="text-red-600">❌ Not installed</span>
                                </template>
                            </p>
                        </div>
                        <div class="system-info-card">
                            <h3 class="font-semibold text-gray-700 mb-2">Network</h3>
                            <p class="text-sm text-gray-600">
                                <template x-if="systemInfo.network.internet_accessible">
                                    <span class="text-green-600">✅ Connected</span>
                                </template>
                                <template x-if="!systemInfo.network.internet_accessible">
                                    <span class="text-red-600">❌ No internet</span>
                                </template>
                            </p>
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

                <!-- Deployment Mode Step -->
                <div x-show="currentStep.id === 'deployment_mode'" class="space-y-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">🏗️ Choose Deployment Mode</h2>
                    <p class="text-gray-600 mb-6">Select how you want to deploy each service component</p>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">Database Deployment</h3>
                        <div class="radio-group">
                            <label class="radio-option">
                                <input type="radio" x-model="config.database_deployment" value="docker" class="mr-2">
                                <div>
                                    <div class="font-medium">🐳 Docker (Recommended)</div>
                                    <div class="text-sm text-gray-600">Easy setup, containerized, portable</div>
                                </div>
                            </label>
                            <label class="radio-option">
                                <input type="radio" x-model="config.database_deployment" value="baremetal" class="mr-2">
                                <div>
                                    <div class="font-medium">🖥️ Baremetal</div>
                                    <div class="text-sm text-gray-600">Direct installation, maximum performance</div>
                                </div>
                            </label>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">Backend Deployment</h3>
                        <div class="radio-group">
                            <label class="radio-option">
                                <input type="radio" x-model="config.backend_deployment" value="docker" class="mr-2">
                                <div>
                                    <div class="font-medium">🐳 Docker (Recommended)</div>
                                    <div class="text-sm text-gray-600">Containerized, easy scaling</div>
                                </div>
                            </label>
                            <label class="radio-option">
                                <input type="radio" x-model="config.backend_deployment" value="baremetal" class="mr-2">
                                <div>
                                    <div class="font-medium">🖥️ Baremetal</div>
                                    <div class="text-sm text-gray-600">Systemd service, direct access</div>
                                </div>
                            </label>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">Frontend Deployment</h3>
                        <div class="radio-group">
                            <label class="radio-option">
                                <input type="radio" x-model="config.frontend_deployment" value="docker" class="mr-2">
                                <div>
                                    <div class="font-medium">🐳 Docker (Recommended)</div>
                                    <div class="text-sm text-gray-600">Containerized, easy setup</div>
                                </div>
                            </label>
                            <label class="radio-option">
                                <input type="radio" x-model="config.frontend_deployment" value="nginx" class="mr-2">
                                <div>
                                    <div class="font-medium">🌐 Nginx</div>
                                    <div class="text-sm text-gray-600">Web server, reverse proxy</div>
                                </div>
                            </label>
                            <label class="radio-option">
                                <input type="radio" x-model="config.frontend_deployment" value="node" class="mr-2">
                                <div>
                                    <div class="font-medium">🟢 Node.js</div>
                                    <div class="text-sm text-gray-600">Direct Node.js server</div>
                                </div>
                            </label>
                        </div>
                    </div>
                </div>

                <!-- Configuration Step -->
                <div x-show="currentStep.id === 'configuration'" class="space-y-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4">⚙️ System Configuration</h2>
                    <p class="text-gray-600 mb-6">Customize all system settings and preferences</p>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">🌐 Basic Settings</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Installation Directory</label>
                                <input type="text" x-model="config.install_dir" value="/opt/qgen" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Domain</label>
                                <input type="text" x-model="config.domain" value="localhost" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Environment</label>
                                <select x-model="config.environment" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="production">Production</option>
                                    <option value="development">Development</option>
                                    <option value="staging">Staging</option>
                                </select>
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">🗄️ Database Settings</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">PostgreSQL Database</label>
                                <input type="text" x-model="config.postgres_db" value="qgen_rag" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">PostgreSQL User</label>
                                <input type="text" x-model="config.postgres_user" value="qgen_user" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">PostgreSQL Password</label>
                                <input type="password" x-model="config.postgres_password" value="qgen_password" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">PostgreSQL Port</label>
                                <input type="number" x-model="config.postgres_port" value="5432" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Redis Password</label>
                                <input type="password" x-model="config.redis_password" value="redis_password" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Redis Port</label>
                                <input type="number" x-model="config.redis_port" value="6379" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">🔧 Service Ports</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Backend Port</label>
                                <input type="number" x-model="config.backend_port" value="8000" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Frontend Port</label>
                                <input type="number" x-model="config.frontend_port" value="5173" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Nginx Port</label>
                                <input type="number" x-model="config.nginx_port" value="80" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">🔑 API Keys</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">OpenAI API Key</label>
                                <input type="password" x-model="config.openai_api_key" placeholder="sk-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">DeepSeek API Key</label>
                                <input type="password" x-model="config.deepseek_api_key" placeholder="sk-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Anthropic API Key</label>
                                <input type="password" x-model="config.anthropic_api_key" placeholder="sk-ant-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">🤖 Model Configuration</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Base Model</label>
                                <select x-model="config.base_model" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="deepseek-ai/DeepSeek-R1-Distill-Llama-8B">DeepSeek-R1-8B (Recommended)</option>
                                    <option value="deepseek-ai/DeepSeek-R1-Distill-Llama-70B">DeepSeek-R1-70B (Large)</option>
                                    <option value="meta-llama/Llama-2-7b-chat-hf">Llama-2-7B</option>
                                    <option value="meta-llama/Llama-2-13b-chat-hf">Llama-2-13B</option>
                                    <option value="mistralai/Mistral-7B-Instruct-v0.2">Mistral-7B</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Max Tokens</label>
                                <input type="number" x-model="config.max_tokens" value="4096" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Temperature</label>
                                <input type="number" step="0.1" x-model="config.temperature" value="0.7" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">📁 Directory Paths</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Model Cache Directory</label>
                                <input type="text" x-model="config.model_cache_dir" :value="config.install_dir + '/models'" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Training Data Directory</label>
                                <input type="text" x-model="config.training_data_dir" :value="config.install_dir + '/training_data'" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Upload Directory</label>
                                <input type="text" x-model="config.upload_dir" :value="config.install_dir + '/uploads'" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">🔒 SSL Configuration</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">SSL Type</label>
                                <select x-model="config.ssl_type" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="self_signed">Self-Signed</option>
                                    <option value="letsencrypt">Let's Encrypt</option>
                                    <option value="custom">Custom Certificate</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">SSL Email</label>
                                <input type="email" x-model="config.ssl_email" value="admin@example.com" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">SSL Days</label>
                                <input type="number" x-model="config.ssl_days" value="365" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="config-section">
                        <h3 class="text-lg font-semibold text-gray-800 mb-4">📊 Monitoring & Logging</h3>
                        <div class="config-grid">
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Enable Metrics</label>
                                <select x-model="config.enable_metrics" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="true">Enabled</option>
                                    <option value="false">Disabled</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Log Level</label>
                                <select x-model="config.log_level" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                    <option value="DEBUG">Debug</option>
                                    <option value="INFO">Info</option>
                                    <option value="WARNING">Warning</option>
                                    <option value="ERROR">Error</option>
                                </select>
                            </div>
                            <div>
                                <label class="block text-sm font-medium text-gray-700">Sentry DSN</label>
                                <input type="text" x-model="config.sentry_dsn" placeholder="https://..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex justify-end">
                        <button @click="saveConfig" class="bg-blue-500 text-white py-2 px-6 rounded-md hover:bg-blue-600 transition-colors">
                            Save Configuration
                        </button>
                    </div>
                </div>

                <!-- Configuration Steps (Virtual Environment, Dependencies, etc.) -->
                <div x-show="['virtual_env', 'dependencies', 'repository', 'database', 'frontend', 'services', 'ssl', 'data_initialization', 'training_setup'].includes(currentStep.id)" class="space-y-6">
                    <h2 class="text-2xl font-bold text-gray-800 mb-4" x-text="currentStep.icon + ' ' + currentStep.title"></h2>
                    <p class="text-gray-600 mb-4" x-text="currentStep.description"></p>
                    
                    <!-- Step Execution -->
                    <div x-show="!stepExecuted">
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
                                <a :href="`http://${config.domain}:${config.frontend_port}`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:${config.frontend_port}`"></a>
                            </div>
                            <div>
                                <strong>🔧 Backend API:</strong> 
                                <a :href="`http://${config.domain}:${config.backend_port}`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:${config.backend_port}`"></a>
                            </div>
                            <div>
                                <strong>📚 API Documentation:</strong> 
                                <a :href="`http://${config.domain}:${config.backend_port}/docs`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:${config.backend_port}/docs`"></a>
                            </div>
                            <div>
                                <strong>👤 Admin Panel:</strong> 
                                <a :href="`http://${config.domain}:${config.frontend_port}/admin`" class="text-blue-600 hover:underline" x-text="`http://${config.domain}:${config.frontend_port}/admin`"></a>
                            </div>
                        </div>
                    </div>
                    
                    <div class="bg-blue-50 border-l-4 border-blue-400 p-6">
                        <h3 class="font-semibold text-blue-800 mb-4">Deployment Summary</h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                                <strong>Database:</strong> <span x-text="config.database_deployment"></span>
                            </div>
                            <div>
                                <strong>Backend:</strong> <span x-text="config.backend_deployment"></span>
                            </div>
                            <div>
                                <strong>Frontend:</strong> <span x-text="config.frontend_deployment"></span>
                            </div>
                            <div>
                                <strong>SSL:</strong> <span x-text="config.ssl_type"></span>
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
                    {"id": "deployment_mode", "title": "Deployment Mode", "description": "Choose deployment mode for services", "icon": "🏗️"},
                    {"id": "configuration", "title": "Configuration", "description": "Customize all system settings", "icon": "⚙️"},
                    {"id": "virtual_env", "title": "Virtual Environment", "description": "Setup Python virtual environment", "icon": "🐍"},
                    {"id": "dependencies", "title": "Dependencies", "description": "Install system dependencies", "icon": "📦"},
                    {"id": "repository", "title": "Source Code", "description": "Clone QGen RAG repository", "icon": "📥"},
                    {"id": "database", "title": "Database Setup", "description": "Setup PostgreSQL and Redis", "icon": "🗄️"},
                    {"id": "frontend", "title": "Frontend Setup", "description": "Setup trainer-web and client applications", "icon": "🎨"},
                    {"id": "services", "title": "Services", "description": "Start all application services", "icon": "🚀"},
                    {"id": "ssl", "title": "SSL Configuration", "description": "Setup SSL certificates", "icon": "🔒"},
                    {"id": "data_initialization", "title": "Data Initialization", "description": "Initialize sample data", "icon": "📊"},
                    {"id": "training_setup", "title": "Training Pipeline", "description": "Configure ML training pipeline", "icon": "🤖"},
                    {"id": "completion", "title": "Setup Complete", "description": "Review and access your application", "icon": "✅"}
                ],
                currentStepIndex: 0,
                systemInfo: {},
                config: {
                    // Deployment modes
                    database_deployment: 'docker',
                    backend_deployment: 'docker',
                    frontend_deployment: 'docker',
                    
                    // Basic settings
                    install_dir: '/opt/qgen',
                    domain: 'localhost',
                    environment: 'production',
                    
                    // Database settings
                    postgres_db: 'qgen_rag',
                    postgres_user: 'qgen_user',
                    postgres_password: 'qgen_password',
                    postgres_port: 5432,
                    redis_password: 'redis_password',
                    redis_port: 6379,
                    
                    // Service ports
                    backend_port: 8000,
                    frontend_port: 5173,
                    nginx_port: 80,
                    
                    // API keys
                    openai_api_key: '',
                    deepseek_api_key: '',
                    anthropic_api_key: '',
                    
                    // Model configuration
                    base_model: 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B',
                    max_tokens: 4096,
                    temperature: 0.7,
                    
                    // Directory paths
                    model_cache_dir: '/opt/qgen/models',
                    training_data_dir: '/opt/qgen/training_data',
                    upload_dir: '/opt/qgen/uploads',
                    
                    // SSL configuration
                    ssl_type: 'self_signed',
                    ssl_email: 'admin@example.com',
                    ssl_days: 365,
                    
                    // Monitoring
                    enable_metrics: 'true',
                    log_level: 'INFO',
                    sentry_dsn: '',
                    
                    // Repository
                    repository_url: 'https://github.com/your-org/qgen_rag.git'
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
                    window.open(`http://${this.config.domain}:${this.config.frontend_port}`, '_blank');
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
