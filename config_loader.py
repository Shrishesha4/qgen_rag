#!/usr/bin/env python3
"""
Configuration Loader Utility for QGen RAG

This utility allows you to load, validate, and manage configuration templates
for the QGen RAG setup wizard.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional

class ConfigLoader:
    """Configuration loader and validator."""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config_template.json"
        self.config = {}
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        config_path = Path(self.config_file)
        
        if not config_path.exists():
            print(f"❌ Configuration file not found: {self.config_file}")
            return {}
        
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
            print(f"✅ Configuration loaded from {self.config_file}")
            return self.config
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in configuration file: {e}")
            return {}
        except Exception as e:
            print(f"❌ Error loading configuration: {e}")
            return {}
    
    def validate_config(self) -> bool:
        """Validate configuration structure and required fields."""
        if not self.config:
            return False
        
        required_sections = [
            "deployment_modes",
            "basic_settings", 
            "database_config",
            "service_ports",
            "model_configuration"
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in self.config:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"❌ Missing required configuration sections: {missing_sections}")
            return False
        
        # Validate deployment modes
        valid_deployments = ["docker", "baremetal", "nginx", "node"]
        for service, mode in self.config["deployment_modes"].items():
            if mode not in valid_deployments:
                print(f"❌ Invalid deployment mode for {service}: {mode}")
                return False
        
        # Validate ports
        for port_name, port_value in self.config["service_ports"].items():
            if not isinstance(port_value, int) or port_value < 1 or port_value > 65535:
                print(f"❌ Invalid port value for {port_name}: {port_value}")
                return False
        
        print("✅ Configuration validation passed")
        return True
    
    def save_config(self, output_file: Optional[str] = None) -> bool:
        """Save configuration to file."""
        output_path = Path(output_file or f"custom_{self.config_file}")
        
        try:
            with open(output_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            print(f"✅ Configuration saved to {output_path}")
            return True
        except Exception as e:
            print(f"❌ Error saving configuration: {e}")
            return False
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration with new values."""
        try:
            self._deep_update(self.config, updates)
            print("✅ Configuration updated successfully")
            return True
        except Exception as e:
            print(f"❌ Error updating configuration: {e}")
            return False
    
    def _deep_update(self, base_dict: Dict[str, Any], update_dict: Dict[str, Any]):
        """Deep update dictionary."""
        for key, value in update_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def get_config_summary(self) -> str:
        """Get configuration summary."""
        if not self.config:
            return "No configuration loaded"
        
        summary = []
        summary.append("📋 Configuration Summary:")
        summary.append(f"  🏗️  Database: {self.config.get('deployment_modes', {}).get('database_deployment', 'unknown')}")
        summary.append(f"  🔧 Backend: {self.config.get('deployment_modes', {}).get('backend_deployment', 'unknown')}")
        summary.append(f"  🎨 Frontend: {self.config.get('deployment_modes', {}).get('frontend_deployment', 'unknown')}")
        summary.append(f"  🌐 Domain: {self.config.get('basic_settings', {}).get('domain', 'unknown')}")
        summary.append(f"  📁 Install Dir: {self.config.get('basic_settings', {}).get('install_dir', 'unknown')}")
        summary.append(f"  🤖 Model: {self.config.get('model_configuration', {}).get('base_model', 'unknown')}")
        summary.append(f"  🔒 SSL: {self.config.get('ssl_configuration', {}).get('ssl_type', 'unknown')}")
        
        return "\n".join(summary)
    
    def export_wizard_config(self) -> Dict[str, Any]:
        """Export configuration in wizard format."""
        if not self.config:
            return {}
        
        # Flatten configuration for wizard
        wizard_config = {}
        
        # Basic settings
        basic = self.config.get("basic_settings", {})
        wizard_config.update(basic)
        
        # Deployment modes
        deployment = self.config.get("deployment_modes", {})
        wizard_config.update(deployment)
        
        # Database config
        db_config = self.config.get("database_config", {})
        wizard_config.update(db_config)
        
        # Service ports
        ports = self.config.get("service_ports", {})
        wizard_config.update(ports)
        
        # API keys
        api_keys = self.config.get("api_keys", {})
        wizard_config.update(api_keys)
        
        # Model config
        model_config = self.config.get("model_configuration", {})
        wizard_config.update(model_config)
        
        # Directory paths
        paths = self.config.get("directory_paths", {})
        wizard_config.update(paths)
        
        # SSL config
        ssl_config = self.config.get("ssl_configuration", {})
        wizard_config.update(ssl_config)
        
        # Monitoring config
        monitoring = self.config.get("monitoring_configuration", {})
        wizard_config.update(monitoring)
        
        # Repository config
        repo_config = self.config.get("repository_configuration", {})
        wizard_config.update(repo_config)
        
        # Data initialization
        data_init = self.config.get("data_initialization", {})
        wizard_config.update(data_init)
        
        return wizard_config

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="QGen RAG Configuration Loader")
    parser.add_argument("--config", default="config_template.json", help="Configuration file path")
    parser.add_argument("--validate", action="store_true", help="Validate configuration")
    parser.add_argument("--summary", action="store_true", help="Show configuration summary")
    parser.add_argument("--export", help="Export configuration for wizard")
    parser.add_argument("--save", help="Save configuration to file")
    parser.add_argument("--update", help="Update configuration with JSON string")
    
    args = parser.parse_args()
    
    loader = ConfigLoader(args.config)
    
    # Load configuration
    config = loader.load_config()
    if not config:
        sys.exit(1)
    
    # Validate if requested
    if args.validate:
        if not loader.validate_config():
            sys.exit(1)
    
    # Show summary if requested
    if args.summary:
        print(loader.get_config_summary())
    
    # Export if requested
    if args.export:
        wizard_config = loader.export_wizard_config()
        with open(args.export, 'w') as f:
            json.dump(wizard_config, f, indent=2)
        print(f"✅ Wizard configuration exported to {args.export}")
    
    # Save if requested
    if args.save:
        loader.save_config(args.save)
    
    # Update if requested
    if args.update:
        try:
            updates = json.loads(args.update)
            loader.update_config(updates)
        except json.JSONDecodeError:
            print("❌ Invalid JSON for update")
            sys.exit(1)

if __name__ == "__main__":
    main()
