#!/usr/bin/env python3
"""
Interactive Web Setup for QGen RAG System

Automatically detects system configuration and provides a web interface
for guided setup and deployment of the QGen RAG project.
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
    """Detects system configuration and capabilities."""
    
    def __init__(self):
        self.system_info = {}
        self.detect_all()
    
    def detect_all(self) -> Dict[str, Any]:
        """Detect all system information."""
        self.system_info = {
            "os": self._detect_os(),
            "architecture": self._detect_architecture(),
            "manufacturer": self._detect_manufacturer(),
            "hardware": self._detect_hardware(),
            "network": self._detect_network(),
            "software": self._detect_software(),
            "recommendations": self._get_recommendations()
        }
        return self.system_info
    
    def _detect_os(self) -> Dict[str, str]:
        """Detect operating system information."""
        return {
            "name": platform.system(),
            "version": platform.version(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        }
    
    def _detect_architecture(self) -> Dict[str, Any]:
        """Detect system architecture."""
        return {
            "bits": platform.architecture()[0],
            "linkage": platform.architecture()[1],
            "machine": platform.machine(),
            "total_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False)
        }
    
    def _detect_manufacturer(self) -> Dict[str, str]:
        """Detect system manufacturer and model with cross-platform support."""
        manufacturer = "Unknown"
        model = "Unknown"
        
        try:
            system_name = platform.system()
            
            if system_name == "Linux":
                # Try to read DMI information
                dmi_paths = [
                    "/sys/class/dmi/id/product_name",
                    "/sys/class/dmi/id/product_version",
                    "/sys/class/dmi/id/board_vendor",
                    "/sys/class/dmi/id/board_name"
                ]
                
                for dmi_path in dmi_paths:
                    if os.path.exists(dmi_path):
                        try:
                            with open(dmi_path, "r") as f:
                                content = f.read().strip()
                                if "product_name" in dmi_path:
                                    model = content
                                elif "board_vendor" in dmi_path:
                                    manufacturer = content
                                elif "board_name" in dmi_path and model == "Unknown":
                                    model = content
                        except (PermissionError, OSError):
                            continue
                
                # Fallback: try dmidecode command
                if manufacturer == "Unknown" or model == "Unknown":
                    try:
                        result = subprocess.run(["sudo", "dmidecode", "-s", "system-manufacturer"], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            manufacturer = result.stdout.strip()
                        
                        result = subprocess.run(["sudo", "dmidecode", "-s", "system-product-name"], 
                                              capture_output=True, text=True, timeout=10)
                        if result.returncode == 0:
                            model = result.stdout.strip()
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                        pass
            
            elif system_name == "Darwin":  # macOS
                # Get model identifier
                try:
                    result = subprocess.run(["sysctl", "-n", "hw.model"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        model = result.stdout.strip()
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    pass
                
                # Get manufacturer (always Apple for Mac)
                manufacturer = "Apple"
                
                # Try to get more detailed model info
                try:
                    result = subprocess.run(["system_profiler", "SPHardwareDataType", "-json"], 
                                          capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        import json
                        data = json.loads(result.stdout)
                        hardware = data.get("SPHardwareDataType", [{}])[0]
                        
                        if "machine_model" in hardware:
                            model = hardware["machine_model"]
                        if "machine_name" in hardware:
                            model = hardware["machine_name"]
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
                    pass
            
            elif system_name == "Windows":
                try:
                    import wmi
                    c = wmi.WMI()
                    for item in c.Win32_ComputerSystem():
                        manufacturer = item.Manufacturer or "Unknown"
                        model = item.Model or "Unknown"
                        break
                except ImportError:
                    # Fallback: use systeminfo command
                    try:
                        result = subprocess.run(["systeminfo"], capture_output=True, text=True, timeout=30)
                        if result.returncode == 0:
                            lines = result.stdout.split('\n')
                            for line in lines:
                                if "System Manufacturer:" in line:
                                    manufacturer = line.split(":")[1].strip()
                                elif "System Model:" in line:
                                    model = line.split(":")[1].strip()
                    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                        pass
                except Exception:
                    pass
        
        except Exception as e:
            logger.warning(f"Could not detect manufacturer: {e}")
        
        return {"manufacturer": manufacturer, "model": model}
    
    def _detect_hardware(self) -> Dict[str, Any]:
        """Detect hardware specifications."""
        hardware = {
            "cpu": {
                "name": platform.processor(),
                "cores": psutil.cpu_count(logical=True),
                "physical_cores": psutil.cpu_count(logical=False),
                "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "usage_percent": psutil.cpu_percent(interval=1)
            },
            "memory": {
                "total": psutil.virtual_memory().total,
                "available": psutil.virtual_memory().available,
                "percent": psutil.virtual_memory().percent
            },
            "disk": {
                "total": psutil.disk_usage('/').total,
                "free": psutil.disk_usage('/').free,
                "percent": psutil.disk_usage('/').percent
            },
            "gpu": self._detect_gpu()
        }
        
        # Convert bytes to GB
        hardware["memory"]["total_gb"] = hardware["memory"]["total"] / (1024**3)
        hardware["memory"]["available_gb"] = hardware["memory"]["available"] / (1024**3)
        hardware["disk"]["total_gb"] = hardware["disk"]["total"] / (1024**3)
        hardware["disk"]["free_gb"] = hardware["disk"]["free"] / (1024**3)
        
        return hardware
    
    def _detect_gpu(self) -> Dict[str, Any]:
        """Detect GPU information with cross-platform support."""
        gpu_info = {"gpus": [], "cuda_available": False, "nvidia_driver": None, "platform_gpu": None}
        
        try:
            system_name = platform.system()
            
            # NVIDIA GPU detection
            try:
                result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", 
                                       "--format=csv,noheader,nounits"], 
                                      capture_output=True, text=True, timeout=15)
                
                if result.returncode == 0:
                    gpu_info["cuda_available"] = True
                    lines = result.stdout.strip().split('\n')
                    for i, line in enumerate(lines):
                        if line.strip():
                            parts = line.split(', ')
                            if len(parts) >= 2:
                                gpu_info["gpus"].append({
                                    "id": i,
                                    "name": parts[0].strip(),
                                    "memory_mb": int(parts[1].strip())
                                })
                    
                    # Get driver version
                    driver_result = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", 
                                                  "--format=csv,noheader,nounits"], 
                                                 capture_output=True, text=True, timeout=10)
                    if driver_result.returncode == 0:
                        gpu_info["nvidia_driver"] = driver_result.stdout.strip().split('\n')[0]
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            # Platform-specific GPU detection
            if system_name == "Darwin":  # macOS
                try:
                    # Apple Silicon GPU detection
                    result = subprocess.run(["system_profiler", "SPDisplaysDataType", "-json"], 
                                          capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        import json
                        data = json.loads(result.stdout)
                        displays = data.get("SPDisplaysDataType", [])
                        
                        for display in displays:
                            gpu_name = display.get("_name", "Unknown GPU")
                            vram = display.get("VRAM", "Integrated")
                            
                            gpu_info["gpus"].append({
                                "id": len(gpu_info["gpus"]),
                                "name": gpu_name,
                                "memory_mb": vram,
                                "type": "apple_silicon" if "Apple" in gpu_name else "integrated"
                            })
                            
                            if not gpu_info["platform_gpu"]:
                                gpu_info["platform_gpu"] = gpu_name
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError):
                    # Fallback for older macOS
                    gpu_info["gpus"].append({
                        "id": 0,
                        "name": "Apple GPU",
                        "memory_mb": "Integrated",
                        "type": "integrated"
                    })
                    gpu_info["platform_gpu"] = "Apple GPU"
            
            elif system_name == "Linux":
                # Try to detect other GPUs (Intel, AMD)
                try:
                    # Check for Intel GPUs
                    if os.path.exists("/sys/class/drm"):
                        drm_devices = os.listdir("/sys/class/drm")
                        for device in drm_devices:
                            if device.startswith("card") and "-" not in device:
                                try:
                                    device_path = f"/sys/class/drm/{device}/device"
                                    if os.path.exists(device_path):
                                        # Try to read GPU name
                                        vendor_file = os.path.join(device_path, "vendor")
                                        device_file = os.path.join(device_path, "device")
                                        
                                        vendor = "Unknown"
                                        device_id = "Unknown"
                                        
                                        if os.path.exists(vendor_file):
                                            with open(vendor_file, "r") as f:
                                                vendor_hex = f.read().strip()
                                                if vendor_hex == "0x8086":
                                                    vendor = "Intel"
                                                elif vendor_hex == "0x1002":
                                                    vendor = "AMD"
                                        
                                        if vendor != "Unknown":
                                            gpu_info["gpus"].append({
                                                "id": len(gpu_info["gpus"]),
                                                "name": f"{vendor} Integrated GPU",
                                                "memory_mb": "Shared",
                                                "type": "integrated"
                                            })
                                            
                                            if not gpu_info["platform_gpu"]:
                                                gpu_info["platform_gpu"] = f"{vendor} GPU"
                                except (PermissionError, OSError):
                                    continue
                except Exception:
                    pass
            
            elif system_name == "Windows":
                try:
                    import wmi
                    c = wmi.WMI()
                    
                    # Get GPU information
                    for gpu in c.Win32_VideoController():
                        gpu_name = gpu.Name or "Unknown GPU"
                        adapter_ram = gpu.AdapterRAM
                        
                        if adapter_ram:
                            memory_mb = adapter_ram // (1024 * 1024)
                        else:
                            memory_mb = "Unknown"
                        
                        gpu_info["gpus"].append({
                            "id": len(gpu_info["gpus"]),
                            "name": gpu_name,
                            "memory_mb": memory_mb,
                            "type": "discrete" if "NVIDIA" in gpu_name or "AMD" in gpu_name else "integrated"
                        })
                        
                        if not gpu_info["platform_gpu"]:
                            gpu_info["platform_gpu"] = gpu_name
                except ImportError:
                    # Fallback: use dxdiag
                    try:
                        result = subprocess.run(["dxdiag", "/t", "dxdiag_output.txt"], 
                                              capture_output=True, text=True, timeout=30)
                        # Parse dxdiag output (simplified)
                        if os.path.exists("dxdiag_output.txt"):
                            with open("dxdiag_output.txt", "r") as f:
                                content = f.read()
                                # Simple parsing for GPU info
                                if "Card name:" in content:
                                    lines = content.split('\n')
                                    for line in lines:
                                        if "Card name:" in line:
                                            gpu_name = line.split(":")[1].strip()
                                            gpu_info["gpus"].append({
                                                "id": len(gpu_info["gpus"]),
                                                "name": gpu_name,
                                                "memory_mb": "Unknown",
                                                "type": "unknown"
                                            })
                                            
                                            if not gpu_info["platform_gpu"]:
                                                gpu_info["platform_gpu"] = gpu_name
                                            break
                            os.remove("dxdiag_output.txt")
                    except Exception:
                        pass
                except Exception:
                    pass
        
        except Exception as e:
            logger.warning(f"Could not detect GPU: {e}")
        
        return gpu_info
    
    def _detect_network(self) -> Dict[str, Any]:
        """Detect network configuration."""
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Try to get public IP
            public_ip = None
            try:
                import urllib.request
                public_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
            except:
                pass
            
            return {
                "hostname": hostname,
                "local_ip": local_ip,
                "public_ip": public_ip,
                "ports": self._scan_common_ports()
            }
        
        except Exception as e:
            logger.warning(f"Could not detect network: {e}")
            return {"hostname": "Unknown", "local_ip": "Unknown"}
    
    def _scan_common_ports(self) -> Dict[str, bool]:
        """Scan common ports to check availability."""
        common_ports = {
            22: "SSH",
            80: "HTTP", 
            443: "HTTPS",
            5432: "PostgreSQL",
            6379: "Redis",
            8000: "FastAPI",
            5173: "Vite"
        }
        
        port_status = {}
        for port, name in common_ports.items():
            port_status[port] = self._is_port_open(port)
        
        return port_status
    
    def _is_port_open(self, port: int) -> bool:
        """Check if a port is open."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', port))
                return result == 0
        except:
            return False
    
    def _detect_software(self) -> Dict[str, Any]:
        """Detect installed software."""
        software = {
            "docker": self._check_docker(),
            "docker_compose": self._check_docker_compose(),
            "git": self._check_git(),
            "python": self._check_python(),
            "node": self._check_node(),
            "nginx": self._check_nginx()
        }
        
        return software
    
    def _check_docker(self) -> Dict[str, Any]:
        """Check Docker installation with cross-platform support."""
        system_name = platform.system()
        
        try:
            # Try different Docker commands based on platform
            docker_cmds = ["docker", "docker.exe"]
            
            for cmd in docker_cmds:
                try:
                    result = subprocess.run([cmd, "--version"], 
                                          capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        version = result.stdout.strip()
                        
                        # Check if Docker is running
                        running = False
                        try:
                            if system_name == "Windows":
                                # On Windows, check Docker Desktop
                                running_result = subprocess.run([cmd, "info"], 
                                                            capture_output=True, text=True, timeout=10)
                            else:
                                running_result = subprocess.run([cmd, "info"], 
                                                            capture_output=True, text=True, timeout=10)
                            
                            running = running_result.returncode == 0
                        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                            pass
                        
                        return {
                            "installed": True,
                            "version": version,
                            "running": running,
                            "command": cmd
                        }
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    continue
        except Exception:
            pass
        
        return {"installed": False, "version": None, "running": False, "command": None}
    
    def _check_docker_compose(self) -> Dict[str, Any]:
        """Check Docker Compose installation with cross-platform support."""
        system_name = platform.system()
        
        # Try different Docker Compose commands
        compose_cmds = [
            "docker-compose",
            "docker-compose.exe",
            "docker compose",  # New plugin syntax
            "docker.exe compose"
        ]
        
        for cmd in compose_cmds:
            try:
                # Handle command with space
                if " " in cmd:
                    parts = cmd.split()
                    result = subprocess.run(parts, capture_output=True, text=True, timeout=10)
                else:
                    result = subprocess.run([cmd, "--version"], 
                                          capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    return {
                        "installed": True, 
                        "version": result.stdout.strip(),
                        "command": cmd
                    }
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return {"installed": False, "version": None, "command": None}
    
    def _check_git(self) -> Dict[str, Any]:
        """Check Git installation with cross-platform support."""
        git_cmds = ["git", "git.exe", "git.cmd"]
        
        for cmd in git_cmds:
            try:
                result = subprocess.run([cmd, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {
                        "installed": True, 
                        "version": result.stdout.strip(),
                        "command": cmd
                    }
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return {"installed": False, "version": None, "command": None}
    
    def _check_python(self) -> Dict[str, Any]:
        """Check Python installation."""
        return {
            "installed": True,
            "version": platform.python_version(),
            "executable": sys.executable
        }
    
    def _check_node(self) -> Dict[str, Any]:
        """Check Node.js installation with cross-platform support."""
        node_cmds = ["node", "node.exe", "node.cmd"]
        
        for cmd in node_cmds:
            try:
                result = subprocess.run([cmd, "--version"], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return {
                        "installed": True, 
                        "version": result.stdout.strip(),
                        "command": cmd
                    }
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return {"installed": False, "version": None, "command": None}
    
    def _check_nginx(self) -> Dict[str, Any]:
        """Check Nginx installation with cross-platform support."""
        system_name = platform.system()
        nginx_cmds = []
        
        if system_name == "Windows":
            nginx_cmds = ["nginx.exe", "nginx"]
        else:
            nginx_cmds = ["nginx", "/usr/sbin/nginx", "/usr/local/nginx/sbin/nginx"]
        
        for cmd in nginx_cmds:
            try:
                result = subprocess.run([cmd, "-v"], 
                                      capture_output=True, text=True, timeout=10, stderr=subprocess.STDOUT)
                if result.returncode == 0 or "nginx version" in result.stdout:
                    return {
                        "installed": True, 
                        "version": result.stdout.strip(),
                        "command": cmd
                    }
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        return {"installed": False, "version": None, "command": None}
    
    def _get_recommendations(self) -> Dict[str, Any]:
        """Get setup recommendations based on system detection."""
        recommendations = {
            "deployment_type": "docker",
            "gpu_acceleration": False,
            "memory_allocation": "standard",
            "storage_requirements": "standard",
            "network_setup": "local",
            "warnings": [],
            "suggestions": []
        }
        
        # Check GPU availability
        if self.system_info.get("hardware", {}).get("gpu", {}).get("cuda_available"):
            recommendations["gpu_acceleration"] = True
            recommendations["deployment_type"] = "dgx" if len(self.system_info["hardware"]["gpu"]["gpus"]) > 1 else "gpu"
        
        # Check memory
        memory_gb = self.system_info.get("hardware", {}).get("memory", {}).get("total_gb", 0)
        if memory_gb < 8:
            recommendations["memory_allocation"] = "minimal"
            recommendations["warnings"].append("Low memory detected (< 8GB). Consider upgrading for better performance.")
        elif memory_gb >= 32:
            recommendations["memory_allocation"] = "high"
        
        # Check storage
        disk_gb = self.system_info.get("hardware", {}).get("disk", {}).get("total_gb", 0)
        if disk_gb < 50:
            recommendations["storage_requirements"] = "minimal"
            recommendations["warnings"].append("Low disk space detected (< 50GB). Free up space for model storage.")
        elif disk_gb >= 500:
            recommendations["storage_requirements"] = "high"
        
        # Check software requirements
        missing_software = []
        if not self.system_info.get("software", {}).get("docker", {}).get("installed"):
            missing_software.append("Docker")
        if not self.system_info.get("software", {}).get("docker_compose", {}).get("installed"):
            missing_software.append("Docker Compose")
        if not self.system_info.get("software", {}).get("git", {}).get("installed"):
            missing_software.append("Git")
        
        if missing_software:
            recommendations["warnings"].append(f"Missing required software: {', '.join(missing_software)}")
            recommendations["suggestions"].append("Install missing software before proceeding")
        
        # OS-specific recommendations
        os_name = self.system_info.get("os", {}).get("name", "")
        if os_name == "Darwin":
            recommendations["suggestions"].append("Consider using Docker Desktop for Mac")
        elif os_name == "Windows":
            recommendations["suggestions"].append("Consider using Docker Desktop for Windows")
            recommendations["suggestions"].append("Use WSL2 for better performance")
        
        return recommendations

class SetupManager:
    """Manages the setup process."""
    
    def __init__(self):
        self.detector = SystemDetector()
        self.setup_config = {}
        self.setup_progress = {}
    
    def get_setup_config(self) -> Dict[str, Any]:
        """Get current setup configuration."""
        return {
            "system_info": self.detector.system_info,
            "setup_config": self.setup_config,
            "setup_progress": self.setup_progress
        }
    
    def save_setup_config(self, config: Dict[str, Any]) -> bool:
        """Save setup configuration."""
        try:
            self.setup_config.update(config)
            
            # Save to file
            config_path = Path.home() / ".qgen_setup.json"
            with open(config_path, "w") as f:
                json.dump(self.get_setup_config(), f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save setup config: {e}")
            return False
    
    def load_setup_config(self) -> bool:
        """Load setup configuration."""
        try:
            config_path = Path.home() / ".qgen_setup.json"
            if config_path.exists():
                with open(config_path, "r") as f:
                    data = json.load(f)
                    self.setup_config = data.get("setup_config", {})
                    self.setup_progress = data.get("setup_progress", {})
                return True
        except Exception as e:
            logger.error(f"Failed to load setup config: {e}")
        
        return False
    
    async def run_setup_step(self, step: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Run a specific setup step."""
        try:
            self.setup_progress[step] = {"status": "running", "started_at": datetime.now().isoformat()}
            
            if step == "dependencies":
                result = await self._install_dependencies(config)
            elif step == "clone":
                result = await self._clone_repository(config)
            elif step == "environment":
                result = await self._setup_environment(config)
            elif step == "database":
                result = await self._setup_database(config)
            elif step == "frontend":
                result = await self._setup_frontend(config)
            elif step == "services":
                result = await self._start_services(config)
            elif step == "ssl":
                result = await self._setup_ssl(config)
            elif step == "initialize":
                result = await self._initialize_data(config)
            else:
                result = {"success": False, "error": f"Unknown setup step: {step}"}
            
            self.setup_progress[step] = {
                "status": "completed" if result.get("success") else "failed",
                "completed_at": datetime.now().isoformat(),
                "result": result
            }
            
            return result
        
        except Exception as e:
            self.setup_progress[step] = {
                "status": "failed",
                "completed_at": datetime.now().isoformat(),
                "error": str(e)
            }
            return {"success": False, "error": str(e)}
    
    async def _install_dependencies(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Install required dependencies with cross-platform support."""
        system_name = platform.system()
        commands = []
        
        # OS-specific dependency installation
        if system_name == "Linux":
            # Linux package installation
            package_manager = self._detect_package_manager()
            
            if package_manager == "apt":
                commands.extend([
                    "sudo apt update",
                    "sudo apt install -y git curl wget build-essential"
                ])
                
                # Install Docker if not present
                if not self.detector.system_info["software"]["docker"]["installed"]:
                    commands.extend([
                        "curl -fsSL https://get.docker.com -o get-docker.sh",
                        "sudo sh get-docker.sh",
                        "sudo usermod -aG docker $USER"
                    ])
                
                # Install Docker Compose if not present
                if not self.detector.system_info["software"]["docker_compose"]["installed"]:
                    commands.extend([
                        "sudo curl -L \"https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose",
                        "sudo chmod +x /usr/local/bin/docker-compose"
                    ])
            
            elif package_manager == "yum":
                commands.extend([
                    "sudo yum update -y",
                    "sudo yum install -y git curl wget"
                ])
                
                if not self.detector.system_info["software"]["docker"]["installed"]:
                    commands.extend([
                        "sudo yum install -y yum-utils",
                        "sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo",
                        "sudo yum install -y docker-ce docker-ce-cli containerd.io",
                        "sudo systemctl start docker",
                        "sudo systemctl enable docker",
                        "sudo usermod -aG docker $USER"
                    ])
            
            elif package_manager == "pacman":
                commands.extend([
                    "sudo pacman -Sy --noconfirm git curl wget"
                ])
                
                if not self.detector.system_info["software"]["docker"]["installed"]:
                    commands.extend([
                        "sudo pacman -S --noconfirm docker",
                        "sudo systemctl start docker",
                        "sudo systemctl enable docker",
                        "sudo usermod -aG docker $USER"
                    ])
        
        elif system_name == "Darwin":  # macOS
            # macOS setup
            if not self.detector.system_info["software"]["docker"]["installed"]:
                commands.extend([
                    "# Please install Docker Desktop for Mac from https://docs.docker.com/docker-for-mac/install/",
                    "# Or use Homebrew: brew install --cask docker"
                ])
            
            # Install Homebrew if not present
            try:
                subprocess.run(["brew", "--version"], capture_output=True, timeout=5)
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                commands.extend([
                    '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
                    "# Add Homebrew to PATH (for Apple Silicon Macs):",
                    "echo 'eval $(/opt/homebrew/bin/brew shellenv)' >> ~/.zshrc"
                ])
        
        elif system_name == "Windows":
            # Windows setup
            if not self.detector.system_info["software"]["docker"]["installed"]:
                commands.extend([
                    "# Please install Docker Desktop for Windows from https://docs.docker.com/docker-for-windows/install/",
                    "# Ensure WSL2 is enabled and configured"
                ])
            
            # Install Git for Windows if not present
            if not self.detector.system_info["software"]["git"]["installed"]:
                commands.extend([
                    "# Please install Git for Windows from https://git-scm.com/download/win",
                    "# Or use Chocolatey: choco install git"
                ])
        
        # Execute commands
        results = []
        for cmd in commands:
            try:
                if cmd.startswith("#"):
                    results.append({"command": cmd, "status": "info", "output": cmd[1:]})
                else:
                    # Handle platform-specific command execution
                    if system_name == "Windows" and not cmd.startswith("#"):
                        # On Windows, use PowerShell for some commands
                        if "sudo" in cmd:
                            # Replace sudo with PowerShell Run as Administrator
                            cmd = cmd.replace("sudo ", "")
                            results.append({
                                "command": cmd,
                                "status": "warning",
                                "output": "Please run this command as Administrator in PowerShell"
                            })
                            continue
                    
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                    results.append({
                        "command": cmd,
                        "status": "success" if result.returncode == 0 else "error",
                        "output": result.stdout,
                        "error": result.stderr
                    })
            except subprocess.TimeoutExpired:
                results.append({"command": cmd, "status": "timeout", "error": "Command timed out"})
            except Exception as e:
                results.append({"command": cmd, "status": "error", "error": str(e)})
        
        return {"success": True, "results": results}
    
    def _detect_package_manager(self) -> str:
        """Detect the Linux package manager."""
        package_managers = {
            "apt": ["apt-get", "apt"],
            "yum": ["yum", "dnf"],
            "pacman": ["pacman"],
            "zypper": ["zypper"],
            "emerge": ["emerge"]
        }
        
        for pm_name, pm_commands in package_managers.items():
            for cmd in pm_commands:
                try:
                    subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
                    return pm_name
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    continue
        
        return "unknown"
    
    async def _clone_repository(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Clone repository with cross-platform support."""
        repo_url = config.get("repository_url", "https://github.com/your-org/qgen_rag.git")
        install_dir = config.get("install_dir", "/opt/qgen")
        
        system_name = platform.system()
        
        # Adjust install directory for Windows
        if system_name == "Windows":
            install_dir = install_dir.replace("/opt/", "C:\\opt\\")
        
        try:
            # Create install directory with cross-platform support
            install_path = Path(install_dir)
            install_path.mkdir(parents=True, exist_ok=True)
            
            # Get git command
            git_cmd = self.detector.system_info["software"]["git"].get("command", "git")
            
            # Clone repository
            result = subprocess.run(
                [git_cmd, "clone", repo_url, install_dir],
                capture_output=True, text=True, timeout=600
            )
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr,
                "install_dir": install_dir
            }
        
        except Exception as e:
            return {"success": False, "error": str(e), "install_dir": install_dir}
    
    async def _setup_environment(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup environment configuration with cross-platform support."""
        install_dir = config.get("install_dir", "/opt/qgen")
        system_name = platform.system()
        
        # Adjust install directory for Windows
        if system_name == "Windows":
            install_dir = install_dir.replace("/opt/", "C:\\opt\\")
        
        try:
            # Create environment file
            env_content = self._generate_env_file(config)
            env_path = Path(install_dir) / ".env"
            
            with open(env_path, "w") as f:
                f.write(env_content)
            
            # Create necessary directories with cross-platform paths
            directories = ["models", "lora_adapters", "training_data", "logs", "backups"]
            created_dirs = []
            
            for dir_name in directories:
                dir_path = Path(install_dir) / dir_name
                dir_path.mkdir(exist_ok=True)
                created_dirs.append(str(dir_path))
            
            return {
                "success": True,
                "env_file": str(env_path),
                "directories_created": created_dirs,
                "install_dir": install_dir
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _generate_env_file(self, config: Dict[str, Any]) -> str:
        """Generate environment file content."""
        env_vars = [
            "# System Configuration",
            f"ENVIRONMENT={config.get('environment', 'production')}",
            f"DEBUG={config.get('debug', 'false')}",
            f"LOG_LEVEL={config.get('log_level', 'INFO')}",
            "",
            "# Domain Configuration",
            f"DOMAIN={config.get('domain', 'localhost')}",
            f"SSL_EMAIL={config.get('ssl_email', 'admin@example.com')}",
            "",
            "# Security",
            f"SECRET_KEY={config.get('secret_key', 'your-secret-key-here')}",
            f"POSTGRES_PASSWORD={config.get('postgres_password', 'postgres')}",
            f"REDIS_PASSWORD={config.get('redis_password', 'redis')}",
            "",
            "# External APIs",
            f"OPENAI_API_KEY={config.get('openai_api_key', '')}",
            f"DEEPSEEK_API_KEY={config.get('deepseek_api_key', '')}",
            "",
            "# Model Configuration",
            f"LOCAL_MODEL_PATH={config.get('local_model_path', 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B')}",
            f"MODEL_CACHE_DIR={config.get('install_dir', '/opt/qgen')}/models",
            f"LORA_ADAPTERS_DIR={config.get('install_dir', '/opt/qgen')}/lora_adapters",
            f"TRAINING_DATA_DIR={config.get('install_dir', '/opt/qgen')}/training_data",
            "",
            "# GPU Configuration",
            f"CUDA_VISIBLE_DEVICES={config.get('cuda_devices', '0,1,2,3')}",
            f"USE_FLASH_ATTN={config.get('use_flash_attn', 'true')}",
            f"USE_4BIT={config.get('use_4bit', 'true')}",
            f"MAX_NEW_TOKENS={config.get('max_new_tokens', '2048')}",
            f"BATCH_SIZE={config.get('batch_size', '4')}",
            f"MAX_BATCH_SIZE={config.get('max_batch_size', '8')}",
            "",
            "# Training Configuration",
            f"TRAINING_BASE_MODEL={config.get('training_base_model', 'deepseek-ai/DeepSeek-R1-Distill-Llama-8B')}",
            f"LEARNING_RATE={config.get('learning_rate', '2e-4')}",
            f"NUM_EPOCHS={config.get('num_epochs', '3')}",
            f"LORA_R={config.get('lora_r', '16')}",
            f"LORA_ALPHA={config.get('lora_alpha', '32')}",
            "",
            "# Monitoring",
            f"GRAFANA_PASSWORD={config.get('grafana_password', 'admin')}",
        ]
        
        return "\n".join(env_vars)
    
    async def _setup_database(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup database and backend services."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            # Start database services
            commands = [
                f"cd {install_dir}",
                "docker-compose -f docker-compose.dgx.yml up -d postgres redis"
            ]
            
            results = []
            for cmd in commands:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                results.append({
                    "command": cmd,
                    "status": "success" if result.returncode == 0 else "error",
                    "output": result.stdout,
                    "error": result.stderr
                })
            
            # Wait for database to be ready
            import time
            time.sleep(30)
            
            # Run database migrations
            migrate_cmd = f"cd {install_dir} && docker-compose exec backend alembic upgrade head"
            migrate_result = subprocess.run(migrate_cmd, shell=True, capture_output=True, text=True, timeout=300)
            
            results.append({
                "command": migrate_cmd,
                "status": "success" if migrate_result.returncode == 0 else "error",
                "output": migrate_result.stdout,
                "error": migrate_result.stderr
            })
            
            return {"success": True, "results": results}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_frontend(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup frontend trainer-web application."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            system_name = platform.system()
            commands = []
            
            # Check if Node.js is installed
            if not self.detector.system_info["software"]["node"]["installed"]:
                commands.append("# Node.js is required for frontend build")
                if system_name == "Windows":
                    commands.append("# Please install Node.js from https://nodejs.org")
                elif system_name == "Darwin":
                    commands.append("brew install node")
                else:
                    commands.append("# Install Node.js using your package manager")
                    commands.append("# For Ubuntu/Debian: sudo apt install nodejs npm")
                    commands.append("# For CentOS/RHEL: sudo yum install nodejs npm")
                    commands.append("# For Arch: sudo pacman -S nodejs npm")
            
            # Navigate to trainer-web directory
            trainer_web_dir = os.path.join(install_dir, "trainer-web")
            
            if os.path.exists(trainer_web_dir):
                # Install frontend dependencies
                install_cmd = f"cd {trainer_web_dir} && npm install"
                commands.append(install_cmd)
                
                # Build frontend for production
                build_cmd = f"cd {trainer_web_dir} && npm run build"
                commands.append(build_cmd)
                
                # Check if build was successful
                build_dir = os.path.join(trainer_web_dir, "build")
                if os.path.exists(build_dir):
                    commands.append("# Frontend build completed successfully")
                else:
                    commands.append("# Frontend build may have failed - check logs")
            else:
                commands.append(f"# Trainer-web directory not found at {trainer_web_dir}")
                commands.append("# Frontend will be served from development mode")
            
            results = []
            for cmd in commands:
                try:
                    if cmd.startswith("#"):
                        results.append({"command": cmd, "status": "info", "output": cmd[1:]})
                    else:
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
                        results.append({
                            "command": cmd,
                            "status": "success" if result.returncode == 0 else "error",
                            "output": result.stdout,
                            "error": result.stderr
                        })
                except subprocess.TimeoutExpired:
                    results.append({"command": cmd, "status": "timeout", "error": "Command timed out"})
                except Exception as e:
                    results.append({"command": cmd, "status": "error", "error": str(e)})
            
            return {"success": True, "results": results}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _start_services(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Start all services including backend and frontend."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            commands = []
            results = []
            
            # Start all services with docker-compose
            start_cmd = f"cd {install_dir} && docker-compose -f docker-compose.dgx.yml up -d"
            commands.append(start_cmd)
            
            # Wait for services to start
            commands.append("# Waiting for services to start...")
            import time
            time.sleep(30)
            
            # Check service status
            status_cmd = f"cd {install_dir} && docker-compose -f docker-compose.dgx.yml ps"
            commands.append(status_cmd)
            
            # Check if frontend is running in development mode
            frontend_check_cmd = f"cd {install_dir} && docker-compose logs frontend | tail -10"
            commands.append(frontend_check_cmd)
            
            # Check backend health
            health_check_cmd = f"cd {install_dir} && docker-compose exec backend curl -f http://localhost:8000/health || echo 'Backend not ready yet'"
            commands.append(health_check_cmd)
            
            for cmd in commands:
                try:
                    if cmd.startswith("#"):
                        results.append({"command": cmd, "status": "info", "output": cmd[1:]})
                    else:
                        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                        results.append({
                            "command": cmd,
                            "status": "success" if result.returncode == 0 else "error",
                            "output": result.stdout,
                            "error": result.stderr
                        })
                except subprocess.TimeoutExpired:
                    results.append({"command": cmd, "status": "timeout", "error": "Command timed out"})
                except Exception as e:
                    results.append({"command": cmd, "status": "error", "error": str(e)})
            
            return {
                "success": True, 
                "results": results,
                "services": {
                    "backend_url": f"http://{config.get('domain', 'localhost')}:8000",
                    "frontend_url": f"http://{config.get('domain', 'localhost')}:5173",
                    "api_docs": f"http://{config.get('domain', 'localhost')}:8000/docs"
                }
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _setup_ssl(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup SSL certificate."""
        domain = config.get("domain", "localhost")
        email = config.get("ssl_email", "admin@example.com")
        
        if domain == "localhost":
            return {"success": True, "message": "SSL not required for localhost"}
        
        try:
            # Install certbot if not present
            install_cmd = "sudo apt install -y certbot python3-certbot-nginx"
            install_result = subprocess.run(install_cmd, shell=True, capture_output=True, text=True, timeout=300)
            
            # Get SSL certificate
            ssl_cmd = f"sudo certbot --nginx -d {domain} --email {email} --agree-tos --non-interactive"
            ssl_result = subprocess.run(ssl_cmd, shell=True, capture_output=True, text=True, timeout=300)
            
            return {
                "success": ssl_result.returncode == 0,
                "install_result": install_result.stdout,
                "ssl_result": ssl_result.stdout,
                "error": ssl_result.stderr
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _initialize_data(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize sample data."""
        install_dir = config.get("install_dir", "/opt/qgen")
        
        try:
            cmd = f"cd {install_dir} && docker-compose exec backend python scripts/init_data_collection.py"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
            
            return {
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}

# FastAPI Application
app = FastAPI(title="QGen RAG Interactive Setup", version="1.0.0")

# Templates
templates = Jinja2Templates(directory="templates")

# Global instances
detector = SystemDetector()
setup_manager = SetupManager()

@app.get("/", response_class=HTMLResponse)
async def setup_home(request: Request):
    """Main setup page."""
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "system_info": detector.system_info
    })

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

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>QGen RAG Interactive Setup</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        .step-card { @apply bg-white rounded-lg shadow-md p-6 mb-4; }
        .step-active { @apply border-l-4 border-blue-500; }
        .step-completed { @apply border-l-4 border-green-500; }
        .step-error { @apply border-l-4 border-red-500; }
        .progress-bar { @apply bg-blue-500 h-2 rounded-full transition-all duration-500; }
    </style>
</head>
<body class="bg-gray-100">
    <div class="container mx-auto px-4 py-8">
        <header class="text-center mb-8">
            <h1 class="text-4xl font-bold text-gray-800 mb-2">🚀 QGen RAG Setup</h1>
            <p class="text-gray-600">Interactive setup for your SLM/LLM training system</p>
        </header>

        <!-- System Detection -->
        <div class="step-card">
            <h2 class="text-2xl font-semibold mb-4">🖥️ System Detection</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div class="bg-gray-50 p-4 rounded">
                    <h3 class="font-semibold text-gray-700">Operating System</h3>
                    <p class="text-sm text-gray-600">{{ system_info.os.name }} {{ system_info.os.version }}</p>
                </div>
                <div class="bg-gray-50 p-4 rounded">
                    <h3 class="font-semibold text-gray-700">Hardware</h3>
                    <p class="text-sm text-gray-600">{{ system_info.hardware.cpu.cores }} cores, {{ "%.1f"|format(system_info.hardware.memory.total_gb) }}GB RAM</p>
                </div>
                <div class="bg-gray-50 p-4 rounded">
                    <h3 class="font-semibold text-gray-700">GPU</h3>
                    <p class="text-sm text-gray-600">
                        {% if system_info.hardware.gpu.cuda_available %}
                            {{ system_info.hardware.gpu.gpus|length }} NVIDIA GPUs
                        {% else %}
                            No CUDA GPU detected
                        {% endif %}
                    </p>
                </div>
            </div>
            
            <!-- Recommendations -->
            <div class="mt-4">
                <h3 class="font-semibold text-gray-700 mb-2">Recommendations</h3>
                {% if system_info.recommendations.warnings %}
                    <div class="bg-yellow-50 border-l-4 border-yellow-400 p-4 mb-2">
                        <h4 class="font-semibold text-yellow-800">⚠️ Warnings</h4>
                        <ul class="list-disc list-inside text-yellow-700">
                            {% for warning in system_info.recommendations.warnings %}
                                <li>{{ warning }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                {% endif %}
                {% if system_info.recommendations.suggestions %}
                    <div class="bg-blue-50 border-l-4 border-blue-400 p-4">
                        <h4 class="font-semibold text-blue-800">💡 Suggestions</h4>
                        <ul class="list-disc list-inside text-blue-700">
                            {% for suggestion in system_info.recommendations.suggestions %}
                                <li>{{ suggestion }}</li>
                            {% endfor %}
                        </ul>
                    </div>
                {% endif %}
            </div>
        </div>

        <!-- Setup Configuration -->
        <div class="step-card">
            <h2 class="text-2xl font-semibold mb-4">⚙️ Configuration</h2>
            <form id="setupForm" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Installation Directory</label>
                        <input type="text" name="install_dir" value="/opt/qgen" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Domain</label>
                        <input type="text" name="domain" value="localhost" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">SSL Email</label>
                        <input type="email" name="ssl_email" value="admin@example.com" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Environment</label>
                        <select name="environment" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            <option value="production">Production</option>
                            <option value="development">Development</option>
                        </select>
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">OpenAI API Key</label>
                        <input type="password" name="openai_api_key" placeholder="sk-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">DeepSeek API Key</label>
                        <input type="password" name="deepseek_api_key" placeholder="sk-..." class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                    </div>
                </div>
                
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Repository URL</label>
                        <input type="url" name="repository_url" value="https://github.com/your-org/qgen_rag.git" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-gray-700">Base Model</label>
                        <select name="local_model_path" class="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500">
                            <option value="deepseek-ai/DeepSeek-R1-Distill-Llama-8B">DeepSeek-R1-8B (Recommended)</option>
                            <option value="deepseek-ai/DeepSeek-R1-Distill-Llama-70B">DeepSeek-R1-70B (Large)</option>
                        </select>
                    </div>
                </div>
                
                <button type="submit" class="w-full bg-blue-500 text-white py-2 px-4 rounded-md hover:bg-blue-600 transition-colors">
                    Start Setup
                </button>
            </form>
        </div>

        <!-- Setup Progress -->
        <div class="step-card" id="progressSection" style="display: none;">
            <h2 class="text-2xl font-semibold mb-4">🔄 Setup Progress</h2>
            <div class="space-y-4">
                <div class="step-item" data-step="dependencies">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">📦 Install Dependencies</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="clone">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">📥 Clone Repository</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="environment">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">⚙️ Setup Environment</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="database">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">🗄️ Setup Database</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="frontend">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">🎨 Setup Frontend</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="services">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">🚀 Start Services</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="ssl">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">🔒 Setup SSL</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
                
                <div class="step-item" data-step="initialize">
                    <div class="flex justify-between items-center">
                        <span class="font-medium">🎯 Initialize Data</span>
                        <span class="step-status text-sm text-gray-500">Pending</span>
                    </div>
                    <div class="mt-2 bg-gray-200 rounded-full h-2">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="step-output hidden mt-2 bg-gray-900 text-green-400 p-2 rounded text-sm font-mono text-xs max-h-32 overflow-y-auto"></div>
                </div>
            </div>
        </div>

        <!-- Completion -->
        <div class="step-card" id="completionSection" style="display: none;">
            <h2 class="text-2xl font-semibold mb-4">✅ Setup Complete!</h2>
            <div class="bg-green-50 border-l-4 border-green-400 p-4 mb-4">
                <h3 class="font-semibold text-green-800">Your QGen RAG system is ready!</h3>
                <div class="mt-2 space-y-2">
                    <p><strong>🎨 Frontend (Trainer Web):</strong> <a href="#" id="frontendUrl" class="text-blue-600 hover:underline">http://localhost:5173</a></p>
                    <p><strong>🔧 Backend API:</strong> <a href="#" id="backendUrl" class="text-blue-600 hover:underline">http://localhost:8000</a></p>
                    <p><strong>📚 API Documentation:</strong> <a href="#" id="apiDocsUrl" class="text-blue-600 hover:underline">http://localhost:8000/docs</a></p>
                    <p><strong>👤 Admin Panel:</strong> <a href="#" id="adminUrl" class="text-blue-600 hover:underline">http://localhost:5173/admin</a></p>
                    <p><strong>📊 Monitoring:</strong> <a href="#" id="monitoringUrl" class="text-blue-600 hover:underline">http://localhost:3000</a></p>
                </div>
            </div>
            <div class="bg-blue-50 border-l-4 border-blue-400 p-4">
                <h3 class="font-semibold text-blue-800">Next Steps</h3>
                <ol class="list-decimal list-inside text-blue-700 mt-2 space-y-1">
                    <li>Create admin and user accounts</li>
                    <li>Upload reference documents</li>
                    <li>Start generating questions</li>
                    <li>Begin vetting process</li>
                    <li>Monitor system performance</li>
                </ol>
            </div>
        </div>
    </div>

    <script>
        let setupConfig = {};
        let currentStep = 0;
        const steps = ['dependencies', 'clone', 'environment', 'database', 'frontend', 'services', 'ssl', 'initialize'];

        // Form submission
        document.getElementById('setupForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Collect form data
            const formData = new FormData(e.target);
            setupConfig = Object.fromEntries(formData);
            
            // Save configuration
            const response = await fetch('/api/setup-config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(setupConfig)
            });
            
            if (response.ok) {
                // Show progress section
                document.getElementById('progressSection').style.display = 'block';
                e.target.style.display = 'none';
                
                // Start setup process
                await runSetupProcess();
            }
        });

        async function runSetupProcess() {
            for (let i = 0; i < steps.length; i++) {
                const step = steps[i];
                await runStep(step);
            }
            
            // Show completion
            document.getElementById('progressSection').style.display = 'none';
            document.getElementById('completionSection').style.display = 'block';
            
            // Update URLs
            const domain = setupConfig.domain || 'localhost';
            document.getElementById('frontendUrl').href = `http://${domain}:5173`;
            document.getElementById('frontendUrl').textContent = `http://${domain}:5173`;
            document.getElementById('backendUrl').href = `http://${domain}:8000`;
            document.getElementById('backendUrl').textContent = `http://${domain}:8000`;
            document.getElementById('apiDocsUrl').href = `http://${domain}:8000/docs`;
            document.getElementById('apiDocsUrl').textContent = `http://${domain}:8000/docs`;
            document.getElementById('adminUrl').href = `http://${domain}:5173/admin`;
            document.getElementById('adminUrl').textContent = `http://${domain}:5173/admin`;
            document.getElementById('monitoringUrl').href = `http://${domain}:3000`;
            document.getElementById('monitoringUrl').textContent = `http://${domain}:3000`;
        }

        async function runStep(step) {
            const stepElement = document.querySelector(`[data-step="${step}"]`);
            const statusElement = stepElement.querySelector('.step-status');
            const progressBar = stepElement.querySelector('.progress-bar');
            const outputElement = stepElement.querySelector('.step-output');
            
            // Update UI
            statusElement.textContent = 'Running...';
            statusElement.className = 'step-status text-sm text-blue-500';
            progressBar.style.width = '50%';
            stepElement.classList.add('step-active');
            
            try {
                const response = await fetch(`/api/setup-step/${step}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(setupConfig)
                });
                
                const result = await response.json();
                
                if (result.success) {
                    statusElement.textContent = 'Completed';
                    statusElement.className = 'step-status text-sm text-green-500';
                    progressBar.style.width = '100%';
                    stepElement.classList.add('step-completed');
                    
                    // Show output if available
                    if (result.output) {
                        outputElement.textContent = result.output;
                        outputElement.classList.remove('hidden');
                    }
                } else {
                    statusElement.textContent = 'Failed';
                    statusElement.className = 'step-status text-sm text-red-500';
                    stepElement.classList.add('step-error');
                    
                    // Show error
                    if (result.error) {
                        outputElement.textContent = result.error;
                        outputElement.classList.remove('hidden');
                        outputElement.classList.add('text-red-400');
                    }
                }
            } catch (error) {
                statusElement.textContent = 'Error';
                statusElement.className = 'step-status text-sm text-red-500';
                stepElement.classList.add('step-error');
                outputElement.textContent = error.message;
                outputElement.classList.remove('hidden');
                outputElement.classList.add('text-red-400');
            }
        }

        // Load existing setup config
        async function loadSetupConfig() {
            try {
                const response = await fetch('/api/setup-config');
                const config = await response.json();
                
                if (config.setup_config) {
                    setupConfig = config.setup_config;
                    // Populate form
                    Object.keys(setupConfig).forEach(key => {
                        const element = document.querySelector(`[name="${key}"]`);
                        if (element) {
                            element.value = setupConfig[key];
                        }
                    });
                }
            } catch (error) {
                console.log('No existing configuration found');
            }
        }

        // Initialize
        loadSetupConfig();
    </script>
</body>
</html>
"""

# Create templates directory and file
def create_templates():
    """Create templates directory and HTML file."""
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)
    
    with open(templates_dir / "setup.html", "w") as f:
        f.write(HTML_TEMPLATE)

async def main():
    """Main entry point."""
    print("🚀 QGen RAG Interactive Setup")
    print("=" * 50)
    
    # Create templates
    create_templates()
    
    # Load existing configuration
    setup_manager.load_setup_config()
    
    # Detect system
    system_info = detector.detect_all()
    
    print(f"🖥️  System: {system_info['os']['name']} {system_info['os']['version']}")
    print(f"💾 Memory: {system_info['hardware']['memory']['total_gb']:.1f}GB")
    print(f"🔧 CPU: {system_info['hardware']['cpu']['cores']} cores")
    
    if system_info['hardware']['gpu']['cuda_available']:
        print(f"🎮 GPU: {len(system_info['hardware']['gpu']['gpus'])} NVIDIA GPUs")
    else:
        print("⚠️  No CUDA GPU detected")
    
    print("\n📝 Recommendations:")
    recommendations = system_info['recommendations']
    
    if recommendations['warnings']:
        print("⚠️  Warnings:")
        for warning in recommendations['warnings']:
            print(f"   - {warning}")
    
    if recommendations['suggestions']:
        print("💡 Suggestions:")
        for suggestion in recommendations['suggestions']:
            print(f"   - {suggestion}")
    
    print(f"\n🌐 Starting web setup at: http://localhost:8080")
    print("📋 Open your browser and follow the interactive setup guide")
    
    # Start web server
    config = uvicorn.Config(app, host="0.0.0.0", port=8080, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
