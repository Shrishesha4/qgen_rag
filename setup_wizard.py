#!/usr/bin/env python3
"""
QGen RAG Setup Wizard — Bootstrap Entry Point

Usage:
    python setup_wizard.py                  # Start wizard on port 8080
    python setup_wizard.py --port 9090      # Custom port
    python setup_wizard.py --debug          # Enable debug logging
    python setup_wizard.py --no-browser     # Don't auto-open browser

This script:
  1. Detects the system environment
  2. Starts a local web server on localhost:8080
  3. Opens the browser to the setup wizard
  4. User completes configuration via the browser UI
  5. Generates configs, installs deps, spins up services
"""

import argparse
import logging
import os
import sys
import socket
import webbrowser
import time
import threading
from pathlib import Path


def check_python_version():
    """Ensure we're running Python 3.8+."""
    if sys.version_info < (3, 8):
        print(f"Error: Python 3.8+ required (found {sys.version})")
        sys.exit(1)


def find_project_root() -> str:
    """Find the project root directory (where this script lives)."""
    return str(Path(__file__).resolve().parent)


def check_port_available(port: int) -> bool:
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def setup_logging(debug: bool = False):
    """Configure logging."""
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt)

    if not debug:
        # Quiet down noisy loggers in non-debug mode
        logging.getLogger("http.server").setLevel(logging.WARNING)


def open_browser_delayed(url: str, delay: float = 1.5):
    """Open the browser after a short delay to let the server start."""
    def _open():
        time.sleep(delay)
        print(f"\n  Opening browser: {url}\n")
        webbrowser.open(url)
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def print_banner(port: int):
    """Print the startup banner."""
    print()
    print("  ┌──────────────────────────────────────────────┐")
    print("  │                                              │")
    print("  │       QGen RAG — Setup Wizard                │")
    print("  │                                              │")
    print(f"  │   http://localhost:{port:<5}                    │")
    print("  │                                              │")
    print("  │   Press Ctrl+C to stop the wizard            │")
    print("  │                                              │")
    print("  └──────────────────────────────────────────────┘")
    print()


def main():
    check_python_version()

    parser = argparse.ArgumentParser(
        description="QGen RAG Setup Wizard — Interactive browser-based configuration"
    )
    parser.add_argument(
        "--port", type=int, default=8080,
        help="Port for the setup wizard server (default: 8080)"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--no-browser", action="store_true",
        help="Don't automatically open the browser"
    )
    args = parser.parse_args()

    setup_logging(args.debug)
    logger = logging.getLogger("setup_wizard")

    project_root = find_project_root()
    logger.info("Project root: %s", project_root)

    # Check port availability
    if not check_port_available(args.port):
        logger.warning("Port %d is in use. Trying alternatives...", args.port)
        for alt_port in [8081, 8082, 8090, 9090]:
            if check_port_available(alt_port):
                logger.info("Using port %d instead", alt_port)
                args.port = alt_port
                break
        else:
            print(f"Error: No available port found. Tried {args.port}, 8081, 8082, 8090, 9090")
            sys.exit(1)

    # Import wizard modules (after confirming setup_wizard package exists)
    try:
        from setup_wizard.server import run_server
    except ImportError as e:
        logger.error("Failed to import setup_wizard package: %s", e)
        print("Error: setup_wizard package not found. Ensure you're running from the project root.")
        sys.exit(1)

    print_banner(args.port)

    # Open browser
    if not args.no_browser:
        open_browser_delayed(f"http://localhost:{args.port}")

    # Start the server (blocking)
    try:
        run_server(project_root, args.port)
    except KeyboardInterrupt:
        print("\n  Wizard stopped. Your configuration has been saved.")
        print("  Re-run this script anytime to reconfigure.\n")
    except Exception as e:
        logger.exception("Server error")
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
