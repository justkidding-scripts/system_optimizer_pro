#!/usr/bin/env python3
"""
Core configuration management system for System Optimizer Pro
Handles application configuration, user settings, and plugin configuration
"""

import os
import json
try:
    import yaml
except ImportError:
    yaml = None
from typing import Dict, Any, Optional, Union
from pathlib import Path
from datetime import datetime
import logging

class Config:
    """Central configuration manager with YAML support and validation"""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or os.path.expanduser("~/.system_optimizer_pro"))
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.config_dir / "config.yaml"
        self.user_config_file = self.config_dir / "user_config.yaml"
        self.plugin_config_dir = self.config_dir / "plugins"
        self.plugin_config_dir.mkdir(exist_ok=True)
        
        self._config: Dict[str, Any] = {}
        self._user_config: Dict[str, Any] = {}
        self._plugin_configs: Dict[str, Dict[str, Any]] = {}
        
        self.load_config()
    
    def get_default_config(self) -> Dict[str, Any]:
        """Get default configuration values"""
        return {
            'core': {
                'log_level': 'INFO',
                'log_file': str(self.config_dir / 'system_optimizer.log'),
                'log_rotation': True,
                'log_max_size': '10MB',
                'log_backup_count': 5,
                'debug_mode': False,
                'performance_monitoring': True,
                'auto_backup': True,
                'backup_retention_days': 30
            },
            'scheduler': {
                'enabled': True,
                'max_concurrent_jobs': 3,
                'job_timeout': 3600,
                'retry_attempts': 3,
                'retry_delay': 300,
                'persistent_schedule': True,
                'schedule_file': str(self.config_dir / 'schedule.yaml')
            },
            'monitoring': {
                'update_interval': 5,
                'history_retention_days': 90,
                'alert_thresholds': {
                    'cpu_usage': 85,
                    'memory_usage': 90,
                    'disk_usage': 95,
                    'temperature': 80
                },
                'monitor_network': True,
                'monitor_processes': True,
                'monitor_hardware': True
            },
            'notifications': {
                'enabled': True,
                'email_enabled': False,
                'desktop_enabled': True,
                'webhook_enabled': False,
                'smtp_server': '',
                'smtp_port': 587,
                'smtp_user': '',
                'smtp_password': '',
                'webhook_url': '',
                'notification_levels': ['ERROR', 'WARNING', 'INFO']
            },
            'github': {
                'enabled': False,
                'username': '',
                'token': '',
                'repo_name': 'system-optimizer-backups',
                'backup_branch': 'main',
                'backup_schedule': '0 2 * * 0',  # Weekly at 2 AM Sunday
                'include_configs': True,
                'include_logs': False,
                'compression': 'gzip'
            },
            'plugins': {
                'auto_discovery': True,
                'plugin_dirs': ['plugins', '/usr/local/lib/system_optimizer_plugins'],
                'enable_remote_plugins': False,
                'plugin_timeout': 300,
                'max_memory_per_plugin': '100MB'
            },
            'security': {
                'require_auth': False,
                'session_timeout': 3600,
                'max_failed_attempts': 5,
                'lockout_duration': 300,
                'encrypt_sensitive_data': True
            },
            'web_interface': {
                'enabled': False,
                'host': '127.0.0.1',
                'port': 8080,
                'ssl_enabled': False,
                'ssl_cert': '',
                'ssl_key': '',
                'cors_enabled': False
            }
        }
    
    def load_config(self):
        """Load configuration from files"""
        # Load main config
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    if yaml:
                        self._config = yaml.safe_load(f) or {}
                    else:
                        # Fallback to JSON if YAML not available
                        try:
                            self._config = json.load(f) or {}
                        except json.JSONDecodeError:
                            logging.warning("YAML not available and config is not valid JSON, using defaults")
                            self._config = {}
            except Exception as e:
                logging.error(f"Failed to load config: {e}")
                self._config = {}
        
        # Merge with defaults
        default_config = self.get_default_config()
        self._config = self._merge_configs(default_config, self._config)
        
        # Load user config
        if self.user_config_file.exists():
            try:
                with open(self.user_config_file, 'r') as f:
                    if yaml:
                        self._user_config = yaml.safe_load(f) or {}
                    else:
                        try:
                            self._user_config = json.load(f) or {}
                        except json.JSONDecodeError:
                            self._user_config = {}
            except Exception as e:
                logging.error(f"Failed to load user config: {e}")
                self._user_config = {}
        
        # Load plugin configs
        for plugin_file in self.plugin_config_dir.glob("*.yaml"):
            plugin_name = plugin_file.stem
            try:
                with open(plugin_file, 'r') as f:
                    if yaml:
                        self._plugin_configs[plugin_name] = yaml.safe_load(f) or {}
                    else:
                        try:
                            self._plugin_configs[plugin_name] = json.load(f) or {}
                        except json.JSONDecodeError:
                            self._plugin_configs[plugin_name] = {}
            except Exception as e:
                logging.error(f"Failed to load plugin config {plugin_name}: {e}")
    
    def save_config(self):
        """Save current configuration to files"""
        try:
            with open(self.config_file, 'w') as f:
                if yaml:
                    yaml.dump(self._config, f, default_flow_style=False, indent=2)
                else:
                    json.dump(self._config, f, indent=2)
            
            if self._user_config:
                with open(self.user_config_file, 'w') as f:
                    if yaml:
                        yaml.dump(self._user_config, f, default_flow_style=False, indent=2)
                    else:
                        json.dump(self._user_config, f, indent=2)
            
            # Save plugin configs
            for plugin_name, plugin_config in self._plugin_configs.items():
                extension = ".yaml" if yaml else ".json"
                plugin_file = self.plugin_config_dir / f"{plugin_name}{extension}"
                with open(plugin_file, 'w') as f:
                    if yaml:
                        yaml.dump(plugin_config, f, default_flow_style=False, indent=2)
                    else:
                        json.dump(plugin_config, f, indent=2)
                    
        except Exception as e:
            logging.error(f"Failed to save config: {e}")
            return False
        return True
    
    def get(self, key: str, default: Any = None, user_override: bool = True) -> Any:
        """Get configuration value with dot notation support"""
        keys = key.split('.')
        
        # Check user config first if user_override is enabled
        if user_override and self._user_config:
            value = self._get_nested_value(self._user_config, keys)
            if value is not None:
                return value
        
        # Check main config
        value = self._get_nested_value(self._config, keys)
        return value if value is not None else default
    
    def set(self, key: str, value: Any, save_immediately: bool = True) -> bool:
        """Set configuration value with dot notation support"""
        keys = key.split('.')
        self._set_nested_value(self._config, keys, value)
        
        if save_immediately:
            return self.save_config()
        return True
    
    def set_user(self, key: str, value: Any, save_immediately: bool = True) -> bool:
        """Set user-specific configuration value"""
        keys = key.split('.')
        self._set_nested_value(self._user_config, keys, value)
        
        if save_immediately:
            return self.save_config()
        return True
    
    def get_plugin_config(self, plugin_name: str, key: Optional[str] = None, default: Any = None) -> Any:
        """Get plugin-specific configuration"""
        if plugin_name not in self._plugin_configs:
            return default if key else {}
        
        plugin_config = self._plugin_configs[plugin_name]
        if key is None:
            return plugin_config
        
        keys = key.split('.')
        value = self._get_nested_value(plugin_config, keys)
        return value if value is not None else default
    
    def set_plugin_config(self, plugin_name: str, key: str, value: Any, save_immediately: bool = True) -> bool:
        """Set plugin-specific configuration"""
        if plugin_name not in self._plugin_configs:
            self._plugin_configs[plugin_name] = {}
        
        keys = key.split('.')
        self._set_nested_value(self._plugin_configs[plugin_name], keys, value)
        
        if save_immediately:
            return self.save_config()
        return True
    
    def _get_nested_value(self, config_dict: Dict[str, Any], keys: list) -> Any:
        """Get nested configuration value"""
        current = config_dict
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        return current
    
    def _set_nested_value(self, config_dict: Dict[str, Any], keys: list, value: Any):
        """Set nested configuration value"""
        current = config_dict
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value
    
    def _merge_configs(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge configuration dictionaries"""
        merged = default.copy()
        
        for key, value in override.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = self._merge_configs(merged[key], value)
            else:
                merged[key] = value
        
        return merged
    
    def validate_config(self) -> tuple[bool, list[str]]:
        """Validate current configuration"""
        errors = []
        
        # Validate core settings
        log_level = self.get('core.log_level', 'INFO')
        if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            errors.append(f"Invalid log level: {log_level}")
        
        # Validate scheduler settings
        max_concurrent = self.get('scheduler.max_concurrent_jobs', 3)
        if not isinstance(max_concurrent, int) or max_concurrent < 1:
            errors.append("scheduler.max_concurrent_jobs must be a positive integer")
        
        # Validate monitoring thresholds
        thresholds = self.get('monitoring.alert_thresholds', {})
        for threshold_name, threshold_value in thresholds.items():
            if not isinstance(threshold_value, (int, float)) or threshold_value < 0 or threshold_value > 100:
                errors.append(f"Invalid threshold {threshold_name}: must be between 0 and 100")
        
        # Validate GitHub settings if enabled
        if self.get('github.enabled', False):
            username = self.get('github.username', '')
            token = self.get('github.token', '')
            if not username or not token:
                errors.append("GitHub username and token are required when GitHub integration is enabled")
        
        # Validate web interface settings
        if self.get('web_interface.enabled', False):
            port = self.get('web_interface.port', 8080)
            if not isinstance(port, int) or port < 1 or port > 65535:
                errors.append("web_interface.port must be between 1 and 65535")
        
        return len(errors) == 0, errors
    
    def backup_config(self, backup_dir: Optional[str] = None) -> str:
        """Create a backup of current configuration"""
        backup_dir = Path(backup_dir or self.config_dir / "backups")
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"config_backup_{timestamp}.yaml"
        
        backup_data = {
            'timestamp': datetime.now().isoformat(),
            'config': self._config,
            'user_config': self._user_config,
            'plugin_configs': self._plugin_configs
        }
        
        try:
            with open(backup_file, 'w') as f:
                if yaml:
                    yaml.dump(backup_data, f, default_flow_style=False, indent=2)
                else:
                    json.dump(backup_data, f, indent=2)
            return str(backup_file)
        except Exception as e:
            logging.error(f"Failed to backup config: {e}")
            return ""
    
    def restore_config(self, backup_file: str) -> bool:
        """Restore configuration from backup"""
        try:
            with open(backup_file, 'r') as f:
                if yaml:
                    backup_data = yaml.safe_load(f)
                else:
                    backup_data = json.load(f)
            
            self._config = backup_data.get('config', {})
            self._user_config = backup_data.get('user_config', {})
            self._plugin_configs = backup_data.get('plugin_configs', {})
            
            return self.save_config()
        except Exception as e:
            logging.error(f"Failed to restore config from {backup_file}: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        return {
            'config_dir': str(self.config_dir),
            'core_settings': {
                'log_level': self.get('core.log_level'),
                'debug_mode': self.get('core.debug_mode'),
                'performance_monitoring': self.get('core.performance_monitoring')
            },
            'scheduler_enabled': self.get('scheduler.enabled'),
            'notifications_enabled': self.get('notifications.enabled'),
            'github_enabled': self.get('github.enabled'),
            'web_interface_enabled': self.get('web_interface.enabled'),
            'plugins_count': len(self._plugin_configs),
            'last_modified': datetime.now().isoformat()
        }

# Global configuration instance
config = Config()