#!/usr/bin/env python3
"""
Quick fix for missing psutil in virtual environment
"""

import subprocess
import sys
from pathlib import Path

def fix_virtual_environment():
    """Install missing packages in the virtual environment."""
    
    # Find the virtual environment
    venv_paths = [
        Path("venv"),
        Path(".venv"), 
        Path("env"),
        Path(".env")
    ]
    
    venv_python = None
    for venv_path in venv_paths:
        if venv_path.exists():
            if sys.platform == "win32":
                python_exe = venv_path / "Scripts" / "python.exe"
            else:
                python_exe = venv_path / "bin" / "python"
            
            if python_exe.exists():
                venv_python = python_exe
                break
    
    if not venv_python:
        print("❌ No virtual environment found")
        return False
    
    print(f"🔧 Found virtual environment: {venv_python}")
    
    # Install required packages
    packages = [
        "fastapi>=0.104.1",
        "uvicorn>=0.24.0", 
        "jinja2>=3.1.2",
        "aiofiles>=23.2.1",
        "psutil>=5.9.6"
    ]
    
    print("📦 Installing required packages...")
    for package in packages:
        try:
            result = subprocess.run([str(venv_python), "-m", "pip", "install", package], 
                                  capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                print(f"✅ Installed {package}")
            else:
                print(f"❌ Failed to install {package}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print(f"❌ Timeout installing {package}")
            return False
    
    print("✅ All packages installed successfully!")
    print("🚀 You can now run: python launch_setup.py")
    return True

if __name__ == "__main__":
    success = fix_virtual_environment()
    sys.exit(0 if success else 1)
