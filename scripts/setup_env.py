#!/usr/bin/env python3
"""
QGen RAG Environment Setup Script

Automates the setup of environment variables and Docker Compose configuration.
Creates secure passwords, validates configuration, and starts services.
"""

import os
import sys
import secrets
import subprocess
import shutil
from pathlib import Path
from typing import Dict, Optional
import argparse

class EnvironmentSetup:
    """Handles environment setup and configuration."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.env_file = self.project_root / ".env.local"
        self.template_file = self.project_root / ".env.template"
        self.docker_example = self.project_root / ".env.docker.example"
        
    def generate_secure_password(self, length: int = 32) -> str:
        """Generate a secure random password."""
        return secrets.token_urlsafe(length)
    
    def check_docker_installation(self) -> bool:
        """Check if Docker and Docker Compose are installed."""
        try:
            # Check Docker
            result = subprocess.run(['docker', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("❌ Docker is not installed or not running")
                return False
            
            # Check Docker Compose
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print("❌ Docker Compose is not installed")
                return False
            
            print("✅ Docker and Docker Compose are installed")
            return True
            
        except subprocess.TimeoutExpired:
            print("❌ Docker/Docker Compose check timed out")
            return False
        except FileNotFoundError:
            print("❌ Docker or Docker Compose not found in PATH")
            return False
    
    def create_env_file(self, force: bool = False) -> bool:
        """Create .env.local file from template with secure values."""
        if self.env_file.exists() and not force:
            print(f"⚠️  {self.env_file} already exists. Use --force to overwrite.")
            return False
        
        # Choose template
        template = self.template_file if self.template_file.exists() else self.docker_example
        if not template.exists():
            print(f"❌ No template file found. Expected {self.template_file} or {self.docker_example}")
            return False
        
        print(f"📝 Creating {self.env_file} from {template}")
        
        # Read template
        with open(template, 'r') as f:
            content = f.read()
        
        # Generate secure values
        replacements = {
            'your_secure_password_here': self.generate_secure_password(),
            'your_redis_password_here': self.generate_secure_password(),
            'your-super-secret-key-change-in-production-minimum-32-chars': self.generate_secure_password(64),
            'your_gemini_api_key_here': '',
            'your_deepseek_api_key_here': '',
            'qgen_password': self.generate_secure_password(),
        }
        
        # Replace placeholders
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        
        # Write env file
        with open(self.env_file, 'w') as f:
            f.write(content)
        
        print(f"✅ Created {self.env_file} with secure configuration")
        return True
    
    def validate_configuration(self) -> bool:
        """Validate the environment configuration."""
        validator_script = self.project_root / "scripts" / "validate_config.py"
        
        if not validator_script.exists():
            print("⚠️  Validation script not found, skipping validation")
            return True
        
        print("🔍 Validating configuration...")
        
        try:
            result = subprocess.run([sys.executable, str(validator_script), 
                                  '--env-file', str(self.env_file)],
                                  capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("✅ Configuration is valid")
                return True
            else:
                print("❌ Configuration validation failed:")
                print(result.stdout)
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Configuration validation timed out")
            return False
        except Exception as e:
            print(f"❌ Configuration validation error: {e}")
            return False
    
    def create_directories(self) -> bool:
        """Create necessary directories."""
        directories = [
            "uploads",
            "training_data", 
            "lora_adapters",
            "logs",
            "nginx",
            "monitoring"
        ]
        
        print("📁 Creating directories...")
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            print(f"   ✓ {directory}")
        
        return True
    
    def setup_permissions(self) -> bool:
        """Set proper file permissions."""
        print("🔐 Setting permissions...")
        
        # Make scripts executable
        scripts = [
            "scripts/setup_dgx_spark.sh",
            "scripts/validate_config.py",
            "scripts/init_data_collection.py"
        ]
        
        for script in scripts:
            script_path = self.project_root / script
            if script_path.exists():
                script_path.chmod(0o755)
                print(f"   ✓ {script}")
        
        return True
    
    def start_services(self, compose_file: Optional[str] = None) -> bool:
        """Start Docker services."""
        if not self.check_docker_installation():
            return False
        
        print("🚀 Starting Docker services...")
        
        # Determine compose command
        if compose_file:
            compose_files = ['-f', compose_file]
        elif (self.project_root / "docker-compose.env.yml").exists():
            compose_files = ['-f', 'docker-compose.env.yml']
        elif (self.project_root / "docker-compose.prod.yml").exists():
            compose_files = ['-f', 'docker-compose.yml', '-f', 'docker-compose.prod.yml']
        else:
            compose_files = []
        
        cmd = ['docker-compose'] + compose_files + ['--env-file', str(self.env_file), 'up', '-d']
        
        try:
            print(f"   Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.project_root, 
                                  capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ Services started successfully")
                return True
            else:
                print("❌ Failed to start services:")
                print(result.stdout)
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Service startup timed out")
            return False
        except Exception as e:
            print(f"❌ Service startup error: {e}")
            return False
    
    def show_status(self) -> bool:
        """Show service status."""
        print("📊 Checking service status...")
        
        try:
            result = subprocess.run(['docker-compose', '--env-file', str(self.env_file), 'ps'],
                                  cwd=self.project_root, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print(result.stdout)
                return True
            else:
                print("❌ Failed to get service status")
                print(result.stderr)
                return False
                
        except Exception as e:
            print(f"❌ Status check error: {e}")
            return False
    
    def show_next_steps(self) -> None:
        """Show next steps for the user."""
        print("\n" + "="*60)
        print("🎉 QGen RAG Setup Complete!")
        print("="*60)
        
        print("\n📋 Next Steps:")
        print("1. Set your LLM provider API keys in .env.local:")
        print("   - For Gemini: Set GEMINI_API_KEY")
        print("   - For DeepSeek: Set DEEPSEEK_API_KEY")
        print("   - For Ollama: Ensure Ollama is running locally")
        
        print("\n2. Access the application:")
        print("   - Frontend: http://localhost:5173")
        print("   - Backend API: http://localhost:8000")
        print("   - API Docs: http://localhost:8000/docs")
        
        print("\n3. Check service status:")
        print("   docker-compose --env-file .env.local ps")
        
        print("\n4. View logs:")
        print("   docker-compose --env-file .env.local logs -f")
        
        print("\n5. Stop services:")
        print("   docker-compose --env-file .env.local down")
        
        print("\n📚 For more information, see the documentation.")
        print("="*60)

def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup QGen RAG environment")
    parser.add_argument("--project-root", default=".", help="Project root directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing .env.local")
    parser.add_argument("--compose-file", help="Specific Docker Compose file to use")
    parser.add_argument("--no-start", action="store_true", help="Don't start services")
    parser.add_argument("--dev", action="store_true", help="Development setup")
    parser.add_argument("--prod", action="store_true", help="Production setup")
    
    args = parser.parse_args()
    
    setup = EnvironmentSetup(args.project_root)
    
    print("🚀 QGen RAG Environment Setup")
    print("="*40)
    
    # Check Docker installation
    if not setup.check_docker_installation():
        sys.exit(1)
    
    # Create environment file
    if not setup.create_env_file(force=args.force):
        print("❌ Failed to create environment file")
        sys.exit(1)
    
    # Create directories
    if not setup.create_directories():
        print("❌ Failed to create directories")
        sys.exit(1)
    
    # Set permissions
    if not setup.setup_permissions():
        print("❌ Failed to set permissions")
        sys.exit(1)
    
    # Validate configuration
    if not setup.validate_configuration():
        print("❌ Configuration validation failed")
        sys.exit(1)
    
    # Start services (unless skipped)
    if not args.no_start:
        if not setup.start_services(args.compose_file):
            print("❌ Failed to start services")
            sys.exit(1)
        
        # Show status
        setup.show_status()
    
    # Show next steps
    setup.show_next_steps()

if __name__ == "__main__":
    main()
