#!/usr/bin/env python3
"""
Advanced System Scanner - Comprehensive System Analysis

Performs deep system scanning including security analysis, integrity checks,
performance assessment, and vulnerability detection before any system modifications.
"""

import os
import sys
import time
import hashlib
import platform
import subprocess
import threading
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging
import json
import re

# Advanced imports for security and system analysis
import psutil
try:
    import yara
    HAS_YARA = True
except ImportError:
    HAS_YARA = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

class ScanCategory(Enum):
    """Categories of system scans"""
    SECURITY = "security"
    INTEGRITY = "integrity"
    PERFORMANCE = "performance"
    VULNERABILITY = "vulnerability"
    MALWARE = "malware"
    NETWORK = "network"
    REGISTRY = "registry"
    SERVICES = "services"
    STARTUP = "startup"
    DRIVERS = "drivers"

class ScanSeverity(Enum):
    """Severity levels for scan findings"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"

@dataclass
class ScanFinding:
    """Individual scan finding"""
    category: ScanCategory
    severity: ScanSeverity
    title: str
    description: str
    location: str
    recommendation: str
    technical_details: Dict[str, Any] = field(default_factory=dict)
    remediation_commands: List[str] = field(default_factory=list)
    risk_score: int = 0
    cve_references: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)

@dataclass
class ScanResult:
    """Complete scan results"""
    scan_id: str
    timestamp: datetime
    duration: float
    categories_scanned: List[ScanCategory]
    findings: List[ScanFinding]
    system_info: Dict[str, Any]
    scan_metadata: Dict[str, Any]
    
    @property
    def critical_findings(self) -> List[ScanFinding]:
        return [f for f in self.findings if f.severity == ScanSeverity.CRITICAL]
    
    @property
    def high_findings(self) -> List[ScanFinding]:
        return [f for f in self.findings if f.severity == ScanSeverity.HIGH]
    
    @property
    def total_risk_score(self) -> int:
        return sum(f.risk_score for f in self.findings)
    
    @property
    def security_score(self) -> int:
        """Calculate security score (0-100, higher is better)"""
        max_possible_risk = len(self.findings) * 100
        if max_possible_risk == 0:
            return 100
        return max(0, 100 - int((self.total_risk_score / max_possible_risk) * 100))

class SystemScanner:
    """Advanced system scanner with comprehensive analysis capabilities"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.platform = platform.system().lower()
        self.is_windows = self.platform == 'windows'
        self.is_linux = self.platform == 'linux'
        
        # Scan configuration
        self.scan_config = {
            'deep_scan': True,
            'include_network': True,
            'check_signatures': HAS_YARA,
            'vulnerability_check': HAS_REQUESTS,
            'max_scan_time': 300,  # 5 minutes max
            'parallel_scans': True,
            'threat_intel_enabled': HAS_REQUESTS
        }
        
        # Initialize scan modules
        self._init_scan_modules()
        
    def _init_scan_modules(self):
        """Initialize platform-specific scan modules"""
        self.scan_modules = {}
        
        # Common scans for all platforms
        self.scan_modules.update({
            ScanCategory.SECURITY: self._scan_security,
            ScanCategory.PERFORMANCE: self._scan_performance,
            ScanCategory.NETWORK: self._scan_network,
            ScanCategory.SERVICES: self._scan_services,
            ScanCategory.STARTUP: self._scan_startup,
            ScanCategory.MALWARE: self._scan_malware
        })
        
        # Platform-specific scans
        if self.is_windows:
            self.scan_modules.update({
                ScanCategory.REGISTRY: self._scan_windows_registry,
                ScanCategory.DRIVERS: self._scan_windows_drivers,
                ScanCategory.VULNERABILITY: self._scan_windows_vulnerabilities
            })
        elif self.is_linux:
            self.scan_modules.update({
                ScanCategory.INTEGRITY: self._scan_linux_integrity,
                ScanCategory.VULNERABILITY: self._scan_linux_vulnerabilities
            })

    def scan_system(self, categories: Optional[List[ScanCategory]] = None, 
                   deep_scan: bool = True, 
                   progress_callback: Optional[Callable] = None) -> ScanResult:
        """
        Perform comprehensive system scan
        
        Args:
            categories: Specific categories to scan (default: all)
            deep_scan: Enable deep scanning (slower but more thorough)
            progress_callback: Function to call with progress updates
            
        Returns:
            ScanResult: Comprehensive scan results
        """
        scan_id = f"scan_{int(time.time())}"
        start_time = time.time()
        
        self.logger.info(f"Starting system scan {scan_id}")
        
        if categories is None:
            categories = list(self.scan_modules.keys())
        
        findings: List[ScanFinding] = []
        completed_categories = []
        
        # Update scan configuration
        self.scan_config['deep_scan'] = deep_scan
        
        try:
            total_categories = len(categories)
            
            for i, category in enumerate(categories):
                if progress_callback:
                    progress_callback(f"Scanning {category.value}...", 
                                    int((i / total_categories) * 100))
                
                try:
                    category_findings = self._execute_category_scan(category)
                    findings.extend(category_findings)
                    completed_categories.append(category)
                    
                    self.logger.info(f"Completed {category.value} scan: "
                                   f"{len(category_findings)} findings")
                    
                except Exception as e:
                    self.logger.error(f"Error scanning {category.value}: {e}")
                    findings.append(ScanFinding(
                        category=category,
                        severity=ScanSeverity.MEDIUM,
                        title=f"Scan Error: {category.value}",
                        description=f"Failed to complete {category.value} scan: {str(e)}",
                        location="System Scanner",
                        recommendation="Check system logs and retry scan",
                        technical_details={"error": str(e)},
                        risk_score=20
                    ))
            
            if progress_callback:
                progress_callback("Finalizing scan results...", 95)
            
            # Generate system info snapshot
            system_info = self._get_system_snapshot()
            
            # Calculate risk scores and prioritize findings
            self._calculate_risk_scores(findings)
            findings.sort(key=lambda x: (x.severity.value, x.risk_score), reverse=True)
            
            duration = time.time() - start_time
            
            scan_result = ScanResult(
                scan_id=scan_id,
                timestamp=datetime.now(),
                duration=duration,
                categories_scanned=completed_categories,
                findings=findings,
                system_info=system_info,
                scan_metadata={
                    'deep_scan': deep_scan,
                    'platform': self.platform,
                    'scanner_version': '1.0.0',
                    'total_findings': len(findings),
                    'critical_count': len([f for f in findings if f.severity == ScanSeverity.CRITICAL]),
                    'high_count': len([f for f in findings if f.severity == ScanSeverity.HIGH])
                }
            )
            
            if progress_callback:
                progress_callback("Scan complete!", 100)
            
            self.logger.info(f"System scan {scan_id} completed in {duration:.2f}s: "
                           f"{len(findings)} findings")
            
            return scan_result
            
        except Exception as e:
            self.logger.error(f"Critical error during system scan: {e}")
            raise
    
    def _execute_category_scan(self, category: ScanCategory) -> List[ScanFinding]:
        """Execute scan for specific category"""
        if category not in self.scan_modules:
            self.logger.warning(f"No scan module for category: {category}")
            return []
        
        try:
            return self.scan_modules[category]()
        except Exception as e:
            self.logger.error(f"Error in {category.value} scan: {e}")
            return []
    
    def _scan_security(self) -> List[ScanFinding]:
        """Comprehensive security scan"""
        findings = []
        
        # Check for suspicious processes
        suspicious_processes = self._detect_suspicious_processes()
        for proc in suspicious_processes:
            findings.append(ScanFinding(
                category=ScanCategory.SECURITY,
                severity=ScanSeverity.HIGH,
                title="Suspicious Process Detected",
                description=f"Process '{proc['name']}' exhibits suspicious behavior",
                location=f"PID: {proc['pid']}",
                recommendation="Investigate process and terminate if malicious",
                technical_details=proc,
                risk_score=75
            ))
        
        # Check for unusual network connections
        suspicious_connections = self._detect_suspicious_connections()
        for conn in suspicious_connections:
            findings.append(ScanFinding(
                category=ScanCategory.SECURITY,
                severity=ScanSeverity.MEDIUM,
                title="Suspicious Network Connection",
                description=f"Unusual connection to {conn['remote_ip']}:{conn['remote_port']}",
                location=f"Local: {conn['local_ip']}:{conn['local_port']}",
                recommendation="Monitor connection and block if malicious",
                technical_details=conn,
                risk_score=50
            ))
        
        # Check file permissions and ownership
        permission_issues = self._check_file_permissions()
        findings.extend(permission_issues)
        
        # Check for weak passwords (if accessible)
        password_issues = self._check_password_security()
        findings.extend(password_issues)
        
        return findings
    
    def _scan_performance(self) -> List[ScanFinding]:
        """Performance analysis scan"""
        findings = []
        
        # CPU usage analysis
        cpu_usage = psutil.cpu_percent(interval=1)
        if cpu_usage > 80:
            findings.append(ScanFinding(
                category=ScanCategory.PERFORMANCE,
                severity=ScanSeverity.MEDIUM,
                title="High CPU Usage",
                description=f"CPU usage is {cpu_usage:.1f}%",
                location="System CPU",
                recommendation="Identify and optimize high-CPU processes",
                technical_details={"cpu_percent": cpu_usage},
                risk_score=30
            ))
        
        # Memory usage analysis
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            findings.append(ScanFinding(
                category=ScanCategory.PERFORMANCE,
                severity=ScanSeverity.MEDIUM,
                title="High Memory Usage",
                description=f"Memory usage is {memory.percent:.1f}%",
                location="System RAM",
                recommendation="Free up memory or add more RAM",
                technical_details={"memory_percent": memory.percent, "available_gb": memory.available / (1024**3)},
                risk_score=35
            ))
        
        # Disk usage analysis
        disk = psutil.disk_usage('/')
        if disk.percent > 90:
            findings.append(ScanFinding(
                category=ScanCategory.PERFORMANCE,
                severity=ScanSeverity.HIGH,
                title="Critical Disk Space",
                description=f"Disk usage is {disk.percent:.1f}%",
                location="Primary Drive",
                recommendation="Free up disk space immediately",
                technical_details={"disk_percent": disk.percent, "free_gb": disk.free / (1024**3)},
                risk_score=70
            ))
        
        # Process analysis - top CPU consumers
        top_processes = self._get_top_cpu_processes()
        for proc in top_processes[:3]:  # Top 3
            if proc['cpu_percent'] > 50:
                findings.append(ScanFinding(
                    category=ScanCategory.PERFORMANCE,
                    severity=ScanSeverity.LOW,
                    title="High CPU Process",
                    description=f"Process '{proc['name']}' using {proc['cpu_percent']:.1f}% CPU",
                    location=f"PID: {proc['pid']}",
                    recommendation="Monitor process or optimize if necessary",
                    technical_details=proc,
                    risk_score=15
                ))
        
        return findings
    
    def _scan_network(self) -> List[ScanFinding]:
        """Network security scan"""
        findings = []
        
        # Check open ports
        open_ports = self._scan_open_ports()
        for port_info in open_ports:
            if port_info['port'] in [22, 23, 135, 139, 445, 3389]:  # Common risky ports
                severity = ScanSeverity.MEDIUM if port_info['port'] in [22, 3389] else ScanSeverity.HIGH
                findings.append(ScanFinding(
                    category=ScanCategory.NETWORK,
                    severity=severity,
                    title="Potentially Risky Open Port",
                    description=f"Port {port_info['port']} is open and accessible",
                    location=f"{port_info['protocol']}:{port_info['port']}",
                    recommendation="Review if this port needs to be open and secure it properly",
                    technical_details=port_info,
                    risk_score=60 if severity == ScanSeverity.HIGH else 40
                ))
        
        # Check network adapters
        network_issues = self._check_network_adapters()
        findings.extend(network_issues)
        
        return findings
    
    def _scan_services(self) -> List[ScanFinding]:
        """System services scan"""
        findings = []
        
        # Check running services
        suspicious_services = self._check_suspicious_services()
        findings.extend(suspicious_services)
        
        # Check service permissions
        service_permission_issues = self._check_service_permissions()
        findings.extend(service_permission_issues)
        
        return findings
    
    def _scan_startup(self) -> List[ScanFinding]:
        """Startup programs scan"""
        findings = []
        
        startup_items = self._get_startup_items()
        
        for item in startup_items:
            # Check for suspicious startup items
            if self._is_suspicious_startup(item):
                findings.append(ScanFinding(
                    category=ScanCategory.STARTUP,
                    severity=ScanSeverity.MEDIUM,
                    title="Suspicious Startup Program",
                    description=f"Startup item '{item['name']}' may be suspicious",
                    location=item.get('location', 'Unknown'),
                    recommendation="Review and disable if unnecessary",
                    technical_details=item,
                    risk_score=45
                ))
            
            # Check for performance impact
            if item.get('impact', 'low') == 'high':
                findings.append(ScanFinding(
                    category=ScanCategory.STARTUP,
                    severity=ScanSeverity.LOW,
                    title="High Impact Startup Program",
                    description=f"Startup item '{item['name']}' has high performance impact",
                    location=item.get('location', 'Unknown'),
                    recommendation="Consider disabling to improve boot time",
                    technical_details=item,
                    risk_score=20
                ))
        
        return findings
    
    def _scan_malware(self) -> List[ScanFinding]:
        """Basic malware detection scan"""
        findings = []
        
        if not HAS_YARA:
            findings.append(ScanFinding(
                category=ScanCategory.MALWARE,
                severity=ScanSeverity.INFO,
                title="Advanced Malware Detection Unavailable",
                description="YARA not installed - basic malware detection only",
                location="System Scanner",
                recommendation="Install YARA for advanced malware detection",
                risk_score=0
            ))
        
        # Check for known malware indicators
        malware_indicators = self._check_malware_indicators()
        findings.extend(malware_indicators)
        
        # Check for suspicious file modifications
        suspicious_files = self._check_suspicious_file_changes()
        findings.extend(suspicious_files)
        
        return findings
    
    def _scan_windows_registry(self) -> List[ScanFinding]:
        """Windows registry scan"""
        findings = []
        
        if not self.is_windows:
            return findings
        
        try:
            import winreg
            
            # Check common registry vulnerabilities
            registry_issues = self._check_registry_security()
            findings.extend(registry_issues)
            
            # Check for registry bloat
            registry_bloat = self._check_registry_bloat()
            findings.extend(registry_bloat)
            
        except ImportError:
            findings.append(ScanFinding(
                category=ScanCategory.REGISTRY,
                severity=ScanSeverity.INFO,
                title="Windows Registry Scan Unavailable",
                description="Windows registry modules not available",
                location="System Scanner",
                recommendation="Install Windows-specific dependencies",
                risk_score=0
            ))
        
        return findings
    
    def _scan_windows_drivers(self) -> List[ScanFinding]:
        """Windows drivers scan"""
        findings = []
        
        if not self.is_windows:
            return findings
        
        # Check for outdated drivers
        driver_issues = self._check_driver_status()
        findings.extend(driver_issues)
        
        return findings
    
    def _scan_windows_vulnerabilities(self) -> List[ScanFinding]:
        """Windows-specific vulnerability scan"""
        findings = []
        
        if not self.is_windows:
            return findings
        
        # Check Windows Update status
        update_issues = self._check_windows_updates()
        findings.extend(update_issues)
        
        # Check Windows Defender status
        defender_issues = self._check_windows_defender()
        findings.extend(defender_issues)
        
        return findings
    
    def _scan_linux_integrity(self) -> List[ScanFinding]:
        """Linux system integrity scan"""
        findings = []
        
        if not self.is_linux:
            return findings
        
        # Check system file integrity
        integrity_issues = self._check_linux_file_integrity()
        findings.extend(integrity_issues)
        
        # Check for rootkit indicators
        rootkit_indicators = self._check_rootkit_indicators()
        findings.extend(rootkit_indicators)
        
        return findings
    
    def _scan_linux_vulnerabilities(self) -> List[ScanFinding]:
        """Linux vulnerability scan"""
        findings = []
        
        if not self.is_linux:
            return findings
        
        # Check package vulnerabilities
        package_vulns = self._check_package_vulnerabilities()
        findings.extend(package_vulns)
        
        # Check kernel vulnerabilities
        kernel_vulns = self._check_kernel_vulnerabilities()
        findings.extend(kernel_vulns)
        
        return findings
    
    # Helper methods for specific scan implementations
    def _detect_suspicious_processes(self) -> List[Dict[str, Any]]:
        """Detect processes with suspicious characteristics"""
        suspicious = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'exe']):
                try:
                    proc_info = proc.info
                    
                    # Check for high resource usage without explanation
                    if proc_info['cpu_percent'] and proc_info['cpu_percent'] > 90:
                        suspicious.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'reason': 'high_cpu',
                            'cpu_percent': proc_info['cpu_percent'],
                            'exe': proc_info.get('exe', 'Unknown')
                        })
                    
                    # Check for processes with suspicious names
                    if proc_info['name'] and any(suspicious_name in proc_info['name'].lower() 
                                               for suspicious_name in ['miner', 'cryptominer', 'botnet']):
                        suspicious.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'reason': 'suspicious_name',
                            'exe': proc_info.get('exe', 'Unknown')
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            self.logger.error(f"Error detecting suspicious processes: {e}")
        
        return suspicious
    
    def _detect_suspicious_connections(self) -> List[Dict[str, Any]]:
        """Detect suspicious network connections"""
        suspicious = []
        
        try:
            connections = psutil.net_connections(kind='inet')
            
            for conn in connections:
                if conn.raddr:  # Has remote address
                    # Check for connections to suspicious IPs or ports
                    if conn.raddr.port in [6667, 6697, 4444, 1234]:  # Common malware ports
                        suspicious.append({
                            'local_ip': conn.laddr.ip,
                            'local_port': conn.laddr.port,
                            'remote_ip': conn.raddr.ip,
                            'remote_port': conn.raddr.port,
                            'status': conn.status,
                            'reason': 'suspicious_port'
                        })
                        
        except Exception as e:
            self.logger.error(f"Error detecting suspicious connections: {e}")
        
        return suspicious
    
    def _check_file_permissions(self) -> List[ScanFinding]:
        """Check for insecure file permissions"""
        findings = []
        
        # Check critical system directories
        critical_paths = ['/etc', '/usr/bin', '/usr/sbin'] if self.is_linux else ['C:\\Windows\\System32']
        
        for path in critical_paths:
            if os.path.exists(path):
                try:
                    stat_info = os.stat(path)
                    if stat_info.st_mode & 0o002:  # World writable
                        findings.append(ScanFinding(
                            category=ScanCategory.SECURITY,
                            severity=ScanSeverity.HIGH,
                            title="Insecure Directory Permissions",
                            description=f"Critical directory {path} is world-writable",
                            location=path,
                            recommendation="Fix directory permissions immediately",
                            risk_score=80
                        ))
                except Exception as e:
                    self.logger.debug(f"Cannot check permissions for {path}: {e}")
        
        return findings
    
    def _check_password_security(self) -> List[ScanFinding]:
        """Check for password security issues"""
        findings = []
        
        if self.is_linux:
            # Check /etc/shadow permissions
            shadow_path = '/etc/shadow'
            if os.path.exists(shadow_path):
                try:
                    stat_info = os.stat(shadow_path)
                    if stat_info.st_mode & 0o044:  # Readable by group or others
                        findings.append(ScanFinding(
                            category=ScanCategory.SECURITY,
                            severity=ScanSeverity.CRITICAL,
                            title="Insecure Password File Permissions",
                            description="/etc/shadow has insecure permissions",
                            location=shadow_path,
                            recommendation="Fix shadow file permissions: chmod 600 /etc/shadow",
                            risk_score=95
                        ))
                except Exception as e:
                    self.logger.debug(f"Cannot check shadow permissions: {e}")
        
        return findings
    
    def _get_top_cpu_processes(self) -> List[Dict[str, Any]]:
        """Get processes consuming most CPU"""
        processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    if proc_info['cpu_percent']:
                        processes.append(proc_info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
            
        except Exception as e:
            self.logger.error(f"Error getting top CPU processes: {e}")
        
        return processes
    
    def _scan_open_ports(self) -> List[Dict[str, Any]]:
        """Scan for open network ports"""
        open_ports = []
        
        try:
            connections = psutil.net_connections(kind='inet')
            
            for conn in connections:
                if conn.status == 'LISTEN':
                    open_ports.append({
                        'port': conn.laddr.port,
                        'ip': conn.laddr.ip,
                        'protocol': 'TCP',
                        'pid': conn.pid
                    })
                    
        except Exception as e:
            self.logger.error(f"Error scanning ports: {e}")
        
        return open_ports
    
    def _check_network_adapters(self) -> List[ScanFinding]:
        """Check network adapter configurations"""
        findings = []
        
        try:
            adapters = psutil.net_if_addrs()
            
            for adapter_name, addresses in adapters.items():
                for addr in addresses:
                    # Check for promiscuous mode indicators
                    if 'promiscuous' in adapter_name.lower():
                        findings.append(ScanFinding(
                            category=ScanCategory.NETWORK,
                            severity=ScanSeverity.MEDIUM,
                            title="Potentially Promiscuous Network Adapter",
                            description=f"Network adapter {adapter_name} may be in promiscuous mode",
                            location=adapter_name,
                            recommendation="Verify network adapter configuration",
                            risk_score=40
                        ))
                        
        except Exception as e:
            self.logger.error(f"Error checking network adapters: {e}")
        
        return findings
    
    def _check_suspicious_services(self) -> List[ScanFinding]:
        """Check for suspicious system services"""
        findings = []
        
        # This would need platform-specific implementations
        # For now, return empty list
        return findings
    
    def _check_service_permissions(self) -> List[ScanFinding]:
        """Check service permission configurations"""
        findings = []
        
        # Platform-specific service permission checks would go here
        return findings
    
    def _get_startup_items(self) -> List[Dict[str, Any]]:
        """Get system startup items"""
        startup_items = []
        
        try:
            if self.is_linux:
                # Check systemd services
                result = subprocess.run(['systemctl', 'list-unit-files', '--type=service', '--state=enabled'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n')[1:]:  # Skip header
                        if line.strip() and not line.startswith('UNIT'):
                            parts = line.split()
                            if len(parts) >= 2:
                                startup_items.append({
                                    'name': parts[0],
                                    'state': parts[1],
                                    'location': 'systemd',
                                    'type': 'service'
                                })
                                
        except Exception as e:
            self.logger.error(f"Error getting startup items: {e}")
        
        return startup_items
    
    def _is_suspicious_startup(self, item: Dict[str, Any]) -> bool:
        """Check if startup item is suspicious"""
        suspicious_names = ['miner', 'bot', 'trojan', 'backdoor', 'keylogger']
        
        item_name = item.get('name', '').lower()
        return any(sus_name in item_name for sus_name in suspicious_names)
    
    def _check_malware_indicators(self) -> List[ScanFinding]:
        """Check for basic malware indicators"""
        findings = []
        
        # Check for suspicious files in common locations
        suspicious_locations = []
        
        if self.is_linux:
            suspicious_locations = ['/tmp', '/var/tmp', '/dev/shm']
        elif self.is_windows:
            suspicious_locations = ['C:\\Windows\\Temp', 'C:\\Temp']
        
        for location in suspicious_locations:
            if os.path.exists(location):
                try:
                    for file_path in Path(location).rglob('*'):
                        if file_path.is_file() and file_path.stat().st_size > 10*1024*1024:  # > 10MB
                            findings.append(ScanFinding(
                                category=ScanCategory.MALWARE,
                                severity=ScanSeverity.LOW,
                                title="Large File in Temporary Directory",
                                description=f"Large file found in {location}: {file_path.name}",
                                location=str(file_path),
                                recommendation="Review file and remove if suspicious",
                                risk_score=25
                            ))
                except Exception as e:
                    self.logger.debug(f"Error checking {location}: {e}")
        
        return findings
    
    def _check_suspicious_file_changes(self) -> List[ScanFinding]:
        """Check for suspicious recent file modifications"""
        findings = []
        
        # Check critical system files for recent modifications
        critical_files = []
        
        if self.is_linux:
            critical_files = ['/etc/passwd', '/etc/shadow', '/etc/sudoers']
        elif self.is_windows:
            critical_files = ['C:\\Windows\\System32\\drivers\\etc\\hosts']
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                try:
                    stat_info = os.stat(file_path)
                    modification_time = datetime.fromtimestamp(stat_info.st_mtime)
                    
                    if datetime.now() - modification_time < timedelta(hours=24):
                        findings.append(ScanFinding(
                            category=ScanCategory.MALWARE,
                            severity=ScanSeverity.MEDIUM,
                            title="Recent Critical File Modification",
                            description=f"Critical system file {file_path} was recently modified",
                            location=file_path,
                            recommendation="Verify if modification was authorized",
                            technical_details={'modification_time': modification_time.isoformat()},
                            risk_score=50
                        ))
                except Exception as e:
                    self.logger.debug(f"Error checking {file_path}: {e}")
        
        return findings
    
    def _check_registry_security(self) -> List[ScanFinding]:
        """Check Windows registry for security issues"""
        findings = []
        # Platform-specific registry checks would be implemented here
        return findings
    
    def _check_registry_bloat(self) -> List[ScanFinding]:
        """Check for Windows registry bloat"""
        findings = []
        # Registry optimization checks would be implemented here
        return findings
    
    def _check_driver_status(self) -> List[ScanFinding]:
        """Check Windows driver status"""
        findings = []
        # Driver update and security checks would be implemented here
        return findings
    
    def _check_windows_updates(self) -> List[ScanFinding]:
        """Check Windows Update status"""
        findings = []
        # Windows Update checks would be implemented here
        return findings
    
    def _check_windows_defender(self) -> List[ScanFinding]:
        """Check Windows Defender status"""
        findings = []
        # Windows Defender status checks would be implemented here
        return findings
    
    def _check_linux_file_integrity(self) -> List[ScanFinding]:
        """Check Linux system file integrity"""
        findings = []
        
        # Check if important system files exist and have correct permissions
        important_files = {
            '/etc/passwd': 0o644,
            '/etc/shadow': 0o600,
            '/etc/group': 0o644,
            '/etc/sudoers': 0o440
        }
        
        for file_path, expected_mode in important_files.items():
            if os.path.exists(file_path):
                try:
                    stat_info = os.stat(file_path)
                    actual_mode = stat_info.st_mode & 0o777
                    
                    if actual_mode != expected_mode:
                        findings.append(ScanFinding(
                            category=ScanCategory.INTEGRITY,
                            severity=ScanSeverity.HIGH,
                            title="Incorrect File Permissions",
                            description=f"{file_path} has incorrect permissions",
                            location=file_path,
                            recommendation=f"Fix permissions: chmod {oct(expected_mode)} {file_path}",
                            technical_details={
                                'expected_mode': oct(expected_mode),
                                'actual_mode': oct(actual_mode)
                            },
                            risk_score=70
                        ))
                except Exception as e:
                    self.logger.debug(f"Error checking {file_path}: {e}")
        
        return findings
    
    def _check_rootkit_indicators(self) -> List[ScanFinding]:
        """Check for rootkit indicators on Linux"""
        findings = []
        
        # Basic rootkit checks - would be expanded with more sophisticated detection
        if shutil.which('rkhunter'):
            try:
                result = subprocess.run(['rkhunter', '--check', '--skip-keypress', '--report-warnings-only'], 
                                      capture_output=True, text=True, timeout=60)
                if result.returncode != 0 and result.stdout:
                    findings.append(ScanFinding(
                        category=ScanCategory.INTEGRITY,
                        severity=ScanSeverity.HIGH,
                        title="Rootkit Hunter Warnings",
                        description="RKHunter detected potential rootkit indicators",
                        location="System",
                        recommendation="Review RKHunter output and investigate warnings",
                        technical_details={'rkhunter_output': result.stdout[:1000]},
                        risk_score=85
                    ))
            except Exception as e:
                self.logger.debug(f"Error running rkhunter: {e}")
        
        return findings
    
    def _check_package_vulnerabilities(self) -> List[ScanFinding]:
        """Check for vulnerable packages on Linux"""
        findings = []
        
        # Check for outdated packages
        try:
            if shutil.which('apt'):
                result = subprocess.run(['apt', 'list', '--upgradable'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    upgradable_count = len([line for line in result.stdout.split('\n') 
                                          if '/' in line and '[upgradable' in line])
                    if upgradable_count > 0:
                        findings.append(ScanFinding(
                            category=ScanCategory.VULNERABILITY,
                            severity=ScanSeverity.MEDIUM,
                            title="Outdated Packages",
                            description=f"{upgradable_count} packages have available updates",
                            location="Package Manager",
                            recommendation="Update packages: sudo apt update && sudo apt upgrade",
                            technical_details={'upgradable_count': upgradable_count},
                            risk_score=35
                        ))
            
        except Exception as e:
            self.logger.debug(f"Error checking package updates: {e}")
        
        return findings
    
    def _check_kernel_vulnerabilities(self) -> List[ScanFinding]:
        """Check for kernel vulnerabilities"""
        findings = []
        
        try:
            kernel_version = platform.release()
            
            # Basic check for very old kernels
            if kernel_version.startswith('3.') or kernel_version.startswith('4.'):
                findings.append(ScanFinding(
                    category=ScanCategory.VULNERABILITY,
                    severity=ScanSeverity.HIGH,
                    title="Potentially Vulnerable Kernel",
                    description=f"Kernel version {kernel_version} may have known vulnerabilities",
                    location="System Kernel",
                    recommendation="Consider updating to a newer kernel version",
                    technical_details={'kernel_version': kernel_version},
                    risk_score=75
                ))
                
        except Exception as e:
            self.logger.debug(f"Error checking kernel version: {e}")
        
        return findings
    
    def _get_system_snapshot(self) -> Dict[str, Any]:
        """Get current system state snapshot"""
        try:
            return {
                'platform': platform.platform(),
                'architecture': platform.architecture(),
                'hostname': platform.node(),
                'cpu_cores': psutil.cpu_count(),
                'total_memory': psutil.virtual_memory().total,
                'disk_usage': {disk.mountpoint: {'total': disk.total, 'used': disk.used, 'free': disk.free} 
                              for disk in psutil.disk_partitions() 
                              if disk.mountpoint and os.path.exists(disk.mountpoint)},
                'network_interfaces': list(psutil.net_if_addrs().keys()),
                'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                'scan_time': datetime.now().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error creating system snapshot: {e}")
            return {}
    
    def _calculate_risk_scores(self, findings: List[ScanFinding]):
        """Calculate and normalize risk scores for findings"""
        severity_multipliers = {
            ScanSeverity.CRITICAL: 4.0,
            ScanSeverity.HIGH: 3.0,
            ScanSeverity.MEDIUM: 2.0,
            ScanSeverity.LOW: 1.0,
            ScanSeverity.INFO: 0.1
        }
        
        for finding in findings:
            if finding.risk_score == 0:  # Auto-calculate if not set
                base_score = 25  # Base risk score
                severity_multiplier = severity_multipliers.get(finding.severity, 1.0)
                finding.risk_score = int(base_score * severity_multiplier)
            
            # Ensure risk score is within bounds
            finding.risk_score = max(0, min(100, finding.risk_score))

# Specialized scan classes
class SecurityScan:
    """Specialized security-focused scanner"""
    pass

class IntegrityScan:
    """System integrity scanner"""
    pass

class PerformanceScan:
    """Performance analysis scanner"""
    pass

class VulnerabilityScan:
    """Vulnerability assessment scanner"""
    pass