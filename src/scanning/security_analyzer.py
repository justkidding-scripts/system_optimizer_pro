#!/usr/bin/env python3
"""
Security Analyzer - Advanced Security Threat Analysis

Provides specialized security analysis capabilities for threat detection,
vulnerability assessment, and security posture evaluation.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime

class ThreatLevel(Enum):
    """Security threat levels"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityThreat:
    """Individual security threat"""
    threat_id: str
    threat_type: str
    level: ThreatLevel
    description: str
    indicators: List[str] = field(default_factory=list)
    mitigation: str = ""
    confidence: float = 0.0  # 0.0 to 1.0

@dataclass
class SecurityReport:
    """Comprehensive security analysis report"""
    report_id: str
    timestamp: datetime
    threats: List[SecurityThreat]
    overall_score: int  # 0-100
    recommendations: List[str] = field(default_factory=list)

class SecurityAnalyzer:
    """Advanced security threat analyzer"""
    
    def __init__(self):
        self.threat_signatures = self._load_threat_signatures()
    
    def _load_threat_signatures(self) -> Dict[str, Any]:
        """Load threat signature database"""
        return {
            'malware_patterns': [
                {'pattern': 'cryptominer', 'level': ThreatLevel.HIGH},
                {'pattern': 'botnet', 'level': ThreatLevel.CRITICAL},
                {'pattern': 'trojan', 'level': ThreatLevel.CRITICAL}
            ],
            'suspicious_ports': [6667, 6697, 4444, 1234, 31337],
            'risky_processes': ['nc', 'netcat', 'nmap', 'wireshark']
        }
    
    def analyze_system(self, system_data: Dict[str, Any]) -> SecurityReport:
        """Perform comprehensive security analysis"""
        threats = []
        
        # Analyze processes
        if 'processes' in system_data:
            threats.extend(self._analyze_processes(system_data['processes']))
        
        # Analyze network connections
        if 'network_connections' in system_data:
            threats.extend(self._analyze_network(system_data['network_connections']))
        
        # Calculate overall security score
        score = self._calculate_security_score(threats)
        
        return SecurityReport(
            report_id=f"sec_report_{int(datetime.now().timestamp())}",
            timestamp=datetime.now(),
            threats=threats,
            overall_score=score,
            recommendations=self._generate_recommendations(threats)
        )
    
    def _analyze_processes(self, processes: List[Dict]) -> List[SecurityThreat]:
        """Analyze running processes for threats"""
        threats = []
        
        for proc in processes:
            proc_name = proc.get('name', '').lower()
            
            # Check against malware patterns
            for pattern in self.threat_signatures['malware_patterns']:
                if pattern['pattern'] in proc_name:
                    threats.append(SecurityThreat(
                        threat_id=f"proc_threat_{proc.get('pid', 'unknown')}",
                        threat_type="Suspicious Process",
                        level=pattern['level'],
                        description=f"Process '{proc_name}' matches malware pattern",
                        indicators=[f"Process name: {proc_name}", f"PID: {proc.get('pid')}"],
                        mitigation="Investigate and terminate if confirmed malicious",
                        confidence=0.8
                    ))
        
        return threats
    
    def _analyze_network(self, connections: List[Dict]) -> List[SecurityThreat]:
        """Analyze network connections for threats"""
        threats = []
        
        for conn in connections:
            port = conn.get('remote_port')
            if port in self.threat_signatures['suspicious_ports']:
                threats.append(SecurityThreat(
                    threat_id=f"net_threat_{port}",
                    threat_type="Suspicious Network Connection",
                    level=ThreatLevel.MEDIUM,
                    description=f"Connection to suspicious port {port}",
                    indicators=[f"Remote: {conn.get('remote_ip')}:{port}"],
                    mitigation="Monitor connection and block if malicious",
                    confidence=0.6
                ))
        
        return threats
    
    def _calculate_security_score(self, threats: List[SecurityThreat]) -> int:
        """Calculate overall security score (0-100)"""
        if not threats:
            return 100
        
        threat_weights = {
            ThreatLevel.CRITICAL: 40,
            ThreatLevel.HIGH: 25,
            ThreatLevel.MEDIUM: 15,
            ThreatLevel.LOW: 5
        }
        
        total_impact = sum(threat_weights.get(threat.level, 0) for threat in threats)
        return max(0, 100 - total_impact)
    
    def _generate_recommendations(self, threats: List[SecurityThreat]) -> List[str]:
        """Generate security recommendations based on threats"""
        recommendations = []
        
        if any(t.level == ThreatLevel.CRITICAL for t in threats):
            recommendations.append("Immediate action required: Critical security threats detected")
        
        if any(t.threat_type == "Suspicious Process" for t in threats):
            recommendations.append("Review and terminate suspicious processes")
        
        if any(t.threat_type == "Suspicious Network Connection" for t in threats):
            recommendations.append("Monitor network activity and implement firewall rules")
        
        if not recommendations:
            recommendations.append("Maintain current security practices")
        
        return recommendations