"""
System Optimizer Pro - Advanced Monitoring

Real-time monitoring, performance analysis, and alerting capabilities
with cross-platform support and WebSocket integration.
"""

__version__ = "1.0.0"

from .realtime_monitor import (
    realtime_monitor, 
    RealTimeMonitor,
    SystemMetrics,
    ProcessInfo,
    NetworkConnection,
    SystemAlert,
    MonitoringSubscriber,
    WebSocketSubscriber,
    MonitoringLevel,
    AlertSeverity
)

__all__ = [
    'realtime_monitor',
    'RealTimeMonitor',
    'SystemMetrics',
    'ProcessInfo', 
    'NetworkConnection',
    'SystemAlert',
    'MonitoringSubscriber',
    'WebSocketSubscriber',
    'MonitoringLevel',
    'AlertSeverity'
]