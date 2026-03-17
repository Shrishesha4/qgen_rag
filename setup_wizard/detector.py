"""
System environment detection module.
Detects OS, CPU architecture, Docker availability, and environment constraints.
"""

import os
import platform
import shutil
import subprocess
import socket
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _run_cmd(cmd: list[str], timeout: int = 10) -> Optional[str]:
    """Run a command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None


def detect_os() -> Dict[str, str]:
    """Detect operating system details."""
    system = platform.system().lower()
    os_map = {"darwin": "macos", "linux": "linux", "windows": "windows"}
    os_name = os_map.get(system, system)

    info = {
        "os": os_name,
        "os_raw": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "hostname": socket.gethostname(),
    }

    if os_name == "macos":
        mac_ver = platform.mac_ver()[0]
        if mac_ver:
            info["os_friendly"] = f"macOS {mac_ver}"
        else:
            info["os_friendly"] = "macOS"
    elif os_name == "linux":
        distro = _run_cmd(["lsb_release", "-d", "-s"])
        if not distro:
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("PRETTY_NAME="):
                            distro = line.split("=", 1)[1].strip().strip('"')
                            break
            except FileNotFoundError:
                pass
        info["os_friendly"] = distro or "Linux"
    elif os_name == "windows":
        info["os_friendly"] = f"Windows {platform.release()}"
    else:
        info["os_friendly"] = platform.platform()

    return info


def detect_architecture() -> Dict[str, str]:
    """Detect CPU architecture."""
    machine = platform.machine().lower()
    arch_map = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "arm64",
        "aarch64": "arm64",
        "armv7l": "armv7",
        "i386": "x86",
        "i686": "x86",
    }
    normalized = arch_map.get(machine, machine)

    info = {
        "arch": normalized,
        "arch_raw": platform.machine(),
        "processor": platform.processor() or "unknown",
        "bits": "64" if "64" in machine else "32",
    }

    # Detect Apple Silicon
    if normalized == "arm64" and platform.system() == "Darwin":
        brand = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
        info["cpu_brand"] = brand or "Apple Silicon"
        info["is_apple_silicon"] = True
    else:
        info["is_apple_silicon"] = False
        if platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if line.startswith("model name"):
                            info["cpu_brand"] = line.split(":", 1)[1].strip()
                            break
            except FileNotFoundError:
                pass
        elif platform.system() == "Darwin":
            brand = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"])
            if brand:
                info["cpu_brand"] = brand

    return info


def detect_environment() -> Dict[str, Any]:
    """Detect if running in VM, container, or cloud environment."""
    env_info: Dict[str, Any] = {
        "type": "local",
        "is_vm": False,
        "is_container": False,
        "is_cloud": False,
        "details": "",
    }

    # Check for Docker/container
    if os.path.exists("/.dockerenv"):
        env_info["is_container"] = True
        env_info["type"] = "container"
        env_info["details"] = "Docker container"
        return env_info

    cgroup = None
    try:
        with open("/proc/1/cgroup") as f:
            cgroup = f.read()
    except (FileNotFoundError, PermissionError):
        pass

    if cgroup and ("docker" in cgroup or "kubepods" in cgroup):
        env_info["is_container"] = True
        env_info["type"] = "container"
        env_info["details"] = "Docker/Kubernetes container"
        return env_info

    # Check for common VM/cloud indicators
    sys_vendor = None
    for path in [
        "/sys/class/dmi/id/sys_vendor",
        "/sys/class/dmi/id/product_name",
    ]:
        try:
            with open(path) as f:
                sys_vendor = f.read().strip().lower()
                break
        except (FileNotFoundError, PermissionError):
            pass

    cloud_vendors = {
        "amazon": ("cloud", "AWS EC2"),
        "google": ("cloud", "Google Cloud"),
        "microsoft": ("cloud", "Azure"),
        "digitalocean": ("cloud", "DigitalOcean"),
        "vmware": ("vm", "VMware"),
        "virtualbox": ("vm", "VirtualBox"),
        "qemu": ("vm", "QEMU/KVM"),
        "parallels": ("vm", "Parallels"),
    }

    if sys_vendor:
        for vendor_key, (env_type, label) in cloud_vendors.items():
            if vendor_key in sys_vendor:
                env_info["type"] = env_type
                env_info[f"is_{env_type}"] = True
                env_info["details"] = label
                return env_info

    # macOS: check for VM via sysctl
    if platform.system() == "Darwin":
        model = _run_cmd(["sysctl", "-n", "hw.model"])
        if model and "virtual" in model.lower():
            env_info["is_vm"] = True
            env_info["type"] = "vm"
            env_info["details"] = "Virtual Machine"

    env_info["details"] = "Local machine"
    return env_info


def detect_docker() -> Dict[str, Any]:
    """Detect Docker and Docker Compose availability."""
    info: Dict[str, Any] = {
        "docker_installed": False,
        "docker_version": None,
        "docker_running": False,
        "compose_installed": False,
        "compose_version": None,
        "compose_command": None,
    }

    # Check docker
    docker_path = shutil.which("docker")
    if docker_path:
        info["docker_installed"] = True
        ver = _run_cmd(["docker", "--version"])
        if ver:
            info["docker_version"] = ver

        # Check if docker daemon is running
        ping = _run_cmd(["docker", "info"])
        info["docker_running"] = ping is not None

    # Check docker compose (v2 plugin style)
    compose_ver = _run_cmd(["docker", "compose", "version"])
    if compose_ver:
        info["compose_installed"] = True
        info["compose_version"] = compose_ver
        info["compose_command"] = "docker compose"
    else:
        # Fallback: docker-compose (standalone)
        compose_ver = _run_cmd(["docker-compose", "--version"])
        if compose_ver:
            info["compose_installed"] = True
            info["compose_version"] = compose_ver
            info["compose_command"] = "docker-compose"

    return info


def detect_tools() -> Dict[str, Any]:
    """Detect availability of required/optional tools."""
    tools = {}

    checks = {
        "python": ["python3", "--version"],
        "node": ["node", "--version"],
        "npm": ["npm", "--version"],
        "git": ["git", "--version"],
        "ollama": ["ollama", "--version"],
        "pip": ["pip3", "--version"],
        "brew": ["brew", "--version"],
    }

    for name, cmd in checks.items():
        ver = _run_cmd(cmd)
        tools[name] = {
            "installed": ver is not None,
            "version": ver,
            "path": shutil.which(cmd[0]),
        }

    return tools


def detect_ports() -> Dict[str, bool]:
    """Check if required ports are available."""
    ports = {
        "5432": "PostgreSQL",
        "6379": "Redis",
        "8000": "API Server",
        "8080": "Setup Wizard",
        "5173": "Trainer Web",
        "11434": "Ollama",
    }

    result = {}
    for port_str, label in ports.items():
        port = int(port_str)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.bind(("127.0.0.1", port))
                result[port_str] = {"available": True, "label": label}
        except OSError:
            result[port_str] = {"available": False, "label": label}

    return result


def detect_existing_config(project_root: str) -> Dict[str, Any]:
    """Detect existing configuration files in the project."""
    root = Path(project_root)
    configs = {}

    files_to_check = [
        (".env.local", "Root environment file"),
        ("client/.env.local", "Client environment file"),
        ("trainer-web/.env.local", "Trainer web environment file"),
        ("docker-compose.yml", "Docker Compose file"),
        ("docker-compose.prod.yml", "Docker Compose production overrides"),
    ]

    for rel_path, label in files_to_check:
        full_path = root / rel_path
        configs[rel_path] = {
            "exists": full_path.exists(),
            "label": label,
            "path": str(full_path),
        }

    return configs


def detect_all(project_root: str) -> Dict[str, Any]:
    """Run all detection routines and return combined results."""
    logger.info("Running system detection...")

    result = {
        "os": detect_os(),
        "architecture": detect_architecture(),
        "environment": detect_environment(),
        "docker": detect_docker(),
        "tools": detect_tools(),
        "ports": detect_ports(),
        "existing_config": detect_existing_config(project_root),
        "project_root": project_root,
    }

    logger.info("System detection complete.")
    return result
