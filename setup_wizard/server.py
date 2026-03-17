"""
Temporary HTTP server for the setup wizard.
Serves the frontend UI and provides API endpoints for configuration.
Uses only Python standard library (http.server + json).
"""

import http.server
import json
import os
import logging
import socketserver
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional

from . import detector
from . import config_generator
from . import installer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session state (in-memory, single-user wizard)
# ---------------------------------------------------------------------------

class WizardState:
    """Holds wizard session state across steps."""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.system_info: Dict[str, Any] = {}
        self.env_values: Dict[str, str] = {}
        self.docker_config: Dict[str, Any] = {
            "enabled": True,
            "mode": "development",
            "services": {"db": True, "redis": True, "api": True, "ollama": False},
            "ports": {},
            "container_names": {},
            "compose_command": "docker compose",
        }
        self.install_options: Dict[str, Any] = {
            "install_client": True,
            "install_trainer": True,
            "setup_ollama": False,
            "ollama_model": "llama3.1:8b",
        }
        self.install_results: Dict[str, Any] = {}
        self.install_log: list = []
        self.current_step: int = 0
        self.completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system_info": self.system_info,
            "env_values": self.env_values,
            "docker_config": self.docker_config,
            "install_options": self.install_options,
            "install_results": self.install_results,
            "current_step": self.current_step,
            "completed": self.completed,
        }


# ---------------------------------------------------------------------------
# Request handler
# ---------------------------------------------------------------------------

class WizardRequestHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the setup wizard."""

    state: WizardState = None  # set by server factory
    _static_dir: str = ""

    def log_message(self, format, *args):
        logger.debug(format, *args)

    # --- Routing ---

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        # API routes
        if path.startswith("/api/"):
            return self._handle_api_get(path, parsed)

        # Serve static files from frontend directory
        return self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()
        return self._handle_api_post(path, body)

    # --- Static file serving ---

    def _serve_static(self, path: str):
        static_dir = Path(self._static_dir)

        if path == "/" or path == "":
            file_path = static_dir / "index.html"
        else:
            # Strip leading slash and resolve
            rel = path.lstrip("/")
            file_path = static_dir / rel

        # Security: prevent directory traversal
        try:
            file_path = file_path.resolve()
            static_resolved = static_dir.resolve()
            if not str(file_path).startswith(str(static_resolved)):
                return self._send_error(403, "Forbidden")
        except (ValueError, OSError):
            return self._send_error(403, "Forbidden")

        if not file_path.exists() or file_path.is_dir():
            # SPA fallback
            file_path = static_dir / "index.html"

        if not file_path.exists():
            return self._send_error(404, "Not found")

        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json",
            ".svg": "image/svg+xml",
            ".png": "image/png",
            ".ico": "image/x-icon",
            ".woff2": "font/woff2",
            ".woff": "font/woff",
        }
        ext = file_path.suffix.lower()
        ct = content_types.get(ext, "application/octet-stream")

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    # --- API GET ---

    def _handle_api_get(self, path: str, parsed):
        routes = {
            "/api/detect": self._api_detect,
            "/api/state": self._api_get_state,
            "/api/env-schema": self._api_env_schema,
            "/api/defaults": self._api_defaults,
            "/api/install-log": self._api_install_log,
            "/api/service-urls": self._api_service_urls,
            "/api/preview-env": self._api_preview_env,
            "/api/preview-compose": self._api_preview_compose,
        }
        handler = routes.get(path)
        if handler:
            return handler()
        return self._send_error(404, f"Unknown API route: {path}")

    # --- API POST ---

    def _handle_api_post(self, path: str, body: Dict):
        routes = {
            "/api/env": self._api_save_env,
            "/api/docker": self._api_save_docker,
            "/api/install-options": self._api_save_install_options,
            "/api/step": self._api_set_step,
            "/api/install": self._api_run_install,
            "/api/validate-path": self._api_validate_path,
            "/api/generate-secret": self._api_generate_secret,
        }
        handler = routes.get(path)
        if handler:
            return handler(body)
        return self._send_error(404, f"Unknown API route: {path}")

    # --- API implementations ---

    def _api_detect(self):
        if not self.state.system_info:
            self.state.system_info = detector.detect_all(self.state.project_root)
        return self._send_json(self.state.system_info)

    def _api_get_state(self):
        return self._send_json(self.state.to_dict())

    def _api_env_schema(self):
        return self._send_json(config_generator.ENV_SCHEMA)

    def _api_defaults(self):
        return self._send_json(config_generator.DEFAULT_ENV)

    def _api_install_log(self):
        return self._send_json({"log": self.state.install_log})

    def _api_service_urls(self):
        runner = installer.TaskRunner(self.state.project_root)
        urls = runner.get_service_urls(self.state.env_values or config_generator.DEFAULT_ENV)
        return self._send_json({"urls": urls})

    def _api_preview_env(self):
        vals = config_generator.build_env_values(self.state.env_values)
        content = config_generator.generate_env_file(vals)
        return self._send_json({"content": content})

    def _api_preview_compose(self):
        vals = config_generator.build_env_values(self.state.env_values)
        content = config_generator.generate_docker_compose(self.state.docker_config, vals)
        return self._send_json({"content": content})

    def _api_save_env(self, body: Dict):
        self.state.env_values.update(body.get("values", {}))
        return self._send_json({"ok": True})

    def _api_save_docker(self, body: Dict):
        cfg = body.get("config", {})
        if "enabled" in cfg:
            self.state.docker_config["enabled"] = cfg["enabled"]
        if "mode" in cfg:
            self.state.docker_config["mode"] = cfg["mode"]
        if "services" in cfg:
            self.state.docker_config["services"].update(cfg["services"])
        if "ports" in cfg:
            self.state.docker_config["ports"].update(cfg["ports"])
        if "container_names" in cfg:
            self.state.docker_config["container_names"].update(cfg["container_names"])
        return self._send_json({"ok": True})

    def _api_save_install_options(self, body: Dict):
        opts = body.get("options", {})
        self.state.install_options.update(opts)
        return self._send_json({"ok": True})

    def _api_set_step(self, body: Dict):
        self.state.current_step = body.get("step", 0)
        return self._send_json({"ok": True, "step": self.state.current_step})

    def _api_run_install(self, body: Dict):
        """Run the installation pipeline in a background thread."""
        if self.state.completed:
            return self._send_json({"ok": False, "error": "Installation already completed"})

        # Build final env values and write configs
        env_vals = config_generator.build_env_values(self.state.env_values)
        self.state.env_values = env_vals

        write_results = config_generator.write_configs(
            self.state.project_root, env_vals, self.state.docker_config
        )

        runner = installer.TaskRunner(self.state.project_root)
        self.state.install_log = runner.log_lines

        def _run():
            try:
                self.state.install_results = runner.run_full_install(
                    docker_config=self.state.docker_config,
                    install_client=self.state.install_options.get("install_client", True),
                    install_trainer=self.state.install_options.get("install_trainer", True),
                    setup_ollama_model=(
                        self.state.install_options.get("ollama_model")
                        if self.state.install_options.get("setup_ollama") else None
                    ),
                )
                self.state.completed = True
            except Exception as e:
                logger.exception("Installation failed")
                self.state.install_results["error"] = str(e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return self._send_json({
            "ok": True,
            "config_files": write_results,
            "message": "Installation started. Poll /api/install-log for progress.",
        })

    def _api_validate_path(self, body: Dict):
        path_str = body.get("path", "")
        if not path_str:
            return self._send_json({"valid": False, "error": "Empty path"})
        p = Path(path_str)
        exists = p.exists()
        is_dir = p.is_dir() if exists else False
        writable = os.access(str(p.parent if not exists else p), os.W_OK)
        return self._send_json({
            "valid": True,
            "exists": exists,
            "is_dir": is_dir,
            "writable": writable,
            "resolved": str(p.resolve()),
        })

    def _api_generate_secret(self, body: Dict):
        length = body.get("length", 64)
        return self._send_json({"key": config_generator.generate_secret_key(length)})

    # --- Helpers ---

    def _read_body(self) -> Dict:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        raw = self.rfile.read(content_length)
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: int, message: str):
        return self._send_json({"error": message}, status)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------

def create_server(project_root: str, port: int = 8080) -> http.server.HTTPServer:
    """Create and return the wizard HTTP server."""
    static_dir = str(Path(__file__).parent / "frontend")
    state = WizardState(project_root)

    # Preload system detection
    state.system_info = detector.detect_all(project_root)

    # Set defaults from existing .env.local if present
    env_path = Path(project_root) / ".env.local"
    if env_path.exists():
        logger.info("Loading existing .env.local values as defaults")
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                state.env_values[key.strip()] = val.strip()

    WizardRequestHandler.state = state
    WizardRequestHandler._static_dir = static_dir

    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadedHTTPServer(("0.0.0.0", port), WizardRequestHandler)
    logger.info("Setup wizard server ready on http://localhost:%d", port)
    return server


def run_server(project_root: str, port: int = 8080):
    """Create and run the wizard server (blocking)."""
    server = create_server(project_root, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down setup wizard server...")
        server.shutdown()
