#!/usr/bin/env python3
"""
Configuration Validation Script

Validates environment variables and Docker Compose configuration.
Ensures all required variables are present and valid.
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess
import json

class ConfigValidator:
    """Validates QGen RAG configuration."""
    
    def __init__(self, env_file: str = ".env.local"):
        self.env_file = Path(env_file)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config: Dict[str, str] = {}
        
    def load_env_file(self) -> bool:
        """Load environment variables from file."""
        if not self.env_file.exists():
            self.errors.append(f"Environment file not found: {self.env_file}")
            return False
        
        try:
            with open(self.env_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if '=' not in line:
                        self.warnings.append(f"Line {line_num}: Invalid format (missing '='): {line}")
                        continue
                    
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    self.config[key] = value
            
            return True
            
        except Exception as e:
            self.errors.append(f"Failed to read environment file: {e}")
            return False
    
    def validate_database_config(self) -> bool:
        """Validate database configuration."""
        required_vars = ['POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB']
        
        for var in required_vars:
            if var not in self.config:
                self.errors.append(f"Missing required database variable: {var}")
                return False
        
        # Validate port
        try:
            port = int(self.config['POSTGRES_PORT'])
            if not (1 <= port <= 65535):
                self.errors.append(f"POSTGRES_PORT must be between 1 and 65535, got: {port}")
                return False
        except ValueError:
            self.errors.append(f"POSTGRES_PORT must be a number, got: {self.config['POSTGRES_PORT']}")
            return False
        
        # Validate password strength
        password = self.config['POSTGRES_PASSWORD']
        if len(password) < 8:
            self.warnings.append("POSTGRES_PASSWORD should be at least 8 characters long")
        
        if password in ['qgen_password', 'password', '123456']:
            self.errors.append("POSTGRES_PASSWORD is too weak, please use a strong password")
            return False
        
        return True
    
    def validate_redis_config(self) -> bool:
        """Validate Redis configuration."""
        required_vars = ['REDIS_HOST', 'REDIS_PORT']
        
        for var in required_vars:
            if var not in self.config:
                self.errors.append(f"Missing required Redis variable: {var}")
                return False
        
        # Validate port
        try:
            port = int(self.config['REDIS_PORT'])
            if not (1 <= port <= 65535):
                self.errors.append(f"REDIS_PORT must be between 1 and 65535, got: {port}")
                return False
        except ValueError:
            self.errors.append(f"REDIS_PORT must be a number, got: {self.config['REDIS_PORT']}")
            return False
        
        # Validate Redis DB number
        if 'REDIS_DB' in self.config:
            try:
                db = int(self.config['REDIS_DB'])
                if not (0 <= db <= 15):
                    self.errors.append(f"REDIS_DB must be between 0 and 15, got: {db}")
                    return False
            except ValueError:
                self.errors.append(f"REDIS_DB must be a number, got: {self.config['REDIS_DB']}")
                return False
        
        return True
    
    def validate_api_config(self) -> bool:
        """Validate API configuration."""
        required_vars = ['API_HOST', 'API_PORT', 'SECRET_KEY']
        
        for var in required_vars:
            if var not in self.config:
                self.errors.append(f"Missing required API variable: {var}")
                return False
        
        # Validate port
        try:
            port = int(self.config['API_PORT'])
            if not (1 <= port <= 65535):
                self.errors.append(f"API_PORT must be between 1 and 65535, got: {port}")
                return False
        except ValueError:
            self.errors.append(f"API_PORT must be a number, got: {self.config['API_PORT']}")
            return False
        
        # Validate secret key
        secret_key = self.config['SECRET_KEY']
        if len(secret_key) < 32:
            self.errors.append("SECRET_KEY must be at least 32 characters long")
            return False
        
        if secret_key in ['your-super-secret-key-change-in-production-minimum-32-chars', 'secret', 'key']:
            self.errors.append("SECRET_KEY is using default value, please change it")
            return False
        
        return True
    
    def validate_llm_config(self) -> bool:
        """Validate LLM provider configuration."""
        if 'LLM_PROVIDER' not in self.config:
            self.errors.append("Missing LLM_PROVIDER variable")
            return False
        
        provider = self.config['LLM_PROVIDER']
        valid_providers = ['ollama', 'gemini', 'deepseek']
        
        if provider not in valid_providers:
            self.errors.append(f"LLM_PROVIDER must be one of {valid_providers}, got: {provider}")
            return False
        
        # Provider-specific validation
        if provider == 'ollama':
            if 'OLLAMA_BASE_URL' not in self.config:
                self.warnings.append("OLLAMA_BASE_URL not set, using default")
            if 'OLLAMA_MODEL' not in self.config:
                self.warnings.append("OLLAMA_MODEL not set, using default")
        
        elif provider == 'gemini':
            if 'GEMINI_API_KEY' not in self.config or not self.config['GEMINI_API_KEY']:
                self.errors.append("GEMINI_API_KEY is required when using Gemini provider")
                return False
        
        elif provider == 'deepseek':
            if 'DEEPSEEK_API_KEY' not in self.config or not self.config['DEEPSEEK_API_KEY']:
                self.errors.append("DEEPSEEK_API_KEY is required when using DeepSeek provider")
                return False
        
        return True
    
    def validate_ports(self) -> bool:
        """Validate that ports don't conflict."""
        port_vars = {
            'POSTGRES_PORT': 'PostgreSQL',
            'REDIS_PORT': 'Redis',
            'API_PORT': 'API',
            'TRAINER_WEB_PORT': 'Trainer Web'
        }
        
        used_ports = {}
        conflicts = False
        
        for var, service in port_vars.items():
            if var in self.config:
                try:
                    port = int(self.config[var])
                    if port in used_ports:
                        self.errors.append(f"Port conflict: {service} ({var}={port}) conflicts with {used_ports[port]}")
                        conflicts = True
                    else:
                        used_ports[port] = service
                except ValueError:
                    self.errors.append(f"Invalid port number for {var}: {self.config[var]}")
                    conflicts = True
        
        return not conflicts
    
    def validate_docker_compose(self) -> bool:
        """Validate Docker Compose configuration."""
        try:
            # Check if docker-compose is available
            result = subprocess.run(['docker-compose', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.errors.append("docker-compose is not installed or not available")
                return False
            
            # Validate docker-compose files
            compose_files = ['docker-compose.yml', 'docker-compose.prod.yml']
            for compose_file in compose_files:
                if Path(compose_file).exists():
                    result = subprocess.run(['docker-compose', '-f', compose_file, 'config'],
                                          capture_output=True, text=True, timeout=30)
                    if result.returncode != 0:
                        self.errors.append(f"Invalid Docker Compose configuration in {compose_file}: {result.stderr}")
                        return False
            
            return True
            
        except subprocess.TimeoutExpired:
            self.errors.append("Docker Compose validation timed out")
            return False
        except FileNotFoundError:
            self.errors.append("docker-compose command not found")
            return False
        except Exception as e:
            self.errors.append(f"Docker Compose validation failed: {e}")
            return False
    
    def check_file_permissions(self) -> bool:
        """Check file and directory permissions."""
        required_dirs = [
            './backend',
            './trainer-web',
            './uploads',
            './training_data',
            './lora_adapters'
        ]
        
        issues = False
        for dir_path in required_dirs:
            path = Path(dir_path)
            if not path.exists():
                self.warnings.append(f"Directory does not exist: {dir_path}")
                continue
            
            if not os.access(path, os.R_OK):
                self.errors.append(f"Directory not readable: {dir_path}")
                issues = True
            
            if not os.access(path, os.W_OK):
                self.errors.append(f"Directory not writable: {dir_path}")
                issues = True
        
        return not issues
    
    def validate_all(self) -> bool:
        """Run all validation checks."""
        if not self.load_env_file():
            return False
        
        all_valid = True
        
        # Run all validations
        all_valid &= self.validate_database_config()
        all_valid &= self.validate_redis_config()
        all_valid &= self.validate_api_config()
        all_valid &= self.validate_llm_config()
        all_valid &= self.validate_ports()
        all_valid &= self.validate_docker_compose()
        all_valid &= self.check_file_permissions()
        
        return all_valid
    
    def print_results(self):
        """Print validation results."""
        print("=" * 60)
        print("QGen RAG Configuration Validation")
        print("=" * 60)
        
        if self.errors:
            print("\n❌ ERRORS:")
            for error in self.errors:
                print(f"   • {error}")
        
        if self.warnings:
            print("\n⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"   • {warning}")
        
        if not self.errors and not self.warnings:
            print("\n✅ Configuration is valid!")
        elif not self.errors:
            print("\n✅ Configuration is valid (with warnings)")
        else:
            print("\n❌ Configuration has errors that must be fixed")
        
        print("=" * 60)
    
    def generate_docker_compose_command(self) -> str:
        """Generate appropriate docker-compose command."""
        if Path('docker-compose.env.yml').exists():
            return "docker-compose -f docker-compose.env.yml --env-file .env.local up -d"
        elif Path('docker-compose.prod.yml').exists():
            return "docker-compose -f docker-compose.yml -f docker-compose.prod.yml --env-file .env.local up -d"
        else:
            return "docker-compose --env-file .env.local up -d"

def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate QGen RAG configuration")
    parser.add_argument("--env-file", default=".env.local", help="Environment file to validate")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix common issues")
    parser.add_argument("--generate", action="store_true", help="Generate docker-compose command")
    
    args = parser.parse_args()
    
    validator = ConfigValidator(args.env_file)
    
    if validator.validate_all():
        validator.print_results()
        
        if args.generate:
            print(f"\n🚀 To start the system:")
            print(f"   {validator.generate_docker_compose_command()}")
        
        sys.exit(0)
    else:
        validator.print_results()
        
        if args.fix:
            print("\n🔧 Attempting to fix common issues...")
            # Add auto-fix logic here if needed
        
        sys.exit(1)

if __name__ == "__main__":
    main()
