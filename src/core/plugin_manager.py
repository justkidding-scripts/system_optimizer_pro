#!/usr/bin/env python3
"""
Plugin management system for System Optimizer Pro
Handles plugin discovery, loading, lifecycle management, and inter-plugin communication
"""

import os
import sys
import importlib
import importlib.util
import inspect
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Type
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, Future
import hashlib
import json

from .config import config

class PluginState(Enum):
    """Plugin lifecycle states"""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    UNLOADING = "unloading"

@dataclass
class PluginMetadata:
    """Plugin metadata container"""
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    min_optimizer_version: str
    max_memory: int = 100 * 1024 * 1024  # 100MB default
    timeout: int = 300  # 5 minutes default
    autostart: bool = True
    category: str = "general"
    tags: List[str] = None
    api_version: str = "1.0"

class BasePlugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self.state = PluginState.UNLOADED
        self.metadata = self.get_metadata()
        self.config = config.get_plugin_config(self.metadata.name)
        self._stop_event = threading.Event()
        self._thread = None
        self._last_error = None
        
    @abstractmethod
    def get_metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass
    
    @abstractmethod
    def initialize(self) -> bool:
        """Initialize the plugin. Return True on success."""
        pass
    
    @abstractmethod
    def start(self) -> bool:
        """Start the plugin. Return True on success."""
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """Stop the plugin. Return True on success."""
        pass
    
    @abstractmethod
    def cleanup(self) -> bool:
        """Cleanup plugin resources. Return True on success."""
        pass
    
    def is_healthy(self) -> bool:
        """Check if plugin is healthy. Override for custom health checks."""
        return self.state in [PluginState.LOADED, PluginState.ACTIVE]
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status information"""
        return {
            'name': self.metadata.name,
            'state': self.state.value,
            'last_error': self._last_error,
            'thread_alive': self._thread.is_alive() if self._thread else False,
            'memory_usage': self.get_memory_usage(),
            'uptime': self.get_uptime()
        }
    
    def get_memory_usage(self) -> int:
        """Get current memory usage in bytes"""
        # Placeholder - in real implementation would use psutil
        return 0
    
    def get_uptime(self) -> float:
        """Get plugin uptime in seconds"""
        # Placeholder - track start time
        return 0.0
    
    def log(self, level: str, message: str):
        """Log a message with plugin context"""
        logger = logging.getLogger(f"plugin.{self.metadata.name}")
        getattr(logger, level.lower())(message)
    
    def emit_event(self, event_type: str, data: Any = None):
        """Emit an event through the plugin manager"""
        self.plugin_manager.emit_event(self.metadata.name, event_type, data)
    
    def subscribe_to_event(self, event_type: str, callback: Callable):
        """Subscribe to events from other plugins"""
        self.plugin_manager.subscribe_to_event(event_type, callback, self.metadata.name)

class PluginManager:
    """Manages plugin lifecycle, communication, and resources"""
    
    def __init__(self):
        self.plugins: Dict[str, BasePlugin] = {}
        self.plugin_modules: Dict[str, Any] = {}
        self.event_subscribers: Dict[str, List[Callable]] = {}
        self.dependency_graph: Dict[str, List[str]] = {}
        self.executor = ThreadPoolExecutor(max_workers=10)
        self.plugin_dirs = []
        self._lock = threading.RLock()
        
        # Initialize plugin directories
        default_dirs = [
            'plugins', 
            'src/plugins',
            str(Path.home() / '.system_optimizer_pro' / 'plugins')
        ]
        self.plugin_dirs = config.get('plugins.plugin_dirs', default_dirs)
        self.plugin_dirs = [Path(d).expanduser().absolute() for d in self.plugin_dirs]
        
        # Create plugin directories if they don't exist (only user-writable ones)
        valid_dirs = []
        for plugin_dir in self.plugin_dirs:
            try:
                plugin_dir.mkdir(parents=True, exist_ok=True)
                valid_dirs.append(plugin_dir)
            except PermissionError:
                logging.warning(f"Cannot create plugin directory {plugin_dir} (permission denied)")
                # Still include if it exists and is readable
                if plugin_dir.exists() and os.access(plugin_dir, os.R_OK):
                    valid_dirs.append(plugin_dir)
        self.plugin_dirs = valid_dirs
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins in plugin directories"""
        discovered = []
        
        for plugin_dir in self.plugin_dirs:
            if not plugin_dir.exists():
                continue
                
            for plugin_path in plugin_dir.rglob("*.py"):
                if plugin_path.name.startswith("__"):
                    continue
                
                try:
                    plugin_info = self._analyze_plugin_file(plugin_path)
                    if plugin_info:
                        discovered.append(plugin_info['name'])
                except Exception as e:
                    logging.warning(f"Failed to analyze plugin {plugin_path}: {e}")
        
        return discovered
    
    def _analyze_plugin_file(self, plugin_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a plugin file to extract metadata"""
        try:
            spec = importlib.util.spec_from_file_location("temp_plugin", plugin_path)
            if not spec or not spec.loader:
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Look for plugin classes
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BasePlugin) and obj != BasePlugin:
                    return {
                        'name': name,
                        'path': str(plugin_path),
                        'class': obj,
                        'module': module
                    }
        except Exception as e:
            logging.error(f"Error analyzing plugin {plugin_path}: {e}")
        
        return None
    
    def load_plugin(self, plugin_name: str, plugin_path: Optional[str] = None) -> bool:
        """Load a plugin by name or path"""
        with self._lock:
            if plugin_name in self.plugins:
                logging.warning(f"Plugin {plugin_name} already loaded")
                return False
            
            try:
                # Find plugin if path not provided
                if not plugin_path:
                    plugin_path = self._find_plugin_path(plugin_name)
                    if not plugin_path:
                        logging.error(f"Plugin {plugin_name} not found")
                        return False
                
                # Load plugin module
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
                if not spec or not spec.loader:
                    logging.error(f"Invalid plugin spec for {plugin_name}")
                    return False
                
                module = importlib.util.module_from_spec(spec)
                self.plugin_modules[plugin_name] = module
                
                # Execute module
                spec.loader.exec_module(module)
                
                # Find plugin class
                plugin_class = None
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BasePlugin) and obj != BasePlugin:
                        plugin_class = obj
                        break
                
                if not plugin_class:
                    logging.error(f"No valid plugin class found in {plugin_name}")
                    return False
                
                # Create plugin instance
                plugin_instance = plugin_class(self)
                plugin_instance.state = PluginState.LOADING
                
                # Check dependencies
                if not self._check_dependencies(plugin_instance):
                    logging.error(f"Dependencies not met for plugin {plugin_name}")
                    plugin_instance.state = PluginState.ERROR
                    return False
                
                # Initialize plugin
                if plugin_instance.initialize():
                    plugin_instance.state = PluginState.LOADED
                    self.plugins[plugin_name] = plugin_instance
                    
                    # Build dependency graph
                    self._update_dependency_graph(plugin_instance)
                    
                    logging.info(f"Plugin {plugin_name} loaded successfully")
                    self.emit_event("system", "plugin_loaded", {"plugin": plugin_name})
                    return True
                else:
                    logging.error(f"Failed to initialize plugin {plugin_name}")
                    plugin_instance.state = PluginState.ERROR
                    return False
                    
            except Exception as e:
                logging.error(f"Error loading plugin {plugin_name}: {e}")
                logging.error(traceback.format_exc())
                return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin"""
        with self._lock:
            if plugin_name not in self.plugins:
                logging.warning(f"Plugin {plugin_name} not loaded")
                return False
            
            plugin = self.plugins[plugin_name]
            plugin.state = PluginState.UNLOADING
            
            try:
                # Stop plugin if active
                if plugin.state == PluginState.ACTIVE:
                    self.stop_plugin(plugin_name)
                
                # Cleanup plugin
                if plugin.cleanup():
                    plugin.state = PluginState.UNLOADED
                    del self.plugins[plugin_name]
                    
                    # Remove from dependency graph
                    self._remove_from_dependency_graph(plugin_name)
                    
                    # Remove module
                    if plugin_name in self.plugin_modules:
                        del self.plugin_modules[plugin_name]
                    
                    logging.info(f"Plugin {plugin_name} unloaded successfully")
                    self.emit_event("system", "plugin_unloaded", {"plugin": plugin_name})
                    return True
                else:
                    logging.error(f"Failed to cleanup plugin {plugin_name}")
                    plugin.state = PluginState.ERROR
                    return False
                    
            except Exception as e:
                logging.error(f"Error unloading plugin {plugin_name}: {e}")
                plugin.state = PluginState.ERROR
                return False
    
    def start_plugin(self, plugin_name: str) -> bool:
        """Start a loaded plugin"""
        with self._lock:
            if plugin_name not in self.plugins:
                logging.error(f"Plugin {plugin_name} not loaded")
                return False
            
            plugin = self.plugins[plugin_name]
            if plugin.state != PluginState.LOADED:
                logging.error(f"Plugin {plugin_name} not in LOADED state (current: {plugin.state})")
                return False
            
            try:
                if plugin.start():
                    plugin.state = PluginState.ACTIVE
                    logging.info(f"Plugin {plugin_name} started successfully")
                    self.emit_event("system", "plugin_started", {"plugin": plugin_name})
                    return True
                else:
                    logging.error(f"Failed to start plugin {plugin_name}")
                    plugin.state = PluginState.ERROR
                    return False
                    
            except Exception as e:
                logging.error(f"Error starting plugin {plugin_name}: {e}")
                plugin.state = PluginState.ERROR
                plugin._last_error = str(e)
                return False
    
    def stop_plugin(self, plugin_name: str) -> bool:
        """Stop an active plugin"""
        with self._lock:
            if plugin_name not in self.plugins:
                logging.error(f"Plugin {plugin_name} not loaded")
                return False
            
            plugin = self.plugins[plugin_name]
            if plugin.state != PluginState.ACTIVE:
                logging.warning(f"Plugin {plugin_name} not active")
                return True
            
            try:
                if plugin.stop():
                    plugin.state = PluginState.LOADED
                    logging.info(f"Plugin {plugin_name} stopped successfully")
                    self.emit_event("system", "plugin_stopped", {"plugin": plugin_name})
                    return True
                else:
                    logging.error(f"Failed to stop plugin {plugin_name}")
                    return False
                    
            except Exception as e:
                logging.error(f"Error stopping plugin {plugin_name}: {e}")
                plugin._last_error = str(e)
                return False
    
    def restart_plugin(self, plugin_name: str) -> bool:
        """Restart a plugin"""
        return self.stop_plugin(plugin_name) and self.start_plugin(plugin_name)
    
    def reload_plugin(self, plugin_name: str) -> bool:
        """Reload a plugin (unload then load)"""
        plugin_path = None
        if plugin_name in self.plugins:
            # Store path before unloading
            plugin_path = self._find_plugin_path(plugin_name)
        
        return self.unload_plugin(plugin_name) and self.load_plugin(plugin_name, plugin_path)
    
    def get_plugin_status(self, plugin_name: Optional[str] = None) -> Dict[str, Any]:
        """Get status of one or all plugins"""
        with self._lock:
            if plugin_name:
                if plugin_name in self.plugins:
                    return self.plugins[plugin_name].get_status()
                else:
                    return {"error": f"Plugin {plugin_name} not found"}
            else:
                return {name: plugin.get_status() for name, plugin in self.plugins.items()}
    
    def get_plugin_list(self) -> List[Dict[str, Any]]:
        """Get list of all plugins with metadata"""
        with self._lock:
            plugin_list = []
            for name, plugin in self.plugins.items():
                plugin_info = {
                    'name': name,
                    'state': plugin.state.value,
                    'metadata': {
                        'version': plugin.metadata.version,
                        'description': plugin.metadata.description,
                        'author': plugin.metadata.author,
                        'category': plugin.metadata.category
                    }
                }
                plugin_list.append(plugin_info)
            return plugin_list
    
    def emit_event(self, source: str, event_type: str, data: Any = None):
        """Emit an event to all subscribers"""
        event = {
            'source': source,
            'type': event_type,
            'data': data,
            'timestamp': time.time()
        }
        
        if event_type in self.event_subscribers:
            for callback in self.event_subscribers[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logging.error(f"Error in event callback for {event_type}: {e}")
    
    def subscribe_to_event(self, event_type: str, callback: Callable, subscriber_name: str = "unknown"):
        """Subscribe to an event type"""
        if event_type not in self.event_subscribers:
            self.event_subscribers[event_type] = []
        
        self.event_subscribers[event_type].append(callback)
        logging.debug(f"{subscriber_name} subscribed to event {event_type}")
    
    def unsubscribe_from_event(self, event_type: str, callback: Callable):
        """Unsubscribe from an event type"""
        if event_type in self.event_subscribers:
            try:
                self.event_subscribers[event_type].remove(callback)
            except ValueError:
                pass
    
    def _find_plugin_path(self, plugin_name: str) -> Optional[str]:
        """Find plugin file path by name"""
        for plugin_dir in self.plugin_dirs:
            for plugin_file in plugin_dir.rglob("*.py"):
                if plugin_file.stem == plugin_name:
                    return str(plugin_file)
        return None
    
    def _check_dependencies(self, plugin: BasePlugin) -> bool:
        """Check if plugin dependencies are met"""
        for dep in plugin.metadata.dependencies:
            if dep not in self.plugins:
                logging.error(f"Dependency {dep} not loaded for plugin {plugin.metadata.name}")
                return False
            if self.plugins[dep].state != PluginState.LOADED:
                logging.error(f"Dependency {dep} not ready for plugin {plugin.metadata.name}")
                return False
        return True
    
    def _update_dependency_graph(self, plugin: BasePlugin):
        """Update dependency graph with new plugin"""
        self.dependency_graph[plugin.metadata.name] = plugin.metadata.dependencies.copy()
    
    def _remove_from_dependency_graph(self, plugin_name: str):
        """Remove plugin from dependency graph"""
        if plugin_name in self.dependency_graph:
            del self.dependency_graph[plugin_name]
        
        # Remove as dependency from other plugins
        for deps in self.dependency_graph.values():
            if plugin_name in deps:
                deps.remove(plugin_name)
    
    def get_load_order(self, plugin_names: List[str]) -> List[str]:
        """Calculate plugin load order based on dependencies"""
        loaded = set()
        ordered = []
        
        def load_plugin_recursive(name: str):
            if name in loaded:
                return
            
            # Load dependencies first
            if name in self.dependency_graph:
                for dep in self.dependency_graph[name]:
                    if dep in plugin_names:  # Only load if requested
                        load_plugin_recursive(dep)
            
            ordered.append(name)
            loaded.add(name)
        
        for plugin_name in plugin_names:
            load_plugin_recursive(plugin_name)
        
        return ordered
    
    def load_all_plugins(self) -> Dict[str, bool]:
        """Load all discovered plugins"""
        discovered = self.discover_plugins()
        load_order = self.get_load_order(discovered)
        results = {}
        
        for plugin_name in load_order:
            results[plugin_name] = self.load_plugin(plugin_name)
        
        return results
    
    def start_all_plugins(self) -> Dict[str, bool]:
        """Start all loaded plugins"""
        results = {}
        for plugin_name, plugin in self.plugins.items():
            if plugin.state == PluginState.LOADED and plugin.metadata.autostart:
                results[plugin_name] = self.start_plugin(plugin_name)
        return results
    
    def stop_all_plugins(self) -> Dict[str, bool]:
        """Stop all active plugins"""
        results = {}
        for plugin_name, plugin in self.plugins.items():
            if plugin.state == PluginState.ACTIVE:
                results[plugin_name] = self.stop_plugin(plugin_name)
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Perform health check on all plugins"""
        health_status = {}
        
        for plugin_name, plugin in self.plugins.items():
            try:
                is_healthy = plugin.is_healthy()
                health_status[plugin_name] = {
                    'healthy': is_healthy,
                    'state': plugin.state.value,
                    'last_error': plugin._last_error
                }
                
                # Auto-restart unhealthy plugins if configured
                if not is_healthy and config.get(f'plugins.{plugin_name}.auto_restart', False):
                    logging.warning(f"Auto-restarting unhealthy plugin {plugin_name}")
                    self.restart_plugin(plugin_name)
                    
            except Exception as e:
                health_status[plugin_name] = {
                    'healthy': False,
                    'error': str(e)
                }
        
        return health_status
    
    def cleanup(self):
        """Cleanup plugin manager resources"""
        self.stop_all_plugins()
        
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)
        
        self.executor.shutdown(wait=True)

# Global plugin manager instance
plugin_manager = PluginManager()