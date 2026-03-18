"""
Dependency installer and service startup module.
Handles installing dependencies and spinning up services.
"""

import os
import subprocess
import shutil
import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


class TaskRunner:
    """Runs installation tasks with progress reporting."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.log_lines: List[str] = []
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable):
        self._progress_callback = callback

    def _log(self, message: str, level: str = "info"):
        entry = {"time": time.strftime("%H:%M:%S"), "level": level, "msg": message}
        self.log_lines.append(json.dumps(entry))
        getattr(logger, level, logger.info)(message)
        if self._progress_callback:
            self._progress_callback(entry)

    def _run(self, cmd: list[str], cwd: Optional[str] = None, timeout: int = 300) -> tuple[bool, str]:
        """Run a command, return (success, output)."""
        self._log(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=cwd or str(self.project_root),
                timeout=timeout,
            )
            output = result.stdout + result.stderr
            if result.returncode != 0:
                self._log(f"Command failed (exit {result.returncode}): {output[:500]}", "error")
                return False, output
            self._log(f"Command succeeded")
            return True, output
        except subprocess.TimeoutExpired:
            self._log(f"Command timed out after {timeout}s", "error")
            return False, "timeout"
        except FileNotFoundError:
            self._log(f"Command not found: {cmd[0]}", "error")
            return False, "not found"

    def check_prerequisites(self) -> Dict[str, Any]:
        """Check that minimum requirements are met."""
        results = {}

        # Python
        ok, out = self._run(["python3", "--version"])
        results["python"] = {"ok": ok, "detail": out.strip() if ok else "Python 3 not found"}

        # Docker
        ok, out = self._run(["docker", "--version"])
        results["docker"] = {"ok": ok, "detail": out.strip() if ok else "Docker not found"}

        if ok:
            ok2, out2 = self._run(["docker", "info"])
            results["docker_running"] = {"ok": ok2, "detail": "Docker daemon running" if ok2 else "Docker daemon not running"}
        else:
            results["docker_running"] = {"ok": False, "detail": "Docker not installed"}

        # Docker Compose
        ok, out = self._run(["docker", "compose", "version"])
        if not ok:
            ok, out = self._run(["docker-compose", "--version"])
        results["docker_compose"] = {"ok": ok, "detail": out.strip() if ok else "Docker Compose not found"}

        # Node.js
        ok, out = self._run(["node", "--version"])
        results["node"] = {"ok": ok, "detail": out.strip() if ok else "Node.js not found"}

        # npm
        ok, out = self._run(["npm", "--version"])
        results["npm"] = {"ok": ok, "detail": out.strip() if ok else "npm not found"}

        return results

    def install_backend_deps(self, use_docker: bool = True) -> Dict[str, Any]:
        """Install backend Python dependencies."""
        if use_docker:
            self._log("Backend dependencies will be installed via Docker build")
            return {"ok": True, "method": "docker"}

        self._log("Installing backend Python dependencies locally...")
        req_path = self.project_root / "backend" / "requirements.txt"
        if not req_path.exists():
            self._log("requirements.txt not found", "error")
            return {"ok": False, "error": "requirements.txt not found"}

        ok, out = self._run(
            ["pip3", "install", "-r", str(req_path)],
            cwd=str(self.project_root / "backend"),
            timeout=600,
        )
        return {"ok": ok, "method": "pip", "output": out[:1000]}

    def install_client_deps(self) -> Dict[str, Any]:
        """Install client (Expo) npm dependencies."""
        client_dir = self.project_root / "client"
        if not (client_dir / "package.json").exists():
            self._log("client/package.json not found, skipping", "warning")
            return {"ok": False, "error": "package.json not found"}

        self._log("Installing client npm dependencies...")
        ok, out = self._run(
            ["npm", "install", "--legacy-peer-deps"],
            cwd=str(client_dir),
            timeout=300,
        )
        return {"ok": ok, "output": out[:1000]}

    def install_trainer_web_deps(self) -> Dict[str, Any]:
        """Install trainer-web npm dependencies."""
        tw_dir = self.project_root / "trainer-web"
        if not (tw_dir / "package.json").exists():
            self._log("trainer-web/package.json not found, skipping", "warning")
            return {"ok": False, "error": "package.json not found"}

        self._log("Installing trainer-web npm dependencies...")
        ok, out = self._run(
            ["npm", "install"],
            cwd=str(tw_dir),
            timeout=300,
        )
        return {"ok": ok, "output": out[:1000]}

    def start_docker_services(self, compose_cmd: str = "docker compose") -> Dict[str, Any]:
        """Start Docker services using docker-compose."""
        self._log("Starting Docker services...")
        cmd_parts = compose_cmd.split() + [
            "--env-file", ".env.local", "up", "-d", "--build"
        ]
        ok, out = self._run(cmd_parts, timeout=600)
        return {"ok": ok, "output": out[:2000]}

    def stop_docker_services(self, compose_cmd: str = "docker compose") -> Dict[str, Any]:
        """Stop Docker services."""
        self._log("Stopping Docker services...")
        cmd_parts = compose_cmd.split() + ["down"]
        ok, out = self._run(cmd_parts, timeout=120)
        return {"ok": ok, "output": out[:1000]}

    def check_docker_services(self, compose_cmd: str = "docker compose") -> Dict[str, Any]:
        """Check status of Docker services."""
        cmd_parts = compose_cmd.split() + ["ps", "--format", "json"]
        ok, out = self._run(cmd_parts, timeout=30)
        if ok:
            try:
                services = []
                for line in out.strip().split("\n"):
                    if line.strip():
                        services.append(json.loads(line))
                return {"ok": True, "services": services}
            except json.JSONDecodeError:
                return {"ok": True, "services": [], "raw": out[:1000]}
        return {"ok": False, "output": out[:1000]}

    def setup_ollama(self, model: str = "llama3.1:8b") -> Dict[str, Any]:
        """Check Ollama and pull required models."""
        self._log("Checking Ollama...")

        ok, out = self._run(["ollama", "--version"])
        if not ok:
            return {"ok": False, "error": "Ollama not installed. Install from https://ollama.ai"}

        # Check if ollama is serving
        import urllib.request
        try:
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=5)
            self._log("Ollama is running")
        except Exception:
            self._log("Ollama is not running. Please start it with: ollama serve", "warning")
            return {"ok": False, "error": "Ollama not running"}

        # Pull model
        self._log(f"Pulling Ollama model: {model} (this may take a while)...")
        ok, out = self._run(["ollama", "pull", model], timeout=1800)
        result = {"ok": ok, "model": model}

        if ok:
            # Also pull embedding model
            self._log("Pulling embedding model: nomic-embed-text...")
            ok2, out2 = self._run(["ollama", "pull", "nomic-embed-text"], timeout=900)
            result["embedding_ok"] = ok2

        return result

    def create_directories(self) -> Dict[str, Any]:
        """Create required directories."""
        dirs = [
            self.project_root / "training_data",
            self.project_root / "lora_adapters",
        ]
        created = []
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            created.append(str(d))
            self._log(f"Created directory: {d}")

        return {"ok": True, "created": created}

    def run_full_install(
        self,
        docker_config: Dict[str, Any],
        install_client: bool = True,
        install_trainer: bool = True,
        setup_ollama_model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run the complete installation pipeline."""
        results = {}

        # 1. Create directories
        self._log("=== Step 1: Creating directories ===")
        results["directories"] = self.create_directories()

        # 2. Prerequisites
        self._log("=== Step 2: Checking prerequisites ===")
        results["prerequisites"] = self.check_prerequisites()

        # 3. Backend
        use_docker = docker_config.get("enabled", True) and docker_config.get("services", {}).get("api", True)
        self._log("=== Step 3: Backend dependencies ===")
        results["backend"] = self.install_backend_deps(use_docker=use_docker)

        # 4. Client
        if install_client:
            self._log("=== Step 4: Client dependencies ===")
            results["client"] = self.install_client_deps()
        else:
            self._log("=== Step 4: Client installation skipped ===")
            results["client"] = {"ok": True, "skipped": True}

        # 5. Trainer web
        if install_trainer:
            self._log("=== Step 5: Trainer web dependencies ===")
            results["trainer_web"] = self.install_trainer_web_deps()
        else:
            self._log("=== Step 5: Trainer web installation skipped ===")
            results["trainer_web"] = {"ok": True, "skipped": True}

        # 6. Ollama
        if setup_ollama_model:
            self._log("=== Step 6: Ollama setup ===")
            results["ollama"] = self.setup_ollama(setup_ollama_model)
        else:
            self._log("=== Step 6: Ollama setup skipped ===")
            results["ollama"] = {"ok": True, "skipped": True}

        # 7. Docker services
        if docker_config.get("enabled", True):
            self._log("=== Step 7: Starting Docker services ===")
            compose_cmd = docker_config.get("compose_command", "docker compose")
            results["docker"] = self.start_docker_services(compose_cmd)
        else:
            self._log("=== Step 7: Docker services skipped (native mode) ===")
            results["docker"] = {"ok": True, "skipped": True}

        self._log("=== Installation complete ===")
        return results

    def get_service_urls(self, env_values: Dict[str, str]) -> List[Dict[str, str]]:
        """Return list of service URLs based on config."""
        api_port = env_values.get("API_PORT", "8000")
        urls = [
            {"name": "API Server", "url": f"http://localhost:{api_port}", "description": "FastAPI backend"},
            {"name": "API Docs (Swagger)", "url": f"http://localhost:{api_port}/docs", "description": "Interactive API documentation"},
            {"name": "Health Check", "url": f"http://localhost:{api_port}/health", "description": "Service health status"},
        ]

        if env_values.get("ENABLE_METRICS", "true").lower() == "true":
            urls.append({"name": "Metrics", "url": f"http://localhost:{api_port}/metrics", "description": "Prometheus metrics"})

        urls.append({"name": "Trainer Web", "url": "http://localhost:5173", "description": "SvelteKit trainer dashboard"})

        return urls
