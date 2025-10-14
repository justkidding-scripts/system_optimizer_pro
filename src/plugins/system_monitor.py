#!/usr/bin/env python3
"""
System Monitor Plugin for System Optimizer Pro
Provides real-time system resource monitoring and alerting
"""

import time
import threading
import psutil
from datetime import datetime
from core.plugin_manager import BasePlugin, PluginMetadata

class SystemMonitorPlugin(BasePlugin):
    """System monitoring plugin with resource tracking"""
    
    def get_metadata(self):
        """Return plugin metadata"""
        return PluginMetadata(
            name="SystemMonitor",
            version="1.0.0",
            description="Real-time system resource monitoring and alerting",
            author="System Optimizer Pro Team",
            dependencies=[],
            min_optimizer_version="1.0.0",
            category="monitoring",
            tags=["system", "monitoring", "resources", "alerts"]
        )
    
    def initialize(self):
        """Initialize the system monitor plugin"""
        try:
            self.monitoring_thread = None
            self.monitoring_data = {
                "cpu": [],
                "memory": [],
                "disk": [],
                "network": {},
                "alerts": []
            }
            self.alert_thresholds = {
                "cpu": 85.0,
                "memory": 90.0,
                "disk": 95.0,
                "load_avg": 80.0
            }
            self.last_network_io = None
            
            self.log("info", "System Monitor Plugin initialized successfully")
            return True
            
        except Exception as e:
            self.log("error", f"Failed to initialize System Monitor Plugin: {e}")
            return False
    
    def start(self):
        """Start system monitoring"""
        try:
            if self.monitoring_thread and self.monitoring_thread.is_alive():
                self.log("warning", "Monitoring already running")
                return True
            
            self._stop_event.clear()
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name=f"plugin-{self.metadata.name}-monitor",
                daemon=True
            )
            self.monitoring_thread.start()
            
            self.log("info", "System monitoring started")
            self.emit_event("plugin_started", {"plugin": self.metadata.name})
            return True
            
        except Exception as e:
            self.log("error", f"Failed to start system monitoring: {e}")
            return False
    
    def stop(self):
        """Stop system monitoring"""
        try:
            if not self.monitoring_thread or not self.monitoring_thread.is_alive():
                self.log("info", "Monitoring not running")
                return True
            
            self._stop_event.set()
            self.monitoring_thread.join(timeout=5.0)
            
            if self.monitoring_thread.is_alive():
                self.log("warning", "Monitoring thread did not stop gracefully")
                return False
            
            self.log("info", "System monitoring stopped")
            self.emit_event("plugin_stopped", {"plugin": self.metadata.name})
            return True
            
        except Exception as e:
            self.log("error", f"Failed to stop system monitoring: {e}")
            return False
    
    def cleanup(self):
        """Cleanup plugin resources"""
        try:
            self.stop()
            self.monitoring_data.clear()
            self.log("info", "System Monitor Plugin cleaned up")
            return True
            
        except Exception as e:
            self.log("error", f"Failed to cleanup System Monitor Plugin: {e}")
            return False
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.log("info", "Monitoring loop started")
        
        while not self._stop_event.is_set():
            try:
                # Collect system metrics
                current_time = datetime.now()
                
                # CPU Usage
                cpu_percent = psutil.cpu_percent(interval=1)
                self._add_metric("cpu", cpu_percent, current_time)
                
                # Memory Usage
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                self._add_metric("memory", memory_percent, current_time)
                
                # Disk Usage
                disk = psutil.disk_usage('/')
                disk_percent = disk.percent
                self._add_metric("disk", disk_percent, current_time)
                
                # Load Average (if available)
                if hasattr(psutil, 'getloadavg'):
                    load_avg = psutil.getloadavg()[0]  # 1-minute load average
                    cpu_count = psutil.cpu_count()
                    load_percent = (load_avg / cpu_count) * 100
                    
                    # Check load average threshold
                    if load_percent > self.alert_thresholds["load_avg"]:
                        self._create_alert(
                            "high_load_average",
                            f"High load average: {load_avg:.2f} ({load_percent:.1f}%)",
                            "warning"
                        )
                
                # Network I/O
                self._collect_network_stats()
                
                # Check thresholds and create alerts
                self._check_thresholds(cpu_percent, memory_percent, disk_percent)
                
                # Emit monitoring event
                self.emit_event("system_metrics", {
                    "timestamp": current_time.isoformat(),
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "disk_percent": disk_percent,
                    "memory_available": memory.available,
                    "disk_free": disk.free
                })
                
            except Exception as e:
                self.log("error", f"Error in monitoring loop: {e}")
            
            # Sleep for monitoring interval
            time.sleep(5)  # Monitor every 5 seconds
        
        self.log("info", "Monitoring loop stopped")
    
    def _add_metric(self, metric_type, value, timestamp):
        """Add a metric value to the data store"""
        metric_data = {
            "value": value,
            "timestamp": timestamp.isoformat()
        }
        
        self.monitoring_data[metric_type].append(metric_data)
        
        # Keep only last 100 data points per metric
        if len(self.monitoring_data[metric_type]) > 100:
            self.monitoring_data[metric_type] = self.monitoring_data[metric_type][-100:]
    
    def _collect_network_stats(self):
        """Collect network I/O statistics"""
        try:
            current_io = psutil.net_io_counters()
            
            if self.last_network_io:
                # Calculate bytes/sec
                time_diff = 5  # 5 second monitoring interval
                
                bytes_sent_per_sec = (current_io.bytes_sent - self.last_network_io.bytes_sent) / time_diff
                bytes_recv_per_sec = (current_io.bytes_recv - self.last_network_io.bytes_recv) / time_diff
                
                self.monitoring_data["network"] = {
                    "bytes_sent_per_sec": bytes_sent_per_sec,
                    "bytes_recv_per_sec": bytes_recv_per_sec,
                    "total_bytes_sent": current_io.bytes_sent,
                    "total_bytes_recv": current_io.bytes_recv,
                    "packets_sent": current_io.packets_sent,
                    "packets_recv": current_io.packets_recv
                }
            
            self.last_network_io = current_io
            
        except Exception as e:
            self.log("warning", f"Failed to collect network stats: {e}")
    
    def _check_thresholds(self, cpu_percent, memory_percent, disk_percent):
        """Check if any metrics exceed thresholds"""
        alerts = []
        
        if cpu_percent > self.alert_thresholds["cpu"]:
            alerts.append(self._create_alert(
                "high_cpu_usage",
                f"High CPU usage: {cpu_percent:.1f}%",
                "warning"
            ))
        
        if memory_percent > self.alert_thresholds["memory"]:
            alerts.append(self._create_alert(
                "high_memory_usage",
                f"High memory usage: {memory_percent:.1f}%",
                "warning"
            ))
        
        if disk_percent > self.alert_thresholds["disk"]:
            alerts.append(self._create_alert(
                "high_disk_usage",
                f"High disk usage: {disk_percent:.1f}%",
                "critical"
            ))
        
        # Emit alerts if any
        if alerts:
            self.emit_event("system_alerts", {
                "alerts": alerts,
                "timestamp": datetime.now().isoformat()
            })
    
    def _create_alert(self, alert_type, message, severity):
        """Create a system alert"""
        alert = {
            "type": alert_type,
            "message": message,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "plugin": self.metadata.name
        }
        
        # Add to alerts list (keep last 50)
        self.monitoring_data["alerts"].append(alert)
        if len(self.monitoring_data["alerts"]) > 50:
            self.monitoring_data["alerts"] = self.monitoring_data["alerts"][-50:]
        
        self.log(severity, message)
        return alert
    
    def get_current_metrics(self):
        """Get current system metrics"""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None,
                "network": self.monitoring_data.get("network", {}),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            self.log("error", f"Failed to get current metrics: {e}")
            return {}
    
    def get_historical_data(self, metric_type, limit=50):
        """Get historical data for a specific metric"""
        if metric_type not in self.monitoring_data:
            return []
        
        return self.monitoring_data[metric_type][-limit:]
    
    def get_alerts(self, limit=20):
        """Get recent alerts"""
        return self.monitoring_data["alerts"][-limit:]
    
    def set_threshold(self, metric_type, threshold):
        """Set alert threshold for a metric"""
        if metric_type in self.alert_thresholds:
            self.alert_thresholds[metric_type] = float(threshold)
            self.log("info", f"Set {metric_type} threshold to {threshold}%")
            return True
        return False
    
    def get_status(self):
        """Get plugin status with monitoring data"""
        base_status = super().get_status()
        
        # Add monitoring-specific status
        base_status.update({
            "monitoring_active": self.monitoring_thread and self.monitoring_thread.is_alive(),
            "data_points": {
                metric: len(data) for metric, data in self.monitoring_data.items() 
                if isinstance(data, list)
            },
            "alert_count": len(self.monitoring_data["alerts"]),
            "thresholds": self.alert_thresholds
        })
        
        return base_status

# Plugin class must be available for discovery
plugin_class = SystemMonitorPlugin