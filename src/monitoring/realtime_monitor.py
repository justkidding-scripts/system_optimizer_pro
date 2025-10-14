#!/usr/bin/env python3
"""
Advanced Real-time Monitoring System for System Optimizer Pro
Provides comprehensive system monitoring with WebSocket support, GPU monitoring, 
network analysis, and real-time dashboards
"""

import asyncio
import threading
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import queue
import weakref

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    psutil = None

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    websockets = None

try:
    import GPUtil
    HAS_GPUTIL = True
except ImportError:
    HAS_GPUTIL = False
    GPUtil = None

from ..core.config import config
from ..core.platform_compat import platform_manager

class MonitoringLevel(Enum):
    """Monitoring detail levels"""
    BASIC = "basic"
    DETAILED = "detailed"
    INTENSIVE = "intensive"

class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class SystemMetrics:
    """Comprehensive system metrics data structure"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Core system metrics
    cpu_percent: float = 0.0
    cpu_cores: int = 0
    cpu_freq: Dict[str, float] = field(default_factory=dict)
    cpu_per_core: List[float] = field(default_factory=list)
    
    memory_total: int = 0
    memory_used: int = 0
    memory_available: int = 0
    memory_percent: float = 0.0
    swap_total: int = 0
    swap_used: int = 0
    swap_percent: float = 0.0
    
    disk_total: int = 0
    disk_used: int = 0
    disk_free: int = 0
    disk_percent: float = 0.0
    disk_io_read: int = 0
    disk_io_write: int = 0
    
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    network_packets_sent: int = 0
    network_packets_recv: int = 0
    network_connections: int = 0
    
    # Advanced metrics
    load_average: List[float] = field(default_factory=list)
    boot_time: datetime = field(default_factory=datetime.now)
    uptime: float = 0.0
    
    # Process information
    process_count: int = 0
    thread_count: int = 0
    
    # GPU metrics (if available)
    gpu_count: int = 0
    gpu_metrics: List[Dict[str, Any]] = field(default_factory=list)
    
    # Temperature sensors
    temperatures: Dict[str, float] = field(default_factory=dict)
    
    # Platform-specific metrics
    platform_metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ProcessInfo:
    """Detailed process information"""
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_mb: int
    memory_percent: float
    create_time: datetime
    cmdline: List[str] = field(default_factory=list)
    username: str = ""
    connections: int = 0
    threads: int = 0

@dataclass
class NetworkConnection:
    """Network connection information"""
    local_address: str
    local_port: int
    remote_address: str
    remote_port: int
    status: str
    pid: Optional[int] = None
    process_name: str = ""

@dataclass
class SystemAlert:
    """System alert/notification"""
    id: str
    timestamp: datetime
    severity: AlertSeverity
    category: str
    title: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    auto_resolve: bool = True

class MonitoringSubscriber:
    """Base class for monitoring event subscribers"""
    
    def __init__(self, subscriber_id: str):
        self.subscriber_id = subscriber_id
        self.subscribed_metrics: Set[str] = set()
        self.alert_filters: Dict[str, Any] = {}
    
    def on_metrics_update(self, metrics: SystemMetrics):
        """Called when metrics are updated"""
        pass
    
    def on_process_update(self, processes: List[ProcessInfo]):
        """Called when process list is updated"""
        pass
    
    def on_alert(self, alert: SystemAlert):
        """Called when an alert is triggered"""
        pass

class WebSocketSubscriber(MonitoringSubscriber):
    """WebSocket client subscriber for real-time monitoring"""
    
    def __init__(self, subscriber_id: str, websocket):
        super().__init__(subscriber_id)
        self.websocket = websocket
        self.message_queue = asyncio.Queue()
        self.is_active = True
    
    async def send_message(self, message_type: str, data: Dict[str, Any]):
        """Send message to WebSocket client"""
        if not self.is_active:
            return
            
        try:
            message = {
                'type': message_type,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            await self.websocket.send(json.dumps(message))
        except Exception as e:
            logging.error(f"Failed to send WebSocket message: {e}")
            self.is_active = False
    
    async def on_metrics_update(self, metrics: SystemMetrics):
        """Send metrics update to WebSocket client"""
        await self.send_message('metrics_update', asdict(metrics))
    
    async def on_process_update(self, processes: List[ProcessInfo]):
        """Send process update to WebSocket client"""
        process_data = [asdict(p) for p in processes]
        await self.send_message('process_update', {'processes': process_data})
    
    async def on_alert(self, alert: SystemAlert):
        """Send alert to WebSocket client"""
        await self.send_message('alert', asdict(alert))

class RealTimeMonitor:
    """Advanced real-time system monitoring with WebSocket support"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.platform = platform_manager.get_platform()
        
        # Monitoring configuration
        self.monitoring_level = MonitoringLevel.DETAILED
        self.update_interval = config.get('monitoring.update_interval', 1.0)  # seconds
        self.history_retention = config.get('monitoring.history_retention_hours', 24)
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Data storage
        self.current_metrics: Optional[SystemMetrics] = None
        self.metrics_history: List[SystemMetrics] = []
        self.current_processes: List[ProcessInfo] = []
        self.active_connections: List[NetworkConnection] = []
        self.active_alerts: List[SystemAlert] = []
        
        # Subscribers and event handling
        self.subscribers: Dict[str, MonitoringSubscriber] = {}
        self.websocket_server = None
        self.websocket_port = config.get('monitoring.websocket_port', 8765)
        
        # Alert thresholds
        self.alert_thresholds = {
            'cpu_percent': config.get('monitoring.alert_thresholds.cpu_usage', 85),
            'memory_percent': config.get('monitoring.alert_thresholds.memory_usage', 90),
            'disk_percent': config.get('monitoring.alert_thresholds.disk_usage', 95),
            'temperature': config.get('monitoring.alert_thresholds.temperature', 80),
            'load_average': config.get('monitoring.alert_thresholds.load_avg', 80)
        }
        
        # Performance counters
        self.last_disk_io = None
        self.last_network_io = None
        self.last_cpu_times = None
        
        # GPU monitoring
        self.gpu_monitoring_enabled = HAS_GPUTIL and config.get('monitoring.enable_gpu', True)
        
        # Initialize platform-specific monitoring
        self._init_platform_monitoring()
    
    def _init_platform_monitoring(self):
        """Initialize platform-specific monitoring features"""
        try:
            if platform_manager.is_windows():
                # Windows-specific initialization
                self.logger.info("Initializing Windows-specific monitoring")
                # Could initialize WMI, Performance Counters, etc.
                
            elif platform_manager.is_linux():
                # Linux-specific initialization
                self.logger.info("Initializing Linux-specific monitoring")
                # Could initialize /proc monitoring, systemd integration, etc.
                
        except Exception as e:
            self.logger.error(f"Error initializing platform monitoring: {e}")
    
    def start_monitoring(self) -> bool:
        """Start the real-time monitoring system"""
        if self.is_monitoring:
            self.logger.warning("Monitoring already running")
            return False
        
        try:
            self.logger.info("Starting real-time monitoring system")
            
            # Start monitoring thread
            self.stop_event.clear()
            self.monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="realtime-monitor",
                daemon=True
            )
            self.monitor_thread.start()
            
            # Start WebSocket server if available
            if HAS_WEBSOCKETS and config.get('monitoring.enable_websocket', True):
                self._start_websocket_server()
            
            self.is_monitoring = True
            self.logger.info("Real-time monitoring started successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start monitoring: {e}")
            return False
    
    def stop_monitoring(self) -> bool:
        """Stop the real-time monitoring system"""
        if not self.is_monitoring:
            return True
        
        try:
            self.logger.info("Stopping real-time monitoring system")
            
            # Stop monitoring thread
            self.stop_event.set()
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5.0)
            
            # Stop WebSocket server
            if self.websocket_server:
                self.websocket_server.close()
                self.websocket_server = None
            
            self.is_monitoring = False
            self.logger.info("Real-time monitoring stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping monitoring: {e}")
            return False
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        self.logger.info("Monitoring loop started")
        
        while not self.stop_event.is_set():
            try:
                start_time = time.time()
                
                # Collect system metrics
                metrics = self._collect_system_metrics()
                
                # Update current state
                self.current_metrics = metrics
                self._add_to_history(metrics)
                
                # Collect process information if detailed monitoring
                if self.monitoring_level in [MonitoringLevel.DETAILED, MonitoringLevel.INTENSIVE]:
                    self.current_processes = self._collect_process_info()
                    
                    # Network connections for intensive monitoring
                    if self.monitoring_level == MonitoringLevel.INTENSIVE:
                        self.active_connections = self._collect_network_connections()
                
                # Check for alerts
                self._check_alert_conditions(metrics)
                
                # Notify subscribers
                self._notify_subscribers(metrics)
                
                # Calculate sleep time to maintain consistent interval
                elapsed = time.time() - start_time
                sleep_time = max(0, self.update_interval - elapsed)
                
                if sleep_time > 0:
                    self.stop_event.wait(sleep_time)
                else:
                    # Log if monitoring is taking too long
                    self.logger.warning(f"Monitoring cycle took {elapsed:.2f}s, target interval: {self.update_interval}s")
                
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                time.sleep(self.update_interval)
        
        self.logger.info("Monitoring loop stopped")
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """Collect comprehensive system metrics"""
        metrics = SystemMetrics()
        
        try:
            if HAS_PSUTIL:
                # CPU metrics
                metrics.cpu_percent = psutil.cpu_percent(interval=None)
                metrics.cpu_cores = psutil.cpu_count(logical=False)
                metrics.cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
                
                try:
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        metrics.cpu_freq = {
                            'current': cpu_freq.current,
                            'min': cpu_freq.min,
                            'max': cpu_freq.max
                        }
                except:
                    pass
                
                # Memory metrics
                memory = psutil.virtual_memory()
                metrics.memory_total = memory.total
                metrics.memory_used = memory.used
                metrics.memory_available = memory.available
                metrics.memory_percent = memory.percent
                
                swap = psutil.swap_memory()
                metrics.swap_total = swap.total
                metrics.swap_used = swap.used
                metrics.swap_percent = swap.percent
                
                # Disk metrics
                disk = psutil.disk_usage('/')
                metrics.disk_total = disk.total
                metrics.disk_used = disk.used
                metrics.disk_free = disk.free
                metrics.disk_percent = disk.percent
                
                # Disk I/O
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    metrics.disk_io_read = disk_io.read_bytes
                    metrics.disk_io_write = disk_io.write_bytes
                
                # Network metrics
                network_io = psutil.net_io_counters()
                if network_io:
                    metrics.network_bytes_sent = network_io.bytes_sent
                    metrics.network_bytes_recv = network_io.bytes_recv
                    metrics.network_packets_sent = network_io.packets_sent
                    metrics.network_packets_recv = network_io.packets_recv
                
                # Connection count
                try:
                    metrics.network_connections = len(psutil.net_connections())
                except:
                    metrics.network_connections = 0
                
                # System info
                metrics.boot_time = datetime.fromtimestamp(psutil.boot_time())
                metrics.uptime = time.time() - psutil.boot_time()
                
                # Process counts
                metrics.process_count = len(psutil.pids())
                
                # Load average (Linux/Unix)
                if hasattr(psutil, 'getloadavg'):
                    try:
                        metrics.load_average = list(psutil.getloadavg())
                    except:
                        pass
                
                # Temperature sensors
                if hasattr(psutil, 'sensors_temperatures'):
                    try:
                        temps = psutil.sensors_temperatures()
                        for name, entries in temps.items():
                            for entry in entries:
                                sensor_name = f"{name}_{entry.label or 'temp'}"
                                metrics.temperatures[sensor_name] = entry.current
                    except:
                        pass
            
            # GPU metrics
            if self.gpu_monitoring_enabled:
                metrics.gpu_metrics = self._collect_gpu_metrics()
                metrics.gpu_count = len(metrics.gpu_metrics)
            
            # Platform-specific metrics
            try:
                platform_metrics = self.platform.get_system_metrics()
                metrics.platform_metrics = platform_metrics
            except Exception as e:
                self.logger.debug(f"Error collecting platform metrics: {e}")
            
        except Exception as e:
            self.logger.error(f"Error collecting system metrics: {e}")
        
        return metrics
    
    def _collect_gpu_metrics(self) -> List[Dict[str, Any]]:
        """Collect GPU metrics if available"""
        gpu_metrics = []
        
        if not HAS_GPUTIL:
            return gpu_metrics
        
        try:
            gpus = GPUtil.getGPUs()
            for gpu in gpus:
                gpu_info = {
                    'id': gpu.id,
                    'name': gpu.name,
                    'load': gpu.load * 100,  # Convert to percentage
                    'memory_used': gpu.memoryUsed,
                    'memory_total': gpu.memoryTotal,
                    'memory_percent': (gpu.memoryUsed / gpu.memoryTotal * 100) if gpu.memoryTotal > 0 else 0,
                    'temperature': gpu.temperature
                }
                gpu_metrics.append(gpu_info)
        except Exception as e:
            self.logger.debug(f"Error collecting GPU metrics: {e}")
        
        return gpu_metrics
    
    def _collect_process_info(self) -> List[ProcessInfo]:
        """Collect detailed process information"""
        processes = []
        
        if not HAS_PSUTIL:
            return processes
        
        try:
            # Get top processes by CPU and memory
            proc_list = []
            for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent', 'memory_info', 'memory_percent', 'create_time', 'cmdline', 'username', 'num_threads']):
                try:
                    proc_list.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by CPU usage and take top processes
            top_cpu = sorted(proc_list, key=lambda x: x['cpu_percent'] or 0, reverse=True)[:20]
            
            # Sort by memory and take top processes
            top_memory = sorted(proc_list, key=lambda x: x['memory_percent'] or 0, reverse=True)[:20]
            
            # Combine and deduplicate
            seen_pids = set()
            for proc_info in top_cpu + top_memory:
                if proc_info['pid'] in seen_pids:
                    continue
                
                seen_pids.add(proc_info['pid'])
                
                try:
                    process = ProcessInfo(
                        pid=proc_info['pid'],
                        name=proc_info['name'] or 'unknown',
                        status=proc_info['status'] or 'unknown',
                        cpu_percent=proc_info['cpu_percent'] or 0,
                        memory_mb=proc_info['memory_info'].rss // 1024 // 1024 if proc_info['memory_info'] else 0,
                        memory_percent=proc_info['memory_percent'] or 0,
                        create_time=datetime.fromtimestamp(proc_info['create_time']) if proc_info['create_time'] else datetime.now(),
                        cmdline=proc_info['cmdline'] or [],
                        username=proc_info['username'] or '',
                        threads=proc_info['num_threads'] or 0
                    )
                    processes.append(process)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing process {proc_info['pid']}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error collecting process info: {e}")
        
        return processes
    
    def _collect_network_connections(self) -> List[NetworkConnection]:
        """Collect active network connections"""
        connections = []
        
        if not HAS_PSUTIL:
            return connections
        
        try:
            net_connections = psutil.net_connections(kind='inet')
            
            for conn in net_connections:
                try:
                    # Get process name if PID is available
                    process_name = ""
                    if conn.pid:
                        try:
                            process = psutil.Process(conn.pid)
                            process_name = process.name()
                        except:
                            pass
                    
                    connection = NetworkConnection(
                        local_address=conn.laddr.ip if conn.laddr else '',
                        local_port=conn.laddr.port if conn.laddr else 0,
                        remote_address=conn.raddr.ip if conn.raddr else '',
                        remote_port=conn.raddr.port if conn.raddr else 0,
                        status=conn.status,
                        pid=conn.pid,
                        process_name=process_name
                    )
                    connections.append(connection)
                    
                except Exception as e:
                    self.logger.debug(f"Error processing connection: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error collecting network connections: {e}")
        
        return connections
    
    def _add_to_history(self, metrics: SystemMetrics):
        """Add metrics to historical data"""
        self.metrics_history.append(metrics)
        
        # Clean up old history
        cutoff_time = datetime.now() - timedelta(hours=self.history_retention)
        self.metrics_history = [m for m in self.metrics_history if m.timestamp > cutoff_time]
    
    def _check_alert_conditions(self, metrics: SystemMetrics):
        """Check metrics against alert thresholds"""
        alerts = []
        
        # CPU usage alert
        if metrics.cpu_percent > self.alert_thresholds['cpu_percent']:
            alert = SystemAlert(
                id=f"cpu_high_{int(time.time())}",
                timestamp=datetime.now(),
                severity=AlertSeverity.WARNING if metrics.cpu_percent < 95 else AlertSeverity.CRITICAL,
                category="performance",
                title="High CPU Usage",
                message=f"CPU usage is at {metrics.cpu_percent:.1f}%",
                details={"cpu_percent": metrics.cpu_percent, "threshold": self.alert_thresholds['cpu_percent']}
            )
            alerts.append(alert)
        
        # Memory usage alert
        if metrics.memory_percent > self.alert_thresholds['memory_percent']:
            alert = SystemAlert(
                id=f"memory_high_{int(time.time())}",
                timestamp=datetime.now(),
                severity=AlertSeverity.WARNING if metrics.memory_percent < 95 else AlertSeverity.CRITICAL,
                category="performance",
                title="High Memory Usage",
                message=f"Memory usage is at {metrics.memory_percent:.1f}%",
                details={"memory_percent": metrics.memory_percent, "threshold": self.alert_thresholds['memory_percent']}
            )
            alerts.append(alert)
        
        # Disk usage alert
        if metrics.disk_percent > self.alert_thresholds['disk_percent']:
            alert = SystemAlert(
                id=f"disk_high_{int(time.time())}",
                timestamp=datetime.now(),
                severity=AlertSeverity.CRITICAL,
                category="storage",
                title="High Disk Usage",
                message=f"Disk usage is at {metrics.disk_percent:.1f}%",
                details={"disk_percent": metrics.disk_percent, "threshold": self.alert_thresholds['disk_percent']}
            )
            alerts.append(alert)
        
        # Temperature alerts
        for sensor_name, temp in metrics.temperatures.items():
            if temp > self.alert_thresholds['temperature']:
                alert = SystemAlert(
                    id=f"temp_high_{sensor_name}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.WARNING if temp < 90 else AlertSeverity.CRITICAL,
                    category="hardware",
                    title="High Temperature",
                    message=f"{sensor_name} temperature is {temp:.1f}°C",
                    details={"sensor": sensor_name, "temperature": temp, "threshold": self.alert_thresholds['temperature']}
                )
                alerts.append(alert)
        
        # GPU alerts
        for gpu in metrics.gpu_metrics:
            if gpu.get('temperature', 0) > self.alert_thresholds['temperature']:
                alert = SystemAlert(
                    id=f"gpu_temp_high_{gpu['id']}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.WARNING if gpu['temperature'] < 90 else AlertSeverity.CRITICAL,
                    category="hardware",
                    title="High GPU Temperature",
                    message=f"GPU {gpu['name']} temperature is {gpu['temperature']:.1f}°C",
                    details={"gpu_id": gpu['id'], "gpu_name": gpu['name'], "temperature": gpu['temperature']}
                )
                alerts.append(alert)
            
            if gpu.get('memory_percent', 0) > 90:
                alert = SystemAlert(
                    id=f"gpu_memory_high_{gpu['id']}_{int(time.time())}",
                    timestamp=datetime.now(),
                    severity=AlertSeverity.WARNING,
                    category="performance",
                    title="High GPU Memory Usage",
                    message=f"GPU {gpu['name']} memory usage is {gpu['memory_percent']:.1f}%",
                    details={"gpu_id": gpu['id'], "gpu_name": gpu['name'], "memory_percent": gpu['memory_percent']}
                )
                alerts.append(alert)
        
        # Add new alerts
        for alert in alerts:
            self._add_alert(alert)
    
    def _add_alert(self, alert: SystemAlert):
        """Add a new alert"""
        # Check if similar alert already exists (avoid spam)
        existing_alert = None
        for existing in self.active_alerts:
            if (existing.category == alert.category and 
                existing.title == alert.title and 
                not existing.acknowledged):
                existing_alert = existing
                break
        
        if not existing_alert:
            self.active_alerts.append(alert)
            self._notify_alert_subscribers(alert)
            self.logger.warning(f"Alert: {alert.title} - {alert.message}")
    
    def _notify_subscribers(self, metrics: SystemMetrics):
        """Notify all subscribers of metrics update"""
        try:
            # Create tasks for async subscribers
            async_tasks = []
            
            for subscriber in self.subscribers.values():
                try:
                    if isinstance(subscriber, WebSocketSubscriber):
                        # Schedule async notification
                        async_tasks.append(subscriber.on_metrics_update(metrics))
                    else:
                        # Sync notification
                        subscriber.on_metrics_update(metrics)
                        
                except Exception as e:
                    self.logger.error(f"Error notifying subscriber {subscriber.subscriber_id}: {e}")
            
            # Run async tasks if any
            if async_tasks:
                asyncio.create_task(self._run_async_notifications(async_tasks))
                
        except Exception as e:
            self.logger.error(f"Error in subscriber notifications: {e}")
    
    def _notify_alert_subscribers(self, alert: SystemAlert):
        """Notify subscribers of new alert"""
        try:
            async_tasks = []
            
            for subscriber in self.subscribers.values():
                try:
                    if isinstance(subscriber, WebSocketSubscriber):
                        async_tasks.append(subscriber.on_alert(alert))
                    else:
                        subscriber.on_alert(alert)
                        
                except Exception as e:
                    self.logger.error(f"Error notifying subscriber of alert: {e}")
            
            if async_tasks:
                asyncio.create_task(self._run_async_notifications(async_tasks))
                
        except Exception as e:
            self.logger.error(f"Error in alert notifications: {e}")
    
    async def _run_async_notifications(self, tasks: List):
        """Run async notification tasks"""
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.logger.error(f"Error running async notifications: {e}")
    
    def subscribe(self, subscriber: MonitoringSubscriber):
        """Add a monitoring subscriber"""
        self.subscribers[subscriber.subscriber_id] = subscriber
        self.logger.info(f"Added subscriber: {subscriber.subscriber_id}")
    
    def unsubscribe(self, subscriber_id: str):
        """Remove a monitoring subscriber"""
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            self.logger.info(f"Removed subscriber: {subscriber_id}")
    
    def get_current_metrics(self) -> Optional[SystemMetrics]:
        """Get current system metrics"""
        return self.current_metrics
    
    def get_metrics_history(self, hours: int = 1) -> List[SystemMetrics]:
        """Get metrics history for specified hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [m for m in self.metrics_history if m.timestamp > cutoff_time]
    
    def get_current_processes(self) -> List[ProcessInfo]:
        """Get current process list"""
        return self.current_processes
    
    def get_active_alerts(self, acknowledged: bool = False) -> List[SystemAlert]:
        """Get active alerts"""
        if acknowledged:
            return self.active_alerts
        else:
            return [a for a in self.active_alerts if not a.acknowledged]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        for alert in self.active_alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                self.logger.info(f"Alert acknowledged: {alert_id}")
                return True
        return False
    
    def set_monitoring_level(self, level: MonitoringLevel):
        """Set monitoring detail level"""
        self.monitoring_level = level
        self.logger.info(f"Monitoring level set to: {level.value}")
    
    def update_alert_thresholds(self, thresholds: Dict[str, float]):
        """Update alert thresholds"""
        self.alert_thresholds.update(thresholds)
        self.logger.info(f"Alert thresholds updated: {thresholds}")
    
    def _start_websocket_server(self):
        """Start WebSocket server for real-time monitoring"""
        if not HAS_WEBSOCKETS:
            self.logger.warning("WebSocket support not available")
            return
        
        try:
            async def websocket_handler(websocket, path):
                """Handle WebSocket connections"""
                subscriber_id = f"websocket_{id(websocket)}"
                subscriber = WebSocketSubscriber(subscriber_id, websocket)
                self.subscribe(subscriber)
                
                try:
                    # Send current metrics immediately
                    if self.current_metrics:
                        await subscriber.on_metrics_update(self.current_metrics)
                    
                    # Keep connection alive
                    async for message in websocket:
                        try:
                            data = json.loads(message)
                            await self._handle_websocket_message(subscriber, data)
                        except json.JSONDecodeError:
                            await subscriber.send_message('error', {'message': 'Invalid JSON'})
                            
                except websockets.exceptions.ConnectionClosed:
                    pass
                except Exception as e:
                    self.logger.error(f"WebSocket error: {e}")
                finally:
                    self.unsubscribe(subscriber_id)
            
            # Start WebSocket server in thread
            def run_server():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                start_server = websockets.serve(
                    websocket_handler,
                    "localhost",
                    self.websocket_port
                )
                
                self.websocket_server = loop.run_until_complete(start_server)
                self.logger.info(f"WebSocket server started on port {self.websocket_port}")
                
                try:
                    loop.run_forever()
                except Exception as e:
                    self.logger.error(f"WebSocket server error: {e}")
                finally:
                    loop.close()
            
            websocket_thread = threading.Thread(target=run_server, daemon=True)
            websocket_thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start WebSocket server: {e}")
    
    async def _handle_websocket_message(self, subscriber: WebSocketSubscriber, data: Dict[str, Any]):
        """Handle incoming WebSocket messages"""
        try:
            message_type = data.get('type')
            
            if message_type == 'subscribe_metrics':
                # Subscribe to specific metrics
                metrics = data.get('metrics', [])
                subscriber.subscribed_metrics.update(metrics)
                await subscriber.send_message('subscription_updated', {'metrics': list(subscriber.subscribed_metrics)})
            
            elif message_type == 'acknowledge_alert':
                # Acknowledge an alert
                alert_id = data.get('alert_id')
                if alert_id and self.acknowledge_alert(alert_id):
                    await subscriber.send_message('alert_acknowledged', {'alert_id': alert_id})
            
            elif message_type == 'get_history':
                # Send historical data
                hours = data.get('hours', 1)
                history = self.get_metrics_history(hours)
                history_data = [asdict(m) for m in history]
                await subscriber.send_message('metrics_history', {'history': history_data})
            
            elif message_type == 'get_processes':
                # Send current process list
                if self.current_processes:
                    await subscriber.on_process_update(self.current_processes)
            
        except Exception as e:
            self.logger.error(f"Error handling WebSocket message: {e}")
            await subscriber.send_message('error', {'message': str(e)})

# Global real-time monitor instance
realtime_monitor = RealTimeMonitor()