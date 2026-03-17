#!/usr/bin/env python3
"""
Verification script to ensure launch_setup.py is properly configured
"""

import os
import sys
from pathlib import Path

def verify_setup():
    """Verify that the setup system is properly configured."""
    
    print("🔍 Verifying QGen RAG Setup System...")
    print("=" * 50)
    
    # Check if launch_setup.py exists in root
    root_launch = Path("launch_setup.py")
    if root_launch.exists():
        print("✅ launch_setup.py found in root directory")
    else:
        print("❌ launch_setup.py not found in root directory")
        return False
    
    # Check if interactive_setup.py exists in scripts
    scripts_setup = Path("scripts/interactive_setup.py")
    if scripts_setup.exists():
        print("✅ interactive_setup.py found in scripts directory")
    else:
        print("❌ interactive_setup.py not found in scripts directory")
        return False
    
    # Check if platform launchers exist
    windows_launcher = Path("scripts/setup_windows.bat")
    unix_launcher = Path("scripts/setup_unix.sh")
    
    if windows_launcher.exists():
        print("✅ Windows launcher (setup_windows.bat) found")
    else:
        print("⚠️  Windows launcher not found")
    
    if unix_launcher.exists():
        print("✅ Unix launcher (setup_unix.sh) found")
        # Check if it's executable
        if os.access(unix_launcher, os.X_OK):
            print("✅ Unix launcher is executable")
        else:
            print("⚠️  Unix launcher is not executable")
    else:
        print("⚠️  Unix launcher not found")
    
    # Check if requirements file exists
    requirements = Path("scripts/setup_requirements.txt")
    if requirements.exists():
        print("✅ setup_requirements.txt found")
    else:
        print("❌ setup_requirements.txt not found")
        return False
    
    # Check if docker-compose files exist
    docker_files = [
        "docker-compose.yml",
        "docker-compose.dgx.yml",
        "docker-compose.prod.yml"
    ]
    
    for docker_file in docker_files:
        if Path(docker_file).exists():
            print(f"✅ {docker_file} found")
        else:
            print(f"⚠️  {docker_file} not found")
    
    # Check if trainer-web directory exists
    trainer_web = Path("trainer-web")
    if trainer_web.exists():
        print("✅ trainer-web directory found")
        
        # Check for key frontend files
        frontend_files = [
            "trainer-web/package.json",
            "trainer-web/Dockerfile",
            "trainer-web/src/app.html"
        ]
        
        for frontend_file in frontend_files:
            if Path(frontend_file).exists():
                print(f"✅ {frontend_file} found")
            else:
                print(f"⚠️  {frontend_file} not found")
    else:
        print("❌ trainer-web directory not found")
        return False
    
    # Check if backend directory exists
    backend = Path("backend")
    if backend.exists():
        print("✅ backend directory found")
    else:
        print("❌ backend directory not found")
        return False
    
    print("\n🎉 Setup system verification completed!")
    print("\n📋 Available launch methods:")
    print("   1. Universal launcher: python launch_setup.py")
    print("   2. Windows launcher: scripts\\setup_windows.bat")
    print("   3. Unix launcher: ./scripts/setup_unix.sh")
    
    return True

if __name__ == "__main__":
    success = verify_setup()
    if not success:
        print("\n❌ Verification failed! Please check the missing files.")
        sys.exit(1)
    else:
        print("\n✅ All systems ready! You can now run the setup.")
        sys.exit(0)
