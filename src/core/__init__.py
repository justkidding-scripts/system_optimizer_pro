"""
System Optimizer Pro - Core Components

Core functionality including configuration management, plugin system, 
job scheduling, and system monitoring.
"""

__version__ = "1.0.0"

from .config import config
from .plugin_manager import plugin_manager, BasePlugin, PluginMetadata
from .scheduler import scheduler, JobDefinition, TriggerType

__all__ = [
    'config',
    'plugin_manager', 
    'BasePlugin',
    'PluginMetadata',
    'scheduler',
    'JobDefinition',
    'TriggerType'
]